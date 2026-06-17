# gate-access 与 gateway 联调说明

本文档说明 `gate-access` 固件与 `smartparcel-gateway` 的联调关系。当前硬件为 ESP32P4 + ESP8266 AT + PN532 + ST7701S MIPI 屏，目标是局域网硬件闭环演示，不要求生产级安全、HTTPS 或正式微信登录。

## 职责边界

```text
ESP32P4 + PN532
  -> 读取卡 UID
  -> 通过 ESP8266 AT 连接 gateway 热点
  -> POST /local/gate/access-card
  -> 串口/屏幕显示 gateway 返回结果

smartparcel-gateway
  -> 查询 local_nfc_credentials
  -> 判断是否允许通行
  -> 继续处理取件会话、标签唤醒和审计同步
```

固件不保存用户隐私，不判断包裹归属，不直接控制标签，也不参与 server 同步细节。

## 固件请求

```json
{
  "reader_id": "GATE01",
  "credential_type": "CARD_UID",
  "credential_value": "04A1B2C3D4"
}
```

`credential_value` 来自 PN532 读到的 UID，格式为大写十六进制且不带空格。

## gateway 准备

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main init-db
python -m gateway.main register-nfc-credential --credential-type CARD_UID --credential-value CARD_UID_001 --user-id 2
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

真机刷卡前，需要先用串口日志确认真实 UID，然后把示例里的 `CARD_UID_001` 替换成真实 UID 并注册到 `local_nfc_credentials`。

## 固件准备

集中配置文件：

```text
gate-access/main/app_config.h
```

重点确认：

```c
#define SPS_GATEWAY_HOST "192.168.4.1"
#define SPS_GATEWAY_PORT 19000
#define SPS_GATEWAY_PATH "/local/gate/access-card"
#define SPS_WIFI_SSID "SPS_GATEWAY_AP"
#define SPS_WIFI_PASSWORD "12345678"
#define SPS_READER_ID "GATE01"
```

编译和烧录：

```powershell
cd gate-access
idf.py set-target esp32p4
idf.py build
idf.py -p COMx flash monitor
```

## 预期日志

```text
ESP32P4 boot
ESP8266 init...
Connecting SPS_GATEWAY_AP...
ESP8266 AT init ok
WiFi ready
Gateway ready
PN532 init ok
Card detected UID = ...
POST /local/gate/access-card
Gateway access granted
```

如果 UID 未注册或 gateway 判断不允许，预期看到：

```text
Gateway access denied
```

如果 gateway 未启动、ESP8266 未连接、IP 不通或 HTTP 响应异常，预期看到：

```text
Network error
```

## 人工确认清单

1. ESP8266 TX/RX 是否与 ESP32P4 GPIO43/GPIO44 交叉连接。
2. ESP8266 是否使用稳定 3.3V 供电并与 ESP32P4 共地。
3. PN532 是否处于 I2C 模式。
4. PN532 SDA/SCL 是否接到 GPIO20/GPIO21。
5. PN532 是否需要额外 I2C 上拉电阻。
6. gateway 热点 SSID、密码和 `192.168.4.1:19000` 是否符合现场网络。
7. 真实卡 UID 是否已注册到 gateway 的 `local_nfc_credentials`。
8. 屏幕驱动未接通时，串口日志是否仍能完整验证 ESP8266、PN532 和 HTTP 上报。
