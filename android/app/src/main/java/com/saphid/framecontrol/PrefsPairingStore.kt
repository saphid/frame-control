package com.saphid.framecontrol

import android.annotation.SuppressLint
import android.content.Context
import com.saphid.framecontrol.core.FrameHostKey
import com.saphid.framecontrol.core.FrameSettings
import com.saphid.framecontrol.core.Pairing
import com.saphid.framecontrol.core.PairingStore

/**
 * The pairing in app-private preferences: address, port, user and the confirmed host key.
 * None of it is secret (the password is never stored, and the SSH key is in the Keystore),
 * and none of it is backed up (res/xml/data_extraction_rules.xml).
 */
class PrefsPairingStore(context: Context) : PairingStore {
    private val prefs = context.getSharedPreferences("frame-control-pairing", Context.MODE_PRIVATE)

    override fun load(): Pairing? {
        val host = prefs.getString(HOST, null) ?: return null
        val user = prefs.getString(USER, null) ?: return null
        val key = FrameHostKey.decode(prefs.getString(HOST_KEY, null)) ?: return null
        val settings = FrameSettings.parse(host, user, prefs.getInt(PORT, 22).toString()) ?: return null
        return Pairing(settings, key)
    }

    // commit, not apply: connecting starts straight after, and a pairing lost to a crash
    // would mean typing the password again.
    @SuppressLint("ApplySharedPref")
    override fun save(pairing: Pairing) {
        prefs.edit()
            .putString(HOST, pairing.settings.host)
            .putInt(PORT, pairing.settings.port)
            .putString(USER, pairing.settings.user)
            .putString(HOST_KEY, pairing.hostKey.encode())
            .commit()
    }

    @SuppressLint("ApplySharedPref")
    override fun clear() {
        prefs.edit().clear().commit()
    }

    private companion object {
        const val HOST = "host"
        const val PORT = "port"
        const val USER = "user"
        const val HOST_KEY = "hostKey"
    }
}
