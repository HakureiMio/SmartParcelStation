# Gateway Provisioning / Binding Flow

网关从出厂到上线的完整配网绑定流程，供小程序和 server 开发参考。

## 流程概览

```text
1. 网关开机，检查本地绑定状态。
2. 如果 UNBOUND：
   - 初始化 SQLite
   - 开启 Wi-Fi 热点 (SSID: SmartParcel-GW-XXXX)
   - 启动 Provisioning API (http://192.168.4.1:19000)
3. 员工手机连接网关热点。
4. 员工打开微信小程序 → "网关绑定" 页面。
5. 小程序调用网关 GET /local/provisioning/status。
6. 小程序向 VPS server 提交绑定申请。
7. VPS server 校验员工身份和站点权限。
8. VPS server 返回绑定参数给小程序。
9. 小程序把绑定参数 POST 到网关 /local/provisioning/bind。
10. 网关调用 server /api/v1/gateways/bootstrap/activate。
11. Server 返回长期 GATEWAY_SECRET。
12. 网关保存配置、发送 heartbeat。
13. heartbeat 成功 → 状态切换 BOUND → ONLINE。
14. 关闭开放式 provisioning API，启动完整 runtime。
```

## 小程序需要调用的接口

### 1. 查询网关状态

```
GET http://192.168.4.1:19000/local/provisioning/status
```

响应：

```json
{
  "ok": true,
  "binding_status": "UNBOUND",
  "gateway_device_id": "GWDEV-0001",
  "gateway_serial": "SPS-GW-0001",
  "provisioning_enabled": true,
  "ap_ssid": "SmartParcel-GW-0001",
  "local_ip": "192.168.4.1",
  "server_base_url": null,
  "gateway_code": null,
  "station_id": null
}
```

小程序从响应中获取 `gateway_device_id` 和 `gateway_serial`。

### 2. 向 Server 提交绑定申请

小程序向 VPS server 发起绑定申请（具体 API 由 server 端定义，可能需要 admin 权限）。

小程序需要提供：
- `gateway_device_id`
- `gateway_serial`
- `station_id`
- 员工身份凭证

Server 返回绑定参数：
- `server_base_url`
- `gateway_code`
- `station_id`
- `registration_token` (一次性绑定令牌，有时效性)
- `mqtt_host` / `mqtt_port` / `mqtt_tls_enabled`
- `gateway_config_version`
- `expires_at`

### 3. 向网关写入绑定参数

```
POST http://192.168.4.1:19000/local/provisioning/bind
```

请求头：

```http
Content-Type: application/json
X-Local-Timestamp: <unix seconds>
X-Local-Nonce: <random hex string>
X-Local-Body-SHA256: <SHA256 of request body>
```

请求体：

```json
{
  "server_base_url": "https://api.example.com",
  "gateway_code": "GW001",
  "station_id": "1",
  "registration_token": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "mqtt_host": "api.example.com",
  "mqtt_port": 1883,
  "mqtt_tls_enabled": false,
  "config_version": 1,
  "expires_at": "2026-06-30T12:00:00Z"
}
```

响应：

```json
{
  "ok": true,
  "binding_status": "BOUND",
  "gateway_code": "GW001",
  "station_id": "1",
  "server_base_url": "https://api.example.com",
  "heartbeat": "OK"
}
```

### 4. 验证绑定结果

```
POST http://192.168.4.1:19000/local/provisioning/verify
```

响应：

```json
{
  "ok": true,
  "binding_status": "BOUND",
  "gateway_code": "GW001",
  "station_id": "1",
  "last_heartbeat_status": "ONLINE",
  "last_heartbeat_at": "2026-06-30T12:00:05Z"
}
```

## 网络拓扑说明

### 场景 A：网关热点有外网上联

```
员工手机 → (Wi-Fi) → 网关热点 → (以太网/4G/第二 Wi-Fi + NAT) → VPS Server
```

此场景下小程序可以直接通过热点同时访问网关和 server。

### 场景 B：网关热点无外网

```
步骤 1-6: 员工手机 → (蜂窝网络) → VPS Server (获取绑定参数)
步骤 7-9: 员工手机 → (Wi-Fi) → 网关热点 (写入绑定参数)
```

小程序需要支持"两段式流程"：
1. 先通过蜂窝网络从 server 获取绑定参数
2. 再切换到网关热点 Wi-Fi，把参数写入网关

## 小程序不应保存的数据

- ❌ `gateway_secret` — 密钥仅存在于网关的 `.env` 中
- ❌ server admin token — 小程序不应持有管理员凭证
- ✅ `local_session_token` — 可以短期缓存（默认 1 小时 TTL）

## 安全设计

- Provisioning API 仅在 UNBOUND 状态下开放
- 绑定成功后自动关闭开放式 provisioning
- 绑定请求需要 timestamp + nonce + body hash 防重放
- registration_token 是一次性的，用完即标记为 USED
- gateway_secret 在 server 端只存储 hash，从不明文存储
- gateway_secret 在 gateway 端存储在 `.env`，不进入 SQLite

## 相关接口

| 组件 | 接口 | 认证 |
|------|------|------|
| Gateway | `GET /local/provisioning/status` | 无 |
| Gateway | `POST /local/provisioning/bind` | timestamp+nonce |
| Gateway | `POST /local/provisioning/verify` | 无 |
| Server | `POST /api/v1/gateways/registration-tokens` | Admin |
| Server | `POST /api/v1/gateways/bootstrap/activate` | registration_token |
| Server | `POST /api/v1/gateways/heartbeat` | HMAC-SHA256 |
