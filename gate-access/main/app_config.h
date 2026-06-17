#pragma once

#include "driver/gpio.h"
#include "driver/i2c.h"
#include "driver/uart.h"

/*
 * 当前阶段先采用集中硬编码配置，后续可迁移到 Kconfig 或 NVS。
 * 固件只上传 UID，业务判断继续留在 smartparcel-gateway。
 */

#define SPS_GATEWAY_HOST            "192.168.4.1"
#define SPS_GATEWAY_PORT            19000
#define SPS_GATEWAY_PATH            "/local/gate/access-card"
#define SPS_GATEWAY_URL             "http://192.168.4.1:19000"

#define SPS_WIFI_SSID               "SPS_GATEWAY_AP"
#define SPS_WIFI_PASSWORD           "12345678"
#define SPS_READER_ID               "GATE01"

#define SPS_ESP8266_UART_PORT       UART_NUM_1
#define SPS_ESP8266_UART_TX_GPIO    GPIO_NUM_43
#define SPS_ESP8266_UART_RX_GPIO    GPIO_NUM_44
#define SPS_ESP8266_UART_RTS_GPIO   UART_PIN_NO_CHANGE
#define SPS_ESP8266_UART_CTS_GPIO   UART_PIN_NO_CHANGE
#define SPS_ESP8266_UART_BAUD       115200
#define SPS_ESP8266_AT_TIMEOUT_MS   5000
#define SPS_ESP8266_UART_BUF_SIZE   2048

#define SPS_PN532_I2C_PORT          I2C_NUM_0
#define SPS_PN532_I2C_SDA_GPIO      GPIO_NUM_20
#define SPS_PN532_I2C_SCL_GPIO      GPIO_NUM_21
#define SPS_PN532_IRQ_GPIO          GPIO_NUM_22
#define SPS_PN532_RST_GPIO          GPIO_NUM_23
#define SPS_PN532_I2C_FREQ_HZ       100000
#define SPS_PN532_I2C_ADDR          0x24
#define SPS_CARD_DEBOUNCE_MS        3000
#define SPS_CARD_POLL_INTERVAL_MS   300

#define SPS_HTTP_RESPONSE_MAX       2048

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
