# clip-node-nrf52810

## 1. 固件定位

`clip-node-nrf52810` 是 SmartParcelStation 的 nRF52810 智能寻物标签固件工程。当前用于验证 gateway 通过 BLE 控制标签，触发 RGB LED 和蜂鸣器，读取标签状态，并为后续触点检测、电池检测和状态上报保留基础结构。

## 2. 当前硬件平台

当前测试硬件：

```text
EWT73-2G4M04S1A 测试套件
E73-2G4M04S1A / nRF52810 模组
3.3V 供电
ST-LINK 或其他 SWD 调试器
```

正式智能寻物标签应使用单独 E73 小模组设计自研 PCB，测试套件只用于固件和引脚验证。

## 3. 当前 BLE 能力

固件已启用 BLE Peripheral，并提供 SPS Tag GATT Service。

gateway 可通过 `CMD_WRITE` 写入轻量二进制命令帧；标签通过 `EVENT_NOTIFY` 上报事件，并提供 `STATUS_READ` 读取入口。

`mock_receive_cmd` 仅保留为本地测试入口，不是当前主通信路径。

## 4. BLE 命名规范

当前测试默认名称：

```text
SPS-F01-20260610-0001
```

格式：

```text
SPS-{factory_code}-{production_date}-{serial_no}
```

示例：

```text
SPS-F01-20260610-0001
SPS-F01-20260610-0002
SPS-F02-20260611-0001
```

第一阶段 BLE 名称写在 `prj.conf` 中。后续批量生产应通过 NVS 或产测工具写入唯一出厂信息。

## 5. GATT Service 设计

UUID：

```text
Service UUID:       8f7e9000-5d1b-4c2f-9e8a-5f2f5b7b0001
CMD_WRITE UUID:    8f7e9001-5d1b-4c2f-9e8a-5f2f5b7b0001
EVENT_NOTIFY UUID: 8f7e9002-5d1b-4c2f-9e8a-5f2f5b7b0001
STATUS_READ UUID:  8f7e9003-5d1b-4c2f-9e8a-5f2f5b7b0001
```

命令帧：

```text
[0] 0xA5
[1] command
[2] payload_len
[3..] payload
[last] xor checksum
```

支持命令：

```text
PING
WAKE_TAG
STOP_ALERT
SET_BINDING
CLEAR_BINDING
READ_STATUS
```

当前 `WAKE_TAG` 的 `color/duration` payload 在标签侧尚未完全用于多颜色和动态时长控制，默认执行寻物闪烁和蜂鸣。

## 6. 引脚连接

当前测试引脚见 `docs/hardware_pins.md`。常用连接：

```text
PIN_LED_R_PWM = P0.11
PIN_LED_G_PWM = P0.12
PIN_LED_B_PWM = P0.15
PIN_BUZZER_CTRL = P0.16
PIN_REMOVE_SENSE = P0.19
PIN_BAT_ADC = P0.02 / AIN0
PIN_BAT_DIV_EN = P0.20
PIN_USER_BTN = P0.21
PIN_STATUS_LED = P0.22
```

调试器与目标板必须共地，模块供电不得超过 3.6V。

## 7. 编译环境

请在 nRF Connect SDK / Nordic Toolchain Terminal 中执行 `west build`。

不要使用 `smartparcel-gateway/.venv` 中的 Python 或 `west` 编译固件。gateway 的 `.venv` 只用于 Python 网关项目。

本工程使用自定义 board：

```text
clip_node_nrf52810
```

除非明确要临时移植到 Nordic DK，否则不要使用 `nrf52dk_nrf52810` 作为默认 board。

## 8. 编译固件

推荐命令：

```powershell
cd clip-node-nrf52810
west build -b clip_node_nrf52810 . -d build -p always
```

编译产物只用于本地烧录，不应提交到 Git。不要提交 `build/`、`.hex`、`.bin`、`.elf`、`.map` 等文件。

## 9. ST-LINK + OpenOCD 烧录

连接验证：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; targets; shutdown"
```

擦除：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; nrf52 mass_erase; shutdown"
```

烧录：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; program build/merged.hex verify reset; shutdown"
```

当前 sysbuild 场景常见产物是 `build/merged.hex`。如果使用普通 Zephyr 构建，产物也可能位于 `build/zephyr/merged.hex`，对应命令为：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; program build/zephyr/merged.hex verify reset; shutdown"
```

如果 `merged.hex` 不存在，说明 build 失败或产物路径不同，先检查：

```powershell
Get-ChildItem .\build\
Get-ChildItem .\build\zephyr\
```

## 10. 与 gateway real BLE 联调

联调链路：

```text
smartparcel-gateway BLE_BACKEND=real
  -> bleak 扫描 SPS-F01-20260610-0001
  -> 连接标签
  -> CMD_WRITE 写入 WAKE_TAG / STOP_ALERT / READ_STATUS
  -> 标签驱动 RGB LED / 蜂鸣器
```

PowerShell 可先直接调用 gateway API，再接小程序：

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:19000/local/tags/scan" `
  -ContentType "application/json" `
  -Body '{"timeout_sec":5}'
```

## 11. 本地硬件自检

建议流程：

```text
1. 编译固件。
2. 烧录固件。
3. 打开 RTT 日志。
4. 确认启动 banner。
5. 确认 BLE name: SPS-F01-20260610-0001。
6. 启动 gateway local API。
7. 设置 BLE_BACKEND=real。
8. 小程序或 PowerShell 调用 /local/tags/scan。
9. 注册扫描到的标签。
10. 调用 /connect。
11. 调用 /wake。
12. 观察 RGB LED，并确认蜂鸣器测试阶段保持高电平有效。
13. 调用 /stop。
14. 观察 RGB LED 停止，蜂鸣器测试阶段仍保持高电平有效。
15. 调用 /status。
```

## 12. 已知限制

1. 当前 `WAKE_TAG` 的 `color/duration` payload 在标签侧尚未完全用于多颜色和动态时长控制，默认执行寻物闪烁和蜂鸣。
2. 第一阶段 BLE 名称写死在 `prj.conf`，后续批量生产应通过 NVS 或产测工具写入唯一出厂信息。
3. 当前主要验证单标签连接和控制，多标签并发调度后续再做。
4. 当前重点是员工小程序 -> gateway -> 标签，不代表门禁流程已经完全迁移到 real BLE。
5. nRF52810 RAM 资源有限，新增功能需要谨慎控制日志、栈和 BLE 缓冲配置。
