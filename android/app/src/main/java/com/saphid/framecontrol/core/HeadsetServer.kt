package com.saphid.framecontrol.core

import com.jcraft.jsch.ChannelExec
import java.security.MessageDigest
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException

/** The server, headset helpers and catalogue the app copies to the Frame (android/scripts/frame_bundle.py). */
class FrameBundle(val data: ByteArray, val version: String) {
    init {
        require(Regex("[0-9a-f]{16}").matches(version)) { "bad bundle version" }
        val digest = MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) }
        require(digest.startsWith(version)) { "the bundle doesn't match its version" }
    }
}

/**
 * Frame Control's server, running on the Frame itself, as the iPhone app runs it
 * (ios/FrameControl/SSH/HeadsetServer.swift): copied to ~/.cache/frame-control/<version>
 * once per version, started over SSH, listening only on the Frame's 127.0.0.1, and
 * stopping when this SSH session ends (--exit-on-eof).
 */
class HeadsetServer private constructor(val port: Int, private val channel: ChannelExec, private val ended: CompletableFuture<String>) {
    /** Set once the server stops, with its last output. */
    val exited: String? get() = ended.getNow(null)

    /** Calls back once when the server stops (at once if it already has), on the output reader's thread. */
    fun whenExited(callback: (String) -> Unit) {
        ended.thenAccept(callback)
    }

    fun stop() = channel.disconnect()

    companion object {
        const val CACHE_DIR = ".cache/frame-control"

        /** Copies the bundle over unless this version is already there; removes old versions. */
        fun deploy(bundle: FrameBundle, link: FrameLink, progress: (String) -> Unit): String {
            val dir = "$CACHE_DIR/${bundle.version}"
            val (py, pyStatus) = link.run("command -v python3 >/dev/null && python3 -c 'import sys; print(sys.version_info >= (3, 8))'")
            if (pyStatus != 0 || !py.endsWith("True")) {
                throw FrameFailure("The Frame has no Python 3.8 or later, which Frame Control needs there.")
            }
            if (link.run("test -f $dir/ui/server.py").second != 0) {
                progress("Copying Frame Control to the headset")
                link.check("mkdir -p $CACHE_DIR", "Couldn't make $CACHE_DIR")
                val archive = "$dir.tar.gz"
                link.upload(bundle.data, archive)
                progress("Unpacking")
                link.check("rm -rf $dir.tmp && mkdir $dir.tmp && tar xzf $archive -C $dir.tmp && rm -f $archive " +
                    "&& rm -rf $dir && mv $dir.tmp $dir", "Couldn't unpack Frame Control on the headset")
            }
            // Another phone may be running a different version right now: a version goes only
            // when no server runs from it and it hasn't been used for two weeks.
            runCatching {
                link.run("touch $dir && cd $CACHE_DIR && for d in */; do d=\${d%/}; " +
                    "[ \"\$d\" = ${bundle.version} ] && continue; " +
                    "[ -n \"\$(find \"\$d\" -maxdepth 0 -mtime +14)\" ] || continue; " +
                    "pgrep -f \"\$PWD/\$d/\" >/dev/null && continue; rm -rf -- \"\$d\"; done")
            }
            return dir
        }

        /** Starts the server in dir and waits for it to say which port it took. */
        fun start(dir: String, link: FrameLink, key: String, device: String, timeoutMs: Long = 30_000): HeadsetServer {
            require(Regex("[0-9a-f]{32,128}").matches(key)) { "bad UI key" }
            val channel = link.exec("cd $dir && FRAME_LOCAL=1 FRAME_UI_KEY=$key FRAME_DEVICE=${shellQuote(device)} " +
                "exec python3 -I -u -B \"\$PWD/ui/server.py\" --port 0 --exit-on-eof 2>&1")
            val input = channel.inputStream
            channel.connect(15_000)
            val portFound = CompletableFuture<Int>()
            val ended = CompletableFuture<String>()
            Thread({
                val text = StringBuilder()
                val buf = ByteArray(4096)
                try {
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        text.append(String(buf, 0, n, Charsets.UTF_8))
                        if (text.length > 20_000) text.delete(0, text.length - 10_000)
                        if (!portFound.isDone) port(text)?.let { portFound.complete(it) }
                    }
                } catch (e: Exception) {
                    text.append("\n").append(e.javaClass.simpleName)
                }
                val tail = text.takeLast(600).trim().toString()
                portFound.completeExceptionally(FrameFailure("Frame Control's server on the headset stopped: ${tail.ifEmpty { "no output" }}"))
                ended.complete(tail)
            }, "frame-server-output").apply { isDaemon = true }.start()
            val port = try {
                portFound.get(timeoutMs, TimeUnit.MILLISECONDS)
            } catch (e: TimeoutException) {
                channel.disconnect()
                throw FrameFailure("Frame Control's server on the headset didn't start within ${timeoutMs / 1000} s")
            } catch (e: Exception) {
                channel.disconnect()
                throw (e.cause as? FrameFailure) ?: FrameFailure("Frame Control's server on the headset didn't start", cause = e)
            }
            return HeadsetServer(port, channel, ended)
        }

        /**
         * The port from the server's first line. Output arrives in chunks, so the digits only
         * count once something follows them (the line goes on after the port).
         */
        fun port(text: CharSequence): Int? {
            val m = Regex("""Frame Control on http://127\.0\.0\.1:([0-9]+)\s""").find(text) ?: return null
            return m.groupValues[1].toIntOrNull()?.takeIf { it in 1..65535 }
        }
    }
}
