# ESP32S3 门禁读卡器引脚映射

本文档记录 `gate-access-esp32s3` 当前默认硬件连接。当前阶段先使用占位 GPIO，后续换成真实开发板时只需要集中修改配置和本说明。

## 当前默认引脚

| 功能 | 默认引脚 | 当前用途 | 代码配置位置 |
| --- | --- | --- | --- |
| PN532 I2C SDA | GPIO 8 | I2C 数据线 | `main/app_config.h` 的 `SPS_PN532_I2C_SDA_GPIO` |
| PN532 I2C SCL | GPIO 9 | I2C 时钟线 | `main/app_config.h` 的 `SPS_PN532_I2C_SCL_GPIO` |
| PN532 IRQ | GPIO 10 | 预留，当前轮询实现暂未使用 | `main/app_config.h` 的 `SPS_PN532_IRQ_GPIO` |
| PN532 RST | GPIO 11 | 预留，当前未主动复位 PN532 | `main/app_config.h` 的 `SPS_PN532_RST_GPIO` |

## 更换真实开发板时需要确认

1. ESP32S3 开发板上 GPIO 8/9 是否已经被板载 Flash、PSRAM、USB、摄像头或显示屏占用。
2. PN532 模块是否已经焊接 I2C 上拉电阻；如果没有，需要外接 3.3V 上拉。
3. PN532 模块拨码或焊盘是否切换到 I2C 模式。
4. PN532 供电电压是否与模块要求一致，优先使用 3.3V 逻辑电平。
5. 如果现场刷卡不稳定，再评估接入 IRQ/RST 并在驱动里启用硬件复位和中断等待。

## 代码中的配置位置

所有硬件引脚和 I2C 参数集中在：

```text
gate-access-esp32s3/main/app_config.h
```

当前相关宏：

```c
#define SPS_PN532_I2C_PORT         I2C_NUM_0
#define SPS_PN532_I2C_SDA_GPIO     GPIO_NUM_8
#define SPS_PN532_I2C_SCL_GPIO     GPIO_NUM_9
#define SPS_PN532_IRQ_GPIO         GPIO_NUM_10
#define SPS_PN532_RST_GPIO         GPIO_NUM_11
#define SPS_PN532_I2C_FREQ_HZ      100000
#define SPS_PN532_I2C_ADDR         0x24
```

## 未来切换到 SPI 或 UART

如果 PN532 模块改为 SPI 或 UART，请同步修改：

1. `main/app_config.h`：新增 SPI/UART 引脚、端口和波特率等配置，移除或保留 I2C 配置作为备用。
2. `main/pn532_reader.c`：替换底层 `pn532_send_command`、`pn532_wait_ready`、`pn532_read_raw` 的传输实现。
3. `main/pn532_reader.h`：尽量保持 `pn532_reader_init` 和 `pn532_reader_poll_uid` 接口不变，避免影响主循环。
4. `docs/pin_mapping.md`：更新真实接线表。
5. `README.md`：更新硬件连接和当前限制。
