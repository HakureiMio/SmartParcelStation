# EWT73-2G4M04S1A hardware pin map

Current hardware validation uses the Ebyte EWT73-2G4M04S1A test kit with the E73-2G4M04S1A / nRF52810 module.

The test kit is suitable for firmware bring-up and GPIO/PWM/ADC verification. The production smart tag should use a standalone E73 module on a custom PCB. The EWT73 test kit board itself is not intended to be the final mechanical structure.

## Test pin assignment

| Signal | nRF52810 pin | Usage |
| --- | --- | --- |
| `PIN_LED_R_PWM` | `P0.11` | Full-color RGB red PWM voltage input |
| `PIN_LED_G_PWM` | `P0.12` | Full-color RGB green PWM voltage input |
| `PIN_LED_B_PWM` | `P0.15` | Full-color RGB blue PWM voltage input |
| `PIN_BUZZER_CTRL` | `P0.16` | Passive buzzer PWM tone output |
| `PIN_REMOVE_SENSE` | `P0.19` | Clip contact/remove detect input |
| `PIN_BAT_ADC` | `P0.02 / AIN0` | Battery divider ADC input |
| `PIN_BAT_DIV_EN` | `P0.20` | Battery divider enable output |
| `PIN_USER_BTN` | `P0.21` | Optional test button |
| `PIN_STATUS_LED` | `P0.22` | Optional debug status LED |

## Reserved debug and power pins

- `SWDIO`, `SWDCLK`, `VCC`, and `GND` are reserved for SWD debug and board power.
- Do not use `SWDIO` or `SWDCLK` as normal GPIO in firmware or the production PCB.
- Keep `VCC` as the debug probe voltage reference and always share `GND`.

## Production PCB notes

- Replace the board DTS pin aliases when moving from the EWT73 test kit to the custom clip PCB.
- Keep the same logical names in firmware (`led-red-pwm`, `led-green-pwm`, `led-blue-pwm`, `buzzer-pwm`, `remove-sense`, `bat-adc`, `bat-div-en`) so application code does not need to change.
- Recheck RGB common-anode/common-cathode polarity, passive buzzer resonant frequency, remove contact polarity, and battery divider enable polarity on the production schematic.
