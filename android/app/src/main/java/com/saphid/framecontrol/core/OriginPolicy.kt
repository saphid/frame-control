package com.saphid.framecontrol.core

import java.net.URI

/**
 * Where the web view may go. Only the exact origin of the current tunnel
 * (http://127.0.0.1:<its port>) loads in the app; ordinary web links open in the
 * system browser; anything else (other local ports, file:, content:, intent:,
 * javascript:, data:, links with user info) goes nowhere.
 */
class OriginPolicy(val port: Int) {
    enum class Decision { STAY, EXTERNAL, BLOCK }

    init {
        require(port in 1..65535)
    }

    val origin: String get() = "http://127.0.0.1:$port"

    fun decide(url: String, mainFrame: Boolean = true): Decision {
        val uri = runCatching { URI(url) }.getOrNull() ?: return Decision.BLOCK
        val scheme = uri.scheme?.lowercase() ?: return Decision.BLOCK
        if (scheme != "http" && scheme != "https") return Decision.BLOCK
        if (uri.rawUserInfo != null) return Decision.BLOCK
        val host = uri.host?.lowercase() ?: return Decision.BLOCK
        if (scheme == "http" && host == "127.0.0.1" && uri.port == port) return Decision.STAY
        if (loopbackLike(host)) return Decision.BLOCK
        return if (mainFrame) Decision.EXTERNAL else Decision.BLOCK
    }

    /** Names and numbers that reach this phone itself: never handed to a browser. */
    private fun loopbackLike(host: String): Boolean {
        val h = host.removePrefix("[").removeSuffix("]")
        return h == "localhost" || h.endsWith(".localhost") || h.startsWith("127.") || h == "0.0.0.0" ||
            h == "::1" || h == "::" || h.startsWith("0x") || h.all { it.isDigit() || it == '.' } && h.count { it == '.' } < 3
    }
}

/**
 * frame-control://install?manifest=URL or ?url=URL (docs/web-install.md): the same first
 * filter as the iPhone app (ios/FrameControl/App/InstallLink.swift). The server on the
 * Frame applies the full rules (HTTPS, no private addresses, redirects) before fetching.
 */
data class InstallLink(val kind: String, val target: String) {
    companion object {
        const val SCHEME = "frame-control"
        private const val MAX_LINK = 4096
        private const val MAX_URL = 2048

        fun parse(raw: String): InstallLink? {
            if (raw.length > MAX_LINK || !raw.lowercase().startsWith("$SCHEME:")) return null
            val link = runCatching { URI(raw) }.getOrNull() ?: return null
            if (link.scheme?.lowercase() != SCHEME || link.host?.lowercase() != "install" || link.path !in listOf("", "/")) return null
            val items = link.rawQuery?.split('&')?.filter { it.isNotEmpty() } ?: return null
            if (items.size != 1) return null
            val eq = items[0].indexOf('=')
            if (eq <= 0) return null
            val kind = items[0].substring(0, eq)
            if (kind != "manifest" && kind != "url") return null
            // Percent-decoding only, as URLComponents does: "+" stays "+".
            val value = items[0].substring(eq + 1).replace("+", "%2B")
            val target = runCatching { java.net.URLDecoder.decode(value, "UTF-8") }.getOrNull() ?: return null
            if (target.isEmpty() || target.length > MAX_URL) return null
            val url = runCatching { URI(target) }.getOrNull() ?: return null
            if (url.scheme?.lowercase() !in listOf("https", "http") || url.host.isNullOrEmpty() || url.rawUserInfo != null) return null
            return InstallLink(kind, target)
        }
    }
}
