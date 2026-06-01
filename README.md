# SmartParcelStation

SmartParcelStation（SPS）是一个面向小型快递站场景的智能包裹管理与辅助取件系统。当前项目处于局域网验证阶段，重点验证“服务端 + 本地网关 + 智能夹具节点”的核心链路：服务端负责业务数据、任务下发与同步管理，本地网关负责本地离线缓存、门禁/NFC 触发、BLE 标签通信与事件回传，智能夹具节点负责包裹侧的亮灯、蜂鸣、取下检测、电池检测和低功耗运行。

本仓库采用单仓库多目录结构，便于在早期阶段统一维护服务端、网关和固件之间的接口约定，降低联调成本。

## 1. 项目构成

```text
SmartParcelStation/
├─ smartparcel-server/        # 服务端项目：FastAPI + MySQL + EMQX
├─ smartparcel-gateway/       # 本地网关项目：SQLite + HTTP/MQTT + NFC/BLE 接入
├─ clip-node-nrf52810/        # 智能夹具节点固件：nRF52810 + Zephyr
└─ README.md                  # 项目总说明
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

同时预留网关签名校验框架，用于验证网关侧请求来源。

### 1.2 smartparcel-gateway

`smartparcel-gateway` 是 SPS 的本地边缘网关项目，运行在 Linux 设备、开发电脑或后续树莓派/小型主机上。它负责连接本地设备与远程服务端，在局域网验证阶段提供 mock NFC / mock BLE 流程，并为后续接入 PN532 与真实 BLE 标签做准备。

主要能力：

- 本地 SQLite 离线数据存储
- HTTP/HTTPS 与服务端同步
- MQTT 接收服务端命令与上报事件
- HMAC-SHA256 网关签名鉴权
- heartbeat 心跳上报
- sync pull / sync push 数据同步
- mock NFC 刷卡触发 TAG_WAKE
- mock BLE 模拟标签亮灯/蜂鸣
- 预留 PN532 NFC 与 BLE 标签接口

### 1.3 clip-node-nrf52810

`clip-node-nrf52810` 是 SPS 的智能夹具节点固件工程，基于 nRF Connect SDK / Zephyr 与 nRF52810 实现。该目录对应快递包裹侧的低功耗标签/夹具节点，用于接收网关 BLE 指令并执行亮灯、蜂鸣、状态上报和取下检测。

主要能力：

- BLE 通信模块骨架
- 夹具状态机：idle / bound / authorized / alerting / removed / confirmed / low_battery / exception
- 轻量二进制协议解析与分发
- 事件上报接口
- RGB PWM 控制
- 蜂鸣器模式控制
- GPIO 取下检测与软件消抖
- ADC 电池检测与电量等级
- 低功耗行为约束

构建方式示例：

```bash
cd clip-node-nrf52810
west build -b clip_node_nrf52810 . -p
west flash
```

当前固件仍处于骨架阶段，默认引脚留空，后续需要根据实际硬件原理图完善 `docs/hardware_pins.md`。

## 2. 系统实现方式

当前 SPS 的核心实现方式可以概括为：

```text
服务端 FastAPI + MySQL + EMQX
        ↑            ↓
   HTTP REST       MQTT Topic
        ↑            ↓
本地网关 Python + SQLite + NFC/BLE
        ↑            ↓
  BLE GATT / Binary Frame
        ↑            ↓
nRF52810 智能夹具节点 + RGB + Buzzer + Battery + Low Power
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

### 2.3 夹具节点实现

夹具节点固件不负责用户、包裹、数据库和云同步逻辑，只保留和硬件执行直接相关的最小功能。网关通过 BLE 向夹具节点发送轻量二进制命令，夹具节点根据命令进入告警、确认、低电量或异常等状态。

该设计可以避免在 nRF52810 这类资源受限芯片上引入复杂 JSON 解析或业务数据库逻辑，同时减少隐私数据在包裹侧设备上的暴露。

### 2.4 通信方式

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

#### BLE / Binary Frame

网关与智能夹具节点之间通过 BLE 通信。固件侧采用轻量二进制帧，不在夹具端解析复杂业务对象。

典型命令包括：

- 绑定标签
- 唤醒标签
- RGB 亮灯
- 蜂鸣提醒
- 停止提醒
- 状态查询
- 低电量上报
- 取下事件上报

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
↓
后续可通过 BLE 将必要绑定状态同步给夹具节点
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
网关通过 mock BLE 或真实 BLE 向夹具节点下发提醒命令
↓
夹具节点执行亮灯/蜂鸣
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

当前测试分为两个阶段：

- 阶段 A：软件 mock 闭环，验证 `server + gateway + mock NFC + mock BLE`。
- 阶段 B：固件接入闭环，验证 `server + gateway + NFC/mock NFC + nRF52810 clip node`。

建议优先完成阶段 A，再接入阶段 B。这样可以先证明服务端与网关业务链路可运行，再逐步替换真实硬件。

## 5. 阶段 A：软件 mock 闭环测试

### 5.1 启动服务端基础服务

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

### 5.2 测试服务端健康检查

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/health"
```

如果返回正常状态，说明服务端 API 已启动。

### 5.3 创建站点

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

#### 5.3.1 初始化开发占位用户（建议先执行）

`/api/v1/stations`、`/api/v1/parcels` 等接口默认启用开发态鉴权，会校验请求头：

- `X-Dev-User-Id`
- `X-Dev-Role`

若数据库中不存在对应用户，或角色不匹配，常见报错为：

- `User not found or inactive`
- `Role mismatch`

建议先执行一次初始化脚本（幂等，可重复执行）：

```powershell
cd smartparcel-server
$env:PYTHONPATH='.'
.venv\Scripts\python.exe scripts/init_dev_user.py
```

输出 `created` 或 `updated` 都表示可用。该脚本会确保存在：

- `id = 1`
- `role = SERVER_ADMIN`
- `is_active = true`

#### 5.3.2 常见问题排查

1. 创建站点时报一大串数据库异常  
通常是 `station_code` 重复（例如 `ST001` 已存在）。先查询站点列表再决定是否换编码：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/stations"
```

2. 创建快递时报外键错误（`receiver_user_id`）  
`receiver_user_id` 必须在 `users.id` 中存在。联调阶段可先不传该字段，或先创建对应用户。

#### 5.3.3 初始化收件人占位用户（用于 `receiver_user_id=2`）

如需按示例使用 `receiver_user_id = 2`，请先创建占位收件用户：

```powershell
cd smartparcel-server
$env:PYTHONPATH='.'
.venv\Scripts\python.exe scripts/init_dev_receiver_user.py
```

输出 `created` 或 `updated` 都表示可用。该脚本会确保存在：

- `id = 2`
- `role = USER`
- `is_active = true`

### 5.4 创建快递测试数据

```powershell
$headers = @{
  "Content-Type" = "application/json"
  "X-Dev-User-Id" = "1"
  "X-Dev-Role" = "SERVER_ADMIN"
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

若仅做最小联调（不依赖收件人外键），可使用不带 `receiver_user_id` 的请求：

```powershell
$headers = @{
  "Content-Type" = "application/json"
  "X-Dev-User-Id" = "1"
  "X-Dev-Role" = "SERVER_ADMIN"
}

$body = @{
  parcel_code = "P20260528002"
  station_id = 1
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:18000/api/v1/parcels" `
  -Headers $headers `
  -Body $body
```

### 5.5 启动本地网关

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

#### 5.5.1 先注册网关（`heartbeat` 前置步骤）

若未注册网关，执行 `python -m gateway.main heartbeat` 会返回 `404` 或 `gateway not found`。  
请先在服务端执行网关注册：

```powershell
$body = @{
  gateway_code = "GW001"
  station_id = 1
  device_secret_hash = "gw-secret-demo"
  status = "ACTIVE"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:18000/api/v1/gateways/register" `
  -ContentType "application/json" `
  -Body $body
```

然后检查并对齐 `smartparcel-gateway/.env`：

```env
GATEWAY_CODE=GW001
GATEWAY_SECRET=gw-secret-demo
STATION_ID=1
SERVER_BASE_URL=http://127.0.0.1:18000
```

发送心跳：

```powershell
python -m gateway.main heartbeat
```

### 5.6 执行同步测试

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

### 5.7 执行 mock NFC 取件测试

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

如果服务端能够收到取件事件，说明局域网软件 mock 闭环验证通过。

### 5.8 启动网关常驻运行模式

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

## 6. 阶段 B：nRF52810 固件接入测试

阶段 B 用于在阶段 A 通过后，将 mock BLE 替换为真实 nRF52810 智能夹具节点。

### 6.1 准备 nRF Connect SDK 环境

推荐使用 Windows + VS Code：

- Visual Studio Code
- nRF Connect for VS Code Extension Pack
- Nordic Toolchain Manager / nRF Connect SDK
- C/C++ Extension
- Cortex-Debug（可选）
- J-Link 或兼容 SWD 调试器

### 6.2 构建固件

进入固件目录：

```powershell
cd clip-node-nrf52810
```

在 nRF Connect Toolchain 终端中执行：

```bash
west build -b clip_node_nrf52810 . -p
```

### 6.3 烧录固件

通过 SWD 连接目标板：

```text
SWDIO  -> 模组 SWDIO
SWDCLK -> 模组 SWDCLK
VCC    -> 模组 VCC
GND    -> 模组 GND
RESET  -> 模组 RESET
```

烧录：

```bash
west flash
```

### 6.4 查看日志

推荐使用 RTT：

- VS Code nRF Connect 的 Serial/RTT Terminal
- J-Link RTT Viewer

固件默认开启 RTT 相关配置：

```text
CONFIG_USE_SEGGER_RTT=y
CONFIG_LOG_BACKEND_RTT=y
```

### 6.5 替换 mock BLE

当固件可正常启动并广播/连接后，逐步将网关侧 mock BLE 替换为真实 BLE 控制逻辑：

```text
mock BLE TAG_WAKE
↓
真实 BLE 扫描/连接
↓
发现 clip node GATT Service
↓
发送轻量二进制命令帧
↓
夹具节点执行亮灯/蜂鸣
↓
夹具节点上报状态/事件
↓
网关写入 pickup event / sync queue
```

### 6.6 验证真实标签提醒流程

推荐验证顺序：

1. 网关能扫描到 nRF52810 夹具节点。
2. 网关能连接夹具节点。
3. 网关能发送 TAG_WAKE / ALERT 命令。
4. 夹具节点 RGB 能亮起。
5. 夹具节点蜂鸣器能按时响起并自动停止。
6. 夹具节点能上报状态。
7. 网关能记录事件并通过 sync-push 回传服务端。

## 7. 当前验证目标

当前阶段的目标不是直接上线，而是完成局域网最小闭环验证。

### 7.1 软件 mock 最小闭环

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

### 7.2 硬件接入最小闭环

```text
nRF52810 固件构建成功
↓
SWD 烧录成功
↓
夹具节点启动并输出 RTT 日志
↓
网关发现并连接夹具节点
↓
用户 mock-nfc / NFC 刷卡
↓
网关向夹具节点发送提醒命令
↓
夹具节点亮灯/蜂鸣
↓
网关记录事件
↓
网关 sync-push 回传服务端
```

完成以上闭环后，即可证明 SPS 的服务端、本地网关和智能夹具节点三端架构可运行。

## 8. 后续开发方向

后续可以按以下顺序推进：

1. 统一服务端与网关的 HMAC 签名规则。
2. 明确网关与夹具节点的 BLE GATT Service 与二进制帧协议。
3. 补充完整的包裹、标签、绑定关系初始化接口。
4. 完善 `clip-node-nrf52810/docs/hardware_pins.md` 的实际引脚映射。
5. 将 mock NFC 替换为 PN532 / RC522 实际读卡器。
6. 将 mock BLE 替换为真实 BLE 标签控制。
7. 接入微信小程序，完成管理员入库与用户取件入口。
8. 增加正式认证，例如 JWT / 微信登录。
9. 迁移到公网服务器，并启用 HTTPS、MQTT TLS、密钥轮换和日志监控。
10. 做夹具节点功耗实测：空闲电流、告警电流、日均电量消耗。

## 9. 子项目文档

更多细节请查看：

- `smartparcel-server/README.md`
- `smartparcel-gateway/README.md`
- `clip-node-nrf52810/README.md`
