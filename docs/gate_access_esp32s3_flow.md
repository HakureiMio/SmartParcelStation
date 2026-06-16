# ESP32S3 门禁读卡器联调说明

本文档补充 `gate-access-esp32s3` 与 `smartparcel-gateway` 的联调关系。当前阶段目标是毕业设计局域网硬件闭环演示，不要求生产级安全、HTTPS 或正式微信登录。

## 职责边界

```text
ESP32S3 + PN532
  -> 读取卡 UID
  -> POST /local/gate/access-card
  -> 打印 gateway 返回结果

smartparcel-gateway
  -> 查询 local_nfc_credentials
  -> 查询待取包裹和本地标签绑定
  -> 创建 pickup_session
  -> 创建 TAG_WAKE task
  -> mock BLE 或 real BLE 唤醒标签
  -> sync-push 上传审计事件
```

ESP32S3 固件不保存用户隐私、不判断包裹归属、不直接控制标签、不参与 server 同步细节。

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
python -m gateway.main inbound-parcel --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --receiver-user-id 2 --receiver-name-masked "张*" --shelf-code A03
python -m gateway.main register-tag --tag-id TAG001
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

真机刷卡前，需要先用串口日志确认真实 UID，然后把示例里的 `CARD_UID_001` 替换成真实 UID 并注册到 `local_nfc_credentials`。

## 固件准备

编辑：

```text
gate-access-esp32s3/main/app_config.h
```

重点确认：

```c
#define SPS_WIFI_SSID      "SPS_GATEWAY_AP"
#define SPS_WIFI_PASSWORD  "12345678"
#define SPS_GATEWAY_URL    "http://192.168.4.1:19000"
#define SPS_READER_ID      "GATE01"
```

编译和烧录：

```powershell
cd gate-access-esp32s3
idf.py set-target esp32s3
idf.py build
idf.py -p COMx flash monitor
```

## 预期日志

```text
Wi-Fi connecting
Wi-Fi connected, IP = ...
PN532 init ok
Card detected UID = ...
POST /local/gate/access-card
Gateway access granted
```

如果 UID 未注册或没有待取包裹，预期看到：

```text
Gateway access denied
```

如果 gateway 未启动、IP 不通或 JSON 异常，预期看到：

```text
Gateway request failed
```

## 人工确认清单

1. PN532 模块是否处于 I2C 模式。
2. ESP32S3 开发板 GPIO 8/9/10/11 是否可用于外设连接。
3. PN532 是否需要额外 I2C 上拉电阻。
4. gateway 热点或局域网 IP 是否确认为 `SPS_GATEWAY_URL`。
5. 真实卡 UID 是否已注册到 gateway 的 `local_nfc_credentials`。
6. gateway 当前使用 mock BLE 还是 real BLE。
