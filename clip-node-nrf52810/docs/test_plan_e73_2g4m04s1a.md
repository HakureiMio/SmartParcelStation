# E73-2G4M04S1A / EWT73 test plan

This plan verifies the current clip-node firmware on the Ebyte EWT73-2G4M04S1A test kit with the E73-2G4M04S1A / nRF52810 module.

## 1. Flash firmware

```powershell
cd clip-node-nrf52810
west build -b clip_node_nrf52810 . -d build -p always
"D:\Program Files\SEGGER\JLink_V950\JLink.exe" -nogui 1 -CommanderScript tools\jlink_flash.jlink
```

Confirm SWDIO, SWDCLK, VCC, and GND are connected to the debug probe. These pins are reserved for debug and power only.

## 2. Check RTT boot log

- Open VS Code nRF Connect RTT Terminal or J-Link RTT Viewer.
- Reset the board.
- Confirm logs include `clip node boot: EWT73-2G4M04S1A / E73-2G4M04S1A`.

## 3. Test full-color RGB PWM

- Power on the board.
- Confirm RGB cycles through multiple colors continuously.
- Send or mock `WAKE_TAG`.
- Confirm blue finding blink on `P0.15`, then RGB returns to the rainbow cycle after alert stop.
- Use firmware effects or direct debug calls to confirm red `P0.11`, green `P0.12`, and blue `P0.15`.
- Confirm the full-color RGB lamp mixes color through the R/G/B PWM voltage inputs.

## 4. Test buzzer active-high output

- Power on the board.
- Confirm `P0.16` stays at active high level.
- Send or mock `WAKE_TAG` and `STOP_ALERT`, and confirm `P0.16` remains active high during this test stage.

## 5. Test clip contact input

- Toggle the clip contact wired to `P0.19`.
- Confirm RTT logs show a debounced stable change.
- Confirm firmware reports `CLIP_REMOVED` and `CLIP_RETURNED` events.

## 6. Test battery ADC sampling

- Send or mock `READ_STATUS`.
- Confirm `P0.20` enables the battery divider only during sampling.
- Confirm ADC reads from `P0.02 / AIN0`.
- Confirm RTT logs report battery state `OK`, `LOW`, or `CRITICAL`.

## 7. Test `WAKE_TAG` auto-stop

- Send or mock `WAKE_TAG`.
- Confirm state changes to `alerting`.
- Wait 30 seconds.
- Confirm RGB stops automatically and state returns to `bound` or `idle`; buzzer remains active high during this test stage.

## 8. Test `STOP_ALERT`

- Send or mock `WAKE_TAG`.
- Send or mock `STOP_ALERT` before 30 seconds.
- Confirm RGB stops immediately; buzzer remains active high during this test stage.
- Confirm state returns to `bound` or `idle`.
