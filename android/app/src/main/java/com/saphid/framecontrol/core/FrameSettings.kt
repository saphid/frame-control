package com.saphid.framecontrol.core

/** Where the Frame is and who to log in as. */
data class FrameSettings(val host: String, val port: Int = 22, val user: String = "steamos") {
    /** The address as people type it: "host", "host:port" or "[v6]:port". */
    val label: String
        get() = when {
            port == 22 -> host
            ':' in host -> "[$host]:$port"
            else -> "$host:$port"
        }

    companion object {
        /**
         * "host", "host:port" or "[v6]:port", plus a user name. A port given on its own
         * (the setup screen's Port field) wins over one in the address.
         */
        fun parse(address: String, user: String, port: String = ""): FrameSettings? {
            var host = address.trim()
            var p = 22
            if (host.startsWith("[")) {
                val close = host.indexOf(']')
                if (close < 0) return null
                val rest = host.substring(close + 1)
                when {
                    rest.startsWith(":") -> p = rest.substring(1).toIntOrNull() ?: return null
                    rest.isNotEmpty() -> return null
                }
                host = host.substring(1, close)
            } else if (host.count { it == ':' } == 1) {
                val colon = host.lastIndexOf(':')
                p = host.substring(colon + 1).toIntOrNull() ?: return null
                host = host.substring(0, colon)
            }
            if (port.isNotBlank()) p = port.trim().toIntOrNull() ?: return null
            val name = user.trim()
            if (host.isEmpty() || host.startsWith("-") || p !in 1..65535 || !HOST.matches(host) || !USER.matches(name)) return null
            return FrameSettings(host, p, name)
        }

        // Names, IPv4, and IPv6 with an optional zone; nothing a shell or URL would read specially.
        private val HOST = Regex("[A-Za-z0-9._%:-]+")
        private val USER = Regex("[A-Za-z0-9_][A-Za-z0-9._-]*")
    }
}

/** Why connecting failed, in words for the user. */
class FrameFailure(
    message: String,
    /** Retrying can't help: the Frame's identity changed, or it refused this phone's login. */
    val needsPairing: Boolean = false,
    cause: Throwable? = null,
) : Exception(message, cause)

fun shellQuote(s: String): String = "'" + s.replace("'", "'\\''") + "'"
