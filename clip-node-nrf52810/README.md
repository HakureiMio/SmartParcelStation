# clip-node-nrf52810

`clip-node-nrf52810` 是基于 **nRF Connect SDK / Zephyr** 的 nRF52810 智能寻物标签固件工程。
本工程用于 SPS 项目的智能寻物标签节点，聚焦本地 BLE 通信、标签状态机、RGB 与蜂鸣提醒、取下检测、电池检测和基础低功耗行为。

本节点过去在讨论中被称为夹具节点，但在后续文档中统一称为“智能寻物标签”。

当前硬件测试平台为 **亿佰特 EWT73-2G4M04S1A 测试套件**，核心模组为 **E73-2G4M04S1A / nRF52810**。该测试套件用于 GPIO/PWM/ADC 和烧录验证；正式智能寻物标签应使用单独 E73 小模组设计自研 PCB，测试套件板子本体不作为最终结构件。

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
   - nRF Connect SDK（选择稳定版本，如 `v2.x` 或当前项目验证版本）
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
- 模组供电不得超过 3.6V。
- `SWDIO` / `SWDCLK` 保留为调试接口，不作为普通 GPIO 使用。
- 纽扣电池供电场景下，调试时建议外部稳定电源，避免电压跌落。

### 3.1 nRF52810 模组：使用 ST-LINK + OpenOCD 进行连接验证、编译与烧录

本项目中的 nRF52810 标签节点可以使用 **ST-LINK 通过 SWD 接口**连接，不要求只能使用 Nordic 官方 DK 或 J-Link。Windows 终端下推荐使用 xPack OpenOCD 进行连接验证、擦除和烧录。

硬件连接：

- `ST-LINK SWDIO` -> `nRF52810 SWDIO`
- `ST-LINK SWCLK` -> `nRF52810 SWCLK`
- `ST-LINK GND` -> `nRF52810 GND`
- nRF52810 需要稳定 3.3V 供电。
- 如果使用外部 3.3V 供电，必须与 ST-LINK 共地。
- 不建议直接给裸模块上 5V。

安装 xPack OpenOCD：

```powershell
winget install xpack-dev-tools.openocd-xpack
```

安装后验证：

```powershell
openocd --version
```

ST-LINK 连接验证：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; targets; shutdown"
```

该命令只用于验证 ST-LINK 是否能够通过 SWD 正确识别 nRF52810，不会烧录程序。连接成功时，终端通常会出现类似 STLINK 版本、Target voltage、Cortex-M4 detected、nRF52810-QFAA 等信息。

擦除：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; nrf52 mass_erase; shutdown"
```

烧录 `build/merged.hex`：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; program build/merged.hex verify reset; shutdown"
```

如果使用 Zephyr / nRF Connect SDK 默认产物路径，则烧录 `build/zephyr/merged.hex`：

```powershell
openocd -f interface/stlink.cfg -f target/nrf52.cfg -c "adapter speed 1000; init; reset halt; program build/zephyr/merged.hex verify reset; shutdown"
```

如果使用 nRF Connect SDK / Zephyr / west，可先编译生成 hex 文件：

```powershell
west build -b nrf52dk_nrf52810 . -p always
```

本工程已有自定义 board 配置时，也可以继续使用前文的 `clip_node_nrf52810` 目标。常见产物位置：

```text
build/zephyr/merged.hex
```

如果实际工程使用自定义 Makefile、CMake 或其他构建系统，则按实际工程编译生成 hex 文件，再替换上方 OpenOCD `program` 命令中的 hex 路径。

常见问题：

- 如果 OpenOCD 提示找不到 `interface/stlink.cfg` 或 `target/nrf52.cfg`，说明 OpenOCD scripts 路径没有被正确识别，需要检查 xPack OpenOCD 安装路径或环境变量。
- 如果提示无法连接 target，优先检查 `SWDIO` / `SWCLK` 是否接反、`GND` 是否共地、模块是否有 3.3V 供电。
- 如果 Target voltage 异常或为 0，说明 ST-LINK 没有检测到目标板电压。
- 如果烧录失败，可以先执行 mass erase 再重新烧录。
- 如果连接不稳定，可以把 `adapter speed` 从 `1000` 降到 `500` 或 `100`。

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

说明：当前 DTS 已按 EWT73-2G4M04S1A 测试套件分配测试引脚。切换到正式智能寻物标签 PCB 时，优先替换 `boards/nordic/clip_node_nrf52810/clip_node_nrf52810.dts` 中的 Devicetree alias 和 pinctrl 映射，保持应用层逻辑名称不变。

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

已提供以下模块：

- BLE 通信模块（简化服务 + mock 命令接收入口）
- 智能寻物标签状态机（idle / bound / authorized / alerting / removed / confirmed / low_battery / exception）
- 控制命令解析与分发（轻量二进制协议）
- 事件上报接口
- 全彩 RGB 三路 PWM 控制（R/G/B 三针 PWM 电压输入，7 档亮度）
- 无源蜂鸣器 PWM 发声模式控制（含最大持续时间限制）
- 取下检测（GPIO + 软件消抖）
- 电池检测（ADC + 电量等级）
- 非告警状态关闭 RGB、蜂鸣器和电池分压的低功耗约束

## 8. 重要设计约束

- nRF52810 资源受限，不引入复杂 JSON 解析。
- 智能寻物标签与网关通信协议采用轻量二进制帧。
- 用户权限、包裹绑定、数据库、云同步均不在智能寻物标签端实现。
- 智能寻物标签不存储用户和包裹隐私数据。
- 智能寻物标签仅保留 `tag_id`、短 `binding_token` 或 hash、`device_config`、`last_state`。

## 实体智能寻物标签测试流程

该流程用于从 mock BLE 阶段过渡到真实 E73-2G4M04S1A / nRF52810 硬件测试。当前阶段只验证智能寻物标签的本地硬件能力和 BLE 执行能力，不要求接入完整 server/gateway 生产链路。

### 1. 硬件准备

当前测试硬件：

- 测试套件：EWT73-2G4M04S1A
- 核心模组：E73-2G4M04S1A / nRF52810
- 供电：开发板 Type-C 或稳定 3.3V 电源
- 调试：SWD / J-Link / nRF Connect for VS Code
- 外设：全彩 RGB 灯或 5050 RGB 灯珠测试板，通过 R/G/B 三针 PWM 电压输入调节三原色
- 外设：无源蜂鸣器，可配合 MOSFET/NPN 驱动，由 `P0.16` 输出 PWM 方波发声
- 外设：触点/微动开关，用于模拟标签被取下或夹具状态变化
- 外设：电池分压采样电路，用于模拟 CR2032 电压检测

安全与结构提醒：

- 模组供电不得超过 3.6V。
- 调试器与目标板必须共地。
- `SWDIO` / `SWDCLK` 不作为普通 GPIO 使用。
- 测试套件适合验证固件和引脚，正式智能寻物标签应使用单独 E73 小模组设计 PCB。

### 2. 引脚连接确认

详细说明见 `docs/hardware_pins.md`。当前测试引脚：

- `PIN_LED_R_PWM = P0.11`
- `PIN_LED_G_PWM = P0.12`
- `PIN_LED_B_PWM = P0.15`
- `PIN_BUZZER_CTRL = P0.16`
- `PIN_REMOVE_SENSE = P0.19`
- `PIN_BAT_ADC = P0.02 / AIN0`
- `PIN_BAT_DIV_EN = P0.20`
- `PIN_USER_BTN = P0.21`
- `PIN_STATUS_LED = P0.22`

### 3. 编译固件

```bash
cd clip-node-nrf52810
west build -b clip_node_nrf52810 . -p
```

说明：

- 如果使用 VS Code nRF Connect 插件，也可以通过 `Add Build Configuration` 选择 `clip_node_nrf52810` 后 Build。
- 编译产物只用于本地烧录，不应提交到 Git。
- `.gitignore` 应忽略 `build/`、`.hex`、`.bin`、`.elf`、`.map` 等产物。

### 4. 烧录固件

```bash
west flash
```

也可以使用 VS Code nRF Connect 的 `Flash` 按钮。

烧录后应通过 RTT 或串口日志看到：

- 固件版本或启动 banner
- `tag_id`
- 当前状态
- 电池状态
- BLE 初始化状态
- 外设初始化结果

### 5. 本地硬件自检

建议固件提供 test mode 或 mock command 入口，用于不接入完整生产链路时验证本地外设。

| 测试项 | 预期现象 |
| --- | --- |
| RGB 红色点亮 | 红灯点亮 1 秒后熄灭 |
| RGB 绿色点亮 | 绿灯点亮 1 秒后熄灭 |
| RGB 蓝色点亮 | 蓝灯点亮 1 秒后熄灭 |
| RGB 寻物闪烁模式 | RGB 按寻物模式周期闪烁 |
| 蜂鸣器短鸣 | 无源蜂鸣器收到 PWM 方波，鸣叫 100~300ms 后停止 |
| 蜂鸣器间歇鸣叫 | 无源蜂鸣器按间歇 PWM 方波鸣叫，非告警时 PWM 输出关闭 |
| 触点输入变化检测 | 按下/松开微动开关后，RTT 日志输出 `REMOVE_SENSE_CHANGED` |
| 电池 ADC 采样 | 打开分压使能，完成 ADC 采样后关闭分压使能 |
| 电池低电压模拟 | 降低模拟输入后，状态上报 `LOW` 或 `CRITICAL` |
| 30 秒自动停止告警 | 执行 `WAKE_TAG` 后 RGB 和蜂鸣器工作，最长 30 秒后自动停止 |

### 6. BLE 寻物命令测试

当前正式 GATT 服务仍可处于 mock 阶段，但代码保留 mock BLE 命令入口，便于后续替换为真实 GATT Service。

可测试命令：

- `PING`：确认智能寻物标签在线
- `READ_STATUS`：读取状态、电池等级、绑定状态
- `WAKE_TAG`：触发寻物提醒
- `STOP_ALERT`：停止寻物提醒
- `SET_BINDING`：写入测试绑定信息
- `CLEAR_BINDING`：清除测试绑定信息

gateway 在门禁取件会话中下发 `WAKE_TAG` 时，payload 语义如下。标签固件仍使用轻量二进制帧承载这些字段，以下 JSON 仅用于文档说明：

```json
{
  "cmd": "WAKE_TAG",
  "tag_id": "TAG001",
  "pickup_session_id": "sess_xxx",
  "led_color": "BLUE",
  "blink_pattern": "SLOW",
  "beep_pattern": "SHORT_INTERVAL",
  "duration_sec": 30
}
```

标签端行为：

- 按 `led_color` 控制全彩 RGB 三针 PWM 输出。
- 按 `blink_pattern` 执行闪烁模式。
- 按 `beep_pattern` 控制无源蜂鸣器 PWM 方波。
- 到达 `duration_sec` 后自动停止。
- 收到 `STOP_ALERT` 后立即关闭 RGB 和蜂鸣器。
- 不保存用户、包裹、货架号等隐私信息。

预期行为：

- `WAKE_TAG` 后进入 `alerting`
- RGB 闪烁
- 蜂鸣器间歇鸣叫
- 30 秒超时自动停止
- `STOP_ALERT` 可立即停止
- `READ_STATUS` 能返回当前状态

### 7. 与 SPS 网关 mock 流程的关系

当前 `smartparcel-gateway` 仍保留 mock BLE / mock NFC 流程。实体智能寻物标签测试完成后，下一阶段才将 gateway 的 mock BLE 替换为真实 BLE 控制。

当前阶段关系如下：

```text
server 负责包裹与用户侧数据
gateway 负责本地认证、标签绑定、寻物任务创建
智能寻物标签负责 BLE 接收命令、亮灯、蜂鸣、状态上报
```

边界约束：

- 智能寻物标签不保存用户隐私。
- 智能寻物标签不保存包裹详情。
- 智能寻物标签只保存最小设备信息、绑定 token 或测试绑定状态。
- 真实 BLE 接入前，gateway 侧 mock 流程可以继续保留。

### 8. 阶段验收标准

实体智能寻物标签测试通过条件：

- 固件可以成功编译。
- 固件可以成功烧录到 EWT73-2G4M04S1A。
- RTT 或串口日志能正常输出启动信息。
- RGB 三色和寻物闪烁模式正常。
- 无源蜂鸣器 PWM 短鸣和间歇鸣叫正常。
- 触点输入变化能被检测并消抖。
- 电池 ADC 可以完成一次采样。
- `WAKE_TAG` 能触发寻物提醒。
- `STOP_ALERT` 能停止寻物提醒。
- 寻物提醒超时后能自动停止。
- 非告警状态下 RGB、蜂鸣器、电池分压默认关闭。
- Git 状态中不出现 `build/`、`.hex`、`.bin`、`.elf` 等编译或烧录产物。

## 9. 后续落地建议

1. 根据实体接线完成 `docs/test_plan_e73_2g4m04s1a.md` 的逐项验证。
2. 将 `ble_clip_service` 中 mock 接口替换为正式 GATT Service。
3. 补充 `settings`/NVS（仅存储必要设备参数，避免隐私数据）。
4. 做功耗实测：空闲电流、告警电流、日均电量消耗。
