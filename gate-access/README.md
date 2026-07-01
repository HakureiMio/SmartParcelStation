# gate-access

`gate-access` 是 SmartParcelStation 的门禁读卡器固件子工程，使用 ESP-IDF，不使用 Arduino。

当前硬件组合：

- 主控：ESP32-P4，目标开发板为 WT9932P4-TINY。
- 网络：ESP8266 串口 Wi-Fi 模块，使用 AT 指令连接 gateway 热点。
- 读卡：PN532，通过 I2C 读取 ISO14443A 卡 UID。
- 屏幕：WT9932P4-TINY 板载 DSI FPC 连接的 ST7701S 480x640 MIPI DSI 屏。

当前阶段目标是最小可验证演示：固件读取卡 UID，并通过 ESP8266 串口 Wi-Fi 以 HTTP POST 调用 `smartparcel-gateway` 本地门禁接口。固件不实现取件会话、包裹匹配、标签唤醒、审计上传等业务逻辑，这些判断继续留在 gateway。

## 当前已实现

- 初始化 NVS。
- 初始化 ESP8266 UART，并发送基础 AT 指令。
- 连接默认 gateway 热点 `SPS_GATEWAY_AP`。
- 通过普通明文 HTTP POST 调用 `POST /local/gate/access-card`。
- 初始化 PN532 I2C，读取 ISO14443A UID。
- 串口日志打印启动、联网、读卡、上传和授权结果。
- `display_ui` 已接入 ST7701S MIPI DSI 初始化，并临时运行屏幕五色测试。

## 屏幕测试实现

当前 [main/display_ui.c](main/display_ui.c) 不是正式业务 UI，而是硬件验证用的五色轮播测试：

- 使用 `esp_lcd_new_dsi_bus` 创建 ESP32-P4 MIPI DSI bus。
- 使用 `esp_lcd_new_panel_io_dbi` 通过 DBI 向 ST7701S 发送初始化命令。
- 初始化序列来自目录中的 `4、初始化代码 ST7701S+28-480640_INIT.txt`。
- 使用 `esp_lcd_new_panel_dpi` 创建 480x640 DPI video panel。
- 使用 RGB565 格式刷全屏颜色。
- 启动 `lcd_color_test` FreeRTOS task，每 1 秒轮流显示：
  - red
  - green
  - blue
  - black
  - white

显示相关参数集中在 [main/app_config.h](main/app_config.h)：

```c
#define SPS_DISPLAY_WIDTH           480
#define SPS_DISPLAY_HEIGHT          640
#define SPS_DISPLAY_MIPI_DSI_LANES  1
#define SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS 500
#define SPS_DISPLAY_DPI_CLOCK_MHZ   24
#define SPS_DISPLAY_HSYNC_PW        10
#define SPS_DISPLAY_HSYNC_BP        20
#define SPS_DISPLAY_HSYNC_FP        40
#define SPS_DISPLAY_VSYNC_PW        2
#define SPS_DISPLAY_VSYNC_BP        8
#define SPS_DISPLAY_VSYNC_FP        12
#define SPS_DISPLAY_MIPI_DSI_PHY_LDO_CHAN 3
#define SPS_DISPLAY_MIPI_DSI_PHY_LDO_VOLTAGE_MV 2500
#define SPS_DISPLAY_BACKLIGHT_GPIO  GPIO_NUM_NC
#define SPS_DISPLAY_RESET_GPIO      GPIO_NUM_NC
```

注意：当前背光和 reset 引脚仍为 `GPIO_NUM_NC`。如果屏幕初始化日志正常但仍黑屏，需要优先确认板子的背光使能脚、reset 脚、DSI lane 数和实际屏幕时序。

## 当前不做

- 门锁控制。
- 摄像头二维码。
- HTTPS。
- NVS 配网。
- 完整触摸 UI。
- 固件内取件业务逻辑。

## 默认配置

所有硬件引脚和联调参数集中在 [main/app_config.h](main/app_config.h)。

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

先激活 ESP-IDF v6.0.1 PowerShell 环境：

```powershell
. C:\Espressif\tools\Microsoft.v6.0.1.PowerShell_profile.ps1
```

首次配置目标芯片：

```powershell
idf.py set-target esp32p4
```

编译：

```powershell
idf.py build
```

烧录，当前调试使用 `COM9`：

```powershell
idf.py -p COM9 flash
```

需要看串口日志时：

```powershell
idf.py -p COM9 monitor
```

## ESP32-P4 rev v1.3 兼容配置

当前板子的芯片版本是 ESP32-P4 revision v1.3。ESP-IDF 默认可能生成要求 v3.1 以上芯片的 bootloader，烧录时会报类似错误：

```text
bootloader/bootloader.bin requires chip revision [v3.1 - v3.99], this chip is revision v1.3
```

芯片 revision 是硅片硬件版本，不能通过固件升级。项目已在 `sdkconfig.defaults` 中固定为支持 rev v1.x：

```text
CONFIG_IDF_TARGET="esp32p4"
CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y
CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y
CONFIG_ESP32P4_REV_MIN_100=y
CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_360=y
```

rev v1.x 下 CPU 频率使用 360MHz，而不是较新 P4 revision 可用的 400MHz。

## PSRAM 配置

480x640 RGB565 全屏帧缓冲至少需要约 600KB。未启用 PSRAM 时，运行日志会出现：

```text
lcd.dsi: esp_lcd_new_panel_dpi(...): no memory for frame buffer
display_ui: create MIPI DPI panel failed
ESP_ERR_NO_MEM
```

因此当前项目启用了 ESP32-P4 PSRAM：

```text
CONFIG_SPIRAM=y
CONFIG_SPIRAM_MODE_HEX=y
CONFIG_SPIRAM_SPEED_200M=y
```

因为当前芯片是 rev v1.3，PSRAM 使用 200MHz；不要切到只适合新 revision 的 250MHz。

## set-target 问题记录

最开始执行 `idf.py set-target esp32p4` 时遇到过这个错误：

```text
Directory 'D:\Project\SmartParcelStation\gate-access\build' doesn't seem to be a CMake build directory.
Refusing to automatically delete files in this directory.
Delete the directory manually to 'clean' it.
Adding "set-target"'s dependency "fullclean" to list of commands with default set of options.
Executing action: fullclean
```

原因是 `build` 目录已经存在，但里面不是 ESP-IDF/CMake 认可的构建目录。`set-target` 会触发 `fullclean`，ESP-IDF 为避免误删用户文件，拒绝自动清理这个目录。

处理方法：

1. 确认 `build` 目录中没有需要保留的文件。
2. 手动删除 `build` 目录。
3. 重新执行：

```powershell
idf.py set-target esp32p4
```

随后又遇到组件依赖问题：`main/CMakeLists.txt` 中原本依赖 `json`，但当前工程通过 ESP-IDF component manager 使用的是 `espressif/cjson`，实际组件名为 `espressif__cjson`。

解决方法：

- 新增 [main/idf_component.yml](main/idf_component.yml)，声明：

```yaml
dependencies:
  espressif/cjson: "^1.7.19"
```

- 将 [main/CMakeLists.txt](main/CMakeLists.txt) 中的 `json` 改为 `espressif__cjson`。
- 同时补齐 ESP-IDF v6 分拆后的驱动依赖：

```cmake
REQUIRES
    driver
    esp_driver_gpio
    esp_driver_i2c
    esp_driver_uart
    esp_event
    esp_hw_support
    esp_lcd
    esp_timer
    nvs_flash
    espressif__cjson
```

## 预期串口日志

正常启动时应能看到类似日志：

```text
ESP32P4 boot
ST7701S color test started (480x640)
LCD color test: red
LCD color test: green
LCD color test: blue
LCD color test: black
LCD color test: white
SPS Gate P4 booting...
ESP8266 init...
Connecting SPS_GATEWAY_AP...
ESP8266 AT init ok
WiFi ready
Gateway ready
PN532 init ok
PN532 ready
Tap card
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
# Stage 4: gate reader firmware

## Hardware

- ESP32-P4 drives the 480×640 ST7701S MIPI-DSI display.
- ESP8266 AT firmware is connected over UART1 and joins the gateway AP.
- PN532 is connected in HSU mode over UART2. UID bytes are converted to uppercase hexadecimal
  without separators, for example `04A1B2C3D4`.
- A separate NTAG213/NTAG215 should be attached beside the gate for phone NFC authentication.

Check `docs/pin_mapping.md` before wiring. The PN532 mode switches must be set to HSU before power-on.

## Configuration

Demo defaults in `main/app_config.h` are deliberately non-personal:

```c
#define SPS_WIFI_SSID       "SPS_GATEWAY_AP"
#define SPS_WIFI_PASSWORD   "12345678"
#define SPS_READER_ID       "GATE01"
#define SPS_READER_TOKEN    "change-this-reader-token"
#define SPS_GATEWAY_HOST    "192.168.4.1"
#define SPS_GATEWAY_PORT    19000
```

Change the reader token for deployment, but never commit a real Wi-Fi password or reader token.
The token is inserted into HTTP headers and is never printed by the firmware. ESP8266 `CWJAP`
logging is redacted so the Wi-Fi password does not appear in serial logs.

## Three authentication flows

### Card

PN532 reads the UID and applies a 3000 ms duplicate-card debounce. Firmware sends:

```http
POST /local/gate/access-card HTTP/1.1
X-Gate-Reader-Id: GATE01
X-Gate-Reader-Token: <reader-token>
Content-Type: application/json

{"reader_id":"GATE01","credential_type":"CARD_UID","credential_value":"04A1B2C3D4"}
```

### QR

Firmware fetches `/local/gate/qr-session?reader_id=GATE01`, encodes `qr_payload` locally with the
vendored MIT-licensed Project Nayuki `qrcodegen` C library, and draws the matrix centered on the
RGB565 framebuffer. No network image is used. The current custom framebuffer UI has no complete
CJK font; the three-line caption is emitted to serial as `WeChat scan / card / gate NFC` while the
screen displays the QR matrix.

### Gate NFC tag

Firmware does not write the static tag. Program an NTAG213/NTAG215 with an NDEF URI such as:

```text
sps://gate-nfc?v=1&gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001
```

The mini program reads this tag and submits user authentication to the server. Firmware observes
the result through the same gateway polling endpoint as QR authentication.

## Result polling and UI state

Every second firmware calls `/local/gate/auth-result?reader_id=GATE01` with reader headers. Both
`access=GRANTED/DENIED` and `status=GRANTED/DENIED` responses are accepted. It parses reason,
display text, pickup count, shelves, parcel codes, session color and warnings.

```text
BOOTING -> WIFI_CONNECTING -> READY -> QR_READY
                                  |-> CARD_READING -> GRANTED / DENIED -> QR_READY
QR_READY -> WAITING_GATE_AUTH -> GRANTED / DENIED -> QR_READY
                                  `-> ERROR
```

GRANTED uses a green screen, DENIED red, and ERROR yellow. Detailed package/shelf text is logged;
the custom display layer currently renders status colors and QR, with full text awaiting a CJK font.

## Build and flash

```bash
idf.py set-target esp32p4
idf.py build
idf.py -p COMx flash monitor
```

Common failures:

- PN532 timeout: verify HSU switches, crossed TX/RX, common ground and stable 3.3 V power.
- ESP8266 join failure: verify AP SSID/password and independent power supply.
- HTTP 401: reader ID/token must match the gateway configuration.
- QR not visible: verify PSRAM framebuffer allocation, ST7701S timings and PCA9536 backlight/reset.
- Always rebuild locally rather than sharing build logs, which can retain old configuration strings.
