# SmartParcel Server

SmartParcelStation 快递站系统服务端项目（局域网验证阶段）。提供统一的 `/api/v1` REST API，覆盖站点管理、网关同步、快递取件流程、通知管理，以及与 EMQX 的 MQTT 基础集成。智能寻物标签采用 gateway-local-first 管理模式，server 不作为标签管理后台。

## 1. 项目说明

- 技术栈：Python 3.11+、FastAPI、SQLAlchemy 2.x、Alembic、MySQL、Pydantic v2、gmqtt。
- 数据库驱动说明：
  - 应用运行（异步）：`mysql+aiomysql://...`
  - Alembic 迁移（同步）：项目已在 `alembic/env.py` 中自动转换为 `mysql+pymysql://...`
- 目标：用于局域网环境的后端验证，支撑本地网关同步、入库/取件业务流，并为后续微信小程序接入预留统一 API。
- 当前认证：开发模式请求头（`X-Dev-User-Id`、`X-Dev-Role`）+ 网关签名校验框架。

## 2. 局域网验证部署方式

1. 进入项目目录：`cd smartparcel-server`
2. 创建虚拟环境：`python -m venv .venv`
3. 激活虚拟环境：`.\\.venv\\Scripts\\activate`
4. 安装依赖：`pip install -r requirements.txt`
5. 复制配置文件：`copy .env.example .env`
6. 启动基础服务：`docker compose up -d mysql emqx`
7. 执行数据库迁移：`python -m alembic upgrade head`
8. 启动 API 服务：`uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload`

## 3. .env 配置说明

`.env` 关键配置项如下：

- `DATABASE_URL`：MySQL 连接串（推荐 `mysql+aiomysql://smartparcel:smartparcel@127.0.0.1:3306/smartparcel`）。
- `DEBUG`：布尔值，建议使用 `true/false`（项目已兼容 `release/prod/dev` 字符串）。
- `DEV_AUTH_ENABLED`：是否启用开发模式认证。
- `DEFAULT_GATEWAY_SECRET`：早期本地开发兜底值，公网实验不应长期依赖。
- `GATEWAY_SIGNATURE_TOLERANCE_SECONDS`：网关 HMAC timestamp 允许偏差，默认 300 秒。
- `ADMIN_BOOTSTRAP_TOKEN`：开发阶段初始化默认用户、注册网关的临时保护 token，公网实验前必须改强随机值。
- `PUBLIC_BASE_URL`：公网 HTTPS 域名，例如 `https://sps.example.com`。
- `MQTT_ENABLED`：是否启用 MQTT 生命周期连接。
- `MQTT_HOST`、`MQTT_PORT`、`MQTT_USERNAME`、`MQTT_PASSWORD`：EMQX 连接参数。
- MQTT Topic 模板：
  - `MQTT_TOPIC_COMMAND_TEMPLATE=server/{gateway_code}/commands`
  - `MQTT_TOPIC_EVENT_TEMPLATE=gateway/{gateway_code}/events`
  - `MQTT_TOPIC_STATUS_TEMPLATE=gateway/{gateway_code}/status`

## 4. MySQL 初始化方式

使用 Docker Compose 启动 MySQL：

- `docker compose up -d mysql`

也可使用本机 MySQL 手动创建数据库和用户，然后在 `.env` 中更新 `DATABASE_URL`。

## 5. Alembic 迁移方式

- 创建新迁移：`python -m alembic revision --autogenerate -m "msg"`
- 执行迁移：`python -m alembic upgrade head`
- 回滚一步：`python -m alembic downgrade -1`

## 5.1 网关短期注册凭证流程

公网实验不再建议由管理员手动把长期 `GATEWAY_SECRET` 同时填入 server 面板和 gateway `.env`。推荐流程：

1. 服务端管理员在 server 面板或 API 创建短期 `registration_token`。
2. 管理员通过手机端查看该凭证；当前手机端暂未实现，使用 server 面板/API 返回结果模拟。
3. 管理员通过蓝牙或网关热点连接 ARM 网关；当前阶段使用 gateway CLI 模拟写入。
4. gateway 使用 `registration_token` 调用 `/api/v1/gateways/bootstrap/activate`。
5. server 校验凭证未过期、未使用、未撤销，并生成长期 `gateway_secret`。
6. gateway 保存 `GATEWAY_CODE`、`GATEWAY_SECRET`、`STATION_ID`、`SERVER_BASE_URL`。
7. 后续 heartbeat / sync-push / sync-pull 继续使用长期 `gateway_secret` 做 HMAC-SHA256 签名。

安全说明：

- 短期注册凭证默认 10 分钟有效，由 `GATEWAY_REGISTRATION_TOKEN_TTL_SECONDS=600` 控制。
- 明文 `registration_token` 只在创建时返回一次，数据库仅保存 SHA-256 hash。
- token 使用成功后会标记为 `USED`，不能重复使用。
- 管理员可撤销未使用 token，被撤销 token 不能激活网关。
- 长期 `gateway_secret` 只在激活成功时返回给 gateway，不能提交到 Git。
- 当前 `gateways.device_secret_hash` 字段沿用历史命名，实际保存的是 HMAC 共享密钥，不是真正的 hash。

新增 API：

- `POST /api/v1/gateways/registration-tokens`：创建短期注册凭证，需要 `SERVER_ADMIN` 或本地开发 bootstrap token。
- `GET /api/v1/gateways/registration-tokens`：查看凭证列表，不返回明文 token。
- `POST /api/v1/gateways/registration-tokens/{id}/revoke`：撤销未使用凭证。
- `POST /api/v1/gateways/bootstrap/activate`：gateway 用短期凭证激活注册，成功后返回长期 `gateway_secret`。

## 6. 启动 FastAPI

- `uvicorn app.main:app --host 0.0.0.0 --port 18000`

示例接口：

- `GET /api/v1/health`
- `GET /api/v1/version`

## 7. 启动 EMQX

- `docker compose up -d emqx`
- EMQX 管理台：`http://localhost:18083`
- 本项目默认未在 `docker-compose.yml` 预设 Dashboard 账号密码。若默认账号登录失败，请在 `emqx` 服务中显式配置：
  - `EMQX_DASHBOARD__DEFAULT_USERNAME=admin`
  - `EMQX_DASHBOARD__DEFAULT_PASSWORD=public`
  - 然后执行：`docker compose up -d --force-recreate emqx`

## 8. API 测试示例

健康检查（PowerShell）：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/health"
```

创建站点（PowerShell）：

```powershell
$headers = @{
  "Content-Type" = "application/json"
  "X-Dev-User-Id" = "1"
  "X-Dev-Role" = "SERVER_ADMIN"
}

$body = @{
  station_code = "ST001"
  name = "主站点"
  address = "示例路1号"
  status = "ACTIVE"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:18000/api/v1/stations" `
  -Headers $headers `
  -Body $body
```

创建快递：

```bash
curl -X POST http://127.0.0.1:18000/api/v1/parcels \
  -H "Content-Type: application/json" \
  -H "X-Dev-User-Id: 1" \
  -H "X-Dev-Role: LOCAL_ADMIN" \
  -d '{"parcel_code":"P20260528001","station_id":1,"receiver_user_id":2}'
```

取件确认（按 `event_id` 幂等）：

```bash
curl -X POST http://127.0.0.1:18000/api/v1/pickup/confirm \
  -H "Content-Type: application/json" \
  -H "X-Dev-User-Id: 2" \
  -H "X-Dev-Role: USER" \
  -d '{"event_id":"evt-001","tag_id":"TAG-001","encrypted_token":"ENC-XXX","pickup_binding_id":"bind-xxx"}'
```

## 9. 与本地网关项目的接口约定

- 拉取待同步任务：`GET /api/v1/gateways/{gateway_code}/sync/pull`
- 回传 ACK/同步数据：`POST /api/v1/gateways/{gateway_code}/sync/push`
- 上报网关事件：`POST /api/v1/gateways/{gateway_code}/events`
- 网关请求头：
  - `X-Gateway-Code`
  - `X-Gateway-Timestamp`
  - `X-Gateway-Nonce`
  - `X-Gateway-Body-SHA256`
  - `X-Gateway-Signature`

签名原文为 `METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + BODY_SHA256`。

MQTT Topic 约定：

- 下发命令：`server/{gateway_code}/commands`
- 订阅事件：`gateway/{gateway_code}/events`
- 订阅状态：`gateway/{gateway_code}/status`

## 10. 阶段 A：server 侧 mock 闭环流程

当前阶段快递公司上传用“服务器手动预录入快递”代替；微信小程序前端暂不实现，只保留账号角色和接口职责。server 负责中心记录、通知占位和同步审计，不直接控制智能寻物标签亮灯、蜂鸣、绑定、释放或状态查询。

### 10.1 启动依赖和 API

```powershell
cd smartparcel-server
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d mysql emqx
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

### 10.2 打开服务器终端面板

```powershell
cd smartparcel-server
.\.venv\Scripts\activate
python -m admin_console.main
```

面板包含：

- 系统状态：`health`、`version`、当前 `API_BASE_URL`。
- 用户管理：查看用户、创建默认测试用户、创建用户、启停用户、修改角色。
- 站点管理：查看站点、创建默认站点 `ST001`、创建站点。
- 网关管理：查看网关、注册默认网关 `GW001`、查看心跳状态。
- 中心包裹记录：手动预录入快递、查看包裹、按 `parcel_code` 查询、查看 `origin` 和 `business_status`。
- 用户查询与通知记录：查看待取件、通知记录、标记已读。
- 同步事件审计：查看 `gateway_sync_events`。
- 异常处理：查看 `EXCEPTION` / `CONFLICT`。
- 开发测试工具：一键创建默认用户、站点、网关。

### 10.3 新增 API 能力

- `POST /api/v1/dev/default-users`：创建默认测试用户。
- `GET /api/v1/users`、`POST /api/v1/users`、`PATCH /api/v1/users/{user_id}`：开发阶段用户管理。
- `GET /api/v1/gateways`：查看网关和心跳时间。
- `GET /api/v1/parcels/by-code/{parcel_code}`：按快递号查询中心包裹。
- `GET /api/v1/parcel-query`：按 `user_id`、`parcel_code`、`receiver_phone`、`pickup_code` 查询，返回脱敏字段。
- `GET /api/v1/notifications`：查看通知记录。
- `GET /api/v1/sync-events`：查看同步事件审计。

### 10.4 gateway sync-push 事件处理

server 收到以下事件时会落业务：

- `GATEWAY_INBOUND` / `PARCEL_ARRIVED` / `INBOUND_PARCEL`：按 `parcel_code` 合并预录入包裹，或新建 `GATEWAY_INBOUND` 来源包裹。
- `TAG_EXCEPTION_REPORTED`：接收 gateway 判断后的标签异常摘要，生成站点工作人员通知和同步审计，不更新标签实时状态。
- `PICKUP_CONFIRMED` / `OFFLINE_PICKUP` / `NFC_FAST_PICKUP_CONFIRMED`：更新包裹为 `PICKED_UP`，记录 pickup event；payload 中的 `pickup_method = TAG_NFC_FAST` 用于审计智能寻物标签 NFC 快速取件。
- `NFC_ACCESS_GRANTED` / `NFC_ACCESS_DENIED` / `TAG_WAKE_STARTED`：只保存 `GatewaySyncEvent` 审计，不参与门禁实时放行，不更新包裹或标签状态。
- `TAG_BOUND` / `TAG_RELEASED`：仅保留兼容旧 mock 或可选业务审计语义，不生成标签实时状态表或管理视图。
- `TAG_STATUS_REPORT`：deprecated，仅兼容旧 mock；实体智能寻物标签阶段不作为常规同步事件上传 server。

### 10.5 服务器侧标签相关职责

智能寻物标签的注册、绑定、释放、在线/离线、电量、BLE 地址、固件版本、最后心跳、异常判断和 BLE 控制全部由 gateway 本地管理。server 不保存完整标签状态镜像，也不提供标签实时管理接口。

server 只保留两类标签相关业务信息：

- `TAG_EXCEPTION_REPORTED`：由 gateway 判断并上传异常摘要，server 生成 `STAFF` / `GATEWAY_ADMIN` 工作人员通知和同步事件审计。
- 取件审计：`PICKUP_CONFIRMED`、`OFFLINE_PICKUP` 或兼容的 `NFC_FAST_PICKUP_CONFIRMED` 中保留 `pickup_method`；智能寻物标签 NFC 快速取件统一使用 `TAG_NFC_FAST`。

门禁本地放行相关事件由 gateway 异步上传，server 只做审计：

- `NFC_ACCESS_GRANTED`
- `NFC_ACCESS_DENIED`
- `TAG_WAKE_STARTED`

这些事件不生成 server 标签状态，不创建 `Tag` / `ParcelTagBinding`，也不作为门禁实时裁决依据。

原则：标签日常状态不上云，标签异常才上报；标签控制不上云，取件结果才上报。

### 10.6 已删除的 server 标签管理接口

`/api/v1/tags*` 系列 server 标签管理接口已删除。server 不再提供标签创建、列表、查询、绑定、释放、状态上报 API，OpenAPI/Swagger 中也不再出现这些路由。

已删除接口：

- `POST /api/v1/tags`
- `GET /api/v1/tags`
- `GET /api/v1/tags/{tag_id}`
- `POST /api/v1/tags/bind`
- `POST /api/v1/tags/release`
- `POST /api/v1/tags/status-report`

server 仍只保留：

- `TAG_EXCEPTION_REPORTED` 异常摘要通知。
- `pickup_method = TAG_NFC_FAST` 取件审计。
- `GatewaySyncEvent` 同步事件审计。

`TAG_BOUND`、`TAG_RELEASED`、`TAG_STATUS_REPORT` 仅作为旧 mock 兼容同步事件被审计，不生成 server 标签状态。历史 `Tag` / `ParcelTagBinding` 模型和表暂时保留，避免不必要的删表迁移风险；实体智能寻物标签阶段不作为主数据使用。

### 10.7 数据库迁移

本阶段新增迁移：

- `alembic/versions/0002_sps_stage_a_flow.py`

迁移内容：

- 扩展 `UserRole`：新增 `STAFF`、`GATEWAY_ADMIN`。
- 扩展 `ParcelStatus`：新增 `PRE_REGISTERED`、`ARRIVED_AT_STATION`、`FINDING`、`PICKUP_VERIFYING`。
- `users` 新增 `pickup_level`、`trusted_pickup_enabled`。
- `parcels` 新增 `receiver_name_masked`、`origin`、`sync_status`。
- `parcels.created_by_admin_id` 允许为空，用于表示 gateway 入站产生的包裹不是由人工管理员直接创建。

## 11. 公网 HTTPS 与网关签名准备

公网实验推荐使用 Caddy/Nginx 终止 HTTPS，再反向代理到 `127.0.0.1:18000`。不要把 MySQL `3306`、EMQX `1883`、EMQX Dashboard `18083` 直接暴露公网。详细说明见 `docs/public_https_deployment.md`。

网关核心接口现在统一要求 HMAC-SHA256 签名：

- `POST /api/v1/gateways/heartbeat`
- `GET /api/v1/gateways/{gateway_code}/sync/pull`
- `POST /api/v1/gateways/{gateway_code}/sync/push`
- `POST /api/v1/gateways/{gateway_code}/events`

签名请求头：

- `X-Gateway-Code`
- `X-Gateway-Timestamp`
- `X-Gateway-Nonce`
- `X-Gateway-Body-SHA256`
- `X-Gateway-Signature`

签名原文为 `METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + BODY_SHA256`。server 默认允许 300 秒时间窗口，并通过 `gateway_nonces` 表阻止有效窗口内重复 nonce。

新增配置项：

- `GATEWAY_SIGNATURE_TOLERANCE_SECONDS=300`
- `ADMIN_BOOTSTRAP_TOKEN=change-me-local-only`
- `PUBLIC_BASE_URL=https://example.com`

公网实验前请为每台 gateway 单独生成强随机密钥：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`gateways.device_secret_hash` 是早期字段名遗留；当前阶段实际存放 HMAC 共享密钥。公网实验不要继续使用 `gw-secret-demo`。

新增迁移：

- `alembic/versions/0003_gateway_nonce_replay_protection.py`

迁移内容是新增 `gateway_nonces` 表，用于 timestamp 窗口内的 nonce 防重放。

## 12. 后续迁移到公网服务器需修改的配置项

从局域网迁移到公网时建议至少完成以下调整：

1. 将开发模式认证替换为正式认证（JWT/微信登录）。
2. 强制 HTTPS，并完成密钥轮换。
3. MySQL 与 EMQX 按生产规范部署（高可用、访问控制、备份策略）。
4. 增加 API 网关、限流与 WAF 防护。
5. 网关密钥改为每设备独立安全存储，取消统一兜底密钥。
6. 消息签名增加时间戳/nonce，防重放攻击。
7. 增加监控与告警（metrics、trace、日志聚合）。

## TODO 预留

- TODO：微信登录与 token 服务。
- TODO：生产级 RBAC 权限矩阵。
- TODO：网关命令重试/退避/死信处理。
- TODO：完整 MQTT 业务闭环。

## 附录：已处理的常见问题

- `docker compose` 提示 `version is obsolete`：
  - 这是 Compose 新版本警告，不影响运行，可移除 `docker-compose.yml` 顶部 `version` 字段。
- `WinError 10013`（端口被拒绝）：
  - 端口冲突或权限限制，改用 `18000` 端口可快速启动。
- `sqlalchemy.exc.InvalidRequestError: ... 'pymysql' is not async`：
  - 应用连接串必须使用 `mysql+aiomysql://...`。
- Alembic `MissingGreenlet`：
  - 迁移需要同步驱动，项目已在 `alembic/env.py` 自动改用 `mysql+pymysql://...`。
- MySQL 8 认证报 `cryptography package is required`：
  - 已将 `cryptography` 加入 `requirements.txt`，执行 `pip install -r requirements.txt` 即可。
- `alembic` 命令找不到：
  - 在虚拟环境内优先使用 `python -m alembic ...`，更稳定。
- PowerShell 下 `curl -H -d` 报参数绑定错误：
  - PowerShell 的 `curl` 是 `Invoke-WebRequest` 别名，不兼容 Linux 风格参数。
  - 建议使用 `Invoke-RestMethod`，或改用 `curl.exe`。
- Docker Desktop 里镜像 `Created` 显示“1 year ago / 28 days ago”：
  - 这是镜像在官方仓库的构建时间，不是你本地容器创建时间。
  - 你本地是否刚创建，请看容器列表中的创建/启动时间。

## 停止服务

- 停止并删除 Compose 服务：
  - `docker compose down`
- 停止 FastAPI（uvicorn）：
  - 在运行终端按 `Ctrl + C`

## 13. 账号密码认证接口

server 提供最小可用账号密码认证能力，用于微信小程序原型验证。账号密码保存在 server 数据库，小程序不保存明文密码。

### 13.1 登录接口

```http
POST /api/v1/auth/login
```

请求示例：

```json
{
  "role": "client",
  "username": "user001",
  "password": "123456"
}
```

员工端：

```json
{
  "role": "staff",
  "username": "staff001",
  "password": "123456"
}
```

返回示例：

```json
{
  "token": "demo-token-...",
  "user_id": "2",
  "role": "client",
  "display_name": "用户 002",
  "station_id": "1"
}
```

规则：

- 校验账号、密码和角色。
- 密码错误返回 `401`。
- 用户停用返回 `403`。
- 不返回 `password_hash`。
- 当前 token 为开发演示 token，生产环境应替换为正式 JWT 或服务端会话机制。

### 13.2 注册与忘记密码预留接口

```http
POST /api/v1/auth/register
POST /api/v1/auth/forgot-password
```

当前返回功能暂未开放提示，后续接入正式账号系统。

### 13.3 密码哈希策略

当前使用 Python 标准库实现：

```text
PBKDF2-HMAC-SHA256 + 独立 salt + 120000 次迭代
```

数据库保存格式：

```text
pbkdf2_sha256$120000$salt$base64_digest
```

不会保存明文密码。

### 13.4 开发演示账号

| 入口 | 用户名 | 密码 | 角色 | 用户 ID |
| --- | --- | --- | --- | --- |
| 客户端 | `user001` | `123456` | `client` / `USER` | `2` |
| 员工端 | `staff001` | `123456` | `staff` / `STAFF` | `3` |

这些账号只用于本地开发和毕业设计演示，不用于生产环境。

### 13.5 小程序登录流程

```text
小程序启动页 -> 选择客户/员工入口 -> 登录页输入账号密码 -> /api/v1/auth/login -> 保存 token/role/user_id -> 跳转用户首页或员工工作台
```
