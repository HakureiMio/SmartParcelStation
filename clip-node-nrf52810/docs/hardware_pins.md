# EWT73-2G4M04S1A hardware pin map

Current hardware validation uses the Ebyte EWT73-2G4M04S1A test kit with the E73-2G4M04S1A / nRF52810 module.

The test kit is suitable for firmware bring-up and GPIO/PWM/ADC verification. The production clip should use a standalone E73 module on a custom PCB. The EWT73 test kit board itself is not intended to be the final clip mechanical structure.

## Test pin assignment

| Signal | nRF52810 pin | Usage |
| --- | --- | --- |
| `PIN_LED_R_PWM` | `P0.11` | RGB red PWM output |
| `PIN_LED_G_PWM` | `P0.12` | RGB green PWM output |
| `PIN_LED_B_PWM` | `P0.15` | RGB blue PWM output |
| `PIN_BUZZER_CTRL` | `P0.16` | Active buzzer or MOSFET/NPN control |
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
- Keep the same logical names in firmware (`led-red-pwm`, `buzzer-ctrl`, `remove-sense`, `bat-adc`, `bat-div-en`) so application code does not need to change.
- Recheck active polarity for RGB LEDs, buzzer driver, remove contact, and battery divider enable on the production schematic.
