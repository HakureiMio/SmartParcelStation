# gate-access 引脚映射

当前硬件目标为 ESP32P4 WT9932P4-TINY。所有引脚集中定义在 `main/app_config.h`，源文件中不再分散硬编码。

## ESP8266 串口 Wi-Fi 模块

- ESP32P4 GPIO17 TX -> ESP8266 RX
- ESP32P4 GPIO44 RX <- ESP8266 TX
- GND 共地
- ESP8266 使用独立稳定 3.3V 供电，不建议直接从小电流 3.3V 引脚取电

注意：GPIO43 只能作为普通 GPIO 输出，不支持 UART TX 功能。已改用 GPIO17。

对应配置：

```c
#define SPS_ESP8266_UART_PORT       UART_NUM_1
#define SPS_ESP8266_UART_TX_GPIO    GPIO_NUM_17
#define SPS_ESP8266_UART_RX_GPIO    GPIO_NUM_44
#define SPS_ESP8266_UART_BAUD       115200
```

## PN532 I2C

- GPIO20 SDA
- GPIO21 SCL
- GPIO22 IRQ 预留
- GPIO23 RST 预留/后续可启用
- 3.3V 逻辑电平
- GND 共地

对应配置：

```c
#define SPS_PN532_I2C_PORT          I2C_NUM_0
#define SPS_PN532_I2C_SDA_GPIO      GPIO_NUM_20
#define SPS_PN532_I2C_SCL_GPIO      GPIO_NUM_21
#define SPS_PN532_IRQ_GPIO          GPIO_NUM_22
#define SPS_PN532_RST_GPIO          GPIO_NUM_23
#define SPS_PN532_I2C_FREQ_HZ       100000
#define SPS_PN532_I2C_ADDR          0x24
```

## ST7701S 480x640 MIPI DSI 屏幕

- 使用 WT9932P4-TINY 板载 DSI FPC 连接。
- 不手工把 DSI 差分线当普通 GPIO 分配。
- 复位、背光和触摸 I2C 引脚当前需要 BSP 或硬件资料确认。
- `SPS_DISPLAY_BACKLIGHT_GPIO` 和 `SPS_DISPLAY_RESET_GPIO` 当前用 `GPIO_NUM_NC` 占位。

确认 BSP 或真实硬件连接后，只需要更新 `main/app_config.h` 和本文件。
