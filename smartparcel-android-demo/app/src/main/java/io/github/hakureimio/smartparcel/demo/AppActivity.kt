package io.github.hakureimio.smartparcel.demo

import android.Manifest
import android.content.*
import android.content.pm.PackageManager
import android.graphics.Color
import android.nfc.*
import android.nfc.tech.Ndef
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.switchmaterial.SwitchMaterial
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import org.json.JSONObject
import java.util.concurrent.Executors

class AppActivity : AppCompatActivity(), NfcAdapter.ReaderCallback {
    private enum class Page { LOGIN, HOME, USER, STAFF, QR, NFC, HCE, SERVICE, SETTINGS }
    private lateinit var cfg: Config
    private lateinit var sessions: SessionStore
    private lateinit var body: LinearLayout
    private lateinit var scroll: ScrollView
    private val io = Executors.newCachedThreadPool()
    private var page = Page.LOGIN
    private var payload: SpsPayload? = null
    private var pendingLink: String? = null
    private var result: String? = null
    private var lastScan: String? = null
    private val scanner = registerForActivityResult(ScanContract()) { scan ->
        scan.contents?.let { raw -> if (raw == lastScan) toast("已识别该二维码，请勿重复扫描") else { lastScan = raw; page = Page.QR; parse(raw, false); toast("识别成功") } }
    }
    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { if (it) launchScanner() else toast("相机权限被拒绝") }
    private val receiver = object : BroadcastReceiver() { override fun onReceive(context: Context?, intent: Intent?) { if (page in listOf(Page.HCE, Page.SERVICE)) render() } }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState); cfg = Config(this); sessions = SessionStore(this)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor(IosUi.BACKGROUND)) }
        scroll = ScrollView(this).apply { isFillViewport = true }
        body = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(18), dp(20), dp(32)) }
        scroll.addView(body); root.addView(scroll, LinearLayout.LayoutParams(-1, -1)); setContentView(root)
        ContextCompat.registerReceiver(this, receiver, IntentFilter().apply { addAction(GateForegroundService.ACTION_STATUS); addAction(SmartParcelHostApduService.ACTION_HCE_LOG) }, ContextCompat.RECEIVER_NOT_EXPORTED)
        pendingLink = intent.dataString
        page = Page.LOGIN
        render()
        if (sessions.autoLogin && sessions.username.isNotBlank() && sessions.password.isNotBlank()) {
            loginRequest(sessions.username, sessions.password, sessions.preferredRole, true, true)
        }
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); pendingLink = intent.dataString; if (sessions.session == null) go(Page.LOGIN) else consumeLink() }
    override fun onResume() { super.onResume(); NfcAdapter.getDefaultAdapter(this)?.enableReaderMode(this, this, NfcAdapter.FLAG_READER_NFC_A, null) }
    override fun onPause() { NfcAdapter.getDefaultAdapter(this)?.disableReaderMode(this); super.onPause() }
    override fun onDestroy() { unregisterReceiver(receiver); io.shutdownNow(); super.onDestroy() }
    @Deprecated("Deprecated in Java") override fun onBackPressed() { when(page) { Page.LOGIN, Page.HOME -> super.onBackPressed(); Page.USER, Page.STAFF -> go(Page.HOME); Page.QR, Page.NFC -> go(Page.USER); else -> go(Page.STAFF) } }

    private fun render() {
        body.removeAllViews()
        when(page) { Page.LOGIN -> login(); Page.HOME -> home(); Page.USER -> userMenu(); Page.STAFF -> staffMenu(); Page.QR -> qr(); Page.NFC -> nfc(); Page.HCE -> hce(); Page.SERVICE -> service(); Page.SETTINGS -> settings() }
        scroll.scrollTo(0, 0)
        if (page != Page.LOGIN && pendingLink != null) consumeLink()
    }

    private fun login() {
        heading("SmartParcelStation", "欢迎回来，请选择身份并登录")
        var role = sessions.preferredRole.ifBlank { "client" }
        val client = roleButton("用户端", role == "client"); val staff = roleButton("员工端", role == "staff")
        fun select(value:String) { role=value; styleRole(client,value=="client"); styleRole(staff,value=="staff") }
        client.setOnClickListener { select("client") }; staff.setOnClickListener { select("staff") }
        body.addView(LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL; addView(client,LinearLayout.LayoutParams(0,dp(44),1f)); addView(Space(this@AppActivity),LinearLayout.LayoutParams(dp(10),1)); addView(staff,LinearLayout.LayoutParams(0,dp(44),1f)) }); gap(20)
        val user=IosUi.input(this,"账号",sessions.username); val pass=IosUi.input(this,"密码",if(sessions.rememberPassword)sessions.password else "",true)
        body.addView(card { addView(user); addView(IosUi.gap(this@AppActivity,12)); addView(pass) }); gap(12)
        val remember=switch("保存密码","仅保存在当前设备",sessions.rememberPassword); val auto=switch("自动登录","开启会同时启用保存密码",sessions.autoLogin)
        auto.setOnCheckedChangeListener { _,v -> if(v&&!remember.isChecked)remember.isChecked=true }; remember.setOnCheckedChangeListener { _,v -> if(!v&&auto.isChecked)auto.isChecked=false }
        body.addView(card { addView(remember); divider(this); addView(auto) }); gap(20)
        primary("登录") { loginRequest(user.text.toString().trim(),pass.text.toString(),role,remember.isChecked,auto.isChecked) }
        result?.let { status(it,false) }
    }
    private fun loginRequest(user:String, pass:String, role:String, remember:Boolean, auto:Boolean) {
        if(user.isBlank()||pass.isBlank())return toast("请输入账号和密码")
        result="正在登录…"; render()
        io.execute { runCatching { ApiClient.request("POST","${cfg.serverUrl}/auth/login",body=JSONObject().put("role",role).put("username",user).put("password",pass)) }
            .onSuccess { sessions.saveLogin(JSONObject(it),user,pass,role,remember,auto); runOnUiThread { result=null; page=Page.HOME; render(); toast("登录成功") } }
            .onFailure { runOnUiThread { result="登录失败：${it.message}"; render() } } }
    }

    private fun home() {
        val session=sessions.session ?: return go(Page.LOGIN)
        heading("SmartParcelStation","${session.displayName.ifBlank{session.userId}} · ${if(session.role=="staff")"员工" else "用户"}")
        feature("👤","用户端","扫码开门、NFC 开门与包裹取件",IosUi.BLUE){go(Page.USER)}; gap(14)
        feature("🛠","员工端","网关状态、门禁服务与 HCE 调试",IosUi.ORANGE){go(Page.STAFF)}; gap(20)
        section("当前连接"); body.addView(card { addView(text("Server\n${cfg.serverUrl}\n\nGateway\n${cfg.gatewayUrl}",14f,IosUi.SECONDARY)) })
    }
    private fun userMenu() { nav("用户端","扫码、碰一碰，轻松完成门禁与取件"); feature("▣","扫码开门","竖屏扫描门禁二维码",IosUi.BLUE){go(Page.QR)}; gap(12); feature("◉","NFC 开门 / 取件","读取 NTAG213 门禁或包裹标签",IosUi.GREEN){go(Page.NFC)}; gap(12); feature("⚙","个人与设置","账号、连接参数与退出登录",IosUi.SECONDARY){go(Page.SETTINGS)} }
    private fun staffMenu() { nav("员工端","集中查看门禁与设备调试能力"); feature("⌁","网关与门禁服务","健康检查、认证结果与后台轮询",IosUi.ORANGE){go(Page.SERVICE)}; gap(12); feature("◈","HCE 手机门禁卡","AID、凭据和最近 APDU",IosUi.BLUE){go(Page.HCE)}; gap(12); feature("◉","NFC 工具","读取 NTAG213 并检查 payload",IosUi.GREEN){go(Page.NFC)}; gap(12); feature("⚙","系统设置","Server、Gateway、Reader 与账号",IosUi.SECONDARY){go(Page.SETTINGS)} }

    private fun qr() { nav("扫码开门","将二维码放入取景框内自动识别"); body.addView(card { gravity=Gravity.CENTER; addView(text("▣",64f,IosUi.BLUE,true)); addView(text("标准竖屏相机 · 自动识别",15f,IosUi.SECONDARY).apply{gravity=Gravity.CENTER}) }); gap(16); primary("打开相机扫描"){if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED)launchScanner() else cameraPermission.launch(Manifest.permission.CAMERA)}; payloadBlock(); if(payload?.type==SpsPayload.Type.GATE_QR) secondary("提交门禁认证"){submit()} }
    private fun nfc() { nav("NFC Reader","将手机靠近 NTAG213 标签"); val a=NfcAdapter.getDefaultAdapter(this); val message=if(a==null)"此设备不支持 NFC" else if(!a.isEnabled)"NFC 未开启" else "Reader Mode 已开启，等待标签"; status(message,a?.isEnabled==true); if(a!=null&&!a.isEnabled)secondary("打开 NFC 设置"){startActivity(Intent(Settings.ACTION_NFC_SETTINGS))}; payloadBlock(); payload?.let{secondary(if(it.type==SpsPayload.Type.PICKUP)"确认取件" else "手动提交认证"){submit()}} }
    private fun hce() { nav("HCE Card","手机模拟 ISO-DEP/APDU 门禁凭据"); body.addView(card { addView(kv("AID",cfg.aid)); divider(this); addView(kv("credential_type","PHONE_HCE")); divider(this); addView(kv("credential_value",cfg.credential)) }); gap(14); val p=getSharedPreferences("hce_log",0); body.addView(card { addView(text("最近 APDU",17f,bold=true)); addView(text("请求\n${p.getString("request","尚无")}\n\n响应\n${p.getString("response","尚无")}",13f,IosUi.SECONDARY).apply{setTextIsSelectable(true)}) }) }
    private fun service() { nav("Gate Service","网关健康、门禁结果与后台轮询"); primary("测试 Gateway Health"){request("GET","${cfg.gatewayUrl}/local/health")}; gap(10); secondary("查询 auth-result"){request("GET","${cfg.gatewayUrl}/local/gate/auth-result?reader_id=${cfg.readerId}",ApiClient.readerHeaders(cfg))}; gap(10); secondary("启动前台服务"){if(android.os.Build.VERSION.SDK_INT>=33&&ContextCompat.checkSelfPermission(this,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS),10);ContextCompat.startForegroundService(this,Intent(this,GateForegroundService::class.java));toast("服务已启动")}; gap(10); danger("停止前台服务"){stopService(Intent(this,GateForegroundService::class.java));toast("服务已停止")}; status(result?:getSharedPreferences("service_log",0).getString("last","尚无").orEmpty(),true) }

    private fun settings() {
        nav("设置","连接参数与本地账号管理")
        val values=linkedMapOf("server_base_url" to cfg.serverUrl,"gateway_base_url" to cfg.gatewayUrl,"reader_id" to cfg.readerId,"reader_token" to cfg.readerToken,"demo_user_id" to cfg.userId,"HCE credential_value" to cfg.credential,"hce_aid" to cfg.aid)
        val fields=values.mapValues{(k,v)->IosUi.input(this,k,v,k=="reader_token")}; section("连接与凭据")
        body.addView(card { fields.forEach{(k,v)->addView(text(k,12f,IosUi.SECONDARY));addView(v);addView(IosUi.gap(this@AppActivity,12))} }); gap(12)
        primary("保存设置"){cfg.serverUrl=fields["server_base_url"]!!.text.toString();cfg.gatewayUrl=fields["gateway_base_url"]!!.text.toString();cfg.readerId=fields["reader_id"]!!.text.toString();cfg.readerToken=fields["reader_token"]!!.text.toString();cfg.userId=fields["demo_user_id"]!!.text.toString();cfg.credential=fields["HCE credential_value"]!!.text.toString();cfg.aid=fields["hce_aid"]!!.text.toString();toast("设置已保存")}; gap(22); section("登录与隐私")
        val s=sessions.session
        val remember=switch("保存密码","关闭会清除本机密码",sessions.rememberPassword)
        val auto=switch("自动登录","开启会同时保存密码",sessions.autoLogin)
        auto.setOnCheckedChangeListener { _,v -> sessions.autoLogin=v; if(v&&!remember.isChecked)remember.isChecked=true }
        remember.setOnCheckedChangeListener { _,v -> sessions.rememberPassword=v; if(!v&&auto.isChecked)auto.isChecked=false }
        body.addView(card { addView(kv("当前角色",if(s?.role=="staff")"员工端" else "用户端"));divider(this);addView(kv("当前用户",s?.displayName?:"未登录"));divider(this);addView(remember);divider(this);addView(auto) }); gap(12)
        secondary("退出登录"){sessions.logout();go(Page.LOGIN)};gap(10);danger("清除本地登录信息"){sessions.clearCredentials();go(Page.LOGIN);toast("本地登录信息已清除")}
    }

    override fun onTagDiscovered(tag:Tag) { val raw=runCatching{val n=Ndef.get(tag)?:error("未检测到 NDEF");n.connect();val m=n.ndefMessage?:error("未检测到 NDEF");n.close();decode(m)}.getOrElse{runOnUiThread{toast(it.message?:"NFC 读取失败")};return};runOnUiThread{page=Page.NFC;parse(raw,true)} }
    private fun decode(m:NdefMessage):String { val r=m.records.firstOrNull()?:error("未检测到 NDEF");return when{r.tnf==NdefRecord.TNF_WELL_KNOWN&&r.type.contentEquals(NdefRecord.RTD_URI)->{val p=arrayOf("","http://www.","https://www.","http://","https://");p.getOrElse(r.payload[0].toInt()){ "" }+r.payload.copyOfRange(1,r.payload.size).toString(Charsets.UTF_8)};r.tnf==NdefRecord.TNF_WELL_KNOWN&&r.type.contentEquals(NdefRecord.RTD_TEXT)->{val l=r.payload[0].toInt()and 0x3f;r.payload.copyOfRange(1+l,r.payload.size).toString(Charsets.UTF_8)};else->error("payload 格式错误")} }
    private fun consumeLink(){val raw=pendingLink?:return;pendingLink=null;page=if(raw.startsWith("sps://gate-qr"))Page.QR else Page.NFC;parse(raw,true)}
    private fun parse(raw:String,auto:Boolean){runCatching{SpsPayload.parse(raw)}.onSuccess{payload=it;render();if(auto&&it.type==SpsPayload.Type.GATE_NFC)submit()}.onFailure{toast(it.message?:"payload 格式错误")}}
    private fun submit(){val p=payload?:return toast("请先读取 payload");val auth=ApiClient.bearerHeaders(sessions.session);if(auth.isEmpty())return go(Page.LOGIN);when(p.type){SpsPayload.Type.GATE_QR,SpsPayload.Type.GATE_NFC->request("POST","${cfg.serverUrl}/gate/auth/${if(p.type==SpsPayload.Type.GATE_QR)"qr" else "nfc"}-confirm",auth,ApiClient.authJson(p),true);SpsPayload.Type.PICKUP->{val v=p.values;request("POST","${cfg.serverUrl}/pickup/nfc-confirm",auth,JSONObject().put("event_id","android_nfc_${System.currentTimeMillis()}").put("tag_id",v["tag_id"]).put("pickup_binding_id",v["binding"]).put("encrypted_token",v["token"]),true)}}}
    private fun request(method:String,url:String,headers:Map<String,String> = emptyMap(),json:JSONObject?=null,save:Boolean=false){result="请求中…";render();io.execute{val out=runCatching{ApiClient.request(method,url,headers,json)}.fold({"成功：\n$it"},{"失败：${it.message}"});if(save)getSharedPreferences("auth",0).edit().putString("last",out).apply();runOnUiThread{if(out.contains("HTTP 401")){sessions.logout();result="登录已失效，请重新登录";page=Page.LOGIN}else result=out;render()}}}
    private fun launchScanner(){scanner.launch(ScanOptions().setCaptureActivity(PortraitCaptureActivity::class.java).setDesiredBarcodeFormats(ScanOptions.QR_CODE).setPrompt("将二维码放入框内自动识别").setBeepEnabled(false).setOrientationLocked(true))}

    private fun go(p:Page){page=p;result=null;render()}; private fun dp(v:Int)=IosUi.dp(this,v); private fun gap(v:Int){body.addView(IosUi.gap(this,v))}
    private fun text(v:String,size:Float=15f,color:String=IosUi.LABEL,bold:Boolean=false)=IosUi.label(this,v,size,color,bold)
    private fun card(content:LinearLayout.()->Unit)=IosUi.card(this,content)
    private fun heading(title:String,subtitle:String){body.addView(text(title,31f,bold=true));body.addView(text(subtitle,15f,IosUi.SECONDARY));gap(28)}
    private fun nav(title:String,subtitle:String){body.addView(text("‹  返回",16f,IosUi.BLUE,true).apply{setPadding(0,0,0,dp(14));setOnClickListener{onBackPressed()}});heading(title,subtitle)}
    private fun section(v:String){body.addView(text(v.uppercase(),12f,IosUi.SECONDARY,true).apply{setPadding(dp(4),0,0,dp(8))})}
    private fun primary(v:String,a:(View)->Unit){body.addView(IosUi.button(this,v,IosUi.BLUE,a),LinearLayout.LayoutParams(-1,dp(52)))};private fun secondary(v:String,a:(View)->Unit){body.addView(IosUi.button(this,v,"#8E8E93",a),LinearLayout.LayoutParams(-1,dp(50)))};private fun danger(v:String,a:(View)->Unit){body.addView(IosUi.button(this,v,IosUi.RED,a),LinearLayout.LayoutParams(-1,dp(50)))}
    private fun feature(icon:String,title:String,desc:String,color:String,a:()->Unit){body.addView(card{setOnClickListener{a()};isClickable=true;addView(text(icon,30f,color,true));addView(text(title,21f,bold=true));addView(text(desc,14f,IosUi.SECONDARY));addView(text("继续  ›",14f,color,true).apply{gravity=Gravity.END})})}
    private fun payloadBlock(){val p=payload?:return;gap(18);body.addView(card{addView(text("识别结果",17f,bold=true));addView(text("${p.raw}\n\n${p.pretty()}",13f,IosUi.SECONDARY).apply{setTextIsSelectable(true)})});result?.let{status(it,it.startsWith("成功"))}}
    private fun status(v:String,good:Boolean){gap(14);body.addView(card{addView(text(v,14f,if(good)IosUi.GREEN else IosUi.RED,true).apply{setTextIsSelectable(true)})})}
    private fun kv(k:String,v:String)=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL;addView(text(k),LinearLayout.LayoutParams(0,-2,1f));addView(text(v,14f,IosUi.SECONDARY).apply{gravity=Gravity.END})}
    private fun divider(p:LinearLayout){p.addView(View(this).apply{setBackgroundColor(Color.parseColor("#E5E5EA"))},LinearLayout.LayoutParams(-1,1).apply{setMargins(0,dp(12),0,dp(12))})}
    private fun switch(t:String,s:String,c:Boolean)=SwitchMaterial(this).apply{text="$t\n$s";textSize=14f;isChecked=c;setPadding(0,dp(5),0,dp(5))}
    private fun roleButton(t:String,s:Boolean)=Button(this).apply{text=t;isAllCaps=false;textSize=15f;styleRole(this,s)}
    private fun styleRole(b:Button,s:Boolean){b.setTextColor(Color.parseColor(if(s)"#FFFFFF" else IosUi.BLUE));b.background=IosUi.rounded(if(s)IosUi.BLUE else "#FFFFFF",dp(12),IosUi.BLUE)}
    private fun toast(v:String)=runOnUiThread{Toast.makeText(this,v,Toast.LENGTH_LONG).show()}
}
