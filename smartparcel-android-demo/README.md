# SmartParcelStation Android Demo

独立的 Kotlin Android 原生演示端（包名 `io.github.hakureimio.smartparcel.demo`），用于验证 QR、NTAG213/NDEF、Deep Link、HCE APDU 和 Gateway 前台轮询。`minSdk 23`，不会修改仓库内其他工程。

界面采用轻量 iOS 风格：浅灰背景、大标题、圆角卡片和系统蓝操作按钮。启动结构为：登录页 → 双入口主页 → 用户端/员工端功能菜单 → 具体工具页。原 QR、NFC、Deep Link、HCE、Gateway 和前台服务能力均保留。

## 登录与自动登录

登录调用现有 `POST /auth/login`，角色使用服务端兼容值 `client`（用户端）或 `staff`（员工端）。成功会保存 Bearer token、用户信息和角色；受保护的 QR/NFC/取件请求自动携带该 token，HTTP 401 会清除会话并回到登录页。

- “保存密码”将账号和密码写入 App 私有 SharedPreferences `login_state`；关闭时立即清除密码，并关闭自动登录。
- “自动登录”会联动开启保存密码。下次启动时使用保存的账号、密码和角色重新请求 `/auth/login`，而不是盲目复用旧 token。
- “退出登录”只移除当前 token/用户会话，可保留用户选择的账号密码；“清除本地登录信息”会清空整个 `login_state`。
- Demo 当前使用普通 SharedPreferences，适合受控演示环境；生产版本应迁移到 Android Keystore 支持的加密凭据存储。

## 导入、构建与安装

1. 用 Android Studio（JDK 17）打开本目录 `smartparcel-android-demo`，等待 Gradle Sync。
2. 连接已开启 USB 调试的 Android 手机，在设备下拉框选中手机，运行 `app`。
3. 也可执行 `./gradlew assembleDebug`，再执行 `adb install -r app/build/outputs/apk/debug/app-debug.apk`。
4. 首次扫码时允许相机权限；使用 Gate Service 时允许通知权限。Settings 的值仅写入本机 SharedPreferences，不应填入或提交生产密钥。

默认配置包括 `http://198.13.33.220:18000/api/v1`、`http://10.150.10.140:19000`、`GATE01` 和演示 token。所有值均可编辑。HTTP 仅限受控 Demo 局域网；正式上线必须使用 HTTPS，并采用安全的凭据存储与登录授权机制。

## 测试流程

1. 安装并打开 App，在 Settings 确认 `gateway_base_url = http://10.150.10.140:19000`，保存。
2. Home 点击“测试 Gateway Health”。Gate Service 页可启动/停止 8 秒间隔的前台轮询并查看 health、auth-result 和错误日志。
3. 向 NTAG213 写入 URI：`sps://gate-nfc?v=1&gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001`。可附加 Android Application Record，包名为 `io.github.hakureimio.smartparcel.demo`。
4. App 关闭或打开时触碰标签，确认 App 被唤起、NDEF 被解析并自动提交门禁 NFC 认证。NFC Reader 页也支持 NDEF URI 和 Text；未检测到 NDEF、格式错误、不支持类型及 NFC 未开启均会明确提示。
5. QR 页扫描 `sps://gate-qr?...`，确认七个参数被解析，然后提交。兼容现有小程序字段：`auth_method, gateway_code, reader_id, station_id, session_id, nonce, expires_at, signature`。
6. 取件标签格式为 `sps://pickup?v=1&tag_id=SPS-TAG-0001&binding=DEMO-BINDING-0001&token=demo-token-1`；App 显示三个字段，手动提交时映射到现有 `pickup/nfc-confirm` 的 `pickup_binding_id` 与 `encrypted_token`。
7. HCE Card 页确认 AID/凭据。用 PN532 发送 SELECT AID，检查响应中的 `PHONE_HCE_DEMO_USER_6`，再到 Gate Service 查询 GRANTED/DENIED。

Deep Link 可直接测试：

```bash
adb shell am start -a android.intent.action.VIEW -d "sps://gate-nfc?v=1&gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001"
adb shell am start -a android.intent.action.VIEW -d "sps://gate-qr?v=1&gateway_code=GW001&reader_id=GATE01&station_id=1&session_id=S1&nonce=N1&expires_at=4102444800&signature=demo"
```

`sps://` 适合 Demo 和已安装 App 的环境，不依赖微信 URL Link 权限。正式 HTTPS App Links 需要真实域名、HTTPS intent-filter 及域名下的 `.well-known/assetlinks.json`，本 Demo 不强依赖占位域名。

### UI 验收步骤

1. 首次启动选择“用户端”或“员工端”，输入真实测试账号；勾选保存密码和自动登录后登录。
2. 确认主页显示“用户端”“员工端”两张大卡片，并可分别进入扫码/NFC，以及 Gateway/HCE/Service 页面。
3. 从最近任务划掉 App 后重新打开；App 应重新调用登录接口并自动进入双入口主页。把密码改错或让账号失效后，应留在登录页并显示错误。
4. 用户端 → 扫码开门 → 打开相机扫描。扫码 Activity 在 Manifest 和代码中均固定 `portrait`，预览、取景框和提示文字应保持标准竖屏方向。
5. 连续扫描相同内容时，当前页面会拦截重复结果并提示“请勿重复扫描”。

## HCE / APDU

- AID：`F0010203040506`（系统静态注册；Settings 中修改后，若 AID 不同还需同步修改 `res/xml/apduservice.xml` 并重装）。
- SELECT：`00 A4 04 00 07 F0 01 02 03 04 05 06 00`。
- 成功响应：ASCII `SPSHCE1|credential_type=PHONE_HCE|credential_value=PHONE_HCE_DEMO_USER_6|user_id=6`，尾随 `90 00`；未知 APDU 返回 `6A 82`。
- 手机须支持 NFC/HCE；部分系统要求亮屏或解锁。HCE 是 ISO-DEP/APDU 智能卡模拟，不能也不会模拟固定实体 UID；gate-access/PN532 必须实现 SELECT AID 和 APDU 读取。

## 权限

- `INTERNET`：Server/Gateway 请求。
- `CAMERA`：QR 扫码，运行时授权。
- `NFC`：NDEF Reader Mode 与 HCE。
- `FOREGROUND_SERVICE`、`FOREGROUND_SERVICE_DATA_SYNC`：Android 8+ 前台健康检查。
- `POST_NOTIFICATIONS`：Android 13+ 常驻通知，运行时授权。
- HCE Service 由系统以 `android.permission.BIND_NFC_SERVICE` 保护，外部应用不能随意绑定。

## 已知限制

- Android HCE 不模拟固定 UID；AID 注册来自安装包 XML，运行时设置只用于 APDU 匹配/展示。
- 后台服务受厂商省电策略、网络和进程管理影响；它不是强实时守护进程。
- Server API 通常需要用户登录 Bearer token；本 Demo 未内置真实 token。若服务端要求登录，应在正式安全认证流程接入后再提交 QR/NFC/取件请求。
- Gateway 默认是局域网地址，手机必须能访问同一网络；明文 HTTP 仅为 Demo。
