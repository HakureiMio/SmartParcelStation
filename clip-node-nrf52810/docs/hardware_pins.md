# 硬件引脚分配（待补充）

当前项目为骨架版本，nRF52810 引脚号先留空，后续根据原理图补齐。

## 1. RGB PWM

- `PIN_LED_R_PWM`: TODO
- `PIN_LED_G_PWM`: TODO
- `PIN_LED_B_PWM`: TODO

说明：3 个 5050 RGB 灯珠同步显示，三路 PWM 即可。

## 2. 蜂鸣器驱动

- `PIN_BUZZER_CTRL`: TODO

说明：通过 MOSFET 或 NPN 三极管驱动 3V 有源蜂鸣器。

## 3. 取下检测输入

- `PIN_REMOVE_SENSE`: TODO

说明：可接微动开关/压力触点/机械触点，建议上拉并配合软件消抖。

## 4. 电池检测 ADC

- `PIN_BAT_ADC`: TODO（可选）
- `PIN_BAT_DIV_EN`: TODO（可选）

说明：`PIN_BAT_DIV_EN` 用于按需打开分压回路，降低静态漏电。

## 5. SWD 调试口

- `SWDIO`: 固定调试引脚
- `SWDCLK`: 固定调试引脚
- `RESET`: 建议引出
- `VCC`: 电平参考
- `GND`: 地
