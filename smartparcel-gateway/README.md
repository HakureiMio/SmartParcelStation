# SmartParcel Gateway

SmartParcel 站点本地网关 —— 负责 BLE 标签控制、本地 SQLite 缓存、
server 同步、门禁认证和员工小程序本地 API。

## 1. 网关职责

- 本地 SQLite 数据库（标签主数据、包裹缓存、审计日志）
- 真实 BLE 标签扫描、连接、唤醒、停止和状态读取（`bleak`）
- 本地取件认证和门禁读卡
- 与 `smartparcel-server` 的 HMAC-SHA256 签名通信（heartbeat、sync-push、sync-pull）
- 开机热点配网和 provisioning API
- 本地 API 安全认证（Bearer token + 防重放）

## 2. 部署流程

### 2.1 安装

```bash
cd smartparcel-gateway
bash deploy/install.sh
```

### 2.2 配置 .env

编辑 `.env`，至少设置：

```env
GATEWAY_DEVICE_ID=GWDEV-0001
GATEWAY_SERIAL=SPS-GW-0001
WIFI_AP_PASSWORD=your-secure-password-8chars
SQLITE_PATH=./data/gateway.db
```

**不要**手动设置 `GATEWAY_SECRET` —— 它由 server 在绑定时下发。

### 2.3 初始化数据库

```bash
python -m gateway.main init-db
```

### 2.4 查看状态

```bash
python -m gateway.main status
```

### 2.5 启动网关

自动模式（推荐）：

```bash
python -m gateway.main run
```

- UNBOUND 状态：自动开启 Wi-Fi 热点 + provisioning API，等待小程序绑定。
- BOUND 状态：校验密钥、发送 heartbeat、启动 local API + 同步循环 + MQTT。

手动 provisioning 模式：

```bash
python -m gateway.main provisioning
```

## 3. 绑定流程

完整流程见 [`docs/gateway_provisioning_flow.md`](../docs/gateway_provisioning_flow.md)。

```
1. 网关开机 → 检查绑定状态 → UNBOUND → 开启热点 SmartParcel-GW-XXXX
2. 员工手机连接热点
3. 小程序读取网关 status: GET http://192.168.4.1:19000/local/provisioning/status
4. 小程序向 VPS server 提交注册申请（gateway_device_id, gateway_serial, station_id, staff token）
5. Server 返回绑定参数（registration_token, server_base_url, gateway_code, station_id, mqtt 配置）
6. 小程序调用: POST http://192.168.4.1:19000/local/provisioning/bind
7. 网关调用 server: POST /api/v1/gateways/bootstrap/activate
8. Server 返回长期 gateway_secret
9. 网关保存配置、发送 heartbeat
10. heartbeat 成功 → 状态切换为 BOUND → ONLINE
11. 关闭开放式 provisioning API，启动完整 runtime
```

### 网络说明

- 如果网关热点有外网上联（以太网/4G/第二 Wi-Fi + NAT），小程序可直接通过热点访问 server。
- 如果热点无外网，小程序应先通过蜂窝网络从 server 获取绑定参数，再连接热点写入网关。

## 4. 配置参考

完整配置项见 `.env.example`。

关键配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `GATEWAY_DEVICE_ID` | 网关设备 ID | 无 |
| `GATEWAY_SERIAL` | 网关序列号 | 无 |
| `BINDING_STATUS` | 绑定状态 | UNBOUND |
| `SERVER_BASE_URL` | Server API 地址 | 无 |
| `BLE_BACKEND` | BLE 后端（仅 `real`） | real |
| `WIFI_AP_SSID_PREFIX` | 热点 SSID 前缀 | SmartParcel-GW |
| `WIFI_AP_ADDRESS` | 热点 IP | 192.168.4.1 |
| `PROVISIONING_ENABLED` | 是否允许配网 | true |
| `LOCAL_API_TOKEN_TTL_SECONDS` | 本地 token 有效期 | 3600 |
| `ALLOW_DEV_HTTP` | 允许开发环境 HTTP | false |
| `ALLOW_UNSAFE_DEV_AUTOREGISTER` | 允许不安全自动注册 | false |

## 5. Local API

### 5.1 公开接口（无需认证）

```
GET /local/health
GET /local/provisioning/status
POST /local/provisioning/bind
POST /local/provisioning/verify
```

### 5.2 业务接口（需要 Bearer token）

```
POST /local/gate/access-card
POST /local/tags/scan
POST /local/tags/register-from-ble
GET  /local/tags
GET  /local/tags/{tag_id}
POST /local/tags/{tag_id}/connect
POST /local/tags/{tag_id}/wake
POST /local/tags/{tag_id}/stop
GET  /local/tags/{tag_id}/status
```

认证方式：`Authorization: Bearer <local_session_token>`

## 6. 安全机制

### 6.1 Server-Gateway HMAC

所有 gateway→server 请求使用 HMAC-SHA256 签名：

```
X-Gateway-Code: GW001
X-Gateway-Timestamp: <unix_seconds>
X-Gateway-Nonce: <random_hex>
X-Gateway-Body-SHA256: <sha256>
X-Gateway-Signature: HMAC-SHA256(secret, "METHOD\npath\nts\nnonce\nbody_sha256")
```

### 6.2 本地 API 安全

- 未绑定状态：只开放 `/local/health` 和 `/local/provisioning/*`
- 绑定状态：业务接口需要 `Authorization: Bearer <token>`
- Token 仅存储 SHA-256 哈希
- 支持 TTL 过期和撤销
- 认证失败写入审计日志

### 6.3 防重放 / 防篡改

Provisioning bind 接口：

- `X-Local-Timestamp` 时间窗口校验（300 秒）
- `X-Local-Nonce` 去重
- `X-Local-Body-SHA256` 请求体完整性校验

### 6.4 安全审计

本地审计记录事件类型：

- `provisioning_started`, `provisioning_bind_attempt`, `provisioning_bind_success`, `provisioning_bind_failed`
- `local_auth_success`, `local_auth_failed`, `local_api_unauthorized`
- `heartbeat_success`, `heartbeat_failed`
- `server_signature_rejected`, `replay_detected`, `suspicious_request`

**绝不记录**：`gateway_secret`、明文 token、明文 credential_value。

## 7. BLE 标签管理

### 7.1 后端

仅支持 `BLE_BACKEND=real`（默认）。不再支持 mock fallback。

要求：
- Linux 蓝牙适配器（BlueZ）
- `bleak` Python 包
- 标签 BLE 名称格式：`SPS-{factory}-{date}-{serial}` 或 `SPS-TAG-{hex}`

如果真实 BLE 不可用，会明确报错：
- `bleak_not_installed`
- `scan_failed`
- `connect_failed`
- `command_failed`

### 7.2 标签命名

真实标签：
```
SPS-F01-20260610-0001  (factory code, production date, serial)
```

注册后 gateway 分配：
```
tag_id = SPS-TAG-0001
display_name = 标签 001
tag_uid = SPS-F01-20260610-0001
```

## 8. CLI 命令

```bash
python -m gateway.main init-db          # 初始化数据库
python -m gateway.main status           # 查看状态
python -m gateway.main run              # 自动启动（推荐）
python -m gateway.main provisioning     # 仅 provisioning 模式
python -m gateway.main hotspot-start    # 手动开启热点
python -m gateway.main hotspot-stop     # 手动关闭热点
python -m gateway.main local-api        # 仅启动 local API
python -m gateway.main health           # 检查 server 健康
python -m gateway.main heartbeat        # 发送 heartbeat
python -m gateway.main sync-pull        # 拉取同步数据
python -m gateway.main sync-push        # 推送同步数据
python -m gateway.main bootstrap-activate  # 管理员直接激活网关
python -m gateway.main bind-tag         # 绑定标签到包裹
python -m gateway.main register-tag     # 注册标签
python -m gateway.main list-tags        # 列出标签
python -m gateway.main list-parcels     # 列出包裹
python -m gateway.main list-tasks       # 列出任务
```

## 9. 测试

```bash
cd smartparcel-gateway
pytest tests/ -v
```

测试覆盖：
- `test_gateway_config.py` — 配置加载、默认值、绑定状态
- `test_gateway_security.py` — HMAC 签名、header 构建、哈希一致性
- `test_local_api_auth.py` — 未绑定阻拦、token 认证、过期处理、审计写入
- `test_gateway_provisioning.py` — provisioning API、防重放、字段校验

## 10. 常见问题

| 问题 | 检查 |
|------|------|
| BLE 扫描为空 | 标签上电？固件烧录？BLE_BACKEND=real？蓝牙权限？ |
| 热点启动失败 | `nmcli` 已安装？Wi-Fi 支持 AP 模式？有 root/NetworkManager 权限？ |
| 绑定失败 | server 可达？registration_token 未过期？station_id 匹配？ |
| 小程序无法访问 | 手机连接了网关热点？gateway IP 是 `192.168.4.1`？ |
| Token 认证失败 | token 过期？已撤销？使用了正确的 Bearer 格式？ |

## 11. 安全注意事项

- **不要**提交 `.env` 到 Git
- **不要**在日志或 API 响应中输出 `GATEWAY_SECRET`
- **不要**让 `gateway_secret` 出现在小程序端
- **不要**在生产环境启用 `ALLOW_DEV_HTTP=true`
- **不要**在正式运行路径中使用 mock BLE/NFC
# 阶段 2：统一门禁识别与凭证生命周期

Gateway 统一支持 `CARD_UID`、`GATE_NFC_TAG`、`GATE_QR`。卡只有 `ACTIVE`
状态可用；`LOST`、`REPLACED`、`DISABLED`、`EXPIRED` 一律拒绝。server 下发补卡事件后，
旧 UID 在本地变为 `REPLACED`，新 UID 才会成为 `ACTIVE`，历史 UID不会被陈旧 UPSERT 重新激活。

`sync-pull` 会应用 server 返回的 `events`，包括凭证、包裹、标签绑定、取件确认和
`GATE_USER_AUTH_REQUESTED`。QR/NFC 用户确认最终仍由 Gateway 根据本地待取包裹决定是否放行。

门禁固件使用独立 reader token，不使用小程序或运维 local session token：

```text
X-Gate-Reader-Id: GATE01
X-Gate-Reader-Token: change-this-reader-token
```

接口：`POST /local/gate/access-card`、`GET /local/gate/qr-session`、
`GET /local/gate/nfc-payload`、`GET /local/gate/auth-result`、
`GET /local/gate/auth-session/{session_id}/result`。QR challenge 默认 60 秒，认证结果默认 15 秒。

演示：

```bash
python -m gateway.main seed-demo-gate --user-id 2 --credential-type CARD_UID \
  --credential-value CARD_UID_001 --parcel-code P20260701001 --shelf-code A03 --tag-id SPS-TAG-0001
python -m gateway.main replace-card-demo --user-id 2 --old-card CARD_UID_001 --new-card CARD_UID_002
```
