package com.saphid.framecontrol.core

import java.io.Closeable
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.net.ServerSocket
import java.nio.file.Path
import java.security.PublicKey
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread
import org.apache.sshd.common.config.keys.KeyUtils
import org.apache.sshd.common.config.keys.PublicKeyEntry
import org.apache.sshd.common.digest.BuiltinDigests
import org.apache.sshd.common.file.virtualfs.VirtualFileSystemFactory
import org.apache.sshd.server.Environment
import org.apache.sshd.server.ExitCallback
import org.apache.sshd.server.SshServer
import org.apache.sshd.server.channel.ChannelSession
import org.apache.sshd.server.command.Command
import org.apache.sshd.server.config.keys.AuthorizedKeysAuthenticator
import org.apache.sshd.server.forward.AcceptAllForwardingFilter
import org.apache.sshd.server.keyprovider.SimpleGeneratorHostKeyProvider
import org.apache.sshd.sftp.server.SftpSubsystemFactory

/**
 * A stand-in Frame for tests: a real SSH server (Apache MINA SSHD) on 127.0.0.1 that runs
 * commands with sh in a temporary home, serves SFTP rooted there and allows ssh -L, with a
 * Developer Mode password and the home's ~/.ssh/authorized_keys for logins. It counts
 * every login attempt, so tests can tell whether a password or key was ever offered.
 */
class TestHeadset(val home: File, private val hostKeyFile: Path, val password: String, port: Int = 0) : Closeable {
    val passwordTries = AtomicInteger()
    val keyTries = AtomicInteger()
    val commands = CopyOnWriteArrayList<ShellCommand>()

    private val server: SshServer = SshServer.setUpDefaultServer().also { s ->
        s.host = "127.0.0.1"
        s.port = port
        s.keyPairProvider = SimpleGeneratorHostKeyProvider(hostKeyFile).apply { algorithm = KeyUtils.EC_ALGORITHM; keySize = 256 }
        s.passwordAuthenticator = org.apache.sshd.server.auth.password.PasswordAuthenticator { user, pw, _ ->
            passwordTries.incrementAndGet()
            user == "steamos" && pw == password
        }
        val keys = AuthorizedKeysAuthenticator(home.toPath().resolve(".ssh/authorized_keys"))
        s.publickeyAuthenticator = org.apache.sshd.server.auth.pubkey.PublickeyAuthenticator { user, key, session ->
            keyTries.incrementAndGet()
            user == "steamos" && keys.authenticate(user, key, session)
        }
        s.keyboardInteractiveAuthenticator = null
        s.commandFactory = org.apache.sshd.server.command.CommandFactory { _, command -> ShellCommand(command, home).also { commands += it } }
        s.subsystemFactories = listOf(SftpSubsystemFactory())
        s.fileSystemFactory = VirtualFileSystemFactory(home.toPath())
        s.forwardingFilter = AcceptAllForwardingFilter.INSTANCE
    }

    fun start(): TestHeadset = apply { server.start() }

    val port: Int get() = server.port

    val sessionCount: Int get() = server.activeSessions.size

    /** Drops every connection, as Wi-Fi going away would. */
    fun dropSessions() = server.activeSessions.forEach { it.close(true) }

    val hostPublicKey: PublicKey get() = server.keyPairProvider.loadKeys(null).first().public

    /** The fingerprint as OpenSSH (and MINA, independently of the app's code) prints it. */
    val fingerprint: String get() = KeyUtils.getFingerPrint(BuiltinDigests.sha256, hostPublicKey)

    /** The host key as known_hosts would hold it. */
    val knownHostsEntry: String get() = PublicKeyEntry.toString(hostPublicKey)

    val authorizedKeys: List<String>
        get() = File(home, ".ssh/authorized_keys").takeIf { it.exists() }?.readLines()?.filter { it.isNotBlank() } ?: emptyList()

    override fun close() = server.stop(true)

    companion object {
        fun freePort(): Int = ServerSocket(0).use { it.localPort }
    }
}

/**
 * One exec request: `sh -c COMMAND` in the test home. When the client's channel closes,
 * MINA calls destroy(); like sshd, that closes the command's stdin, and a well-behaved
 * process (the headset server with --exit-on-eof) is given a few seconds to stop by itself.
 */
class ShellCommand(val command: String, private val home: File) : Command {
    private lateinit var input: InputStream
    private lateinit var out: OutputStream
    private lateinit var err: OutputStream
    private lateinit var exit: ExitCallback
    @Volatile private var process: Process? = null

    /** Whether the process ended by itself (rather than being killed). Null while it runs. */
    @Volatile var endedByItself: Boolean? = null
        private set

    override fun setInputStream(`in`: InputStream) { input = `in` }
    override fun setOutputStream(out: OutputStream) { this.out = out }
    override fun setErrorStream(err: OutputStream) { this.err = err }
    override fun setExitCallback(callback: ExitCallback) { exit = callback }

    override fun start(channel: ChannelSession, env: Environment) {
        val pb = ProcessBuilder("sh", "-c", command).directory(home)
        pb.environment()["HOME"] = home.path
        val p = pb.start()
        process = p
        val pumps = listOf(pump(p.inputStream, out), pump(p.errorStream, err))
        thread(isDaemon = true, name = "stdin") {
            val buf = ByteArray(4096)
            runCatching {
                while (true) {
                    val n = input.read(buf)
                    if (n < 0) break
                    p.outputStream.write(buf, 0, n)
                    p.outputStream.flush()
                }
            }
            runCatching { p.outputStream.close() }
        }
        thread(isDaemon = true, name = "wait") {
            val code = p.waitFor()
            if (endedByItself == null) endedByItself = true
            pumps.forEach { it.join(2_000) }
            runCatching { exit.onExit(code) }
        }
    }

    override fun destroy(channel: ChannelSession) {
        val p = process ?: return
        runCatching { p.outputStream.close() }
        if (!p.waitFor(5, TimeUnit.SECONDS)) {
            endedByItself = false
            killDescendants(p)
            p.destroyForcibly()
        }
    }

    /** ProcessHandle isn't in android.jar, which unit tests compile against; the test JVM has it. */
    private fun killDescendants(p: Process) {
        runCatching {
            val handleClass = Class.forName("java.lang.ProcessHandle")
            val handle = Process::class.java.getMethod("toHandle").invoke(p)
            val children = handleClass.getMethod("descendants").invoke(handle) as java.util.stream.Stream<*>
            val kill = handleClass.getMethod("destroyForcibly")
            children.forEach { kill.invoke(it) }
        }
    }

    private fun pump(from: InputStream, to: OutputStream) = thread(isDaemon = true, name = "pump") {
        val buf = ByteArray(8192)
        runCatching {
            while (true) {
                val n = from.read(buf)
                if (n < 0) break
                to.write(buf, 0, n)
                to.flush()
            }
        }
    }
}
