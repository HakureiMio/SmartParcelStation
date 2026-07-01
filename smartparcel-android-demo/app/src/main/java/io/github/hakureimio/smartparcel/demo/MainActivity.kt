package io.github.hakureimio.smartparcel.demo

import android.Manifest
import android.app.PendingIntent
import android.content.*
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.nfc.NdefMessage
import android.nfc.NdefRecord
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.Ndef
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.tabs.TabLayout
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import org.json.JSONObject
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity(), NfcAdapter.ReaderCallback {
    private lateinit var cfg: Config
    private lateinit var body: LinearLayout
    private val io = Executors.newCachedThreadPool()
    private var payload: SpsPayload? = null
    private var activeTab = 0
    private val scan = registerForActivityResult(ScanContract()) { if (it.contents != null) showPayload(it.contents, true) }
    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { if (it) launchScanner() else toast("相机权限被拒绝") }
    private val receiver = object : BroadcastReceiver() { override fun onReceive(c: Context?, i: Intent?) { render(activeTab) } }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state); cfg = Config(this)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        TextView(this).apply { text = "SmartParcelStation Android Demo"; textSize = 21f; setTypeface(null, Typeface.BOLD); setPadding(24,24,24,16); root.addView(this) }
        val tabs = TabLayout(this); listOf("Home","QR","NFC Reader","HCE Card","Gate Service","Settings").forEach { tabs.addTab(tabs.newTab().setText(it)) }; root.addView(tabs)
        body = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24,20,24,40) }
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1,0,1f)); setContentView(root)
        tabs.addOnTabSelectedListener(object: TabLayout.OnTabSelectedListener { override fun onTabSelected(t: TabLayout.Tab) { activeTab=t.position; render(activeTab) }; override fun onTabUnselected(t: TabLayout.Tab){}; override fun onTabReselected(t: TabLayout.Tab){} })
        ContextCompat.registerReceiver(this, receiver, IntentFilter().apply { addAction(GateForegroundService.ACTION_STATUS); addAction(SmartParcelHostApduService.ACTION_HCE_LOG) }, ContextCompat.RECEIVER_NOT_EXPORTED)
        handleIntent(intent); render(activeTab)
    }
    override fun onNewIntent(i: Intent) { super.onNewIntent(i); handleIntent(i) }
    private fun handleIntent(i: Intent) { i.dataString?.let { showPayload(it, true); activeTab = if(it.startsWith("sps://gate-qr")) 1 else 2 } }
    override fun onResume() { super.onResume(); val n=NfcAdapter.getDefaultAdapter(this); if(n!=null) n.enableReaderMode(this,this,NfcAdapter.FLAG_READER_NFC_A,null) }
    override fun onPause() { NfcAdapter.getDefaultAdapter(this)?.disableReaderMode(this); super.onPause() }
    override fun onDestroy() { unregisterReceiver(receiver); io.shutdownNow(); super.onDestroy() }

    override fun onTagDiscovered(tag: Tag) {
        val raw = runCatching { val n=Ndef.get(tag) ?: error("未检测到 NDEF"); n.connect(); val m=n.ndefMessage ?: error("未检测到 NDEF"); n.close(); decode(m) }.getOrElse { runOnUiThread { toast(it.message ?: "NFC 读取失败") }; return }
        runOnUiThread { activeTab=2; showPayload(raw,true) }
    }
    private fun decode(m: NdefMessage): String { val r=m.records.firstOrNull() ?: error("未检测到 NDEF"); return when { r.tnf==NdefRecord.TNF_WELL_KNOWN && r.type.contentEquals(NdefRecord.RTD_URI) -> { val prefixes=arrayOf("","http://www.","https://www.","http://","https://"); prefixes.getOrElse(r.payload[0].toInt()){""}+r.payload.copyOfRange(1,r.payload.size).toString(Charsets.UTF_8) }; r.tnf==NdefRecord.TNF_WELL_KNOWN && r.type.contentEquals(NdefRecord.RTD_TEXT) -> { val lang=r.payload[0].toInt() and 0x3f; r.payload.copyOfRange(1+lang,r.payload.size).toString(Charsets.UTF_8) }; else -> error("payload 格式错误") } }
    private fun render(tab: Int) { body.removeAllViews(); when(tab){0->home();1->qr();2->nfc();3->hce();4->service();else->settings()} }
    private fun home() { title("配置状态"); text("Server: ${cfg.serverUrl}\nGateway: ${cfg.gatewayUrl}\nReader: ${cfg.readerId}\n登录状态: Demo user ${cfg.userId}"); button("测试 Gateway Health") { call("GET", "${cfg.gatewayUrl}/local/health") }; text("最近门禁认证:\n${getSharedPreferences("auth",0).getString("last","尚无")}") }
    private fun qr() { title("QR 扫码认证"); button("扫描二维码") { if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED) launchScanner() else cameraPermission.launch(Manifest.permission.CAMERA) }; payloadView(); button("提交认证") { submitPayload() } }
    private fun nfc() { title("NFC Reader"); val a=NfcAdapter.getDefaultAdapter(this); text(if(a==null) "此设备不支持 NFC" else if(!a.isEnabled) "NFC 未开启" else "Reader Mode 已开启，请触碰 NTAG213"); if(a!=null&&!a.isEnabled) button("打开 NFC 设置") { startActivity(Intent(Settings.ACTION_NFC_SETTINGS)) }; payloadView(); button("手动提交") { submitPayload() }; text("pickup payload 会显示 tag_id / binding / token，并预留取件确认提交。") }
    private fun hce() { title("HCE Card"); text("AID: ${cfg.aid}\ncredential_type: PHONE_HCE\ncredential_value: ${cfg.credential}\nHCE 由系统调度，无需保持本页前台。"); val p=getSharedPreferences("hce_log",0); text("最近 APDU 请求:\n${p.getString("request","尚无")}\n\n最近 APDU 响应:\n${p.getString("response","尚无")}") }
    private fun service() { title("Gate Service"); button("启动前台服务") { if(android.os.Build.VERSION.SDK_INT>=33 && ContextCompat.checkSelfPermission(this,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS),10); ContextCompat.startForegroundService(this,Intent(this,GateForegroundService::class.java)); toast("服务已启动") }; button("停止前台服务") { stopService(Intent(this,GateForegroundService::class.java)); toast("服务已停止") }; button("查询 auth-result") { call("GET","${cfg.gatewayUrl}/local/gate/auth-result?reader_id=${cfg.readerId}",ApiClient.readerHeaders(cfg)) }; text("最近日志:\n${getSharedPreferences("service_log",0).getString("last","尚无")}") }
    private fun settings() { title("Settings（均保存在本机）"); val fields=listOf("server_base_url" to cfg.serverUrl,"gateway_base_url" to cfg.gatewayUrl,"reader_id" to cfg.readerId,"reader_token" to cfg.readerToken,"demo_user_id" to cfg.userId,"demo_hce_credential" to cfg.credential,"hce_aid" to cfg.aid).associate { (k,v)-> k to EditText(this).apply { hint=k; setText(v); body.addView(TextView(this@MainActivity).apply{text=k}); body.addView(this) } }; button("保存配置") { cfg.serverUrl=fields["server_base_url"]!!.text.toString();cfg.gatewayUrl=fields["gateway_base_url"]!!.text.toString();cfg.readerId=fields["reader_id"]!!.text.toString();cfg.readerToken=fields["reader_token"]!!.text.toString();cfg.userId=fields["demo_user_id"]!!.text.toString();cfg.credential=fields["demo_hce_credential"]!!.text.toString();cfg.aid=fields["hce_aid"]!!.text.toString();toast("已保存") } }
    private fun payloadView() { text("Raw:\n${payload?.raw ?: "尚未读取"}\n\n解析结果:\n${payload?.pretty() ?: "尚无"}") }
    private fun showPayload(raw:String, auto:Boolean) { runCatching { SpsPayload.parse(raw) }.onSuccess { payload=it; render(activeTab); if(auto && it.type==SpsPayload.Type.GATE_NFC) submitPayload() }.onFailure { toast(it.message ?: "payload 格式错误") } }
    private fun submitPayload() { val p=payload ?: return toast("请先读取 payload"); when(p.type){ SpsPayload.Type.GATE_QR,SpsPayload.Type.GATE_NFC -> call("POST","${cfg.serverUrl}/gate/auth/${if(p.type==SpsPayload.Type.GATE_QR) "qr" else "nfc"}-confirm",body=ApiClient.authJson(p),saveAuth=true); SpsPayload.Type.PICKUP -> { val v=p.values; val b=JSONObject().put("event_id","android_nfc_${System.currentTimeMillis()}").put("tag_id",v["tag_id"]).put("pickup_binding_id",v["binding"]).put("encrypted_token",v["token"]); call("POST","${cfg.serverUrl}/pickup/nfc-confirm",body=b,saveAuth=true) } } }
    private fun call(method:String,url:String,headers:Map<String,String> = emptyMap(),body:JSONObject?=null,saveAuth:Boolean=false) { text("请求中…"); io.execute { val result=runCatching{ApiClient.request(method,url,headers,body)}.fold({"成功:\n$it"},{"失败: ${it.message}"}); if(saveAuth)getSharedPreferences("auth",0).edit().putString("last",result).apply(); runOnUiThread{ text(result) } } }
    private fun launchScanner() = scan.launch(ScanOptions().setPrompt("扫描 sps://gate-qr 或 sps://gate-nfc").setBeepEnabled(false).setOrientationLocked(false))
    private fun title(s:String)=body.addView(TextView(this).apply{text=s;textSize=20f;setTypeface(null,Typeface.BOLD);setPadding(0,8,0,12)})
    private fun text(s:String)=body.addView(TextView(this).apply{text=s;textSize=15f;setTextIsSelectable(true);setPadding(0,8,0,16)})
    private fun button(s:String, f:(View)->Unit)=body.addView(Button(this).apply{text=s;setOnClickListener { f(it) }})
    private fun toast(s:String)=runOnUiThread{Toast.makeText(this,s,Toast.LENGTH_LONG).show()}
}
