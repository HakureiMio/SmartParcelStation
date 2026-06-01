# clip-node-nrf52810

`clip-node-nrf52810` 是基于 **nRF Connect SDK / Zephyr** 的 nRF52810 智能夹具节点固件骨架工程。
本项目聚焦夹具端最小功能集合：本地 BLE 通信、夹具状态机、RGB 与蜂鸣提醒、取下检测、电池检测和低功耗策略。

## 1. 开发环境与 VS Code 插件

推荐环境（Windows）：

- Visual Studio Code
- nRF Connect for VS Code Extension Pack（Nordic 官方扩展包）
- C/C++（Microsoft）
- Cortex-Debug（用于 SWD 调试，可选）

说明：安装 nRF Connect 扩展包后，通常会一并引导安装 Toolchain Manager、West、Kconfig 支持等组件。

## 2. 安装 nRF Connect SDK

推荐使用 Nordic 官方流程：

1. 安装 `nRF Connect for Desktop`（可选）或直接使用 VS Code 的 nRF Connect 扩展。
2. 在 VS Code 中打开 nRF Connect 扩展面板。
3. 使用 Toolchain Manager 安装：
   - nRF Connect SDK（选择稳定版本，如 `v2.x`）
   - 对应 Toolchain（包含 CMake、Ninja、Python、west）
4. 在扩展中完成 SDK 路径关联。

## 3. SWD 烧录连线说明

通过 SWD 连接调试器（J-Link 或 nRF Command Line Tools 对应设备）到目标板：

- `SWDIO` -> 模组 `SWDIO`
- `SWDCLK` -> 模组 `SWDCLK`
- `VCC` -> 模组 `VCC`（电平参考，通常 3.0V~3.3V）
- `GND` -> 模组 `GND`
- `RESET` -> 模组 `RESET`（建议连接，便于稳定下载）

注意：

- 调试器与目标板必须共地。
- 纽扣电池供电场景下，调试时建议外部稳定电源，避免电压跌落。

## 4. Build 方法

### 方式 A：VS Code 图形化

1. 用 VS Code 打开项目根目录 `clip-node-nrf52810`。
2. 在 nRF Connect 扩展中选择 `Add Build Configuration`。
3. Board 选择本项目自定义目标：`clip_node_nrf52810`。
4. 点击 `Build`。

### 方式 B：命令行（west）

在已激活 nRF Connect Toolchain 的终端执行：

```bash
west build -b clip_node_nrf52810 . -p
```

说明：当前为工程骨架，默认引脚留空，需根据硬件原理图完善 `docs/hardware_pins.md` 中的分配后再联调。

## 5. Flash 方法

### 方式 A：VS Code

- 在 nRF Connect 扩展中点击 `Flash`。

### 方式 B：命令行

```bash
west flash
```

若存在多个调试器，按需增加 runner 参数或序列号参数。

## 6. 查看日志

推荐 RTT 日志：

- VS Code nRF Connect 的 `Serial/RTT Terminal`
- 或使用 J-Link RTT Viewer

本工程默认开启：

- `CONFIG_USE_SEGGER_RTT=y`
- `CONFIG_LOG_BACKEND_RTT=y`

## 7. 功能概览

已提供以下模块骨架：

- BLE 通信模块（简化服务 + mock 命令接收入口）
- 夹具状态机（idle / bound / authorized / alerting / removed / confirmed / low_battery / exception）
- 控制命令解析与分发（轻量二进制协议）
- 事件上报接口
- RGB PWM 控制（7 档亮度）
- 蜂鸣器模式控制（含最大持续时间限制）
- 取下检测（GPIO + 软件消抖）
- 电池检测（ADC + 电量等级）
- 低功耗行为约束

## 8. 重要设计约束

- nRF52810 资源受限，不引入复杂 JSON 解析。
- 夹具与网关通信协议采用轻量二进制帧。
- 用户权限、包裹绑定、数据库、云同步均不在夹具端实现。
- 夹具端不存储用户和包裹隐私数据。

## 9. 后续落地建议

1. 先完成 `docs/hardware_pins.md` 的实际引脚映射。
2. 将 `ble_clip_service` 中 mock 接口替换为正式 GATT Service。
3. 补充 `settings`/NVS（仅存储必要设备参数，避免隐私数据）。
4. 做功耗实测：空闲电流、告警电流、日均电量消耗。
