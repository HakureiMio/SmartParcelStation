# SmartParcel Server

SmartParcelStation 快递站系统服务端项目（局域网验证阶段）。提供统一的 `/api/v1` REST API，覆盖站点管理、网关同步、快递与标签绑定、取件流程、通知管理，以及与 EMQX 的 MQTT 基础集成。

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
- `DEFAULT_GATEWAY_SECRET`：网关签名校验的兜底密钥（HMAC）。
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

- 拉取待同步任务：`GET /api/v1/gateways/{gateway_id}/sync/pull`
- 回传 ACK/同步数据：`POST /api/v1/gateways/{gateway_id}/sync/push`
- 上报网关事件：`POST /api/v1/gateways/{gateway_id}/events`
- 网关请求头：
  - `X-Gateway-Code`
  - `X-Gateway-Signature`（HMAC-SHA256，签名原文为 `gateway_code + "." + raw_body`）

MQTT Topic 约定：

- 下发命令：`server/{gateway_code}/commands`
- 订阅事件：`gateway/{gateway_code}/events`
- 订阅状态：`gateway/{gateway_code}/status`

## 10. 后续迁移到公网服务器需修改的配置项

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
