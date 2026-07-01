package io.github.hakureimio.smartparcel.demo

import android.net.Uri

data class SpsPayload(val type: Type, val raw: String, val values: Map<String, String>) {
    enum class Type { GATE_QR, GATE_NFC, PICKUP }
    fun pretty() = buildString { append("type = $type\n"); values.forEach { (k,v) -> append("$k = $v\n") } }.trim()
    companion object {
        fun parse(raw: String): SpsPayload {
            val uri = runCatching { Uri.parse(raw.trim()) }.getOrElse { throw IllegalArgumentException("payload 格式错误") }
            if (uri.scheme != "sps") throw IllegalArgumentException("不支持的 SPS 类型")
            val type = when (uri.host) { "gate-qr" -> Type.GATE_QR; "gate-nfc" -> Type.GATE_NFC; "pickup" -> Type.PICKUP; else -> throw IllegalArgumentException("不支持的 SPS 类型") }
            val values = uri.queryParameterNames.associateWith { uri.getQueryParameter(it).orEmpty() }
            val required = when(type) {
                Type.GATE_QR -> listOf("gateway_code","reader_id","station_id","session_id","nonce","expires_at","signature")
                Type.GATE_NFC -> listOf("gateway_code","reader_id","station_id","gate_nfc_tag_id")
                Type.PICKUP -> listOf("tag_id","binding","token")
            }
            val missing = required.filter { values[it].isNullOrBlank() }
            if (missing.isNotEmpty()) throw IllegalArgumentException("payload 格式错误：缺少 ${missing.joinToString()}")
            return SpsPayload(type, raw.trim(), values)
        }
    }
}
