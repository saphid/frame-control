package com.saphid.framecontrol.core

import com.jcraft.jsch.ChannelExec
import com.jcraft.jsch.ChannelSftp
import com.jcraft.jsch.JSch
import com.jcraft.jsch.JSchChangedHostKeyException
import com.jcraft.jsch.JSchException
import com.jcraft.jsch.JSchUnknownHostKeyException
import com.jcraft.jsch.Session
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.Closeable
import java.net.ConnectException
import java.net.NoRouteToHostException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.nio.CharBuffer
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.cancellation.CancellationException

/** How to log in: the Developer Mode password (pairing only), or this phone's key. */
sealed interface Login {
    val user: String

    /** The caller clears `password` afterwards; JSch clears its own copy once it has logged in. */
    class Password(override val user: String, val password: CharArray) : Login
    class Key(override val user: String, val identity: SignerIdentity) : Login
}

/** One SSH connection to the Frame, and the few things the app does over it. */
class FrameLink private constructor(private val session: Session, val settings: FrameSettings) : Closeable {
    companion object {
        /** `opened` gets a handle that aborts the connection, for a caller that may give up before it finishes. */
        fun connect(
            settings: FrameSettings, login: Login, gate: HostKeyGate, pinnedType: String?,
            timeoutMs: Int = 8_000, opened: (Closeable) -> Unit = {},
        ): FrameLink {
            val jsch = JSch()
            jsch.hostKeyRepository = gate
            if (login is Login.Key) jsch.addIdentity(login.identity, null)
            val session = jsch.getSession(login.user, settings.host, settings.port)
            session.setConfig("StrictHostKeyChecking", "yes")
            session.setConfig("HashKnownHosts", "no")
            session.setConfig("server_host_key", hostKeyAlgorithms(session.getConfig("server_host_key"), pinnedType))
            session.setConfig("PreferredAuthentications", if (login is Login.Key) "publickey" else "keyboard-interactive,password")
            session.setConfig("PubkeyAcceptedAlgorithms", SshWire.ALGORITHM)
            var secret: ByteArray? = null
            if (login is Login.Password) {
                // Encoded straight from the char array: no String copy of the password.
                val encoded = Charsets.UTF_8.encode(CharBuffer.wrap(login.password))
                secret = ByteArray(encoded.remaining()).also { encoded.get(it) }
                encoded.array().fill(0)
                session.setPassword(secret)
            }
            // A dead link (Wi-Fi gone, headset asleep) shows up within ~45 s.
            session.setServerAliveInterval(15_000)
            session.serverAliveCountMax = 3
            val cancelled = AtomicBoolean()
            opened(Closeable { cancelled.set(true); session.disconnect() })
            try {
                if (cancelled.get()) throw CancellationException("Connection cancelled")
                session.connect(timeoutMs)
                // disconnect() before JSch creates its socket is a no-op. Remember
                // cancellation and own the completed link before returning across
                // a cancellable dispatcher boundary.
                val link = FrameLink(session, settings)
                opened(link)
                if (cancelled.get()) { link.close(); throw CancellationException("Connection cancelled") }
                return link
            } catch (e: Exception) {
                session.disconnect()
                if (e is CancellationException) throw e
                throw FrameFailure(describe(e, settings.host, login is Login.Password), needsPairing = needsPairing(e), cause = e)
            } finally {
                secret?.fill(0)
            }
        }

        /**
         * JSch's own order, without host certificates (only plain keys are pinned), and with
         * the pinned key's type first, so a Frame that offers several keeps showing the same one.
         */
        fun hostKeyAlgorithms(defaults: String, pinnedType: String?): String {
            val plain = defaults.split(',').filter { it.isNotBlank() && !it.contains("-cert-") }
            val types = when (pinnedType) {
                null -> plain
                "ssh-rsa" -> plain.filter { it.startsWith("rsa-sha2-") || it == "ssh-rsa" } + plain.filterNot { it.startsWith("rsa-sha2-") || it == "ssh-rsa" }
                else -> listOf(pinnedType) + plain.filter { it != pinnedType }
            }
            return types.joinToString(",")
        }

        fun needsPairing(e: Throwable): Boolean =
            e is JSchChangedHostKeyException || (e is JSchException && e.message.orEmpty().startsWith("Auth "))

        /** The plain-language reason a connection failed, like the iPhone app's messages. Never includes a secret. */
        fun describe(e: Throwable, host: String, withPassword: Boolean = false): String {
            if (e is FrameFailure) return e.message.orEmpty()
            if (e is JSchChangedHostKeyException) {
                return "The Frame's SSH identity changed (after a reinstall, or a different device at $host). " +
                    "Nothing was sent to it. Pair again only if you know why."
            }
            if (e is JSchUnknownHostKeyException) return "The Frame's identity wasn't confirmed, so nothing was sent to it."
            val text = generateSequence(e) { it.cause }.joinToString(" ") { "${it.javaClass.simpleName} ${it.message.orEmpty()}" }
            val causes = generateSequence(e) { it.cause }.toList()
            return when {
                e is JSchException && e.message.orEmpty().startsWith("Auth ") ->
                    if (withPassword) "The Frame didn't accept that password. Check the Developer Mode password and try again."
                    else "The Frame didn't accept this phone's key. Pair again with the Developer Mode password."
                causes.any { it is UnknownHostException } ->
                    "Can't find $host on the network. Check the address, and that the Frame is on the same network."
                causes.any { it is ConnectException } || "refused" in text ->
                    "The Frame refused the connection at $host. Check Developer Mode is still on."
                causes.any { it is SocketTimeoutException || it is NoRouteToHostException } ||
                    listOf("timeout", "timed out", "unreachable", "EHOSTUNREACH", "ENETUNREACH").any { it in text } ->
                    "The Frame isn't answering at $host. It may be asleep, switched off, or on another network."
                else -> "Couldn't connect to $host: ${e.message ?: e.javaClass.simpleName}"
            }
        }
    }

    val isConnected: Boolean get() = session.isConnected

    /** Runs a shell command; its combined output and exit status. */
    fun run(command: String, timeoutMs: Long = 60_000): Pair<String, Int> {
        val channel = session.openChannel("exec") as ChannelExec
        channel.setCommand("{ $command\n} 2>&1")
        val out = ByteArrayOutputStream()
        try {
            val input = channel.inputStream
            channel.connect(timeoutMs.toInt().coerceAtMost(15_000))
            val deadline = System.nanoTime() + timeoutMs * 1_000_000
            val buf = ByteArray(8192)
            while (true) {
                if (input.available() > 0) {
                    val n = input.read(buf)
                    if (n < 0) break
                    out.write(buf, 0, n)
                    continue
                }
                if (channel.isClosed) {
                    if (input.available() > 0) continue
                    break
                }
                if (System.nanoTime() > deadline) throw FrameFailure("The Frame didn't finish a command in time")
                if (!session.isConnected) throw FrameFailure("Lost the connection to the Frame")
                Thread.sleep(15)
            }
            return out.toString(Charsets.UTF_8.name()).trim() to channel.exitStatus
        } finally {
            channel.disconnect()
        }
    }

    /** Runs a command that must succeed; its output, or a FrameFailure with it. */
    fun check(command: String, what: String): String {
        val (output, status) = run(command)
        if (status != 0) throw FrameFailure("$what: ${output.ifEmpty { "exit $status" }.takeLast(400)}")
        return output
    }

    /** Whether the Frame answers a trivial command in time. */
    fun answers(timeoutMs: Long = 6_000): Boolean = session.isConnected && runCatching { run("true", timeoutMs).second == 0 }.getOrDefault(false)

    /** Writes data to a path relative to the home directory. */
    fun upload(data: ByteArray, path: String) {
        val sftp = session.openChannel("sftp") as ChannelSftp
        try {
            sftp.connect(15_000)
            sftp.put(ByteArrayInputStream(data), path, ChannelSftp.OVERWRITE)
        } finally {
            sftp.disconnect()
        }
    }

    /** A command whose output streams back; it runs until the channel or this link closes. */
    fun exec(command: String): ChannelExec {
        val channel = session.openChannel("exec") as ChannelExec
        channel.setCommand(command)
        return channel
    }

    /** Fetch passive artwork/fonts on the headset, never from the phone's network.
     * Redirects are checked again on the headset; stdout is bounded and has a deadline.
     */
    fun fetchAsset(url: String): RemoteAsset {
        require(AssetPolicy.allows(url)) { "Asset origin blocked" }
        val roots = AssetPolicy.roots.joinToString(",") { "'" + it + "'" }
        val script = """
import sys, urllib.request, urllib.parse
roots = [$roots]
def valid(url):
    p = urllib.parse.urlsplit(url)
    return (p.scheme == 'https' and p.username is None and p.password is None
            and p.port in (None, 443) and not p.fragment and '%' not in p.path
            and '\\' not in url and not any(x in ('.', '..') for x in p.path.split('/'))
            and any(p.hostname == urllib.parse.urlsplit(r).hostname
                    and p.path.startswith(urllib.parse.urlsplit(r).path) for r in roots))
class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not valid(newurl): raise ValueError('blocked redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)
url = sys.argv[1]
if not valid(url): raise ValueError('blocked asset')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect())
with opener.open(urllib.request.Request(url, headers={'User-Agent': 'FrameControl/0.1'}), timeout=12) as r:
    mime = r.headers.get_content_type()
    if url.split('?', 1)[0].endswith('.ttf'): mime = 'font/ttf'
    if not (mime.startswith('image/') or mime.startswith('font/') or mime in ('application/font-woff', 'application/vnd.ms-fontobject')):
        raise ValueError('not a passive asset')
    data = r.read(${AssetPolicy.MAX_BYTES} + 1)
    if len(data) > ${AssetPolicy.MAX_BYTES}: raise ValueError('asset too large')
    sys.stdout.buffer.write(mime.encode('ascii') + b'\n' + data)
""".trimIndent()
        val channel = exec("python3 -I -c ${shellQuote(script)} ${shellQuote(url)}")
        val out = ByteArrayOutputStream()
        try {
            val input = channel.inputStream
            channel.connect(8_000)
            val deadline = System.nanoTime() + 20_000_000_000L
            val buf = ByteArray(8192)
            while (true) {
                if (System.nanoTime() > deadline || !session.isConnected) throw FrameFailure("Artwork request interrupted")
                if (input.available() > 0) {
                    val n = input.read(buf)
                    if (n < 0) break
                    if (out.size() + n > AssetPolicy.MAX_BYTES + 256) throw FrameFailure("Artwork too large")
                    out.write(buf, 0, n)
                } else if (channel.isClosed) break else Thread.sleep(10)
            }
            if (channel.exitStatus != 0) throw FrameFailure("Couldn't load artwork from the headset")
            val bytes = out.toByteArray()
            val line = bytes.indexOf(10)
            if (line !in 1..128) throw FrameFailure("Invalid artwork response")
            val mime = String(bytes, 0, line, Charsets.US_ASCII)
            require(mime.startsWith("image/") || mime.startsWith("font/") || mime in listOf("application/font-woff", "application/vnd.ms-fontobject"))
            return RemoteAsset(mime, bytes.copyOfRange(line + 1, bytes.size))
        } finally { channel.disconnect() }
    }

    /** ssh -L: listens on this phone's 127.0.0.1 only, and carries each connection to the Frame's 127.0.0.1:remotePort. */
    fun forwardLocal(remotePort: Int): Int = session.setPortForwardingL("127.0.0.1", 0, "127.0.0.1", remotePort)

    /** Ends the session: the forward, every channel, and with them the server on the headset. */
    override fun close() = session.disconnect()
}
