# clip-node-nrf52810

> 边界说明：`clip-node-nrf52810` 是 BLE 智能寻物标签，不是门禁 NFC 标签。它负责 BLE 广播、GATT 命令、RGB 闪烁、状态读取和电池状态。门禁 NFC 标签和包裹取件 NFC 标签均为外贴 NTAG213/NTAG215，分别使用 `sps://gate-nfc` 与 `sps://pickup` payload，不能混用。本说明不改变现有 BLE/GATT 协议或硬件配置。

完整五端演示及 BLE 标签在其中的职责见 [端到端演示文档](../docs/demo_three_gate_auth_methods.md)。

## 1. 项目说明

`clip-node-nrf52810` 是 SmartParcelStation 项目的 nRF52810 夹具节点固件工程。

当前阶段主要用于验证以下能力：

- BLE Peripheral 广播与 GATT 服务
- RGB 灯状态指示
- 拆卸检测输入
- 电池电压采样
- 网关到标签的基础命令链路

## 2. 当前硬件平台

当前调试硬件：

```text
EWT73-2G4M04S1A 测试套件
E73-2G4M04S1A / nRF52810 模组
3.3V 供电
J-Link SWD 调试
```

说明：

- 当前仓库面向测试板和现阶段联调。
- 后续量产应切换到自定义 PCB，并重新核对引脚映射与电源能力。

## 3. 当前功能状态

当前版本已恢复 BLE 主流程，主要包括：

- BLE 初始化与广播
- `SPS Tag` GATT Service
- 命令接收与事件上报
- RGB 灯提示
- 拆卸检测与电池采样

当前阶段蜂鸣器策略如下：

- 已保留蜂鸣器相关代码接口
- 业务调用已暂时注释/禁用
- 原因是当前电池供电能力不足，暂时不能稳定支撑蜂鸣器与 RGB 灯同时工作

因此，现阶段请按下面原则理解：

- `WAKE_TAG` 等业务流程可继续验证 BLE 与 RGB
- 暂时禁止蜂鸣器和 RGB 灯同时工作
- 蜂鸣器恢复启用前，应先完成电源能力与负载评估

## 4. BLE 信息

当前固件使用 BLE Peripheral 模式。

当前设备名配置在 `prj.conf` 中，例如：

```conf
CONFIG_BT_DEVICE_NAME="SPS-F02-20260611-0001"
```

命名方式定为“产品名-生产商名-生产日期-生产编号”

## 5. GATT 服务

当前服务 UUID：

```text
Service UUID:       8f7e9000-5d1b-4c2f-9e8a-5f2f5b7b0001
CMD_WRITE UUID:     8f7e9001-5d1b-4c2f-9e8a-5f2f5b7b0001
EVENT_NOTIFY UUID:  8f7e9002-5d1b-4c2f-9e8a-5f2f5b7b0001
STATUS_READ UUID:   8f7e9003-5d1b-4c2f-9e8a-5f2f5b7b0001
```

当前支持的基础命令：

```text
PING
WAKE_TAG
STOP_ALERT
SET_BINDING
CLEAR_BINDING
READ_STATUS
```

补充说明：

- `WAKE_TAG` 当前以 RGB 提示为主
- 由于电池供电限制，当前不启用蜂鸣器联动

## 6. 主要引脚

详细映射见 [docs/hardware_pins.md](D:/Project/SmartParcelStation/clip-node-nrf52810/docs/hardware_pins.md:1)。

当前常用引脚：

```text
RGB_R         P0.11
RGB_G         P0.12
RGB_B         P0.15
BUZZER_CTRL   P0.16
REMOVE_SENSE  P0.19
BAT_ADC       P0.02 / AIN0
BAT_DIV_EN    P0.20
USER_BTN      P0.21
STATUS_LED    P0.22
```

## 7. 编译

请在 Nordic Toolchain Terminal 或正确配置过环境的终端中执行。

推荐命令：

```powershell
west build -b clip_node_nrf52810 . -d build -p always
```

说明：

- 不要把 `build/` 目录产物提交到 Git。
- `nRF52810` RAM 资源较紧，新增功能时要谨慎控制日志、栈和 BLE 缓冲配置。

## 8. 使用 J-Link 烧录

### 方式 A：使用 west runner

```powershell
west flash --runner jlink
```

如果该方式无法正常连接探针，可改用方式 B。

### 方式 B：使用 J-Link Commander 脚本

当前脚本文件：

- [tools/jlink_flash.jlink](D:/Project/SmartParcelStation/clip-node-nrf52810/tools/jlink_flash.jlink:1)

当前命令：

```powershell
& "D:\Program Files\SEGGER\JLink_V950\JLink.exe" -nogui 1 -CommanderScript .\tools\jlink_flash.jlink
```

当前脚本内容：

```text
si SWD
speed 4000
device NRF52810_XXAA
r
loadfile build/clip-node-nrf52810/zephyr/zephyr.hex
r
g
q
```

注意事项：

- 在 PowerShell 中执行带空格路径的 `JLink.exe` 时，要在前面加 `&`
- 当前脚本默认烧录 `build/clip-node-nrf52810/zephyr/zephyr.hex`
- 如果构建输出路径变化，需要同步修改 `tools/jlink_flash.jlink` 中的 `loadfile`
- 目标芯片名称使用 `NRF52810_XXAA`

## 9. 当前联调建议

建议当前按下面顺序联调：

1. 编译固件
2. 使用 J-Link 烧录
3. 上电观察 BLE 是否开始广播
4. 使用网关或调试工具连接 BLE
5. 验证 `PING` / `READ_STATUS`
6. 验证 `WAKE_TAG` 下 RGB 表现
7. 暂不验证蜂鸣器与 RGB 同时动作

## 10. 当前限制

1. 当前电池供电能力不足，暂时禁止蜂鸣器与 RGB 灯同时工作。
2. 蜂鸣器业务代码已保留，但当前版本默认禁用其联动调用。
3. 当前优先目标是 BLE 通路、RGB 指示、状态读写与基础硬件稳定性。
4. `nRF52810` RAM 较小，恢复更多功能前需要持续控制内存占用。
