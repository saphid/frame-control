package com.saphid.framecontrol

import android.app.Application
import android.net.ConnectivityManager
import android.net.Network
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.saphid.framecontrol.core.ConnectionController
import com.saphid.framecontrol.core.Device
import com.saphid.framecontrol.core.FrameBundle
import com.saphid.framecontrol.core.FrameFailure
import com.saphid.framecontrol.core.InstallLink
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** Holds the connection across rotation and window changes; closes it when the app goes for good. */
class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val device = AndroidDevice(app)
    val signer: KeystoreSigner get() = device.signer
    val deviceName: String get() = device.name

    val controller = ConnectionController(PrefsPairingStore(app), device, viewModelScope)

    /** Install links that arrived before the page was ready for them. */
    val pendingInstallLinks = ArrayDeque<InstallLink>()

    private val connectivity = app.getSystemService(ConnectivityManager::class.java)
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        private var first = true
        override fun onAvailable(network: Network) {
            // The callback reports the current network straight away; only changes count.
            if (first) { first = false; return }
            controller.onNetworkChanged()
        }
        override fun onLost(network: Network) = controller.onNetworkChanged()
    }

    init {
        viewModelScope.launch(Dispatchers.IO) { runCatching { device.signer.publicKey } }  // make the key now, off the main thread
        runCatching { connectivity?.registerDefaultNetworkCallback(networkCallback) }
        if (controller.pairing != null) controller.connect()
    }

    fun setForeground(foreground: Boolean) {
        device.foreground = foreground
        if (foreground) controller.onForeground() else controller.onBackground()
    }

    override fun onCleared() {
        runCatching { connectivity?.unregisterNetworkCallback(networkCallback) }
        controller.shutdown()
    }

    private class AndroidDevice(private val app: Application) : Device {
        override val signer = KeystoreSigner(app)

        override val name: String
            get() = if (app.resources.configuration.smallestScreenWidthDp >= 600) "tablet" else "phone"

        override val keyComment: String =
            "frame-control@android-" + Build.MODEL.replace(Regex("[^A-Za-z0-9._-]"), "-").take(40)

        @Volatile var foreground = true
        override val isForeground: Boolean get() = foreground

        @Volatile private var cached: FrameBundle? = null

        override fun bundle(): FrameBundle = cached ?: try {
            // The .tar.gz, under a name asset packaging leaves alone (app/build.gradle.kts).
            val data = app.assets.open("frame-bundle.bin").use { it.readBytes() }
            val version = app.assets.open("frame-bundle.version").use { it.readBytes() }.toString(Charsets.UTF_8).trim()
            FrameBundle(data, version).also { cached = it }
        } catch (e: Exception) {
            throw FrameFailure("This build of the app is missing its Frame bundle", cause = e)
        }
    }
}
