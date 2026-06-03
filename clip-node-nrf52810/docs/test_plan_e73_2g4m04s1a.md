# E73-2G4M04S1A / EWT73 test plan

This plan verifies the current clip-node firmware on the Ebyte EWT73-2G4M04S1A test kit with the E73-2G4M04S1A / nRF52810 module.

## 1. Flash firmware

```powershell
cd clip-node-nrf52810
west build -b clip_node_nrf52810 . -p
west flash
```

Confirm SWDIO, SWDCLK, VCC, and GND are connected to the debug probe. These pins are reserved for debug and power only.

## 2. Check RTT boot log

- Open VS Code nRF Connect RTT Terminal or J-Link RTT Viewer.
- Reset the board.
- Confirm logs include `clip node boot: EWT73-2G4M04S1A / E73-2G4M04S1A`.

## 3. Test full-color RGB PWM

- Send or mock `WAKE_TAG`.
- Confirm blue finding blink on `P0.15`.
- Use firmware effects or direct debug calls to confirm red `P0.11`, green `P0.12`, and blue `P0.15`.
- Confirm the full-color RGB lamp mixes color through the R/G/B PWM voltage inputs.

## 4. Test passive buzzer PWM

- Send or mock `WAKE_TAG`.
- Confirm intermittent PWM tone output on `P0.16`.
- Send or mock `STOP_ALERT` and confirm the PWM output turns off immediately.

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
- Confirm RGB and buzzer stop automatically and state returns to `bound` or `idle`.

## 8. Test `STOP_ALERT`

- Send or mock `WAKE_TAG`.
- Send or mock `STOP_ALERT` before 30 seconds.
- Confirm RGB and buzzer stop immediately.
- Confirm state returns to `bound` or `idle`.
