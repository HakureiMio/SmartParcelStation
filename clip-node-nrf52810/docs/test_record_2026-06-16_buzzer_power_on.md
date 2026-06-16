# Buzzer Power-On Test Record

Date: `2026-06-16`

## Background

This record captures the bring-up and fault isolation work for the EWT73-2G4M04S1A / E73-2G4M04S1A `clip-node-nrf52810` test firmware while verifying the buzzer control path on `P0.16`.

Target test goal:

- Drive `P0.16` active high after power-on.
- Confirm the buzzer works from normal battery power, not only during debug sessions.

## Initial Symptoms

- Firmware could be compiled and flashed.
- `P0.16` often had no output after reset or battery power-on.
- BLE advertising was not observed in earlier full-feature firmware builds.
- In some runs, the board entered HardFault after startup.
- Writing GPIO registers manually through J-Link could force `P0.16` high and make the buzzer sound.
- One flash cycle temporarily made the buzzer work, but the behavior was lost again after power cycling and reconnecting power.

## Key Observations

- J-Link manual register writes proved the buzzer path and output pin were electrically functional.
- A HardFault trace previously pointed into startup/runtime paths rather than the buzzer circuit itself.
- A later fault lookup showed the crash path touching Zephyr logging buffer allocation, not the buzzer GPIO code.
- Board-level defaults were still enabling `SEGGER RTT` and `LOG_BACKEND_RTT`, even after the application config set them to `n`.
- Flashing through `west flash --runner jlink` could fail with tool-side runner/probe issues, while direct J-Link Commander scripting was more transparent.

## Test Steps Performed

1. Reduced the firmware to a minimal buzzer test image.
2. Removed BLE and logging from the minimal validation build.
3. Replaced Zephyr GPIO abstraction in the minimal path with direct `nrf_gpio` control.
4. Added direct high-level drive for:
   - `P0.16` as buzzer test pin
   - `P0.22` as status test pin
5. Moved the GPIO high action into an early `SYS_INIT(..., PRE_KERNEL_1, 0)` hook.
6. Changed the J-Link flashing path to use a direct Commander script targeting:
   - `build/clip-node-nrf52810/zephyr/zephyr.hex`
7. Rebuilt with:

```powershell
west build -b clip_node_nrf52810 . -d build -p always
```

8. Flashed with:

```powershell
& "D:\Program Files\SEGGER\JLink_V950\JLink.exe" -nogui 1 -CommanderScript .\tools\jlink_flash.jlink
```

## Working Result

- After the latest firmware update, the buzzer started working normally.
- Buzzer sound level was clearly stronger than in the earlier unstable runs.
- After disconnecting J-Link and switching to battery power, the buzzer behavior remained valid.
- This confirmed the working state was no longer dependent on an active debugger session.

## Root Cause and Resolution

The issue was not the buzzer hardware itself. The board could always be driven by direct register writes from J-Link. The main problems were in the firmware bring-up path used during testing:

- startup instability in earlier firmware paths
- unnecessary logging / RTT involvement during minimal hardware validation
- board defaults re-enabling RTT-related options
- uncertainty introduced by flashing the merged image path instead of a direct application image during isolation

The effective resolution for this test stage was:

- use a minimal firmware path
- disable BLE and RTT logging for the isolation build
- force the buzzer pin high with direct `nrf_gpio` access
- execute the pin drive very early with `PRE_KERNEL_1`
- flash with a direct J-Link Commander script

## Files Involved

- [src/main.c](D:/Project/SmartParcelStation/clip-node-nrf52810/src/main.c:1)
- [src/early_gpio_test.c](D:/Project/SmartParcelStation/clip-node-nrf52810/src/early_gpio_test.c:1)
- [src/buzzer.c](D:/Project/SmartParcelStation/clip-node-nrf52810/src/buzzer.c:1)
- [prj.conf](D:/Project/SmartParcelStation/clip-node-nrf52810/prj.conf:1)
- [boards/nordic/clip_node_nrf52810/clip_node_nrf52810_defconfig](D:/Project/SmartParcelStation/clip-node-nrf52810/boards/nordic/clip_node_nrf52810/clip_node_nrf52810_defconfig:1)
- [boards/nordic/clip_node_nrf52810/Kconfig.defconfig](D:/Project/SmartParcelStation/clip-node-nrf52810/boards/nordic/clip_node_nrf52810/Kconfig.defconfig:1)
- [boards/nordic/clip_node_nrf52810/board.cmake](D:/Project/SmartParcelStation/clip-node-nrf52810/boards/nordic/clip_node_nrf52810/board.cmake:1)
- [tools/jlink_flash.jlink](D:/Project/SmartParcelStation/clip-node-nrf52810/tools/jlink_flash.jlink:1)

## Notes for Next Stage

- Keep this minimal image available as a hardware sanity-check baseline.
- When re-enabling BLE, RGB, sensor, and battery features, add them back one block at a time.
- If the issue reappears after feature reintroduction, compare behavior against this minimal known-good build first.
- In the current BLE recovery stage, buzzer business logic is intentionally commented out. The present battery path cannot reliably drive the buzzer together with the rest of the application load, so alert behavior is being validated with RGB only.
