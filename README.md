# SmartParcelStation

SmartParcelStation（SPS）是一个面向小型快递站场景的智能包裹管理与辅助取件系统。当前项目处于局域网验证阶段，重点验证“服务端 + 本地网关”的核心链路：服务端负责业务数据、任务下发与同步管理，本地网关负责本地离线缓存、门禁/NFC 触发、标签唤醒任务生成，以及与服务端进行 HTTP/MQTT 通信。

本仓库采用单仓库多目录结构，便于在早期阶段统一维护服务端和网关之间的接口约定，降低联调成本。

## 1. 项目构成

```text
SmartParcelStation/
├─ smartparcel-server/      # 服务端项目
├─ smartparcel-gateway/     # 本地网关项目
└─ README.md                # 项目总说明
```

### 1.1 smartparcel-server

`smartparcel-server` 是 SPS 的服务端项目，当前用于局域网验证。它提供统一的 `/api/v1` REST API，负责站点管理、网关同步、快递与标签绑定、取件确认、通知管理，以及与 EMQX 的 MQTT 基础集成。

主要技术栈：

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- MySQL
- Pydantic v2
- gmqtt
- Docker Compose
- EMQX

服务端当前采用开发模式认证：

- `X-Dev-User-Id`
- `X-Dev-Role`

同时预留了网关签名校验框架，用于验证网关侧请求来源。

### 1.2 smartparcel-gateway

`smartparcel-gateway` 是 SPS 的本地边缘网关项目，运行在 Linux 设备、开发电脑或后续树莓派/小型主机上。它负责连接本地设备与远程服务端，在局域网验证阶段提供 mock NFC / mock BLE 流程。

主要能力：

- 本地 SQLite 离线数据存储
- HTTP/HTTPS 与服务端同步
- MQTT 接收服务端命令与上报事件
- HMAC-SHA256 网关签名鉴权
- heartbeat 心跳上报
- sync pull / sync push 数据同步
- mock NFC 刷卡触发 TAG_WAKE
- 预留 PN532 NFC 与 BLE 标签接口

## 2. 系统实现方式

当前 SPS 的核心实现方式可以概括为：

```text
服务端 FastAPI + MySQL + EMQX
        ↑            ↓
   HTTP REST       MQTT Topic
        ↑            ↓
本地网关 Python + SQLite + mock NFC/BLE
```

### 2.1 服务端实现

服务端使用 FastAPI 提供 REST API，使用 MySQL 存储业务数据，使用 Alembic 管理数据库迁移。EMQX 用于后续命令下发、网关状态上报和事件通信。

核心接口包括：

- `GET /api/v1/health`
- `GET /api/v1/version`
- `POST /api/v1/stations`
- `POST /api/v1/parcels`
- `POST /api/v1/pickup/confirm`
- `GET /api/v1/gateways/{gateway_id}/sync/pull`
- `POST /api/v1/gateways/{gateway_id}/sync/push`
- `POST /api/v1/gateways/{gateway_id}/events`

### 2.2 网关实现

网关使用 Python 实现命令行入口，使用 SQLite 保存本地离线数据。网关启动后会完成数据库初始化、服务端健康检查、MQTT 连接、心跳上报、任务拉取和事件推送。

主要 CLI 命令包括：

- `python -m gateway.main init-db`
- `python -m gateway.main health`
- `python -m gateway.main heartbeat`
- `python -m gateway.main sync-pull`
- `python -m gateway.main sync-push`
- `python -m gateway.main mock-nfc CARD_UID`
- `python -m gateway.main run`
- `python -m gateway.main list-parcels`
- `python -m gateway.main list-tags`
- `python -m gateway.main list-tasks`

### 2.3 通信方式

#### HTTP REST

服务端和网关之间通过 HTTP REST 完成核心业务同步。

网关请求会携带：

- `X-Gateway-Code`
- `X-Gateway-Timestamp`
- `X-Gateway-Nonce`
- `X-Gateway-Signature`

网关签名用于保证请求来源可信，并为后续公网部署预留安全基础。

#### MQTT

MQTT 当前用于局域网阶段的基础通信验证，后续可用于任务下发、状态上报和事件通知。

Topic 约定：

- 服务端下发命令：`server/{gateway_code}/commands`
- 网关上报事件：`gateway/{gateway_code}/events`
- 网关上报状态：`gateway/{gateway_code}/status`

## 3. 业务流程设计

### 3.1 入库流程

```text
管理员创建快递信息
↓
绑定包裹与标签
↓
服务端保存包裹、标签、绑定关系
↓
网关通过 sync-pull 拉取待同步数据
↓
网关写入本地 SQLite
```

### 3.2 取件流程

```text
用户在门禁处刷 NFC / RFID
↓
本地网关识别用户凭证
↓
网关查询本地待取件包裹
↓
网关找到对应标签绑定关系
↓
网关创建 TAG_WAKE 任务
↓
mock BLE 或后续真实 BLE 标签执行亮灯/蜂鸣
↓
用户找到包裹并确认取件
↓
网关生成 pickup event
↓
网关通过 sync-push 回传服务端
↓
服务端完成取件状态更新
```

## 4. 局域网完整测试流程

以下流程用于验证 SPS 当前阶段的最小闭环。

### 4.1 启动服务端基础服务

进入服务端目录：

```powershell
cd smartparcel-server
```

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

安装依赖：

```powershell
pip install -r requirements.txt
```

复制配置文件：

```powershell
copy .env.example .env
```

启动 MySQL 和 EMQX：

```powershell
docker compose up -d mysql emqx
```

执行数据库迁移：

```powershell
python -m alembic upgrade head
```

启动 FastAPI：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

### 4.2 测试服务端健康检查

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/health"
```

如果返回正常状态，说明服务端 API 已启动。

### 4.3 创建站点

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

### 4.4 创建快递测试数据

```powershell
$headers = @{
  "Content-Type" = "application/json"
  "X-Dev-User-Id" = "1"
  "X-Dev-Role" = "LOCAL_ADMIN"
}

$body = @{
  parcel_code = "P20260528001"
  station_id = 1
  receiver_user_id = 2
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:18000/api/v1/parcels" `
  -Headers $headers `
  -Body $body
```

### 4.5 启动本地网关

新开一个终端，进入网关目录：

```powershell
cd smartparcel-gateway
```

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

安装依赖：

```powershell
pip install -r requirements.txt
```

复制配置文件：

```powershell
copy .env.example .env
```

检查 `.env` 中的服务端地址，例如：

```env
SERVER_BASE_URL=http://127.0.0.1:18000
GATEWAY_CODE=GW001
STATION_ID=1
MOCK_NFC_ENABLED=true
MOCK_BLE_ENABLED=true
```

初始化 SQLite：

```powershell
python -m gateway.main init-db
```

测试网关连接服务端：

```powershell
python -m gateway.main health
```

发送心跳：

```powershell
python -m gateway.main heartbeat
```

### 4.6 执行同步测试

从服务端拉取数据：

```powershell
python -m gateway.main sync-pull
```

查看本地包裹、标签或任务数据：

```powershell
python -m gateway.main list-parcels
python -m gateway.main list-tags
python -m gateway.main list-tasks
```

推送本地事件到服务端：

```powershell
python -m gateway.main sync-push
```

### 4.7 执行 mock NFC 取件测试

使用 mock NFC 模拟门禁刷卡：

```powershell
python -m gateway.main mock-nfc CARD_UID
```

预期流程：

```text
网关读取 CARD_UID
↓
查询 local_nfc_credentials
↓
查询用户待取件包裹
↓
查询包裹绑定标签
↓
创建 TAG_WAKE 任务
↓
调用 mock BLE
↓
写入 pickup event
↓
写入 sync queue
```

之后执行：

```powershell
python -m gateway.main sync-push
```

如果服务端能够收到取件事件，说明局域网软件闭环验证通过。

### 4.8 启动网关常驻运行模式

```powershell
python -m gateway.main run
```

常驻模式会执行：

- 初始化本地数据库
- 服务端健康检查
- MQTT 连接
- heartbeat 定时上报
- sync pull 定时拉取
- sync push 定时推送

## 5. 当前验证目标

当前阶段的目标不是直接上线，而是完成局域网最小闭环验证：

```text
服务端启动
↓
MySQL / EMQX 启动
↓
网关初始化 SQLite
↓
网关 health 成功
↓
网关 heartbeat 成功
↓
服务端创建站点、快递与标签绑定数据
↓
网关 sync-pull 拉取数据
↓
网关 mock-nfc 模拟用户刷卡
↓
网关生成 TAG_WAKE 和 pickup event
↓
网关 sync-push 回传服务端
↓
服务端更新取件状态
```

完成该闭环后，即可证明 SPS 的服务端与本地网关核心架构可运行。

## 6. 后续开发方向

后续可以按以下顺序推进：

1. 统一服务端与网关的 HMAC 签名规则。
2. 补充完整的包裹、标签、绑定关系初始化接口。
3. 将 mock NFC 替换为 PN532 / RC522 实际读卡器。
4. 将 mock BLE 替换为真实 BLE 标签控制。
5. 接入微信小程序，完成管理员入库与用户取件入口。
6. 增加正式认证，例如 JWT / 微信登录。
7. 迁移到公网服务器，并启用 HTTPS、MQTT TLS、密钥轮换和日志监控。

## 7. 子项目文档

更多细节请查看：

- `smartparcel-server/README.md`
- `smartparcel-gateway/README.md`
