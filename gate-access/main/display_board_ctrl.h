#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

/*
 * display_board_ctrl — WLK2802MIPI-15P 屏幕转接板 I2C 控制
 *
 * 通过 PCA9536 @ 0x41 (4-bit I2C GPIO 扩展器) 控制：
 *   - LCD panel reset
 *   - Touch panel reset
 *   - Backlight enable
 *
 * 所有操作需要先调用 display_board_ctrl_init()。
 */

esp_err_t display_board_ctrl_init(void);
esp_err_t display_board_ctrl_set_backlight(bool on);
esp_err_t display_board_ctrl_panel_reset(void);
esp_err_t display_board_ctrl_touch_reset(void);
esp_err_t display_board_ctrl_probe_registers(void);
