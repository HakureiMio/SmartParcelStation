# SmartParcel Gateway

## 1. 网关职责

`smartparcel-gateway` 是站点本地网关项目，负责局域网内的本地业务、SQLite 缓存、标签主数据和 BLE 控制。它是智能寻物标签的本地主数据中心，不是中心账号系统。

gateway 当前负责：

- 本地 SQLite 数据库。
- 标签注册、标签本地编号和员工端显示名。
- BLE 标签扫描、连接、唤醒、停止和状态读取。
- 本地取件认证、mock NFC 和门禁读卡原型。
- 与 `smartparcel-server` 的 `sync-push` / `sync-pull`。
- HMAC 网关签名、heartbeat 和同步审计。

## 2. 当前推荐闭环：员工小程序控制 BLE 标签

当前推荐验证闭环是：

```text
smartparcel-miniprogram 员工端 BLE 标签管理
  -> smartparcel-gateway local API
  -> BLE_BACKEND=mock 或 BLE_BACKEND=real
  -> nRF52810 标签 GATT Service
  -> RGB LED / 蜂鸣器
```

gateway 当前已提供 BLE 标签管理 local API，并支持 `BLE_BACKEND=mock/real`。

- `mock` 后端用于无硬件演示。
- `real` 后端通过 `bleak` 扫描和控制真实 BLE 标签。
- 员工 BLE 标签管理接口已经支持 mock/real。
- 门禁 `gate-access-card` 当前仍以原 mock BLE 流程为主，后续再迁移到 real BLE。

## 3. 环境准备

```powershell
cd smartparcel-gateway
Remove-Item -Recurse -Force .\.venv -ErrorAction SilentlyContinue
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

检查不要混入 nRF 依赖：

```powershell
python -m pip show west
python -m pip show pyelftools
```

预期：

```text
WARNING: Package(s) not found: west
WARNING: Package(s) not found: pyelftools
```

`smartparcel-gateway/.venv` 只用于 gateway Python 项目，不用于编译 `clip-node-nrf52810`。

## 4. .env 配置

复制配置：

```powershell
copy .env.example .env
```

关键配置项：

```env
GATEWAY_CODE=GW001
GATEWAY_SECRET=gw-secret-demo
STATION_ID=1
SERVER_BASE_URL=http://127.0.0.1:18000
SQLITE_PATH=./data/gateway.db
BLE_BACKEND=mock
```

`BLE_BACKEND` 可选：

```env
BLE_BACKEND=mock
BLE_BACKEND=real
```

## 5. 启动 local API

```powershell
python -m gateway.main init-db
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

健康检查：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:19000/local/health"
```

## 6. BLE_BACKEND=mock/real

`BLE_BACKEND=mock`：

- 不需要硬件。
- 扫描会返回固定测试标签 `SPS-F01-20260610-0001`。
- 适合小程序页面演示和 API 闭环测试。

`BLE_BACKEND=real`：

- 需要 gateway 设备具备蓝牙适配器。
- 需要系统允许 Python/`bleak` 扫描和连接 BLE 设备。
- 真实标签不能被其他设备持续占用连接。

## 7. BLE 标签管理 API

主要接口：

```text
GET  /local/health
POST /local/tags/scan
POST /local/tags/register-from-ble
GET  /local/tags
GET  /local/tags/{tag_id}
POST /local/tags/{tag_id}/connect
POST /local/tags/{tag_id}/wake
POST /local/tags/{tag_id}/stop
GET  /local/tags/{tag_id}/status
```

`POST /local/tags/scan` 请求示例：

```json
{
  "timeout_sec": 5
}
```

`POST /local/tags/register-from-ble` 请求示例：

```json
{
  "ble_name": "SPS-F01-20260610-0001",
  "ble_address": "MOCK:TAG:FACTORY:0001"
}
```

`POST /local/tags/{tag_id}/wake` 请求示例：

```json
{
  "color": "BLUE",
  "duration_sec": 30
}
```

## 8. 标签命名与本地编号规则

真实标签推荐使用出厂 BLE 名称：

```text
SPS-F01-20260610-0001
```

格式：

```text
SPS-{factory_code}-{production_date}-{serial_no}
```

注册到 gateway 后，gateway 分配本地编号：

```text
tag_id = SPS-TAG-0001
display_name = 标签 001
tag_uid = SPS-F01-20260610-0001
```

员工端列表优先展示 `display_name`，详情页展示 `tag_id`、`tag_uid`、`ble_name`、`ble_address`、状态、电池和最近连接时间。

## 9. 与 server 同步

gateway 与 server 的关系：

- gateway 通过 `heartbeat` 上报在线状态。
- gateway 通过 `sync-push` 上传入站、取件、门禁审计和标签异常摘要。
- gateway 通过 `sync-pull` 拉取 server 侧任务。
- server 不直接控制 BLE 标签。
- server 不保存完整标签实时状态。

常用命令：

```powershell
python -m gateway.main health
python -m gateway.main heartbeat
python -m gateway.main sync-push
python -m gateway.main sync-pull
```

## 10. mock NFC / 门禁流程当前状态

`mock-nfc` 和 `gate-access-card` 是历史阶段 A 的本地门禁验证流程。当前仍可用于演示本地认证、取件会话、`TAG_WAKE` task 和同步审计。

需要注意：

- 员工 BLE 标签管理接口已经支持 mock/real。
- 门禁 `gate-access-card` 当前仍以旧 mock BLE 流程为主。
- 不要把门禁刷卡流程理解为已经完全迁移到真实 BLE。

历史 mock NFC / 阶段 A 流程见 `docs/legacy_stage_a_mock_flow.md`。门禁读卡流程设计见 `docs/gateway_gate_access_flow.md`。

## 11. 测试流程

### 11.1 初始化数据库并启动 local API

```powershell
copy .env.example .env
python -m gateway.main init-db
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

### 11.2 mock BLE 标签扫描

`.env` 设置：

```env
BLE_BACKEND=mock
```

重启 local API 后执行：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:19000/local/tags/scan" `
  -ContentType "application/json" `
  -Body '{"timeout_sec":5}'
```

预期返回包含：

```text
SPS-F01-20260610-0001
```

### 11.3 注册标签

```powershell
$body = @{
  ble_name = "SPS-F01-20260610-0001"
  ble_address = "MOCK:TAG:FACTORY:0001"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:19000/local/tags/register-from-ble" `
  -ContentType "application/json" `
  -Body $body
```

预期：

```text
tag_id = SPS-TAG-0001
display_name = 标签 001
tag_uid = SPS-F01-20260610-0001
```

### 11.4 查看标签列表和详情

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:19000/local/tags"
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:19000/local/tags/SPS-TAG-0001"
```

### 11.5 connect、wake、stop、status

```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:19000/local/tags/SPS-TAG-0001/connect"

$wakeBody = @{
  color = "BLUE"
  duration_sec = 30
} | ConvertTo-Json

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:19000/local/tags/SPS-TAG-0001/wake" `
  -ContentType "application/json" `
  -Body $wakeBody

Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:19000/local/tags/SPS-TAG-0001/stop"
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:19000/local/tags/SPS-TAG-0001/status"
```

### 11.6 真实 BLE 测试

`.env` 设置：

```env
BLE_BACKEND=real
```

重启 local API 后执行：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:19000/local/tags/scan" `
  -ContentType "application/json" `
  -Body '{"timeout_sec":5}'
```

预期扫描到真实标签：

```text
SPS-F01-20260610-0001
```

## 12. 常见问题

扫描不到真实标签时，优先检查：

```text
1. 标签是否已上电。
2. 固件是否已烧录。
3. BLE 名称是否为 SPS-F01-20260610-0001。
4. gateway 设备是否有蓝牙适配器。
5. Windows/Linux 蓝牙权限是否可用。
6. BLE_BACKEND 是否已经改为 real 并重启 local API。
7. 标签是否已经被其他设备连接占用。
```

如果小程序真机访问失败，检查 `gatewayBaseUrl` 是否为 gateway 局域网 IP，而不是 `127.0.0.1`。
