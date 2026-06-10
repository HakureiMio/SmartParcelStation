# 标签 BLE 与网关闭环流程

## 1. 目标

本文说明当前推荐的 BLE 标签闭环测试流程。目标是验证：

```text
员工小程序
  -> smartparcel-gateway local API
  -> BLE_BACKEND=mock/real
  -> nRF52810 标签 GATT Service
  -> RGB LED / 蜂鸣器
```

当前阶段不验证生产级 HTTPS、正式微信发布域名、完整取件业务和云端远程控制。

## 2. 链路图

```text
smartparcel-miniprogram pages/staff-ble-tags
  -> services/gateway-api.js
  -> gatewayBaseUrl
  -> POST /local/tags/scan
  -> POST /local/tags/register-from-ble
  -> POST /local/tags/{tag_id}/connect
  -> POST /local/tags/{tag_id}/wake
  -> POST /local/tags/{tag_id}/stop
  -> GET  /local/tags/{tag_id}/status
  -> BLE_BACKEND=mock/real
  -> nRF52810 SPS Tag GATT Service
```

## 3. 标签命名规则

默认测试 BLE 名称：

```text
SPS-F01-20260610-0001
```

格式：

```text
SPS-{factory_code}-{production_date}-{serial_no}
```

示例：

```text
SPS-F01-20260610-0001
SPS-F01-20260610-0002
SPS-F02-20260611-0001
```

## 4. 网关本地编号规则

标签第一次注册到 gateway 后，由 gateway 分配本地编号：

```text
tag_id = SPS-TAG-0001
display_name = 标签 001
tag_uid = SPS-F01-20260610-0001
```

`tag_uid` 和 `ble_name` 用于识别真实标签，`display_name` 用于员工端显示。

## 5. GATT 协议

UUID：

```text
Service UUID:       8f7e9000-5d1b-4c2f-9e8a-5f2f5b7b0001
CMD_WRITE UUID:    8f7e9001-5d1b-4c2f-9e8a-5f2f5b7b0001
EVENT_NOTIFY UUID: 8f7e9002-5d1b-4c2f-9e8a-5f2f5b7b0001
STATUS_READ UUID:  8f7e9003-5d1b-4c2f-9e8a-5f2f5b7b0001
```

命令帧：

```text
[0] 0xA5
[1] command
[2] payload_len
[3..] payload
[last] xor checksum
```

支持命令：

```text
PING
WAKE_TAG
STOP_ALERT
SET_BINDING
CLEAR_BINDING
READ_STATUS
```

## 6. gateway API

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

启动 gateway：

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main init-db
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

## 7. mock 测试流程

`.env` 设置：

```env
BLE_BACKEND=mock
```

健康检查：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:19000/local/health"
```

扫描：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:19000/local/tags/scan" `
  -ContentType "application/json" `
  -Body '{"timeout_sec":5}'
```

注册：

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

控制：

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

## 8. 真实 BLE 测试流程

1. 在 nRF Connect SDK / Nordic Toolchain Terminal 中编译固件。
2. 烧录 `clip-node-nrf52810`。
3. 打开 RTT 日志，确认 `BLE name: SPS-F01-20260610-0001`。
4. 断开电脑蓝牙设置中可能占用标签的连接。
5. gateway `.env` 设置 `BLE_BACKEND=real`。
6. 重启 gateway local API。
7. 执行 `/local/tags/scan`。
8. 注册扫描到的真实标签。
9. 调用 `/connect`。
10. 调用 `/wake`。
11. 观察 RGB LED 和蜂鸣器。
12. 调用 `/stop`。
13. 调用 `/status`。

## 9. 小程序真机调试

开发者工具在电脑上运行时可使用：

```js
gatewayBaseUrl: 'http://127.0.0.1:19000'
```

手机真机调试时必须改为：

```js
gatewayBaseUrl: 'http://192.168.x.x:19000'
```

手机上的 `127.0.0.1` 是手机自己，不是电脑或 gateway。手机和 gateway 必须在同一局域网。

小程序操作路径：

```text
首页 -> 员工入口 -> 员工登录 -> BLE 标签管理
```

## 10. 常见问题

扫描不到真实标签：

```text
1. 标签是否已上电。
2. 固件是否已烧录。
3. BLE 名称是否为 SPS-F01-20260610-0001。
4. gateway 设备是否有蓝牙适配器。
5. Windows/Linux 蓝牙权限是否可用。
6. BLE_BACKEND 是否已经改为 real 并重启 local API。
7. 标签是否已经被其他设备连接占用。
```

小程序访问失败：

```text
1. gateway local API 是否正在监听 0.0.0.0:19000。
2. 手机和 gateway 是否在同一局域网。
3. gatewayBaseUrl 是否使用局域网 IP。
4. 防火墙是否允许 19000 端口。
5. 微信开发者工具是否按开发阶段要求处理合法域名校验。
```
