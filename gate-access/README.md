# gate-access

`gate-access` 是 SmartParcelStation 的门禁读卡器固件子工程。当前硬件组合为：

- 主控：ESP32P4，目标开发板为 WT9932P4-TINY。
- 网络：ESP8266 串口 Wi-Fi 模块，使用 AT 指令连接 gateway 热点。
- 读卡：PN532，使用 I2C 读取 ISO14443A 卡 UID。
- 屏幕：WT9932P4-TINY 板载 DSI FPC 连接的 ST7701S 480x640 MIPI 屏。

当前阶段目标是最小可验证演示：固件只读取卡 UID，并通过 ESP8266 串口 Wi-Fi 以 HTTP POST 调用 `smartparcel-gateway` 本地门禁接口。固件不实现取件会话、包裹匹配、标签唤醒、审计上传等业务逻辑，这些判断继续留在 gateway。

## 当前已做

- 初始化 NVS。
- 初始化 ESP8266 UART，并发送基础 AT 指令。
- 连接默认 gateway 热点 `SPS_GATEWAY_AP`。
- 通过普通明文 HTTP POST 调用 `POST /local/gate/access-card`。
- 初始化 PN532 I2C，读取 ISO14443A UID。
- 串口日志打印启动、联网、读卡、上传和授权结果。
- 保留统一的 `display_ui` 接口；屏幕驱动暂时是日志 stub，等待 ST7701S MIPI DSI 初始化细节确认。

## 当前不做

- 门锁控制。
- 摄像头二维码。
- HTTPS。
- NVS 配网。
- 完整触摸 UI。
- 固件内取件业务逻辑。

## 默认配置

所有硬件引脚和联调参数集中在 `main/app_config.h`。

gateway 地址：

```c
#define SPS_GATEWAY_HOST "192.168.4.1"
#define SPS_GATEWAY_PORT 19000
#define SPS_GATEWAY_PATH "/local/gate/access-card"
#define SPS_GATEWAY_URL  "http://192.168.4.1:19000"
```

Wi-Fi 热点：

```c
#define SPS_WIFI_SSID     "SPS_GATEWAY_AP"
#define SPS_WIFI_PASSWORD "12345678"
```

读卡器编号：

```c
#define SPS_READER_ID "GATE01"
```

## gateway 请求

固件刷卡后发送：

```http
POST /local/gate/access-card HTTP/1.1
Host: 192.168.4.1:19000
Content-Type: application/json
Connection: close
```

请求 JSON：

```json
{
  "reader_id": "GATE01",
  "credential_type": "CARD_UID",
  "credential_value": "04A1B2C3D4"
}
```

`credential_value` 来自 PN532 读到的 UID，格式为大写十六进制字符串，不带空格。

## 编译和烧录

使用 ESP-IDF，不使用 Arduino：

```powershell
cd gate-access
idf.py set-target esp32p4
idf.py build
idf.py -p COMx flash monitor
```

如果已经有旧 `sdkconfig`，请先删除后重新 `set-target esp32p4`。本仓库的 `sdkconfig.defaults` 已设置默认目标为 `esp32p4`。

## 预期串口日志

```text
ESP32P4 boot
SPS Gate P4 booting...
ESP8266 init...
Connecting SPS_GATEWAY_AP...
ESP8266 AT init ok
WiFi ready
Gateway ready
PN532 init ok
PN532 ready
Tap card
Card detected UID = ...
Uploading UID...
POST /local/gate/access-card
Gateway access granted
```

如果 gateway 拒绝，应看到 `Gateway access denied`。如果网络异常，应看到 `Network error`。如果 PN532 初始化或轮询异常，应看到 `PN532 error`。

## gateway 侧联调

启动 gateway 本地 API：

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main init-db
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

注册真实卡 UID：

```powershell
python -m gateway.main register-nfc-credential --credential-type CARD_UID --credential-value 04A1B2C3D4 --user-id 2
```

请把 `04A1B2C3D4` 替换成固件串口日志打印的真实 UID。

## 屏幕说明

当前 `display_ui.c` 先使用日志 stub，不阻塞 ESP8266、PN532 和 HTTP 上报联调。后续确认 WT9932P4-TINY 的 BSP、ST7701S MIPI DSI 初始化序列、背光和复位引脚后，再把 `display_ui` 替换为真实屏幕显示实现。
