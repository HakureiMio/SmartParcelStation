package io.github.hakureimio.smartparcel.demo

import android.content.Context

class Config(context: Context) {
    private val p = context.getSharedPreferences("demo_config", Context.MODE_PRIVATE)
    var serverUrl: String get() = p.getString("server_url", "http://198.13.33.220:18000/api/v1")!!; set(v) = p.edit().putString("server_url", v.trimEnd('/')).apply()
    var gatewayUrl: String get() = p.getString("gateway_url", "http://10.150.10.140:19000")!!; set(v) = p.edit().putString("gateway_url", v.trimEnd('/')).apply()
    var readerId: String get() = p.getString("reader_id", "GATE01")!!; set(v) = p.edit().putString("reader_id", v).apply()
    var readerToken: String get() = p.getString("reader_token", "change-this-reader-token")!!; set(v) = p.edit().putString("reader_token", v).apply()
    var userId: String get() = p.getString("user_id", "6")!!; set(v) = p.edit().putString("user_id", v).apply()
    var credential: String get() = p.getString("credential", "PHONE_HCE_DEMO_USER_6")!!; set(v) = p.edit().putString("credential", v).apply()
    var aid: String get() = p.getString("aid", "F0010203040506")!!; set(v) = p.edit().putString("aid", v.uppercase()).apply()
}
