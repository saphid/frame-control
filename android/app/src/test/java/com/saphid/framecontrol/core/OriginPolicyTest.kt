package com.saphid.framecontrol.core

import com.saphid.framecontrol.core.OriginPolicy.Decision.BLOCK
import com.saphid.framecontrol.core.OriginPolicy.Decision.EXTERNAL
import com.saphid.framecontrol.core.OriginPolicy.Decision.STAY
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class OriginPolicyTest {
    private val policy = OriginPolicy(43117)

    private fun check(expected: OriginPolicy.Decision, url: String, mainFrame: Boolean = true) =
        assertEquals(url, expected, policy.decide(url, mainFrame))

    @Test
    fun onlyTheTunnelsExactOriginLoadsInTheApp() {
        check(STAY, "http://127.0.0.1:43117/?key=abc")
        check(STAY, "http://127.0.0.1:43117/index.html#games")
        check(STAY, "HTTP://127.0.0.1:43117/")
        // Same host, another port: some other app's server on this phone, or an old tunnel.
        check(BLOCK, "http://127.0.0.1:43118/")
        check(BLOCK, "http://127.0.0.1/")
        check(BLOCK, "https://127.0.0.1:43117/")
        check(BLOCK, "http://localhost:43117/")
        check(BLOCK, "http://[::1]:43117/")
        check(BLOCK, "http://2130706433:43117/")
        check(BLOCK, "http://0x7f000001:43117/")
        check(BLOCK, "http://127.1:43117/")
        check(BLOCK, "http://app.localhost:43117/")
    }

    @Test
    fun lookalikesDontPassForTheTunnel() {
        // User info before the host: the real host is evil.example.
        check(BLOCK, "http://127.0.0.1:43117@evil.example/")
        // The "127.0.0.1:43117" is only in the fragment.
        check(EXTERNAL, "http://evil.example/#@127.0.0.1:43117")
        // Starts like a loopback address: never handed out, even if it is really a name.
        check(BLOCK, "http://127.0.0.1.evil.example:43117/")
    }

    @Test
    fun webLinksGoToTheBrowserFromThePageButNotFromFrames() {
        check(EXTERNAL, "https://store.steampowered.com/remoteplay")
        check(EXTERNAL, "https://f-droid.org/packages/org.example/")
        check(BLOCK, "https://store.steampowered.com/", mainFrame = false)
    }

    @Test
    fun everythingElseGoesNowhere() {
        for (url in listOf(
            "file:///data/data/com.saphid.framecontrol/shared_prefs/frame-control-pairing.xml",
            "content://com.android.contacts/contacts",
            "intent://scan/#Intent;scheme=zxing;package=com.example;end",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "blob:http://127.0.0.1:43117/1234",
            "about:blank",
            "steam://run/123",
            "ftp://example.com/",
            "not a url",
        )) check(BLOCK, url)
    }
}

class InstallLinkTest {
    @Test
    fun acceptsTheTwoDocumentedForms() {
        assertEquals(InstallLink("manifest", "https://example.com/app.json"),
            InstallLink.parse("frame-control://install?manifest=https%3A%2F%2Fexample.com%2Fapp.json"))
        assertEquals(InstallLink("url", "https://example.com/a+b.apk"), InstallLink.parse("frame-control://install?url=https://example.com/a+b.apk"))
    }

    @Test
    fun rejectsAnythingElse() {
        for (raw in listOf(
            "frame-control://install?manifest=file:///etc/passwd",
            "frame-control://install?manifest=https://user:pw@example.com/a.json",
            "frame-control://install?manifest=https://a.example/x&url=https://b.example/y",
            "frame-control://open?url=https://example.com/a.apk",
            "frame-control://install/extra?url=https://example.com/a.apk",
            "frame-control://install?other=https://example.com/a.apk",
            "https://install?url=https://example.com/a.apk",
            "frame-control://install?url=" + "https://example.com/" + "a".repeat(2100),
        )) assertNull(raw, InstallLink.parse(raw))
    }
}

class FrameSettingsTest {
    @Test
    fun readsTheAddressFormsTheSetupScreenTakes() {
        assertEquals(FrameSettings("frame.local", 22, "steamos"), FrameSettings.parse(" frame.local ", "steamos"))
        assertEquals(FrameSettings("192.168.1.20", 2222, "steamos"), FrameSettings.parse("192.168.1.20:2222", "steamos"))
        assertEquals(FrameSettings("fe80::1%wlan0", 22, "steamos"), FrameSettings.parse("fe80::1%wlan0", "steamos"))
        assertEquals(FrameSettings("fd00::5", 2200, "deck"), FrameSettings.parse("[fd00::5]:2200", "deck"))
        // The Port field wins over a port in the address.
        assertEquals(FrameSettings("frame.local", 2022, "steamos"), FrameSettings.parse("frame.local:22", "steamos", "2022"))
    }

    @Test
    fun refusesWhatCouldReachAShellOrIsntAnAddress() {
        for ((host, user, port) in listOf(
            Triple("", "steamos", ""), Triple("frame.local", "", ""), Triple("frame.local", "steamos", "0"),
            Triple("frame.local", "steamos", "70000"), Triple("frame.local", "steamos", "22a"),
            Triple("frame;reboot", "steamos", ""), Triple("frame.local", "steamos;id", ""), Triple("frame.local", "-oProxyCommand=x", ""), Triple("-oProxyCommand", "steamos", ""),
            Triple("frame local", "steamos", ""), Triple("[fd00::5", "steamos", ""), Triple("\$(id).local", "steamos", ""),
        )) assertNull("$host / $user / $port", FrameSettings.parse(host, user, port))
    }

    @Test
    fun aPinnedKeyTypeIsOfferedFirstAndCertificatesNever() {
        val defaults = "ssh-ed25519,ecdsa-sha2-nistp256,ssh-ed25519-cert-v01@openssh.com,rsa-sha2-512,rsa-sha2-256"
        assertEquals("ssh-ed25519,ecdsa-sha2-nistp256,rsa-sha2-512,rsa-sha2-256", FrameLink.hostKeyAlgorithms(defaults, null))
        assertEquals("ecdsa-sha2-nistp256,ssh-ed25519,rsa-sha2-512,rsa-sha2-256", FrameLink.hostKeyAlgorithms(defaults, "ecdsa-sha2-nistp256"))
        assertEquals("rsa-sha2-512,rsa-sha2-256,ssh-ed25519,ecdsa-sha2-nistp256", FrameLink.hostKeyAlgorithms(defaults, "ssh-rsa"))
    }
}
