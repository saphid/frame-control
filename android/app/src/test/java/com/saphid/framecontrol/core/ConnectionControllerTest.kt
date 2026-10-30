package com.saphid.framecontrol.core

import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.file.Files
import java.security.KeyPairGenerator
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.Executors
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test

/**
 * The connection flow end to end against TestHeadset, a real SSH server on 127.0.0.1:
 * host-key confirmation and refusal, what gets stored, cancelling, the headset server's
 * lifetime, and reconnecting. The server on the "headset" is the real bundled ui/server.py.
 */
class ConnectionControllerTest {
    private val password = "dev-mode-pass"
    private lateinit var dir: File
    private lateinit var home: File
    private val headsets = mutableListOf<TestHeadset>()
    private val executor = Executors.newSingleThreadExecutor { r -> Thread(r, "controller").apply { isDaemon = true } }
    private val scope = CoroutineScope(SupervisorJob() + executor.asCoroutineDispatcher())
    private lateinit var store: FileStore
    private val device = TestDevice()

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("frame-control-test").toFile()
        home = File(dir, "home").apply { mkdirs() }
        store = FileStore(File(dir, "app-data"))
    }

    @After
    fun tearDown() {
        scope.cancel()
        executor.shutdownNow()
        headsets.forEach { runCatching { it.close() } }
        dir.deleteRecursively()
    }

    private fun headset(keyName: String = "host-a", port: Int = 0) =
        TestHeadset(home, File(dir, "$keyName.key").toPath(), password, port).start().also { headsets += it }

    private fun controller(timing: ConnectionController.Timing = fastTiming) = ConnectionController(store, device, scope, timing)

    private val fastTiming = ConnectionController.Timing(retryMs = 500, healthMs = 60_000, quickLossMs = 0, confirmMs = 20_000, serverStartMs = 30_000)

    private fun settings(h: TestHeadset) = FrameSettings("127.0.0.1", h.port, "steamos")

    private fun <T> StateFlow<T>.await(what: String, timeoutMs: Long = 30_000, predicate: (T) -> Boolean): T = runBlocking {
        try {
            withTimeout(timeoutMs) { first(predicate) }
        } catch (e: Exception) {
            throw AssertionError("timed out waiting for $what; last value: $value", e)
        }
    }

    private fun waitUntil(what: String, timeoutMs: Long = 15_000, check: () -> Boolean) {
        val end = System.currentTimeMillis() + timeoutMs
        while (!check()) {
            if (System.currentTimeMillis() > end) throw AssertionError("timed out waiting for $what")
            Thread.sleep(50)
        }
    }

    private fun get(url: String, key: String?): Pair<Int, String> {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 5_000
        c.readTimeout = 15_000
        key?.let { c.setRequestProperty("X-Frame-UI", it) }
        val code = c.responseCode
        val body = (if (code < 400) c.inputStream else c.errorStream)?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
        return code to body
    }

    private fun pairAndConfirm(c: ConnectionController, h: TestHeadset): Phase.Ready {
        c.pair(settings(h), password.toCharArray())
        val pending = c.hostKey.await("the host key question") { it != null }!!
        c.answerHostKey(pending.id, true)
        return c.phase.await("Ready") { it is Phase.Ready } as Phase.Ready
    }

    @Test
    fun firstPairingShowsTheRealFingerprintAndSendsThePasswordOnlyAfterItIsConfirmed() {
        assumeTrue("needs python3 for the headset server", python3())
        val h = headset()
        val c = controller()
        val typed = password.toCharArray()
        c.pair(settings(h), typed)

        val pending = c.hostKey.await("the host key question") { it != null }!!
        // The fingerprint shown is the one OpenSSH-compatible code computes from the server's own key.
        assertEquals(h.fingerprint, pending.question.key.fingerprint)
        assertNull(pending.question.previous)
        assertEquals(0, h.passwordTries.get())
        assertTrue(h.authorizedKeys.isEmpty())

        c.answerHostKey(pending.id, true)
        val ready = c.phase.await("Ready") { it is Phase.Ready } as Phase.Ready
        assertTrue("the typed password is wiped", typed.all { it == '\u0000' })

        // Exactly this phone's key was added, once, as authorized_keys expects it.
        assertEquals(listOf(c.authorizedKeysLine), h.authorizedKeys)
        assertTrue(h.authorizedKeys[0].startsWith("ecdsa-sha2-nistp256 "))

        // The pairing stores the address and that exact host key, and no secret.
        val saved = store.load()!!
        assertEquals(settings(h), saved.settings)
        assertEquals(FrameHostKey.decode(h.knownHostsEntry), saved.hostKey)
        assertFalse("no password in app storage", store.dir.walk().filter { it.isFile }.any { password in it.readText() })

        // The page and its API come through the tunnel, from the real headset server.
        val key = ready.url.substringAfter("key=")
        assertTrue(ready.url.startsWith("http://127.0.0.1:${ready.port}/?key="))
        val (code, body) = get("http://127.0.0.1:${ready.port}/api/host", key)
        assertEquals(200, code)
        assertTrue(body, body.contains("\"mobile\": true") && body.contains("\"computer\": \"phone\""))
        assertEquals(403, get("http://127.0.0.1:${ready.port}/api/host", "wrong").first)
        assertEquals(200, get("http://127.0.0.1:${ready.port}/", null).first)
    }

    @Test
    fun decliningTheFingerprintSendsNothingAndSavesNothing() {
        val h = headset()
        val c = controller()
        c.pair(settings(h), password.toCharArray())
        val pending = c.hostKey.await("the host key question") { it != null }!!
        c.answerHostKey(pending.id, false)

        val failed = c.phase.await("Failed") { it is Phase.Failed } as Phase.Failed
        assertTrue(failed.message, failed.message.contains("wasn't confirmed"))
        assertFalse(failed.canRetry)
        assertEquals("no password was offered", 0, h.passwordTries.get())
        assertEquals(0, h.keyTries.get())
        assertNull(store.load())
        assertTrue(h.authorizedKeys.isEmpty())
    }

    @Test
    fun aChangedHostKeyIsRefusedWithoutAskingOrLoggingIn() {
        val port = TestHeadset.freePort()
        val original = headset("host-a", port)
        val pinned = FrameHostKey.decode(original.knownHostsEntry)!!
        original.close()
        // A different machine at the same address, which would even accept this phone's key.
        val impostor = headset("host-b", port)
        File(home, ".ssh").mkdirs()
        File(home, ".ssh/authorized_keys").writeText(SshWire.authorizedKeysLine(device.signer.publicKey, "test") + "\n")
        assertNotEquals(original.fingerprint, impostor.fingerprint)
        store.save(Pairing(settings(impostor), pinned))

        val c = controller()
        val questions = CopyOnWriteArrayList<PendingHostKey>()
        scope.launch { c.hostKey.collect { if (it != null) questions += it } }
        c.connect()

        val failed = c.phase.await("Failed") { it is Phase.Failed } as Phase.Failed
        assertTrue(failed.needsPairing)
        assertFalse("no automatic retry", failed.retrying)
        assertTrue(failed.message, failed.message.contains("identity changed"))
        assertTrue("never asked to accept the new key", questions.isEmpty())
        assertEquals("no login attempted", 0, impostor.keyTries.get())
        assertEquals(0, impostor.passwordTries.get())
        assertEquals("the trusted key is kept", pinned, store.load()!!.hostKey)
    }

    @Test
    fun cancellingDuringTheQuestionClosesTheSessionAndSavesNothing() {
        val h = headset()
        val c = controller()
        c.pair(settings(h), password.toCharArray())
        c.hostKey.await("the host key question") { it != null }
        assertEquals(1, h.sessionCount)

        c.showSetup()
        c.phase.await("Setup") { it is Phase.Setup }
        c.hostKey.await("question withdrawn") { it == null }
        waitUntil("the SSH session to close") { h.sessionCount == 0 }
        assertEquals(0, h.passwordTries.get())
        assertNull(store.load())
        // Nothing comes back to life afterwards.
        Thread.sleep(1_000)
        assertTrue(c.phase.value is Phase.Setup)
    }

    @Test
    fun leavingStopsTheHeadsetServerThroughEndOfInput() {
        assumeTrue("needs python3 for the headset server", python3())
        val h = headset()
        val c = controller()
        val ready = pairAndConfirm(c, h)
        val server = h.commands.single { "exec python3" in it.command }
        assertNull(server.endedByItself)

        c.showSetup()
        c.phase.await("Setup") { it is Phase.Setup }
        waitUntil("the headset server to stop") { server.endedByItself != null }
        assertEquals("it stopped by itself when its input closed", true, server.endedByItself)
        waitUntil("the SSH session to close") { h.sessionCount == 0 }
        assertTrue("the phone's tunnel is closed", runCatching { get("http://127.0.0.1:${ready.port}/", null) }.isFailure)
    }

    @Test
    fun reconnectsWhenTheConnectionDrops() {
        assumeTrue("needs python3 for the headset server", python3())
        val h = headset()
        val c = controller()
        val first = pairAndConfirm(c, h)

        h.dropSessions()
        val second = c.phase.await("a new connection") { it is Phase.Ready && it.port != first.port } as Phase.Ready
        assertNotEquals(first.url.substringAfter("key="), second.url.substringAfter("key="))
        assertEquals(200, get("http://127.0.0.1:${second.port}/api/host", second.url.substringAfter("key=")).first)
        assertEquals("one key line, not a new one per connection", 1, h.authorizedKeys.size)
        assertEquals("one password login, at pairing", 1, h.passwordTries.get())
    }

    @Test
    fun keepsRetryingWhileTheHeadsetIsAwayAndConnectsWhenItIsBack() {
        assumeTrue("needs python3 for the headset server", python3())
        val port = TestHeadset.freePort()
        val h = headset(port = port)
        val c = controller()
        pairAndConfirm(c, h)
        c.showSetup()
        c.phase.await("Setup") { it is Phase.Setup }
        h.close()

        c.connect()
        val failed = c.phase.await("Failed, retrying") { it is Phase.Failed } as Phase.Failed
        assertTrue(failed.retrying)
        assertTrue(failed.message, failed.message.contains("refused") || failed.message.contains("isn't answering"))

        headset(port = port)
        c.phase.await("Ready again") { it is Phase.Ready }
    }

    @Test
    fun aServerThatDiesRightAwayIsReportedInsteadOfRestartedForever() {
        assumeTrue("needs python3 for the headset server", python3())
        val h = headset()
        val c = controller(fastTiming.copy(quickLossMs = 60_000))
        pairAndConfirm(c, h)
        h.dropSessions()
        val failed = c.phase.await("Failed") { it is Phase.Failed } as Phase.Failed
        assertFalse(failed.retrying)
        assertTrue(failed.message, failed.message.contains("stopped"))
    }

    @Test
    fun aLoginTheFrameRefusesAsksToPairAgain() {
        val h = headset()
        val c = controller()
        c.pair(settings(h), "not-the-password".toCharArray())
        val pending = c.hostKey.await("the host key question") { it != null }!!
        c.answerHostKey(pending.id, true)
        val failed = c.phase.await("Failed") { it is Phase.Failed } as Phase.Failed
        assertTrue(failed.message, failed.message.contains("didn't accept that password"))
        assertNull(store.load())
        assertTrue(h.authorizedKeys.isEmpty())
    }

    @Test
    fun shutdownAfterScopeCancellationClosesTheLiveServerAndTunnel() {
        assumeTrue("needs python3 for the headset server", python3())
        val h = headset()
        val c = controller()
        val ready = pairAndConfirm(c, h)
        val server = h.commands.single { "exec python3" in it.command }
        scope.cancel() // Android ViewModel does this BEFORE onCleared.
        c.shutdown()
        waitUntil("server EOF after cancelled scope") { server.endedByItself != null }
        assertEquals(true, server.endedByItself)
        waitUntil("SSH disconnect after cancelled scope") { h.sessionCount == 0 }
        assertTrue(runCatching { get("http://127.0.0.1:${ready.port}/", null) }.isFailure)
        c.connect()
        Thread.sleep(200)
        assertEquals(0, h.sessionCount)
    }

    @Test
    fun shutdownAfterScopeCancellationWithdrawsTheQuestionAndWipesPassword() {
        val h = headset()
        val c = controller()
        val typed = password.toCharArray()
        c.pair(settings(h), typed)
        c.hostKey.await("host key question") { it != null }
        scope.cancel()
        c.shutdown()
        waitUntil("SSH disconnect") { h.sessionCount == 0 }
        waitUntil("password wiped") { typed.all { it == '\u0000' } }
        assertNull(c.hostKey.value)
        assertNull(store.load())
        assertEquals(0, h.passwordTries.get())
    }

    @Test
    fun aPairingScheduledOnAnAlreadyCancelledScopeStillWipesThePassword() {
        val h = headset()
        val c = controller()
        scope.cancel()
        val typed = password.toCharArray()
        c.pair(settings(h), typed)
        waitUntil("unsent password wiped") { typed.all { it == '\u0000' } }
        c.shutdown()
        assertEquals(0, h.passwordTries.get())
        assertEquals(0, h.sessionCount)
    }

    @Test
    fun cancellationBeforeJschCreatesItsSocketCannotLeaveAnAuthenticatedSession() {
        val h = headset()
        File(home, ".ssh").mkdirs()
        File(home, ".ssh/authorized_keys").writeText(SshWire.authorizedKeysLine(device.signer.publicKey, "test") + "\n")
        val pinned = FrameHostKey.decode(h.knownHostsEntry)!!
        val gate = HostKeyGate(settings(h), pinned, null) { false }
        val result = runCatching {
            FrameLink.connect(settings(h), Login.Key("steamos", SignerIdentity(device.signer)), gate, pinned.type) { resource ->
                // An already-closed Attempt closes this handle before connect().
                // JSch's own disconnect() alone does nothing at this point.
                resource.close()
            }
        }
        result.getOrNull()?.close()
        assertTrue("cancelled connection must fail", result.isFailure)
        assertEquals(0, h.keyTries.get())
        waitUntil("no SSH session survives early cancellation") { h.sessionCount == 0 }
    }

    private fun python3() = runCatching { ProcessBuilder("python3", "-c", "import sys; assert sys.version_info >= (3, 8)").start().waitFor() == 0 }.getOrDefault(false)

    /** The pairing in a file, as the phone keeps it in app-private preferences. */
    class FileStore(val dir: File) : PairingStore {
        private val file = File(dir, "pairing.txt")
        override fun load(): Pairing? {
            val lines = file.takeIf { it.exists() }?.readLines() ?: return null
            val s = FrameSettings.parse(lines[0], lines[2], lines[1]) ?: return null
            return Pairing(s, FrameHostKey.decode(lines[3]) ?: return null)
        }
        override fun save(pairing: Pairing) {
            dir.mkdirs()
            file.writeText(listOf(pairing.settings.host, pairing.settings.port, pairing.settings.user, pairing.hostKey.encode()).joinToString("\n"))
        }
        override fun clear() { file.delete() }
    }

    /** A software ECDSA key stands in for the Keystore one; the bundle is the one the build packed. */
    class TestDevice : Device {
        private val pair = KeyPairGenerator.getInstance("EC").apply { initialize(ECGenParameterSpec("secp256r1")) }.generateKeyPair()
        override val signer = object : SshSigner {
            override val publicKey = pair.public as ECPublicKey
            override fun sign(data: ByteArray): ByteArray = Signature.getInstance("SHA256withECDSA").run {
                initSign(pair.private); update(data); sign()
            }
        }
        override val name = "phone"
        override val keyComment = "frame-control@test"
        override val isForeground = true
        override fun bundle(): FrameBundle {
            val dir = File(System.getProperty("frame.bundle.dir") ?: error("frame.bundle.dir isn't set (run through Gradle)"))
            return FrameBundle(File(dir, "frame-bundle.bin").readBytes(), File(dir, "frame-bundle.version").readText().trim())
        }
    }
}
