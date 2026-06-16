# gate-access-esp32s3

`gate-access-esp32s3` 是 SmartParcelStation 的 ESP32S3 + PN532 门禁读卡器固件子工程。它只负责读取卡 UID，并通过局域网 HTTP 调用 `smartparcel-gateway` 的本地门禁 API，不在固件内实现取件会话、包裹匹配、标签唤醒或审计上传等业务逻辑。

## 与 smartparcel-gateway 的关系

固件刷卡后发送：

```http
POST {SPS_GATEWAY_URL}/local/gate/access-card
Content-Type: application/json
```

请求体示例：

```json
{
  "reader_id": "GATE01",
  "credential_type": "CARD_UID",
  "credential_value": "04A1B2C3D4"
}
```

gateway 继续负责本地认证、查询待取包裹、创建 `pickup_session`、创建 `TAG_WAKE` task、走 mock BLE 或后续 real BLE 唤醒标签，并通过 sync-push 上传审计事件。server 不参与门禁实时放行。

## 编译环境

- ESP-IDF，建议使用 ESP-IDF v5.x。
- 目标芯片：ESP32S3。
- 不使用 Arduino 框架。
- 依赖 ESP-IDF 自带组件：`esp_wifi`、`esp_http_client`、`cJSON`、`driver`、`nvs_flash`。

## 编译命令

```powershell
cd gate-access-esp32s3
idf.py set-target esp32s3
idf.py build
```

## 烧录命令

把 `COMx` 替换成真实串口：

```powershell
cd gate-access-esp32s3
idf.py -p COMx flash
```

## 串口监视命令

```powershell
cd gate-access-esp32s3
idf.py -p COMx monitor
```

也可以合并执行：

```powershell
idf.py -p COMx flash monitor
```

## Wi-Fi 与 gateway 地址配置

当前集中配置在：

```text
main/app_config.h
```

默认值：

```c
#define SPS_WIFI_SSID      "SPS_GATEWAY_AP"
#define SPS_WIFI_PASSWORD  "12345678"
#define SPS_GATEWAY_URL    "http://192.168.4.1:19000"
#define SPS_READER_ID      "GATE01"
```

当前阶段为了毕业设计局域网闭环演示，先使用明文 HTTP 和集中硬编码开发配置。后续如果要产品化，可迁移到 `Kconfig`、NVS 配网或安全凭据注入流程。

## PN532 引脚配置

PN532 默认使用 I2C，配置在：

```text
main/app_config.h
docs/pin_mapping.md
```

默认占位引脚：

```text
I2C SDA: GPIO 8
I2C SCL: GPIO 9
PN532 IRQ: GPIO 10，当前暂未使用
PN532 RST: GPIO 11，当前暂未使用
```

UID 会转换成大写十六进制字符串，不带空格，例如 `04A1B2C3D4`，并作为 `credential_value` 上传。

## gateway 侧联调准备

gateway 侧测试准备可以参考：

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

真实 PN532 读到的 UID 必须先注册到 gateway 的 `local_nfc_credentials`，否则 gateway 会拒绝访问。上面的 `CARD_UID_001` 是示例值；真机联调时请替换成串口日志打印的真实 UID。

## 典型测试流程

1. 启动 gateway，并确认 `http://gateway-ip:19000/local/health` 可访问。
2. 根据 gateway 所在网络修改 `main/app_config.h` 的 `SPS_WIFI_SSID`、`SPS_WIFI_PASSWORD` 和 `SPS_GATEWAY_URL`。
3. 编译、烧录并打开串口监视。
4. 确认日志出现 `Wi-Fi connected, IP = ...`。
5. 确认日志出现 `PN532 init ok`。
6. 把已注册 UID 的卡靠近 PN532。
7. 串口应打印 `Card detected UID = ...`、`POST /local/gate/access-card`，随后打印 `Gateway access granted` 或 `Gateway access denied`。
8. 在 gateway 侧观察取件会话、`TAG_WAKE` task、mock BLE 输出和审计事件。

## 当前限制

- 当前只读取 ISO14443A 卡 UID，不写卡，不读取扇区，不处理校园卡加密区。
- PN532 驱动是最小 I2C 实现，已包含 wake/SAMConfiguration/InListPassiveTarget 主流程，但不同 PN532 模块的 I2C 拨码、上拉和供电可能需要现场确认。
- IRQ/RST 引脚已预留但暂未参与驱动流程。
- Wi-Fi 配置和 gateway URL 当前在 `app_config.h` 中集中硬编码。
- 当前只做局域网 HTTP，不实现 HTTPS。
- 只做简单 UID 防重复上传，默认 3000 ms。
- gateway 返回字段按当前本地 API 解析，缺失字段不会导致固件崩溃；JSON 解析失败时会打印原始响应。

## 后续迁移方向

- 将 Wi-Fi、gateway URL、reader_id、引脚和 debounce 时间迁移到 `Kconfig` 或 NVS 配置。
- 根据真实 ESP32S3 开发板修订 GPIO，并视现场稳定性启用 PN532 RST/IRQ。
- 如果 PN532 模块切换到 SPI/UART，保持 `pn532_reader.h` 对外接口不变，只替换 `pn532_reader.c` 的底层传输。
- 门禁链路继续保持固件只上传 UID，业务判断留在 gateway。
- gateway 侧后续可从 mock BLE 迁移到 real BLE 标签唤醒。
