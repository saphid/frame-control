package com.saphid.framecontrol.core

import java.net.URI

/** Passive resources used by the pinned page. No arbitrary remote URLs, scripts or HTML. */
object AssetPolicy {
    const val MAX_BYTES = 8 * 1024 * 1024
    val roots = listOf(
        "https://store.fastly.steamstatic.com/public/shared/fonts/",
        "https://cdn.cloudflare.steamstatic.com/steam/apps/",
        "https://cdn.cloudflare.steamstatic.com/store_item_assets/steam/apps/",
        "https://f-droid.org/repo/",
        "https://f-droid.org/archive/",
        "https://apt.izzysoft.de/fdroid/repo/",
    )
    fun allows(raw: String): Boolean {
        if (raw.length > 4096) return false
        val u = runCatching { URI(raw) }.getOrNull() ?: return false
        if (u.scheme != "https" || u.rawUserInfo != null || u.port !in listOf(-1, 443) || u.rawFragment != null) return false
        if (u.rawPath != u.normalize().rawPath || '%' in u.rawPath.orEmpty() || '\\' in raw) return false
        return roots.any { root ->
            val r = URI(root)
            u.host == r.host && u.path.orEmpty().startsWith(r.path)
        }
    }
}

data class RemoteAsset(val mime: String, val bytes: ByteArray)
