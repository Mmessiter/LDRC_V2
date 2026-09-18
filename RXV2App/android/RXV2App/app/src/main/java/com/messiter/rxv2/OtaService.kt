// LockDownRadioControl — RXV2App (Android)  ::  OtaService.kt
//
// A foreground service that runs for the length of a Bluetooth firmware
// install. Malcolm 2026-09-18, after the iPhone's screen lock stalled one:
// "it would be better if screen timeout or checking emails etc during update
// had no effect on the success."
//
// It does no work itself - the install thread lives in MainActivity - it
// keeps the PROCESS in the foreground, so Android neither freezes it nor
// lets the Bluetooth link lapse when the screen locks or another app comes
// to the front. Started at the top of runBleOta(), stopped in its finally.
package com.messiter.rxv2

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

class OtaService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Firmware updates", NotificationManager.IMPORTANCE_LOW))
        val text = intent?.getStringExtra(EXTRA_TEXT) ?: "Updating over Bluetooth - keep the phone near the receiver"
        @Suppress("DEPRECATION")
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(this, CHANNEL) else Notification.Builder(this)
        val n: Notification = builder
            .setContentTitle("RXV2 update in progress")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setOngoing(true)
            .build()
        // Android 14+ insists on a type; "connected device" is what this is.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        else
            startForeground(NOTIF_ID, n)
        return START_NOT_STICKY
    }

    companion object {
        const val CHANNEL = "rxv2_ota"
        const val NOTIF_ID = 4242
        const val EXTRA_TEXT = "text"

        fun start(ctx: Context, text: String? = null) {
            val i = Intent(ctx, OtaService::class.java)
            if (text != null) i.putExtra(EXTRA_TEXT, text)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i) else ctx.startService(i)
        }

        fun stop(ctx: Context) { ctx.stopService(Intent(ctx, OtaService::class.java)) }
    }
}
