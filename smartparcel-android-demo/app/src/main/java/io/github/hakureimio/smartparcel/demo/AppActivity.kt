package io.github.hakureimio.smartparcel.demo

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.nfc.NdefMessage
import android.nfc.NdefRecord
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.Ndef
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Space
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.switchmaterial.SwitchMaterial
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.Executors

data class ParcelSummary(
    val parcelNo: String,
    val status: String,
    val shelfCode: String,
    val raw: JSONObject? = null,
)

class AppActivity : AppCompatActivity(), NfcAdapter.ReaderCallback {
    private enum class Page {
        ENTRY, LOGIN_USER, LOGIN_STAFF, USER_HOME, STAFF_HOME,
        USER_PARCELS, QR, NFC, HCE, SERVICE, SETTINGS,
    }

    private lateinit var cfg: Config
    private lateinit var sessions: SessionStore
    private lateinit var body: LinearLayout
    private lateinit var scroll: ScrollView
    private val io = Executors.newCachedThreadPool()
    private var page = Page.ENTRY
    private var payload: SpsPayload? = null
    private var pendingLink: String? = null
    private var result: String? = null
    private var lastScan: String? = null
    private var parcels: List<ParcelSummary> = emptyList()
    private var parcelsLoading = false
    private var parcelsLoaded = false
    private var parcelError: String? = null

    private val scanner = registerForActivityResult(ScanContract()) { scan ->
        scan.contents?.let { raw ->
            if (raw == lastScan) {
                toast("已识别该二维码，请勿重复扫描")
            } else {
                lastScan = raw
                page = Page.QR
                parse(raw, false)
                toast("识别成功")
            }
        }
    }
    private val cameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) launchScanner() else toast("相机权限被拒绝")
    }
    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (page == Page.HCE || page == Page.SERVICE) render()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cfg = Config(this)
        sessions = SessionStore(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor(IosUi.BACKGROUND))
        }
        scroll = ScrollView(this).apply { isFillViewport = true }
        body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(32))
        }
        scroll.addView(body)
        root.addView(scroll, LinearLayout.LayoutParams(-1, -1))
        setContentView(root)
        ContextCompat.registerReceiver(
            this,
            receiver,
            IntentFilter().apply {
                addAction(GateForegroundService.ACTION_STATUS)
                addAction(SmartParcelHostApduService.ACTION_HCE_LOG)
            },
            ContextCompat.RECEIVER_NOT_EXPORTED,
        )
        pendingLink = intent.dataString
        render()
        if (sessions.autoLogin && sessions.username.isNotBlank() && sessions.password.isNotBlank()) {
            val role = normalizedRole(sessions.preferredRole) ?: "client"
            page = loginPage(role)
            render()
            loginRequest(sessions.username, sessions.password, role, true, true)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        pendingLink = intent.dataString
        if (sessions.session == null) go(Page.ENTRY) else consumeLink()
    }

    override fun onResume() {
        super.onResume()
        NfcAdapter.getDefaultAdapter(this)?.enableReaderMode(
            this, this, NfcAdapter.FLAG_READER_NFC_A, null,
        )
    }

    override fun onPause() {
        NfcAdapter.getDefaultAdapter(this)?.disableReaderMode(this)
        super.onPause()
    }

    override fun onDestroy() {
        unregisterReceiver(receiver)
        io.shutdownNow()
        super.onDestroy()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        when (page) {
            Page.ENTRY -> super.onBackPressed()
            Page.LOGIN_USER, Page.LOGIN_STAFF -> go(Page.ENTRY)
            Page.USER_HOME, Page.STAFF_HOME -> super.onBackPressed()
            Page.USER_PARCELS, Page.QR -> go(Page.USER_HOME)
            Page.HCE, Page.SERVICE, Page.SETTINGS -> go(Page.STAFF_HOME)
            Page.NFC -> go(if (isStaffSession()) Page.STAFF_HOME else Page.USER_HOME)
        }
    }

    private fun render() {
        body.removeAllViews()
        when (page) {
            Page.ENTRY -> entry()
            Page.LOGIN_USER -> login("client")
            Page.LOGIN_STAFF -> login("staff")
            Page.USER_HOME -> userHome()
            Page.STAFF_HOME -> staffHome()
            Page.USER_PARCELS -> userParcels()
            Page.QR -> qr()
            Page.NFC -> nfc()
            Page.HCE -> hce()
            Page.SERVICE -> service()
            Page.SETTINGS -> settings()
        }
        scroll.scrollTo(0, 0)
        if (page !in listOf(Page.ENTRY, Page.LOGIN_USER, Page.LOGIN_STAFF) && pendingLink != null) {
            consumeLink()
        }
    }

    private fun entry() {
        heading("SmartParcelStation", "请选择要登录的应用端")
        feature("👤", "用户端登录", "查询我的包裹、扫码或 NFC 开门", IosUi.BLUE) {
            sessions.savePreferredRole("client")
            go(Page.LOGIN_USER)
        }
        gap(16)
        feature("🛠", "员工端登录", "网关、门禁服务、HCE 与 NFC 工具", IosUi.ORANGE) {
            sessions.savePreferredRole("staff")
            go(Page.LOGIN_STAFF)
        }
        result?.let { status(it, false) }
    }

    private fun login(role: String) {
        val title = if (role == "staff") "员工端登录" else "用户端登录"
        nav(title, "请输入对应类型的账号，登录端不可在此切换")
        val user = IosUi.input(this, "账号", sessions.username)
        val pass = IosUi.input(
            this, "密码", if (sessions.rememberPassword) sessions.password else "", true,
        )
        body.addView(card {
            addView(user)
            addView(IosUi.gap(this@AppActivity, 12))
            addView(pass)
        })
        gap(12)
        val remember = switch("保存密码", "仅保存在当前设备", sessions.rememberPassword)
        val auto = switch("自动登录", "开启会同时启用保存密码", sessions.autoLogin)
        auto.setOnCheckedChangeListener { _, checked ->
            if (checked && !remember.isChecked) remember.isChecked = true
        }
        remember.setOnCheckedChangeListener { _, checked ->
            if (!checked && auto.isChecked) auto.isChecked = false
        }
        body.addView(card {
            addView(remember)
            divider(this)
            addView(auto)
        })
        gap(20)
        primary("登录") {
            loginRequest(
                user.text.toString().trim(), pass.text.toString(), role,
                remember.isChecked, auto.isChecked,
            )
        }
        result?.let { status(it, false) }
    }

    private fun loginRequest(
        user: String,
        pass: String,
        requestedRole: String,
        remember: Boolean,
        auto: Boolean,
    ) {
        if (user.isBlank() || pass.isBlank()) return toast("请输入账号和密码")
        result = "正在登录…"
        render()
        io.execute {
            runCatching {
                val response = ApiClient.request(
                    "POST",
                    "${cfg.serverUrl}/auth/login",
                    body = JSONObject()
                        .put("role", requestedRole)
                        .put("username", user)
                        .put("password", pass),
                )
                JSONObject(response)
            }.onSuccess { json ->
                val actualRole = normalizedRole(json.optString("role"))
                runOnUiThread {
                    if (actualRole == null || actualRole != requestedRole) {
                        sessions.logout()
                        result = mismatchMessage(requestedRole)
                        page = loginPage(requestedRole)
                        render()
                        toast(result.orEmpty())
                    } else {
                        sessions.saveLogin(json, user, pass, actualRole, remember, auto)
                        result = null
                        page = homePage(actualRole)
                        render()
                        toast("登录成功")
                    }
                }
            }.onFailure { error ->
                runOnUiThread {
                    result = "登录失败：${error.message}"
                    page = loginPage(requestedRole)
                    render()
                }
            }
        }
    }

    private fun userHome() {
        val session = requireRole("client") ?: return
        heading("用户端", "${session.displayName.ifBlank { session.userId }}，欢迎回来")
        feature("📦", "我的包裹 / 待取包裹", "查看包裹号、当前状态与所在货架", IosUi.BLUE) {
            parcelsLoaded = false
            go(Page.USER_PARCELS)
        }
        gap(12)
        feature("▣", "扫码开门", "竖屏扫描门禁二维码", IosUi.BLUE) { go(Page.QR) }
        gap(12)
        feature("◉", "NFC 开门 / 取件", "读取 NTAG213 门禁或包裹标签", IosUi.GREEN) {
            go(Page.NFC)
        }
        gap(20)
        secondary("退出登录") { sessions.logout(); go(Page.ENTRY) }
    }

    private fun staffHome() {
        val session = requireRole("staff") ?: return
        heading("员工端", "${session.displayName.ifBlank { session.userId }} · 设备与门禁工作台")
        feature("⌁", "网关与门禁服务", "Gateway Health、auth-result 与前台轮询", IosUi.ORANGE) {
            go(Page.SERVICE)
        }
        gap(12)
        feature("◈", "HCE 手机门禁卡", "AID、凭据和最近 APDU", IosUi.BLUE) { go(Page.HCE) }
        gap(12)
        feature("◉", "NFC 工具", "读取 NTAG213 并检查 payload", IosUi.GREEN) { go(Page.NFC) }
        gap(12)
        feature("⚙", "设置", "Server、Gateway、Reader 与账号", IosUi.SECONDARY) {
            go(Page.SETTINGS)
        }
    }

    private fun userParcels() {
        if (requireRole("client") == null) return
        nav("我的包裹", "当前账号的待取包裹")
        when {
            parcelsLoading -> status("正在加载包裹…", true)
            parcelError != null -> {
                status("请求失败：$parcelError", false)
                gap(12)
                secondary("重新加载") { loadUserParcels() }
            }
            parcelsLoaded && parcels.isEmpty() -> status("暂无待取包裹", true)
            else -> parcels.forEachIndexed { index, parcel ->
                renderParcelCard(parcel)
                if (index != parcels.lastIndex) gap(12)
            }
        }
        if (!parcelsLoaded && !parcelsLoading) loadUserParcels()
    }

    private fun loadUserParcels() {
        val headers = ApiClient.bearerHeaders(sessions.session)
        if (headers.isEmpty()) return sessionExpired()
        parcelsLoading = true
        parcelError = null
        render()
        io.execute {
            runCatching {
                val array = ApiClient.requestJsonArray("${cfg.serverUrl}/users/me/parcels", headers)
                buildList {
                    for (index in 0 until array.length()) {
                        val item = array.optJSONObject(index) ?: continue
                        add(parseParcel(item))
                    }
                }
            }.onSuccess { loaded ->
                runOnUiThread {
                    parcels = loaded
                    parcelsLoading = false
                    parcelsLoaded = true
                    render()
                }
            }.onFailure { error ->
                runOnUiThread {
                    parcelsLoading = false
                    parcelsLoaded = true
                    if (error.message.orEmpty().contains("HTTP 401")) {
                        sessionExpired()
                    } else {
                        parcelError = error.message ?: "未知错误"
                        render()
                    }
                }
            }
        }
    }

    private fun parseParcel(json: JSONObject): ParcelSummary {
        return ParcelSummary(
            parcelNo = firstValue(json, "parcel_no", "tracking_no", "parcel_code", "parcel_id", "id")
                .ifBlank { "未提供" },
            status = firstValue(json, "status", "parcel_status").ifBlank { "UNKNOWN" },
            shelfCode = firstValue(json, "shelf_code", "shelf", "location", "rack_code")
                .ifBlank { "未提供" },
            raw = json,
        )
    }

    private fun renderParcelCard(parcel: ParcelSummary) {
        body.addView(card {
            addView(text(parcel.parcelNo, 20f, bold = true))
            addView(IosUi.gap(this@AppActivity, 12))
            addView(kv("当前状态", parcel.status))
            divider(this)
            addView(kv("所在货架", parcel.shelfCode))
            parcel.raw?.let { raw ->
                firstValue(raw, "station", "station_name", "station_id").takeIf { it.isNotBlank() }?.let {
                    divider(this)
                    addView(kv("站点", it))
                }
                firstValue(raw, "inbound_at", "created_at").takeIf { it.isNotBlank() }?.let {
                    divider(this)
                    addView(kv("入库时间", it))
                }
            }
        })
    }

    private fun qr() {
        if (requireRole("client") == null) return
        nav("扫码开门", "将二维码放入取景框内自动识别")
        body.addView(card {
            gravity = Gravity.CENTER
            addView(text("▣", 64f, IosUi.BLUE, true))
            addView(text("标准竖屏相机 · 自动识别", 15f, IosUi.SECONDARY).apply {
                gravity = Gravity.CENTER
            })
        })
        gap(16)
        primary("打开相机扫描") {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                launchScanner()
            } else {
                cameraPermission.launch(Manifest.permission.CAMERA)
            }
        }
        payloadBlock()
        if (payload?.type == SpsPayload.Type.GATE_QR) {
            secondary("提交门禁认证") { submit() }
        }
    }

    private fun nfc() {
        if (sessions.session == null) return sessionExpired()
        nav("NFC Reader", "将手机靠近 NTAG213 标签")
        val adapter = NfcAdapter.getDefaultAdapter(this)
        val message = when {
            adapter == null -> "此设备不支持 NFC"
            !adapter.isEnabled -> "NFC 未开启"
            else -> "Reader Mode 已开启，等待标签"
        }
        status(message, adapter?.isEnabled == true)
        if (adapter != null && !adapter.isEnabled) {
            secondary("打开 NFC 设置") { startActivity(Intent(Settings.ACTION_NFC_SETTINGS)) }
        }
        payloadBlock()
        payload?.let {
            secondary(if (it.type == SpsPayload.Type.PICKUP) "确认取件" else "手动提交认证") {
                submit()
            }
        }
    }

    private fun hce() {
        if (requireRole("staff") == null) return
        nav("HCE Card", "手机模拟 ISO-DEP/APDU 门禁凭据")
        body.addView(card {
            addView(kv("AID", cfg.aid)); divider(this)
            addView(kv("credential_type", "PHONE_HCE")); divider(this)
            addView(kv("credential_value", cfg.credential))
        })
        gap(14)
        val prefs = getSharedPreferences("hce_log", 0)
        body.addView(card {
            addView(text("最近 APDU", 17f, bold = true))
            addView(text(
                "请求\n${prefs.getString("request", "尚无")}\n\n响应\n${prefs.getString("response", "尚无")}",
                13f, IosUi.SECONDARY,
            ).apply { setTextIsSelectable(true) })
        })
    }

    private fun service() {
        if (requireRole("staff") == null) return
        nav("Gate Service", "网关健康、门禁结果与后台轮询")
        primary("测试 Gateway Health") { request("GET", "${cfg.gatewayUrl}/local/health") }
        gap(10)
        secondary("查询 auth-result") {
            request(
                "GET", "${cfg.gatewayUrl}/local/gate/auth-result?reader_id=${cfg.readerId}",
                ApiClient.readerHeaders(cfg),
            )
        }
        gap(10)
        secondary("启动前台服务") {
            if (android.os.Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            ) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 10)
            ContextCompat.startForegroundService(this, Intent(this, GateForegroundService::class.java))
            toast("服务已启动")
        }
        gap(10)
        danger("停止前台服务") {
            stopService(Intent(this, GateForegroundService::class.java))
            toast("服务已停止")
        }
        status(result ?: getSharedPreferences("service_log", 0).getString("last", "尚无").orEmpty(), true)
    }

    private fun settings() {
        if (requireRole("staff") == null) return
        nav("设置", "连接参数与本地账号管理")
        val values = linkedMapOf(
            "server_base_url" to cfg.serverUrl, "gateway_base_url" to cfg.gatewayUrl,
            "reader_id" to cfg.readerId, "reader_token" to cfg.readerToken,
            "demo_user_id" to cfg.userId, "HCE credential_value" to cfg.credential,
            "hce_aid" to cfg.aid,
        )
        val fields = values.mapValues { (key, value) -> IosUi.input(this, key, value, key == "reader_token") }
        section("连接与凭据")
        body.addView(card {
            fields.forEach { (key, field) ->
                addView(text(key, 12f, IosUi.SECONDARY)); addView(field)
                addView(IosUi.gap(this@AppActivity, 12))
            }
        })
        gap(12)
        primary("保存设置") {
            cfg.serverUrl = fields.getValue("server_base_url").text.toString()
            cfg.gatewayUrl = fields.getValue("gateway_base_url").text.toString()
            cfg.readerId = fields.getValue("reader_id").text.toString()
            cfg.readerToken = fields.getValue("reader_token").text.toString()
            cfg.userId = fields.getValue("demo_user_id").text.toString()
            cfg.credential = fields.getValue("HCE credential_value").text.toString()
            cfg.aid = fields.getValue("hce_aid").text.toString()
            toast("设置已保存")
        }
        gap(22)
        section("登录与隐私")
        val session = sessions.session
        val remember = switch("保存密码", "关闭会清除本机密码", sessions.rememberPassword)
        val auto = switch("自动登录", "开启会同时保存密码", sessions.autoLogin)
        auto.setOnCheckedChangeListener { _, checked ->
            sessions.autoLogin = checked
            if (checked && !remember.isChecked) remember.isChecked = true
        }
        remember.setOnCheckedChangeListener { _, checked ->
            sessions.rememberPassword = checked
            if (!checked && auto.isChecked) auto.isChecked = false
        }
        body.addView(card {
            addView(kv("当前角色", "员工端")); divider(this)
            addView(kv("当前用户", session?.displayName ?: "未登录")); divider(this)
            addView(remember); divider(this); addView(auto)
        })
        gap(12)
        secondary("退出登录") { sessions.logout(); go(Page.ENTRY) }
        gap(10)
        danger("清除本地登录信息") {
            sessions.clearCredentials(); go(Page.ENTRY); toast("本地登录信息已清除")
        }
    }

    override fun onTagDiscovered(tag: Tag) {
        val raw = runCatching {
            val ndef = Ndef.get(tag) ?: error("未检测到 NDEF")
            ndef.connect()
            val message = ndef.ndefMessage ?: error("未检测到 NDEF")
            ndef.close()
            decode(message)
        }.getOrElse {
            runOnUiThread { toast(it.message ?: "NFC 读取失败") }
            return
        }
        runOnUiThread { page = Page.NFC; parse(raw, true) }
    }

    private fun decode(message: NdefMessage): String {
        val record = message.records.firstOrNull() ?: error("未检测到 NDEF")
        return when {
            record.tnf == NdefRecord.TNF_WELL_KNOWN && record.type.contentEquals(NdefRecord.RTD_URI) -> {
                val prefixes = arrayOf("", "http://www.", "https://www.", "http://", "https://")
                prefixes.getOrElse(record.payload[0].toInt()) { "" } +
                    record.payload.copyOfRange(1, record.payload.size).toString(Charsets.UTF_8)
            }
            record.tnf == NdefRecord.TNF_WELL_KNOWN && record.type.contentEquals(NdefRecord.RTD_TEXT) -> {
                val languageLength = record.payload[0].toInt() and 0x3f
                record.payload.copyOfRange(1 + languageLength, record.payload.size).toString(Charsets.UTF_8)
            }
            else -> error("payload 格式错误")
        }
    }

    private fun consumeLink() {
        val raw = pendingLink ?: return
        pendingLink = null
        if (sessions.session == null) return go(Page.ENTRY)
        page = if (raw.startsWith("sps://gate-qr")) Page.QR else Page.NFC
        parse(raw, true)
    }

    private fun parse(raw: String, auto: Boolean) {
        runCatching { SpsPayload.parse(raw) }
            .onSuccess {
                payload = it
                render()
                if (auto && it.type == SpsPayload.Type.GATE_NFC) submit()
            }
            .onFailure { toast(it.message ?: "payload 格式错误") }
    }

    private fun submit() {
        val current = payload ?: return toast("请先读取 payload")
        val auth = ApiClient.bearerHeaders(sessions.session)
        if (auth.isEmpty()) return sessionExpired()
        when (current.type) {
            SpsPayload.Type.GATE_QR, SpsPayload.Type.GATE_NFC -> request(
                "POST",
                "${cfg.serverUrl}/gate/auth/${if (current.type == SpsPayload.Type.GATE_QR) "qr" else "nfc"}-confirm",
                auth, ApiClient.authJson(current), true,
            )
            SpsPayload.Type.PICKUP -> {
                val values = current.values
                request(
                    "POST", "${cfg.serverUrl}/pickup/nfc-confirm", auth,
                    JSONObject()
                        .put("event_id", "android_nfc_${System.currentTimeMillis()}")
                        .put("tag_id", values["tag_id"])
                        .put("pickup_binding_id", values["binding"])
                        .put("encrypted_token", values["token"]),
                    true,
                )
            }
        }
    }

    private fun request(
        method: String,
        url: String,
        headers: Map<String, String> = emptyMap(),
        json: JSONObject? = null,
        save: Boolean = false,
    ) {
        result = "请求中…"
        render()
        io.execute {
            val out = runCatching { ApiClient.request(method, url, headers, json) }
                .fold({ "成功：\n$it" }, { "失败：${it.message}" })
            if (save) getSharedPreferences("auth", 0).edit().putString("last", out).apply()
            runOnUiThread {
                if (out.contains("HTTP 401")) sessionExpired() else { result = out; render() }
            }
        }
    }

    private fun normalizedRole(value: String): String? {
        return when (value.trim().uppercase(Locale.ROOT)) {
            "CLIENT", "USER", "CUSTOMER", "END_USER" -> "client"
            "STAFF", "EMPLOYEE", "WORKER" -> "staff"
            else -> null
        }
    }

    private fun requireRole(expected: String): LoginSession? {
        val session = sessions.session ?: run { sessionExpired(); return null }
        if (normalizedRole(session.role) != expected) {
            sessions.logout()
            result = mismatchMessage(expected)
            page = Page.ENTRY
            render()
            return null
        }
        return session
    }

    private fun mismatchMessage(expected: String) = if (expected == "client") {
        "账号类型不匹配，请使用员工端入口登录"
    } else {
        "账号类型不匹配，请使用用户端入口登录"
    }

    private fun loginPage(role: String) = if (role == "staff") Page.LOGIN_STAFF else Page.LOGIN_USER
    private fun homePage(role: String) = if (role == "staff") Page.STAFF_HOME else Page.USER_HOME
    private fun isStaffSession() = normalizedRole(sessions.session?.role.orEmpty()) == "staff"
    private fun firstValue(json: JSONObject, vararg keys: String): String {
        for (key in keys) {
            if (json.has(key) && !json.isNull(key)) return json.optString(key)
        }
        return ""
    }

    private fun sessionExpired() {
        sessions.logout()
        result = "登录已失效，请重新登录"
        page = Page.ENTRY
        render()
    }

    private fun launchScanner() {
        scanner.launch(
            ScanOptions().setCaptureActivity(PortraitCaptureActivity::class.java)
                .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                .setPrompt("将二维码放入框内自动识别")
                .setBeepEnabled(false).setOrientationLocked(true),
        )
    }

    private fun go(target: Page) { page = target; result = null; render() }
    private fun dp(value: Int) = IosUi.dp(this, value)
    private fun gap(value: Int) { body.addView(IosUi.gap(this, value)) }
    private fun text(value: String, size: Float = 15f, color: String = IosUi.LABEL, bold: Boolean = false) =
        IosUi.label(this, value, size, color, bold)
    private fun card(content: LinearLayout.() -> Unit) = IosUi.card(this, content)
    private fun heading(title: String, subtitle: String) {
        body.addView(text(title, 31f, bold = true)); body.addView(text(subtitle, 15f, IosUi.SECONDARY)); gap(28)
    }
    private fun nav(title: String, subtitle: String) {
        body.addView(text("‹  返回", 16f, IosUi.BLUE, true).apply {
            setPadding(0, 0, 0, dp(14)); setOnClickListener { onBackPressed() }
        }); heading(title, subtitle)
    }
    private fun section(value: String) {
        body.addView(text(value.uppercase(), 12f, IosUi.SECONDARY, true).apply { setPadding(dp(4), 0, 0, dp(8)) })
    }
    private fun primary(value: String, action: (View) -> Unit) {
        body.addView(IosUi.button(this, value, IosUi.BLUE, action), LinearLayout.LayoutParams(-1, dp(52)))
    }
    private fun secondary(value: String, action: (View) -> Unit) {
        body.addView(IosUi.button(this, value, "#8E8E93", action), LinearLayout.LayoutParams(-1, dp(50)))
    }
    private fun danger(value: String, action: (View) -> Unit) {
        body.addView(IosUi.button(this, value, IosUi.RED, action), LinearLayout.LayoutParams(-1, dp(50)))
    }
    private fun feature(icon: String, title: String, desc: String, color: String, action: () -> Unit) {
        body.addView(card {
            setOnClickListener { action() }; isClickable = true
            addView(text(icon, 30f, color, true)); addView(text(title, 21f, bold = true))
            addView(text(desc, 14f, IosUi.SECONDARY)); addView(text("继续  ›", 14f, color, true).apply { gravity = Gravity.END })
        })
    }
    private fun payloadBlock() {
        val current = payload ?: return
        gap(18)
        body.addView(card {
            addView(text("识别结果", 17f, bold = true))
            addView(text("${current.raw}\n\n${current.pretty()}", 13f, IosUi.SECONDARY).apply { setTextIsSelectable(true) })
        })
        result?.let { status(it, it.startsWith("成功")) }
    }
    private fun status(value: String, good: Boolean) {
        gap(14)
        body.addView(card {
            addView(text(value, 14f, if (good) IosUi.GREEN else IosUi.RED, true).apply { setTextIsSelectable(true) })
        })
    }
    private fun kv(key: String, value: String) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        addView(text(key), LinearLayout.LayoutParams(0, -2, 1f))
        addView(text(value, 14f, IosUi.SECONDARY).apply { gravity = Gravity.END })
    }
    private fun divider(parent: LinearLayout) {
        parent.addView(View(this).apply { setBackgroundColor(Color.parseColor("#E5E5EA")) },
            LinearLayout.LayoutParams(-1, 1).apply { setMargins(0, dp(12), 0, dp(12)) })
    }
    private fun switch(title: String, subtitle: String, checked: Boolean) = SwitchMaterial(this).apply {
        text = "$title\n$subtitle"; textSize = 14f; isChecked = checked; setPadding(0, dp(5), 0, dp(5))
    }
    private fun toast(value: String) = runOnUiThread { Toast.makeText(this, value, Toast.LENGTH_LONG).show() }
}
