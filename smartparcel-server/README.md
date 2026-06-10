# SmartParcel Server

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

- `GATEWAY_INBOUND`：合并或创建中心包裹。
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
