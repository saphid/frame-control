package com.saphid.framecontrol.core

import java.io.Closeable
import java.security.SecureRandom
import java.util.concurrent.CompletableFuture
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.coroutines.cancellation.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** The pairing: which Frame, and the host key confirmed for it. Nothing secret. */
data class Pairing(val settings: FrameSettings, val hostKey: FrameHostKey)

interface PairingStore {
    fun load(): Pairing?
    fun save(pairing: Pairing)
    fun clear()
}

/** What the controller needs from the phone. */
interface Device {
    /** This phone's SSH key (made on first use). */
    val signer: SshSigner

    /** What the page calls this device ("phone", "tablet"). */
    val name: String

    /** The comment on this phone's authorized_keys line, so the user can tell which key to revoke. */
    val keyComment: String

    /** Whether the app is in front, where background retries and health checks make sense. */
    val isForeground: Boolean

    fun bundle(): FrameBundle
}

sealed interface Phase {
    data object Setup : Phase
    data class Connecting(val step: String) : Phase
    data class Ready(val url: String, val port: Int) : Phase
    data class Failed(val message: String, val retrying: Boolean, val needsPairing: Boolean, val canRetry: Boolean) : Phase
}

/** A host key waiting for the user's yes or no. */
class PendingHostKey(val id: Int, val question: HostKeyQuestion, internal val answer: CompletableFuture<Boolean>)

/**
 * The app's one piece of state, ported from the iPhone app's AppModel: which headset,
 * and how far along connecting to it is.
 *
 * Every public method may be called from any thread; the work runs on `scope`, whose
 * dispatcher must run one thing at a time (the main thread on the phone). Blocking SSH
 * work runs on the IO dispatcher. Every attempt has a number; anything that finishes
 * after a newer attempt started (or the user went back to setup) closes what it made.
 */
class ConnectionController(
    private val store: PairingStore,
    private val device: Device,
    private val scope: CoroutineScope,
    private val timing: Timing = Timing(),
) {
    data class Timing(
        val retryMs: Long = 10_000,
        val healthMs: Long = 20_000,
        /** A server that dies this soon after starting is reported, not restarted forever. */
        val quickLossMs: Long = 20_000,
        /** How long the connection is kept while the app is out of sight. */
        val backgroundGraceMs: Long = 180_000,
        val confirmMs: Long = 180_000,
        val connectMs: Int = 8_000,
        val serverStartMs: Long = 30_000,
    )

    private val _phase = MutableStateFlow<Phase>(if (store.load() == null) Phase.Setup else Phase.Connecting("Connecting"))
    val phase: StateFlow<Phase> = _phase.asStateFlow()

    private val _hostKey = MutableStateFlow<PendingHostKey?>(null)
    /** Set while a first connection waits for the user to confirm the Frame's fingerprint. */
    val hostKey: StateFlow<PendingHostKey?> = _hostKey.asStateFlow()

    val pairing: Pairing? get() = store.load()

    /** This phone's line for ~/.ssh/authorized_keys on the Frame. */
    val authorizedKeysLine: String get() = SshWire.authorizedKeysLine(device.signer.publicKey, device.keyComment)

    private class Attempt(val number: Int) {
        private val opened = mutableListOf<Closeable>()
        private var closed = false
        fun own(resource: Closeable) {
            val late = synchronized(this) {
                if (closed) true else { opened.add(resource); false }
            }
            if (late) runCatching { resource.close() }
        }
        fun closeAll() {
            val resources = synchronized(this) {
                closed = true
                opened.toList().also { opened.clear() }
            }
            resources.reversed().forEach { runCatching { it.close() } }
        }
    }

    private class Live(val link: FrameLink, val server: HeadsetServer)

    @Volatile private var attempt = Attempt(0)
    @Volatile private var live: Live? = null
    private val closed = AtomicBoolean()
    private var retryJob: Job? = null
    private var healthJob: Job? = null
    private var backgroundJob: Job? = null
    private var pausedInBackground = false
    private var readySince = 0L
    private val questions = AtomicInteger()

    // MARK: pairing

    /**
     * First time: log in with the Developer Mode password, add this phone's key to
     * ~/.ssh/authorized_keys, and keep the Frame's host key, which the user confirms before
     * the password is sent. Then connect with the key. `password` is cleared here.
     */
    fun pair(settings: FrameSettings, password: CharArray) = on(cleanup = { password.fill('\u0000') }) {
        val a = begin()
        val previous = store.load()?.takeIf { it.settings.host == settings.host && it.settings.port == settings.port }?.hostKey
        _phase.value = Phase.Connecting("Checking ${settings.label}")
        try {
            val gate = HostKeyGate(settings, pinned = null, previous = previous, confirm = asker(a))
            val link = io(a) { FrameLink.connect(settings, Login.Password(settings.user, password), gate, null, timing.connectMs) { a.own(it) } }
            password.fill('\u0000')
            step(a, "Adding this ${device.name}'s key")
            // A file whose last line has no newline would otherwise swallow the key.
            val file = "~/.ssh/authorized_keys"
            io(a) {
                val line = authorizedKeysLine  // the Keystore may be slow: not on the main thread
                link.check("umask 077; mkdir -p ~/.ssh && touch $file && " +
                    "{ grep -qxF ${shellQuote(line)} $file || { " +
                    "[ -s $file ] && [ -n \"\$(tail -c 1 $file)\" ] && printf '\\n' >> $file; " +
                    "printf '%s\\n' ${shellQuote(line)} >> $file; }; }", "Couldn't add the key on the Frame")
            }
            val seen = gate.seen ?: throw FrameFailure("The Frame didn't show a host key")
            store.save(Pairing(settings, seen))
            a.closeAll()
        } catch (e: Throwable) {
            password.fill('\u0000')
            a.closeAll()
            if (closed.get() || e is CancellationException || a.number != attempt.number) return@on
            val f = e as? FrameFailure ?: FrameFailure(FrameLink.describe(e, settings.host, withPassword = true))
            fail(f.message.orEmpty(), retry = false, needsPairing = f.needsPairing)
            return@on
        }
        connectNow(quiet = false)
    }

    /**
     * For someone who added this phone's key to the Frame themselves: no password. The
     * Frame's host key is still confirmed by the user on this first connection.
     */
    fun useKey(settings: FrameSettings) = on {
        val a = begin()
        val previous = store.load()?.takeIf { it.settings.host == settings.host && it.settings.port == settings.port }?.hostKey
        _phase.value = Phase.Connecting("Checking ${settings.label}")
        try {
            val gate = HostKeyGate(settings, pinned = null, previous = previous, confirm = asker(a))
            val link = io(a) { FrameLink.connect(settings, Login.Key(settings.user, SignerIdentity(device.signer)), gate, null, timing.connectMs) { a.own(it) } }
            val seen = gate.seen ?: throw FrameFailure("The Frame didn't show a host key")
            store.save(Pairing(settings, seen))
            a.closeAll()
        } catch (e: Throwable) {
            a.closeAll()
            if (closed.get() || e is CancellationException || a.number != attempt.number) return@on
            val f = e as? FrameFailure ?: FrameFailure(FrameLink.describe(e, settings.host))
            fail(f.message.orEmpty(), retry = false, needsPairing = f.needsPairing)
            return@on
        }
        connectNow(quiet = false)
    }

    /** The user's answer to a pending host key question. */
    fun answerHostKey(id: Int, trust: Boolean) = on {
        val pending = _hostKey.value
        if (pending?.id == id) {
            _hostKey.value = null
            pending.answer.complete(trust)
        }
    }

    /** Forget the headset. The Frame keeps the key line; remove it from ~/.ssh/authorized_keys there to revoke this phone. */
    fun forget() = on {
        begin()
        store.clear()
        _phase.value = Phase.Setup
    }

    /** Disconnect and show the setup screen; the pairing stays. */
    fun showSetup() = on {
        begin()
        _phase.value = Phase.Setup
    }

    // MARK: connecting

    /** Connect with the saved pairing (the app's start, Reconnect, Try again). */
    fun connect() = on { connectNow(quiet = false) }

    /** The waiting screen saw the Frame's SSH port answer: try now, leaving that screen up until it works. */
    fun retryQuietly() = on { if ((_phase.value as? Phase.Failed)?.canRetry == true) connectNow(quiet = true) }

    private fun connectNow(quiet: Boolean) {
        val pairing = store.load()
        if (pairing == null) {
            begin()
            _phase.value = Phase.Setup
            return
        }
        val a = begin()
        val settings = pairing.settings
        scope.launch {
            fun stepIfLoud(s: String) { if (!quiet) step(a, s) }
            stepIfLoud("Connecting to ${settings.label}")
            try {
                val bundle = io(a) { device.bundle() }
                val gate = HostKeyGate(settings, pinned = pairing.hostKey, previous = null) { false }
                val identity = SignerIdentity(device.signer)
                val link = io(a) { FrameLink.connect(settings, Login.Key(settings.user, identity), gate, pairing.hostKey.type, timing.connectMs) { a.own(it) } }
                    val dir = io(a) { HeadsetServer.deploy(bundle, link) { s -> scope.launch { stepIfLoud(s) } } }
                stepIfLoud("Starting Frame Control on the headset")
                val key = randomKey()
                val server = io(a) { HeadsetServer.start(dir, link, key, device.name, timing.serverStartMs) }
                val localPort = io(a) { link.forwardLocal(server.port) }
                server.exited?.let { throw FrameFailure("Frame Control on the headset stopped. ${it.takeLast(200)}") }
                // Only now does this attempt's connection become the app's.
                live = Live(link, server)
                readySince = System.nanoTime()
                _phase.value = Phase.Ready("http://127.0.0.1:$localPort/?key=$key", localPort)
                server.whenExited { tail -> scope.launch { lost(a.number, "Frame Control on the headset stopped. ${tail.takeLast(200)}") } }
                watchHealth(a.number)
            } catch (e: Throwable) {
                a.closeAll()
                if (closed.get() || e is CancellationException || a.number != attempt.number) return@launch
                val f = e as? FrameFailure ?: FrameFailure(FrameLink.describe(e, settings.host))
                fail(f.message.orEmpty(), retry = !f.needsPairing, needsPairing = f.needsPairing)
            }
        }
    }

    private fun fail(message: String, retry: Boolean, needsPairing: Boolean) {
        val paired = store.load() != null
        val retrying = retry && paired
        _phase.value = Phase.Failed(message, retrying, needsPairing, canRetry = paired && !needsPairing)
        if (!retrying) return
        // Keep trying quietly while the app is open: the Frame may just be asleep.
        val number = attempt.number
        retryJob = scope.launch {
            delay(timing.retryMs)
            if (number == attempt.number && _phase.value is Phase.Failed && device.isForeground) connectNow(quiet = true)
        }
    }

    /** While connected, check every 20 s that the SSH session still answers: a network change can leave it looking open. */
    private fun watchHealth(number: Int) {
        healthJob = scope.launch {
            while (true) {
                delay(timing.healthMs)
                if (number != attempt.number || _phase.value !is Phase.Ready) return@launch
                if (!device.isForeground) continue
                if (!healthy()) {
                    if (number == attempt.number) connectNow(quiet = true)
                    return@launch
                }
            }
        }
    }

    private suspend fun healthy(): Boolean {
        val current = live ?: return false
        if (current.server.exited != null) return false
        return withContext(Dispatchers.IO) { current.link.answers() }
    }

    private fun lost(number: Int, why: String) {
        if (number != attempt.number || _phase.value !is Phase.Ready) return
        // Restart it once; if it dies again straight away, say so instead of looping.
        if (System.nanoTime() - readySince < timing.quickLossMs * 1_000_000) {
            begin()
            fail(why, retry = false, needsPairing = false)
        } else {
            connectNow(quiet = false)
        }
    }

    // MARK: lifecycle

    /** The app came to the front: the connection may have dropped, or been put away, meanwhile. */
    fun onForeground() = on {
        backgroundJob?.cancel()
        backgroundJob = null
        if (pausedInBackground) {
            pausedInBackground = false
            connectNow(quiet = false)
            return@on
        }
        when (val p = _phase.value) {
            is Phase.Ready -> {
                val number = attempt.number
                if (!healthy() && number == attempt.number) connectNow(quiet = false)
            }
            // A changed identity or a refused login needs the user, not another try.
            is Phase.Failed -> if (p.canRetry) connectNow(quiet = false)
            else -> {}
        }
    }

    /** The app went out of sight: keep the connection a while, then close it (and the server on the headset). */
    fun onBackground() = on {
        backgroundJob?.cancel()
        backgroundJob = scope.launch {
            delay(timing.backgroundGraceMs)
            val p = _phase.value
            if (p is Phase.Ready || p is Phase.Connecting || (p is Phase.Failed && p.retrying)) {
                begin()
                pausedInBackground = true
                _phase.value = Phase.Connecting("Reconnecting")
            }
        }
    }

    /** The phone changed networks. */
    fun onNetworkChanged() = on {
        when (val p = _phase.value) {
            is Phase.Ready -> {
                val number = attempt.number
                if (!healthy() && number == attempt.number) connectNow(quiet = true)
            }
            is Phase.Failed -> if (p.retrying && device.isForeground) connectNow(quiet = true)
            else -> {}
        }
    }

    /** The app is going away for good: close everything. */
    fun shutdown() {
        // ViewModel clears its scope before onCleared. Resource ownership must not
        // depend on launching another coroutine in that scope. Late registrations
        // on the current attempt are closed immediately too.
        closed.set(true)
        attempt.closeAll()
        live = null
        retryJob?.cancel()
        healthJob?.cancel()
        backgroundJob?.cancel()
        _hostKey.value?.answer?.complete(false)
        _hostKey.value = null
    }

    /** Called on WebView's worker threads; assets are fetched by the headset. */
    fun fetchAsset(url: String): RemoteAsset {
        check(!closed.get()) { "Connection closed" }
        return (live ?: throw FrameFailure("Not connected")).link.fetchAsset(url)
    }

    // MARK: plumbing

    private fun on(cleanup: () -> Unit = {}, block: suspend () -> Unit) {
        if (closed.get()) { cleanup(); return }
        scope.launch { if (!closed.get()) block() }.invokeOnCompletion { cleanup() }
    }

    /** Starts a new attempt: everything the previous one opened, and the live connection, close. */
    private fun begin(): Attempt {
        attempt.closeAll()
        attempt = Attempt(attempt.number + 1)
        if (closed.get()) attempt.closeAll()
        retryJob?.cancel()
        healthJob?.cancel()
        retryJob = null
        healthJob = null
        _hostKey.value?.answer?.complete(false)
        _hostKey.value = null
        // The link belongs to the attempt, including once it becomes live.
        live = null
        return attempt
    }

    private fun step(a: Attempt, s: String) {
        if (!closed.get() && a.number == attempt.number) _phase.value = Phase.Connecting(s)
    }

    /** Runs blocking work off the main thread; a newer attempt meanwhile makes it a cancellation. */
    private suspend fun <T> io(a: Attempt, work: () -> T): T {
        if (closed.get() || a.number != attempt.number) throw CancellationException("superseded")
        var made: T? = null
        try {
            val result = withContext(Dispatchers.IO) {
                work().also { value ->
                    made = value
                    (value as? Closeable)?.let { a.own(it) }
                }
            }
            if (closed.get() || a.number != attempt.number) throw CancellationException("superseded")
            return result
        } catch (e: CancellationException) {
            // withContext may discard a successful result on prompt cancellation.
            (made as? Closeable)?.let { runCatching { it.close() } }
            throw e
        }
    }

    /** Asks the user about a host key, from JSch's thread, and waits for the answer (no answer is a no). */
    private fun asker(a: Attempt): (HostKeyQuestion) -> Boolean = { question ->
        val answer = CompletableFuture<Boolean>()
        a.own(Closeable { answer.complete(false) })
        val pending = PendingHostKey(questions.incrementAndGet(), question, answer)
        scope.launch {
            if (!closed.get() && a.number == attempt.number) {
                _phase.value = Phase.Connecting("Check the headset's identity")
                _hostKey.value = pending
            } else {
                answer.complete(false)
            }
        }
        val yes = runCatching { answer.get(timing.confirmMs, TimeUnit.MILLISECONDS) }.getOrDefault(false)
        scope.launch { if (_hostKey.value?.id == pending.id) _hostKey.value = null }
        yes
    }

    private fun randomKey(): String {
        val bytes = ByteArray(24)
        SecureRandom().nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }
}
