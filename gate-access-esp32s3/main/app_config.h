#pragma once

/*
 * SmartParcelStation gate reader configuration.
 *
 * 当前阶段先使用集中硬编码配置，后续可以平滑迁移到 Kconfig/menuconfig。
 * 不要在其他源文件重复写 Wi-Fi 密码、gateway 地址或读卡器编号。
 */

#define SPS_WIFI_SSID              "SPS_GATEWAY_AP"
#define SPS_WIFI_PASSWORD          "12345678"
#define SPS_GATEWAY_URL            "http://192.168.4.1:19000"
#define SPS_READER_ID              "GATE01"

#define SPS_CARD_DEBOUNCE_MS       3000
#define SPS_CARD_POLL_INTERVAL_MS  300

#define SPS_PN532_I2C_PORT         I2C_NUM_0
#define SPS_PN532_I2C_SDA_GPIO     GPIO_NUM_8
#define SPS_PN532_I2C_SCL_GPIO     GPIO_NUM_9
#define SPS_PN532_IRQ_GPIO         GPIO_NUM_10
#define SPS_PN532_RST_GPIO         GPIO_NUM_11
#define SPS_PN532_I2C_FREQ_HZ      100000
#define SPS_PN532_I2C_ADDR         0x24

#define SPS_HTTP_TIMEOUT_MS        5000
#define SPS_HTTP_RESPONSE_MAX      2048
