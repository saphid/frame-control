package com.saphid.framecontrol

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.Executor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Finds the Frame on the local network so nobody has to type its address. A Frame in
 * Developer Mode advertises Valve's devkit service (`_steamos-devkit._tcp`); failing that,
 * the fallback (the typed or saved address, or frame.local) is checked by opening its SSH
 * port. Both repeat until stopped. Like the iPhone app's FrameFinder.
 */
class FrameFinder(context: Context, private val scope: CoroutineScope) {
    data class Found(val host: String, val name: String)

    private val nsd = context.getSystemService(NsdManager::class.java)
    private val main: Executor = context.mainExecutor
    private val _found = MutableStateFlow<Found?>(null)
    val found: StateFlow<Found?> = _found

    private var discovery: NsdManager.DiscoveryListener? = null
    private val callbacks = mutableListOf<NsdManager.ServiceInfoCallback>()
    private var probe: Job? = null

    fun start(fallbackHost: String, fallbackPort: Int) {
        stop()
        _found.value = null
        browse()
        probe = scope.launch {
            while (isActive) {
                if (_found.value == null && sshAnswers(fallbackHost, fallbackPort)) _found.value = Found(fallbackHost, fallbackHost)
                delay(3_000)
            }
        }
    }

    fun stop() {
        probe?.cancel()
        probe = null
        discovery?.let { runCatching { nsd?.stopServiceDiscovery(it) } }
        discovery = null
        if (Build.VERSION.SDK_INT >= 34) callbacks.forEach { runCatching { nsd?.unregisterServiceInfoCallback(it) } }
        callbacks.clear()
    }

    private fun browse() {
        val nsd = nsd ?: return
        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onServiceLost(service: NsdServiceInfo) {}
            override fun onServiceFound(service: NsdServiceInfo) = main.execute { resolve(nsd, service) }
        }
        discovery = listener
        runCatching { nsd.discoverServices(SERVICE, NsdManager.PROTOCOL_DNS_SD, listener) }
    }

    private fun resolve(nsd: NsdManager, service: NsdServiceInfo) {
        if (discovery == null) return
        if (Build.VERSION.SDK_INT >= 34) {
            val callback = object : NsdManager.ServiceInfoCallback {
                override fun onServiceInfoCallbackRegistrationFailed(errorCode: Int) {}
                override fun onServiceLost() {}
                override fun onServiceInfoCallbackUnregistered() {}
                override fun onServiceUpdated(info: NsdServiceInfo) = found(info.serviceName, info.hostAddresses)
            }
            callbacks += callback
            runCatching { nsd.registerServiceInfoCallback(service, main, callback) }
        } else {
            @Suppress("DEPRECATION")
            runCatching {
                nsd.resolveService(service, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {}
                    override fun onServiceResolved(info: NsdServiceInfo) {
                        main.execute { found(info.serviceName, listOfNotNull(info.host)) }
                    }
                })
            }
        }
    }

    /** A found device is used over the fallback probe; IPv4 first, since link-local IPv6 needs a zone. */
    private fun found(name: String, addresses: List<InetAddress>) {
        if (discovery == null) return
        val address = addresses.firstOrNull { it is Inet4Address } ?: addresses.firstOrNull() ?: return
        _found.value = Found(address.hostAddress ?: return, name)
    }

    companion object {
        const val SERVICE = "_steamos-devkit._tcp"

        /** Whether something answers on host:port within a few seconds. */
        suspend fun sshAnswers(host: String, port: Int): Boolean = withContext(Dispatchers.IO) {
            runCatching { Socket().use { it.connect(InetSocketAddress(host, port), 3_000) } }.isSuccess
        }
    }
}
