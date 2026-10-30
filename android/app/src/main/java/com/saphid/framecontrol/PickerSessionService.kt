package com.saphid.framecontrol

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper

/** Keeps the headset connection running while a system document picker is in front.
 * Started only from the visible Activity, and stopped when its picker returns.
 * This is not a persistent background connection or a restarted service.
 */
class PickerSessionService : Service() {
    companion object {
        private const val CHANNEL = "picker_connection"
        private const val NOTIFICATION = 1

        // Activity and Service callbacks run on the main thread. A release may
        // arrive before onStartCommand: don't stop a pending foreground start
        // until it has fulfilled Android's startForeground requirement.
        private var requested = false
        private var foregroundInstance: PickerSessionService? = null

        fun hold(context: Context) {
            requested = true
            try {
                context.startForegroundService(Intent(context, PickerSessionService::class.java))
            } catch (error: RuntimeException) {
                requested = false
                throw error
            }
        }

        fun release() {
            requested = false
            foregroundInstance?.stopSelf()
        }
    }

    private val expiry = Handler(Looper.getMainLooper())

    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "Frame connection", NotificationManager.IMPORTANCE_LOW),
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val returnToApp = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_monochrome)
            .setContentTitle(getString(R.string.app_name))
            .setContentText("Keeping your Frame connected while you choose a file.")
            .setContentIntent(returnToApp)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            notification.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE)
        }
        startForeground(NOTIFICATION, notification.build(), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        foregroundInstance = this
        expiry.removeCallbacksAndMessages(null)
        if (!requested) {
            stopSelf(startId)
            return START_NOT_STICKY
        }
        // Match the connection's background grace, including if no result arrives.
        expiry.postDelayed({ stopSelf(startId) }, 180_000)
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        if (foregroundInstance === this) foregroundInstance = null
        expiry.removeCallbacksAndMessages(null)
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
}
