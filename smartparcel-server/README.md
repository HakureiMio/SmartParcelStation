# SmartParcel Server

> 最终门禁演示入口：server 负责账号、包裹、卡绑定/补办、认证请求与同步事件，但不直接绕过 gateway 放行。初始化、登录、NFC/QR 门禁和取件确认命令见 [端到端演示文档](../docs/demo_three_gate_auth_methods.md)。

## 1. server 职责

`smartparcel-server` 是 SmartParcelStation 的中心服务端，提供 `/api/v1` REST API，负责账号、站点、网关注册、中心包裹、通知、同步审计和异常摘要。

server 当前负责：

- 用户、员工、站点和网关管理。
- 中心包裹记录和通知记录。
- 网关短期注册凭证和 HMAC 签名校验。
- `sync-push` / `sync-pull` 的中心侧处理。
- gateway 上传的取件审计、门禁审计和标签异常摘要。

## 2. 当前不负责的内容

server 不直接扫描、连接或控制 BLE 标签。

server 不保存完整标签实时状态。以下内容由 gateway 本地保存：

- 标签注册信息。
- 标签本地编号。
- BLE 地址。
- 电量。
- 最后发现时间。
- 最后连接时间。
- 在线/离线和本地运行状态。

server 只接收标签异常摘要和取件审计，不作为 BLE 标签管理后台。

## 3. 启动依赖

```powershell
cd smartparcel-server
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d mysql emqx
```

关键依赖：

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- MySQL
- EMQX

## 4. 启动 API

执行数据库迁移：

```powershell
python -m alembic upgrade head
```

启动服务：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

健康检查：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/health"
```

## 5. 数据库迁移

常用命令：

```powershell
python -m alembic revision --autogenerate -m "message"
python -m alembic upgrade head
python -m alembic downgrade -1
```

应用运行使用异步连接串，例如：

```text
mysql+aiomysql://smartparcel:smartparcel@127.0.0.1:3306/smartparcel
```

Alembic 迁移会在项目配置中转换为同步驱动。

## 6. 网关注册与 HMAC

推荐使用“短期注册凭证 -> 激活 -> 长期网关密钥”的流程：

```text
server 创建 registration_token
gateway 调用 /api/v1/gateways/bootstrap/activate
server 校验 token 并生成 gateway_secret
gateway 保存 GATEWAY_CODE / GATEWAY_SECRET / STATION_ID / SERVER_BASE_URL
后续 heartbeat / sync 使用 HMAC-SHA256 签名
```

相关 API：

```text
POST /api/v1/gateways/registration-tokens
GET  /api/v1/gateways/registration-tokens
POST /api/v1/gateways/registration-tokens/{id}/revoke
POST /api/v1/gateways/bootstrap/activate
```

网关请求头：

```text
X-Gateway-Code
X-Gateway-Timestamp
X-Gateway-Nonce
X-Gateway-Body-SHA256
X-Gateway-Signature
```

## 7. sync-push / sync-pull

中心同步接口：

```text
GET  /api/v1/gateways/{gateway_code}/sync/pull
POST /api/v1/gateways/{gateway_code}/sync/push
POST /api/v1/gateways/{gateway_code}/events
POST /api/v1/gateways/heartbeat
```

server 当前会处理：

- `GATEWAY_INBOUND`：合并或创建中心包裹，并将网关上报的 `shelf_code` 保存到中心数据库。为兼容旧来源，也接受 `shelf`、`location`、`rack_code` 字段。
- `PICKUP_CONFIRMED` / `OFFLINE_PICKUP`：记录取件审计并更新包裹状态。
- `TAG_EXCEPTION_REPORTED`：保存标签异常摘要并生成工作人员通知。
- `NFC_ACCESS_GRANTED` / `NFC_ACCESS_DENIED` / `TAG_WAKE_STARTED`：保存门禁和唤醒审计。

`TAG_BOUND`、`TAG_RELEASED`、`TAG_STATUS_REPORT` 仅作为历史 mock 兼容审计，不生成 server 侧标签实时状态。

## 8. 开发测试账号和管理面板

启动管理面板：

```powershell
python -m admin_console.main
```

开发演示账号：

| 入口 | 用户名 | 密码 | 角色 |
| --- | --- | --- | --- |
| 客户端 | `user001` | `123456` | `USER` |
| 员工端 | `staff001` | `123456` | `STAFF` |

登录接口：

```http
POST /api/v1/auth/login
```

当前用户的待取包裹接口：

```http
GET /api/v1/users/me/parcels
Authorization: Bearer <token>
```

响应中的每个包裹包含 `parcel_code`、`status`、`shelf_code` 等字段。历史数据在迁移后若尚未收到网关重新上报，`shelf_code` 可能为 `null`。

小程序已提供用户端和员工端原型。server 当前只提供部分真实 API，其余页面仍可能使用 mock fallback。

## 9. 与 BLE 标签的关系

server 与 BLE 标签的边界如下：

```text
server 不直接控制 BLE 标签。
server 不保存完整标签实时状态。
标签注册、标签本地编号、BLE 地址、电量、最后心跳等由 gateway 本地保存。
server 只接收标签异常摘要和取件审计。
```

真实 BLE 控制链路为：

```text
小程序员工端
  -> smartparcel-gateway local API
  -> BLE_BACKEND=real
  -> nRF52810 标签 GATT Service
```

## 10. 停止服务

停止 FastAPI：在运行终端按 `Ctrl + C`。

停止 Docker Compose 服务：

```powershell
docker compose down
```

## 11. VPS 部署

### 11.1 入口

```bash
bash deploy/vps/deploy.sh
```

详细说明请参考 [deploy/vps/README.md](../deploy/vps/README.md)。

### 11.2 更新部署

```bash
bash deploy/vps/update.sh
```

### 11.3 健康检查

```bash
bash deploy/vps/healthcheck.sh
```

### 11.4 安全通信设计

```
┌─────────────────┐     HTTPS + HMAC      ┌──────────────────┐
│  smartparcel-    │ ◄──────────────────► │  smartparcel-     │
│  gateway         │   X-Gateway-* 请求头  │  server           │
│  (本地网关)       │                      │  (VPS 中心服务器)  │
└─────────────────┘                      └──────────────────┘
                                                  ▲
                                                  │ HTTPS + Token
                                                  │
                                         ┌────────┴────────┐
                                         │  smartparcel-     │
                                         │  miniprogram      │
                                         │  (微信小程序)      │
                                         └──────────────────┘
```

**小程序 → Server**: HTTPS + 认证凭证。小程序**不保存** gateway secret、server secret、数据库密码或微信 appsecret。

**Gateway → Server**: HTTPS + HMAC-SHA256 + Timestamp + Nonce + Body SHA256。

Server 端校验链：
1. 检查所有必需请求头（`X-Gateway-Code`, `X-Gateway-Timestamp`, `X-Gateway-Nonce`, `X-Gateway-Body-SHA256`, `X-Gateway-Signature`）
2. 查找 gateway 并验证状态
3. 校验 timestamp 在容差范围内（防过期请求）
4. 校验 body SHA256（防篡改）
5. 校验 HMAC-SHA256 签名（防伪造）
6. 校验 nonce 未被使用过（防重放）

### 11.5 网络安全演示

演示脚本位于 `scripts/security_demo/`：

| 脚本 | 预期结果 |
|------|----------|
| `valid_gateway_request.py` | 200 OK |
| `tampered_body_request.py` | 401 Invalid gateway body hash |
| `replay_nonce_request.py` | 401 Replay gateway nonce |
| `invalid_signature_request.py` | 401 Invalid gateway signature |

运行方式：

```bash
export SERVER_BASE_URL=http://127.0.0.1:18000
export GATEWAY_CODE=GW-DEV-001
export GATEWAY_SECRET=<secret>
python scripts/security_demo/valid_gateway_request.py
```

详细说明：[scripts/security_demo/README.md](scripts/security_demo/README.md)

### 11.6 端口暴露建议

| 端口 | 服务 | 公网 |
|------|------|------|
| 80/443 | Nginx / Caddy | ✅ 开放 |
| 18000 | Server API | ❌ 仅本机 |
| 3306 | MySQL | ❌ 仅本机 |
| 1883 | MQTT | ❌ 仅本机 |
| 18083 | EMQX Dashboard | ❌ 仅本机 |
| 8080 | phpMyAdmin | ❌ 默认禁用 |

### 11.7 VPS 服务管理

```bash
cd smartparcel-server

# 查看容器状态
docker compose -f docker-compose.vps.yml ps

# 查看日志
docker compose -f docker-compose.vps.yml logs -f server

# 停止服务
docker compose -f docker-compose.vps.yml down

# 重启服务
docker compose -f docker-compose.vps.yml up -d --build
```
# 用户门禁凭证与补卡（阶段 1）

演示账号为 `station_admin001 / 123456`（STAFF）和 `demo_user001 / 123456`（USER）。
旧账号 `user001`、`staff001` 仅作历史兼容，初始化时会停用。自由注册保持关闭。

服务端支持三种门禁识别入口：实体卡或手机 HCE 的 `CARD_UID`、手机读取门禁标签的
`GATE_NFC_TAG`、小程序扫描门禁屏幕的 `GATE_QR`。后两种入口只创建
`GATE_USER_AUTH_REQUESTED` 事件；server 不直接决定放行，最终由 gateway 判断。

补卡时，STAFF 使用 Bearer token 调用绑定接口。系统把同用户、同站点原有 ACTIVE
卡改为 `REPLACED`，保留历史并下发禁用事件，再创建新 ACTIVE 卡及 UPSERT 事件。
报失会把 ACTIVE 卡改为 `LOST`。已经发放过的 UID（包括 LOST、REPLACED、DISABLED）
不会重新绑定，避免旧卡恢复为可用凭证。

初始化完整演示数据：

```bash
curl -X POST http://localhost:8000/api/v1/dev/demo-data \
  -H "X-Admin-Bootstrap-Token: change-me-local-only"
```

补办卡（先通过 `/api/v1/auth/login` 获取 STAFF token 和用户 ID）：

```bash
curl -X POST http://localhost:8000/api/v1/staff/users/2/cards/bind \
  -H "Authorization: Bearer $STAFF_TOKEN" -H "Content-Type: application/json" \
  -d '{"station_id":1,"credential_type":"CARD_UID","credential_value":"CARD_UID_002","reason":"FIRST_BIND_OR_REPLACEMENT"}'
```

上述调用会令 `CARD_UID_001 -> REPLACED`、`CARD_UID_002 -> ACTIVE`。
