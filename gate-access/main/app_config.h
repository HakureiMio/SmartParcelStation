#pragma once

#include "driver/gpio.h"
#include "driver/i2c.h"
#include "driver/uart.h"

/*
 * 当前阶段先采用集中硬编码配置，后续可迁移到 Kconfig 或 NVS。
 * 固件只上传 UID，业务判断继续留在 smartparcel-gateway。
 */

/* ── 调试开关 ───────────────────────────────────────────────────
 *
 * SPS_DIAG_PN532_ONLY          独立 PN532 诊断（跳过 ESP8266/显示/触摸）
 * SPS_DEMO_DISPLAY_FIRST       优先调试屏幕
 * SPS_DEMO_TOUCH_COLOR_TEST    触摸点击切换颜色
 * SPS_DEMO_FORCE_WHITE_SCREEN  持续白屏
 * SPS_DEMO_WIFI_ENABLE         在 display-first 模式下启动 ESP8266 WiFi
 * SPS_DEMO_PN532_UID_TEST      在 display-first 模式下持续读取卡 UID
 * SPS_DEMO_ESP8266_OPEN_AP_TEST ESP8266 AT 测试（仅 SPS_DEMO_DISPLAY_FIRST=0 时有效）
 * SPS_ESP8266_CONNECT_ONLY_TEST ESP8266 连接 AP 测试（仅 SPS_DEMO_DISPLAY_FIRST=0 时有效）
 *
 * PN532 诊断模式（SPS_DIAG_PN532_ONLY=1）：
 *   - 只初始化 UART2 + 逐步 PN532 诊断
 *   - 不启动显示/触摸/ESP8266/PN532 业务逻辑
 *   - 每步打印原始十六进制 TX/RX
 *
 * 默认：PN532 独立诊断
 */
#define SPS_DIAG_PN532_ONLY             0
#define SPS_DEMO_DISPLAY_FIRST          1
#define SPS_DEMO_TOUCH_COLOR_TEST       1
#define SPS_DEMO_FORCE_WHITE_SCREEN     0
#define SPS_DEMO_WIFI_ENABLE            1
#define SPS_DEMO_PN532_UID_TEST         1
#define SPS_DEMO_ESP8266_OPEN_AP_TEST   0
#define SPS_ESP8266_CONNECT_ONLY_TEST   0

#define SPS_GATEWAY_HOST            "192.168.4.1"
#define SPS_GATEWAY_PORT            19000
#define SPS_GATEWAY_PATH            "/local/gate/access-card"
#define SPS_GATEWAY_URL             "http://192.168.4.1:19000"

#define SPS_WIFI_SSID               "Galaxy zflip 7"
#define SPS_WIFI_PASSWORD           "zjtzjt666"
#define SPS_READER_ID               "GATE01"

/* ── ESP8266 UART ────────────────────────────────────────────────
 *
 * 经测试：GPIO43/J7排针(GPIO17/18/19) 做 UART TX 均不通。
 * GPIO44 做 RX 已验证可用。用同区域 GPIO45 做 TX。
 *
 * 连接：
 *   ESP32P4 GPIO45 (TX) -> ESP8266 RX
 *   ESP32P4 GPIO44 (RX) <- ESP8266 TX
 *   GND 共地
 *   ESP8266 独立 3.3V 稳压供电，不要连接两边 3.3V 电源线
 *
 * 注意：ESP8266 GPIO0 必须上拉 HIGH 才能进入正常运行模式。
 *       如果 GPIO0 被拉低，ESP8266 会停在 boot ROM（74880 baud）。
 *
 * 回环测试：SPS_ESP8266_UART_LOOPBACK_TEST=1 时，用杜邦线短接
 * TX 和 RX 引脚，验证 UART 通道是否正常工作。
 */
#define SPS_ESP8266_UART_PORT           UART_NUM_1
#define SPS_ESP8266_UART_TX_GPIO        GPIO_NUM_45
#define SPS_ESP8266_UART_RX_GPIO        GPIO_NUM_44
#define SPS_ESP8266_UART_RTS_GPIO       UART_PIN_NO_CHANGE
#define SPS_ESP8266_UART_CTS_GPIO       UART_PIN_NO_CHANGE
#define SPS_ESP8266_UART_BAUD           115200
#define SPS_ESP8266_AT_TIMEOUT_MS       5000
#define SPS_ESP8266_UART_BUF_SIZE       2048
#define SPS_ESP8266_UART_LOOPBACK_TEST  0

/* ── PN532 HSU/UART ──────────────────────────────────────────────
 * Set the PN532 board mode switches to HSU before power-on.
 * ESP32-P4 GPIO20 (TX) -> PN532 RXD
 * ESP32-P4 GPIO21 (RX) <- PN532 TXD
 * IRQ is not used in HSU mode. RST remains disabled because many
 * breakout boards expose RSTO (an output), not a reset input. */
#define SPS_PN532_UART_PORT         UART_NUM_2
#define SPS_PN532_UART_TX_GPIO      GPIO_NUM_20
#define SPS_PN532_UART_RX_GPIO      GPIO_NUM_21
#define SPS_PN532_UART_BAUD         115200
#define SPS_PN532_UART_BUF_SIZE     512
#define SPS_PN532_UART_TIMEOUT_MS   1200
#define SPS_PN532_UART_LOOPBACK_TEST 0
#define SPS_PN532_USE_RESET         0
#define SPS_PN532_RST_GPIO          GPIO_NUM_NC
#define SPS_CARD_DEBOUNCE_MS        3000
#define SPS_CARD_POLL_INTERVAL_MS   100

#define SPS_HTTP_RESPONSE_MAX       2048

/* ── Display Board I2C & PCA9536 GPIO Expander ─────────────────
 *
 * WLK2802MIPI-15P 转接板上有一颗 PCA9536 (4-bit I2C GPIO 扩展器)，
 * 位于 IO7/IO8 I2C bus 地址 0x41。
 *
 * PCA9536 4 个 GPIO 的推测用途（根据厂商 Demo binary 字符串推断，
 * 实际引脚映射待硬件确认）：
 *   - IO0: LCD_RST (panel reset)
 *   - IO1: TP_RST  (touch reset)
 *   - IO2: BL_EN   (backlight enable, 高电平有效)
 *   - IO3: 未定 / 保留
 *
 * 如果 IO 映射不对，调整下面的宏即可。
 */
#define SPS_DISPLAY_BOARD_I2C_PORT      I2C_NUM_1
#define SPS_DISPLAY_BOARD_I2C_SDA_GPIO  GPIO_NUM_7
#define SPS_DISPLAY_BOARD_I2C_SCL_GPIO  GPIO_NUM_8
#define SPS_DISPLAY_BOARD_I2C_FREQ_HZ   100000

/* PCA9536 fixed I2C address */
#define SPS_PCA9536_I2C_ADDR            0x41

/* PCA9536 IO pin assignments (0-3) */
#define SPS_PCA9536_PIN_LCD_RST         0
#define SPS_PCA9536_PIN_TP_RST          1
#define SPS_PCA9536_PIN_BL_EN           2
#define SPS_PCA9536_PIN_RESERVED        3

/* Touch I2C: shares the same bus as PCA9536 (IO7/IO8) */
#define SPS_TOUCH_I2C_PORT          I2C_NUM_1
#define SPS_TOUCH_I2C_SDA_GPIO      GPIO_NUM_7
#define SPS_TOUCH_I2C_SCL_GPIO      GPIO_NUM_8
#define SPS_TOUCH_I2C_FREQ_HZ       100000
#define SPS_TOUCH_I2C_ADDR          0x15
#define SPS_TOUCH_I2C_FALLBACK_ADDR 0x38
#define SPS_TOUCH_POLL_INTERVAL_MS  30
#define SPS_TOUCH_SWAP_XY           0
#define SPS_TOUCH_INVERT_Y          0

/* ── ST7701S MIPI DSI Display Timings ──────────────────────────
 *
 * 当前使用 timing profile 1（默认）。
 * 如需尝试其他 profile，修改 SPS_DISPLAY_TIMING_PROFILE。
 */
#define SPS_DISPLAY_TIMING_PROFILE  0

#define SPS_DISPLAY_WIDTH           480
#define SPS_DISPLAY_HEIGHT          640

#if SPS_DISPLAY_TIMING_PROFILE == 0
  /* Profile 0: single-lane, lower bitrate — 保守模式 */
  #define SPS_DISPLAY_MIPI_DSI_LANES              1
  #define SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS  480
  #define SPS_DISPLAY_DPI_CLOCK_MHZ               18
  #define SPS_DISPLAY_HSYNC_PW                    10
  #define SPS_DISPLAY_HSYNC_BP                    20
  #define SPS_DISPLAY_HSYNC_FP                    40
  #define SPS_DISPLAY_VSYNC_PW                    2
  #define SPS_DISPLAY_VSYNC_BP                    8
  #define SPS_DISPLAY_VSYNC_FP                    12
#elif SPS_DISPLAY_TIMING_PROFILE == 1
  /* Profile 1: 2-lane, 500 Mbps, 24 MHz — 当前默认 */
  #define SPS_DISPLAY_MIPI_DSI_LANES              2
  #define SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS  500
  #define SPS_DISPLAY_DPI_CLOCK_MHZ               24
  #define SPS_DISPLAY_HSYNC_PW                    10
  #define SPS_DISPLAY_HSYNC_BP                    20
  #define SPS_DISPLAY_HSYNC_FP                    40
  #define SPS_DISPLAY_VSYNC_PW                    2
  #define SPS_DISPLAY_VSYNC_BP                    8
  #define SPS_DISPLAY_VSYNC_FP                    12
#elif SPS_DISPLAY_TIMING_PROFILE == 2
  /* Profile 2: 2-lane, higher bitrate — 候选（如有需要） */
  #define SPS_DISPLAY_MIPI_DSI_LANES              2
  #define SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS  600
  #define SPS_DISPLAY_DPI_CLOCK_MHZ               30
  #define SPS_DISPLAY_HSYNC_PW                    10
  #define SPS_DISPLAY_HSYNC_BP                    20
  #define SPS_DISPLAY_HSYNC_FP                    40
  #define SPS_DISPLAY_VSYNC_PW                    2
  #define SPS_DISPLAY_VSYNC_BP                    8
  #define SPS_DISPLAY_VSYNC_FP                    12
#else
  #error "Unsupported SPS_DISPLAY_TIMING_PROFILE"
#endif

#define SPS_DISPLAY_MIPI_DSI_PHY_LDO_CHAN        3
#define SPS_DISPLAY_MIPI_DSI_PHY_LDO_VOLTAGE_MV  2500

/*
 * 背光和复位不再用 GPIO_NUM_NC。
 * 改为通过 PCA9536 @ 0x41 控制。
 * 如果 PCA9536 未就绪，代码会输出明确日志并降级。
 */
#define SPS_DISPLAY_BACKLIGHT_GPIO  GPIO_NUM_NC
#define SPS_DISPLAY_RESET_GPIO      GPIO_NUM_NC
