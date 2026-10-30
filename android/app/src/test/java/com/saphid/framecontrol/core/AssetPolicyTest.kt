package com.saphid.framecontrol.core

import org.junit.Assert.*
import org.junit.Test

class AssetPolicyTest {
    @Test fun permitsThePinnedPagesArtworkAndFonts() {
        for (u in listOf(
            "https://store.fastly.steamstatic.com/public/shared/fonts/MotivaSans-Regular.ttf?v=4.015",
            "https://cdn.cloudflare.steamstatic.com/steam/apps/570/header.jpg",
            "https://f-droid.org/repo/icons-640/org.example.png",
            "https://apt.izzysoft.de/fdroid/repo/org.example/icon.png",
        )) assertTrue(u, AssetPolicy.allows(u))
    }
    @Test fun rejectsOtherOriginsPrivateAddressesAndPathEscapes() {
        for (u in listOf(
            "https://f-droid.org.evil.example/repo/icon.png", "https://user@f-droid.org/repo/icon.png",
            "http://f-droid.org/repo/icon.png", "https://f-droid.org:444/repo/icon.png",
            "https://127.0.0.1/repo/icon.png", "https://f-droid.org/repo/../private",
            "https://f-droid.org/repo/%2e%2e/private", "https://f-droid.org/repo/icon.png#x",
            "https://cdn.cloudflare.steamstatic.com/other/script.js", "file:///etc/passwd",
        )) assertFalse(u, AssetPolicy.allows(u))
    }
}
