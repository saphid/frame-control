package com.saphid.framecontrol.core

import java.net.HttpURLConnection
import java.net.URI

/** Stream only the active authenticated tunnel; check every redirect before sending the key. */
object TunnelDownload {
    fun copy(url: String, policy: OriginPolicy, key: String, active: () -> Boolean, write: (Long, ByteArray) -> Unit) {
        var target = URI(url)
        repeat(4) { hop ->
            require(policy.decide(target.toString(), false) == OriginPolicy.Decision.STAY) { "Download origin blocked" }
            check(active()) { "Download cancelled" }
            val c = target.toURL().openConnection() as HttpURLConnection
            c.instanceFollowRedirects = false
            c.connectTimeout = 8_000
            c.readTimeout = 15_000
            c.setRequestProperty("X-Frame-UI", key)
            try {
                val code = c.responseCode
                if (code in 300..399) {
                    check(hop < 3) { "Too many download redirects" }
                    val location = c.getHeaderField("Location") ?: error("Download redirect has no destination")
                    target = target.resolve(location)
                    return@repeat
                }
                check(code in 200..299) { "Download failed (HTTP $code)" }
                val expected = c.contentLengthLong
                require(expected <= SaveTransfer.MAX_SIZE) { "File exceeds 2 GiB" }
                var offset = 0L
                c.inputStream.use { input ->
                    val bytes = ByteArray(SaveTransfer.CHUNK)
                    while (true) {
                        check(active()) { "Download cancelled" }
                        val n = input.read(bytes)
                        if (n < 0) break
                        if (n == 0) continue
                        require(offset + n <= SaveTransfer.MAX_SIZE) { "File exceeds 2 GiB" }
                        write(offset, bytes.copyOf(n))
                        offset += n
                    }
                }
                check(expected < 0 || expected == offset) { "Download interrupted" }
                return
            } finally { c.disconnect() }
        }
    }
}
