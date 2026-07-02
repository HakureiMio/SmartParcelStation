package io.github.hakureimio.smartparcel.demo

import android.content.Context
import org.json.JSONObject

data class LoginSession(
    val token: String,
    val userId: String,
    val role: String,
    val displayName: String,
    val stationId: String?
)

class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("login_state", Context.MODE_PRIVATE)

    var rememberPassword: Boolean
        get() = prefs.getBoolean("remember_password", false)
        set(value) {
            prefs.edit().putBoolean("remember_password", value).apply()
            if (!value) prefs.edit().remove("password").putBoolean("auto_login", false).apply()
        }
    var autoLogin: Boolean
        get() = prefs.getBoolean("auto_login", false)
        set(value) {
            prefs.edit().putBoolean("auto_login", value).apply()
            if (value) prefs.edit().putBoolean("remember_password", true).apply()
        }
    val username get() = prefs.getString("username", "").orEmpty()
    val password get() = prefs.getString("password", "").orEmpty()
    val preferredRole get() = prefs.getString("preferred_role", "client").orEmpty()
    val session: LoginSession?
        get() {
            val token = prefs.getString("token", "").orEmpty()
            if (token.isBlank()) return null
            return LoginSession(token, prefs.getString("user_id", "").orEmpty(), prefs.getString("role", "client").orEmpty(), prefs.getString("display_name", "").orEmpty(), prefs.getString("station_id", null))
        }

    fun saveLogin(json: JSONObject, username: String, password: String, role: String, remember: Boolean, auto: Boolean) {
        prefs.edit()
            .putString("token", json.getString("token"))
            .putString("user_id", json.optString("user_id"))
            .putString("role", json.optString("role", role))
            .putString("display_name", json.optString("display_name", username))
            .putString("station_id", json.optString("station_id").takeIf { it.isNotBlank() })
            .putString("username", username)
            .putString("preferred_role", role)
            .putBoolean("remember_password", remember || auto)
            .putBoolean("auto_login", auto)
            .apply()
        if (remember || auto) prefs.edit().putString("password", password).apply() else prefs.edit().remove("password").apply()
    }

    fun savePreferredRole(role: String) =
        prefs.edit().putString("preferred_role", role).apply()

    fun logout() = prefs.edit().remove("token").remove("user_id").remove("role").remove("display_name").remove("station_id").apply()
    fun clearCredentials() = prefs.edit().clear().apply()
}
