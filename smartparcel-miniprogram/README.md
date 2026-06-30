# SmartParcel MiniProgram

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
