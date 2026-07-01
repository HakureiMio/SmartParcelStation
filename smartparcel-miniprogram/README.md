# SmartParcel MiniProgram

## 用户门禁认证与 NFC 边界

用户端有三种门禁入口：扫描门禁屏幕二维码；手机读取门禁 NFC 标签；直接在门禁设备刷实体卡（该方式不经过小程序）。扫码或 NFC 请求提交后，小程序只显示“认证已提交，请查看门禁屏幕”，最终放行结果由 gateway 判断并由门禁屏幕显示。

门禁 NFC 标签用于请求开门，payload 为 `sps://gate-nfc`；包裹 NFC 标签用于确认取件，payload 为 `sps://pickup`。两者用途、字段和接口不同，不能混用。

安全边界：小程序只保存用户 Bearer token，不保存 `gateway_secret`、`reader_token` 或 `ADMIN_BOOTSTRAP_TOKEN`。

完整演示顺序、账号和 curl 等价请求见 [三种门禁认证端到端演示](../docs/demo_three_gate_auth_methods.md)。用户还可在小程序中查看包裹、报失卡，并通过手动按钮或包裹 NFC 标签确认取件。

### 微信 URL Link 门禁标签演示

可将微信生成的 `https://wxaurl.cn/xxxxxxxx` 直接写入 NTAG213/NTAG215。URL Link 目标页面为 `pages/gate-nfc-auth/gate-nfc-auth`，query 为：

```text
gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001
```

页面参数只描述门禁，不包含 `user_id` 或任何 secret。页面使用当前登录用户 token 自动提交；未登录时保存 pending 参数，登录后回到门禁页继续。URL Link 过期后需重新生成并重写标签。原有 `sps://gate-nfc` 小程序内读取模式继续保留。

## 1. 小程序定位

`smartparcel-miniprogram` 是 SmartParcelStation 的微信小程序，负责用户端和员工端交互。它不是业务主数据中心，也不保存高敏 secret。

## 2. 打开方式

```text
微信开发者工具
打开目录：smartparcel-miniprogram/
可使用测试号或无 AppID 模式进行基础页面预览
```

当前局域网 HTTP 适合毕业设计和开发调试；正式发布需要合法 HTTPS 域名、正式 AppID、微信登录和平台配置。

## 3. 当前页面清单

### 用户端

| 页面 | 说明 |
|---|---|
| `pages/index` | 角色选择首页 |
| `pages/login` | 登录（真实 server auth） |
| `pages/register` | 注册（预留） |
| `pages/forgot-password` | 忘记密码（预留） |
| `pages/user-home` | 用户首页 |
| `pages/user-parcels` | 待取包裹列表 |
| `pages/user-notifications` | 通知列表 |
| `pages/user-pickup-status` | 取件状态和门禁提示 |
| `pages/user-nfc-fast-pickup` | NFC 快速取件 |

### 员工端

| 页面 | 说明 |
|---|---|
| `pages/staff-home` | 员工工作台 |
| `pages/staff-gateway-register` | **网关注册 / 初始化（新增）** |
| `pages/gateway-status` | 网关状态检查 |
| `pages/staff-ble-tags` | BLE 标签管理 |
| `pages/staff-inbound` | 包裹入库登记 |
| `pages/staff-inbound-bind` | 入库并绑定标签 |
| `pages/staff-tag-bind` | 标签与包裹绑定 |
| `pages/staff-tag-nfc` | NFC 标签读取和写入 |
| `pages/staff-exception` | 标签异常上报 |

## 4. 员工端网关注册流程

新增完整的员工从 0 注册网关流程：

```text
员工登录
  -> 员工工作台
  -> 网关注册 / 初始化
  -> 检查服务器
  -> 申请绑定参数
  -> 连接网关热点
  -> 读取网关状态
  -> 写入绑定参数
  -> 等待网关握手
  -> 保存 local session
  -> 网关状态页
  -> BLE 标签管理
```

详细流程文档：`docs/miniprogram_gateway_registration_flow.md`

## 5. 员工 BLE 标签管理流程

### 前置条件

1. 完成网关注册 / 初始化，获得有效的 local session token。
2. Gateway 与标签位于同一局域网 / BLE 范围。
3. Gateway local API 正常运行。

### 操作流程

```text
1. 员工登录小程序。
2. 进入网关注册 / 初始化（如果尚未绑定）。
3. 完成网关绑定，保存 local session。
4. 进入 BLE 标签管理。
5. 检查网关状态（在线 / 已授权）。
6. 点击扫描附近标签。
7. 注册发现的标签到网关。
8. 在已注册标签列表选择标签进入详情。
9. 连接 → 蓝色亮灯/蜂鸣 → 停止 → 读取状态。
```

## 6. 配置说明

配置文件：`services/config.js`

```js
const CONFIG = {
  serverBaseUrl: 'https://api.example.com/api/v1',     // VPS server
  defaultGatewayProvisioningBaseUrl: 'http://192.168.4.1:19000',  // Gateway hotspot
  requestTimeoutMs: 12000,
  localSessionStorageKey: 'sps_gateway_local_session',
  allowInsecureLocalHttp: true,                         // Allow HTTP for gateway LAN
  allowInsecureServerHttpInDev: false                   // Require HTTPS for server
}
```

真机调试时必须根据实际网络环境修改 `serverBaseUrl` 和 gateway 地址。

## 7. 无 mock fallback

**所有 mock 占位逻辑已移除。** 请求失败不会回退到假数据：

- 登录失败 → 显示"服务器连接失败"，不会 mock 成功
- 网关不可达 → 显示具体错误，不会显示"演示模式"
- NFC 不可用 → 提示"请使用真机 NFC 或手动输入"
- BLE 扫描失败 → 显示真实错误原因
- Local session 缺失 → 提示先完成网关注册

历史 mock 数据已归档至 `docs/legacy/miniprogram_mock_data.md`。

## 8. 真机调试注意事项

- 微信开发者工具中需要按开发阶段要求处理合法域名校验。
- 手机连接网关热点时，gateway provisioning 地址为 `http://192.168.4.1:19000`。
- 手机和 gateway 在同一局域网时，gateway 地址为 gateway 的局域网 IP。
- Windows 防火墙需要允许 `19000` 端口入站。
- 小程序不保存 `server secret`、`gateway secret`、微信 `appsecret` 或数据库密码。

## 9. 安全说明

- gateway_secret：小程序**永不**保存、**永不**显示。
- registration_token：使用后立即丢弃，不持久化。
- local_session_token：短期存储，过期自动清除。
- debug 面板：所有敏感字段自动脱敏（redactSensitive）。
- server_base_url：生产环境强制 HTTPS。

## 10. 当前未完成能力

- 正式微信登录、token 刷新和生产级权限矩阵。
- 正式 HTTPS 域名发布。
- 用户端全部接口的真实 server 数据闭环。
- 门禁刷卡流程尚未完全迁移到 real BLE。
- NFC 真实读写尚未接入真机回调。
# 阶段 3：用户门禁认证与取件确认

用户首页提供“门禁认证、我的门禁卡、待取包裹、NFC 确认取件”四个入口。

- 实体卡或手机模拟卡直接在门禁读卡区使用，不经过小程序。
- `GATE_QR` 扫描 `sps://gate-qr?...`，使用用户 Bearer token 向 server 提交请求。
- `GATE_NFC_TAG` 读取门禁 NFC 标签 `sps://gate-nfc?...` 后向 server 提交请求。
- 小程序不显示“已放行”；最终结果以门禁屏幕和 gateway 本地判断为准。
- 包裹 NFC 取件读取的是 `sps://pickup?...` 包裹标签，不是门禁 NFC 标签。

NFC 使用微信真机 NDEF 回调。环境不支持、启动失败或超时时只显示失败信息，并提供手动
payload 输入；手动输入仍调用真实 server，不产生 mock 成功。

用户可以报失 ACTIVE 卡，补办新卡必须联系站点员工。补办完成后旧卡不可再开门。
门禁 QR/NFC 请求只使用用户 Bearer token，不使用 gateway local session、reader token，
也不保存 `gateway_secret`、`reader_token` 或 server secret。
