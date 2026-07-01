package io.github.hakureimio.smartparcel.demo

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object ApiClient {
    fun request(method: String, url: String, headers: Map<String,String> = emptyMap(), body: JSONObject? = null): String {
        val c = URL(url).openConnection() as HttpURLConnection
        c.requestMethod = method; c.connectTimeout = 5000; c.readTimeout = 5000
        headers.forEach { c.setRequestProperty(it.key, it.value) }
        if (body != null) { c.doOutput = true; c.setRequestProperty("Content-Type", "application/json"); c.outputStream.use { it.write(body.toString().toByteArray()) } }
        val code = c.responseCode
        val text = (if (code in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (code !in 200..299) throw IllegalStateException("HTTP $code: $text")
        return if (text.isBlank()) "HTTP $code" else text
    }
    fun readerHeaders(c: Config) = mapOf("X-Gate-Reader-Id" to c.readerId, "X-Gate-Reader-Token" to c.readerToken)
    fun authJson(p: SpsPayload): JSONObject = JSONObject().apply {
        p.values.forEach { (k,v) -> put(k, if (k == "station_id" || k == "expires_at") v.toLongOrNull() ?: v else v) }
        put("auth_method", if (p.type == SpsPayload.Type.GATE_QR) "GATE_QR" else "GATE_NFC_TAG")
    }
}
