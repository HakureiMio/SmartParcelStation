package io.github.hakureimio.smartparcel.demo

import android.app.*
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import java.time.LocalTime
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class GateForegroundService : Service() {
    private val executor = Executors.newSingleThreadScheduledExecutor()
    override fun onCreate() {
        super.onCreate()
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel(CHANNEL, "Gate Demo", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
        startForeground(7, NotificationCompat.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("SmartParcel Gate Demo Running").setContentText("每 8 秒检查 Gateway").build())
        executor.scheduleWithFixedDelay(::poll, 0, 8, TimeUnit.SECONDS)
    }
    private fun poll() {
        val c = Config(this)
        val result = runCatching {
            val health = ApiClient.request("GET", "${c.gatewayUrl}/local/health")
            val auth = ApiClient.request("GET", "${c.gatewayUrl}/local/gate/auth-result?reader_id=${c.readerId}", ApiClient.readerHeaders(c))
            "${LocalTime.now().withNano(0)} health=$health\nauth-result=$auth"
        }.getOrElse { "${LocalTime.now().withNano(0)} ERROR: ${it.message}" }
        getSharedPreferences("service_log", MODE_PRIVATE).edit().putString("last", result).apply()
        sendBroadcast(Intent(ACTION_STATUS).setPackage(packageName))
    }
    override fun onDestroy() { executor.shutdownNow(); super.onDestroy() }
    override fun onBind(intent: Intent?): IBinder? = null
    companion object { const val CHANNEL = "gate_demo"; const val ACTION_STATUS = "io.github.hakureimio.smartparcel.demo.SERVICE_STATUS" }
}
