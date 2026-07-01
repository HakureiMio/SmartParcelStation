package io.github.hakureimio.smartparcel.demo

import android.content.Intent
import android.nfc.cardemulation.HostApduService
import android.os.Bundle

class SmartParcelHostApduService : HostApduService() {
    override fun processCommandApdu(command: ByteArray?, extras: Bundle?): ByteArray {
        val hex = command?.joinToString("") { "%02X".format(it) }.orEmpty()
        val cfg = Config(this)
        val expected = "00A40400${"%02X".format(cfg.aid.length / 2)}${cfg.aid}00"
        val response = if (hex.equals(expected, true)) {
            ("SPSHCE1|credential_type=PHONE_HCE|credential_value=${cfg.credential}|user_id=${cfg.userId}").toByteArray() + byteArrayOf(0x90.toByte(), 0x00)
        } else byteArrayOf(0x6A, 0x82.toByte())
        val responseHex = response.joinToString("") { "%02X".format(it) }
        getSharedPreferences("hce_log", MODE_PRIVATE).edit().putString("request", hex).putString("response", responseHex).apply()
        sendBroadcast(Intent(ACTION_HCE_LOG).setPackage(packageName))
        return response
    }
    override fun onDeactivated(reason: Int) = Unit
    companion object { const val ACTION_HCE_LOG = "io.github.hakureimio.smartparcel.demo.HCE_LOG" }
}
