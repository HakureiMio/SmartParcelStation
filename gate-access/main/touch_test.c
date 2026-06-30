#include "touch_test.h"

#include <inttypes.h>
#include <string.h>

#include "app_config.h"
#include "driver/i2c.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"

static const char *TAG = "touch_test";
static bool s_i2c_ready;
static bool s_touch_found;
static uint8_t s_touch_addr;

static esp_err_t touch_read_regs(uint8_t reg, uint8_t *data, size_t size)
{
    return i2c_master_write_read_device(SPS_TOUCH_I2C_PORT, s_touch_addr,
                                        &reg, 1, data, size, pdMS_TO_TICKS(100));
}

static void scan_i2c_bus(void)
{
    unsigned found = 0;
    ESP_LOGI(TAG, "I2C scan start: port=%d SDA=%d SCL=%d (touch + board ctrl bus)",
             SPS_TOUCH_I2C_PORT,
             SPS_TOUCH_I2C_SDA_GPIO, SPS_TOUCH_I2C_SCL_GPIO);
    for (uint8_t address = 1; address < 0x7f; ++address) {
        i2c_cmd_handle_t cmd = i2c_cmd_link_create();
        if (cmd == NULL) {
            ESP_LOGE(TAG, "I2C scan command allocation failed");
            return;
        }
        i2c_master_start(cmd);
        i2c_master_write_byte(cmd, (address << 1) | I2C_MASTER_WRITE, true);
        i2c_master_stop(cmd);
        esp_err_t err = i2c_master_cmd_begin(SPS_TOUCH_I2C_PORT, cmd, pdMS_TO_TICKS(20));
        i2c_cmd_link_delete(cmd);
        if (err == ESP_OK) {
            ++found;
            if (address == 0x41) {
                ESP_LOGI(TAG, "I2C device found at 0x%02X — likely PCA9536 display board GPIO expander", address);
            } else if (address == 0x38) {
                ESP_LOGI(TAG, "I2C device found at 0x%02X — likely CST826/CST816S touch controller", address);
            } else if (address == 0x15) {
                ESP_LOGI(TAG, "I2C device found at 0x%02X — touch controller (preferred)", address);
            } else {
                ESP_LOGI(TAG, "I2C device found at 0x%02X", address);
            }
            if (address == SPS_TOUCH_I2C_ADDR) {
                s_touch_addr = address;
                s_touch_found = true;
            } else if (!s_touch_found && address == SPS_TOUCH_I2C_FALLBACK_ADDR) {
                s_touch_addr = address;
            }
        }
    }
    if (!s_touch_found && s_touch_addr == SPS_TOUCH_I2C_FALLBACK_ADDR) {
        s_touch_found = true;
        ESP_LOGW(TAG, "Preferred touch address 0x%02X absent; using compatible fallback 0x%02X",
                 SPS_TOUCH_I2C_ADDR, s_touch_addr);
    }
    ESP_LOGI(TAG, "I2C scan complete: %u device(s), selected touch address=%s",
             found,
             s_touch_found ? (s_touch_addr == SPS_TOUCH_I2C_ADDR ? "0x15" : "0x38") : "none");
    if (found > 1) {
        ESP_LOGI(TAG, "Multiple I2C devices on bus — 0x41 is the display board PCA9536 GPIO expander");
    }
}

esp_err_t touch_test_init(void)
{
    if (s_i2c_ready) {
        return s_touch_found ? ESP_OK : ESP_ERR_NOT_FOUND;
    }
    i2c_config_t config = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = SPS_TOUCH_I2C_SDA_GPIO,
        .scl_io_num = SPS_TOUCH_I2C_SCL_GPIO,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = SPS_TOUCH_I2C_FREQ_HZ,
        .clk_flags = 0,
    };

    esp_err_t err = i2c_param_config(SPS_TOUCH_I2C_PORT, &config);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "I2C param config (retry): %s", esp_err_to_name(err));
        /* Continue — driver may have been configured by display_board_ctrl */
    }

    err = i2c_driver_install(SPS_TOUCH_I2C_PORT, config.mode, 0, 0, 0);
    if (err == ESP_ERR_INVALID_STATE) {
        /* Driver already installed by display_board_ctrl_init() — OK, reuse */
        ESP_LOGI(TAG, "I2C driver already installed (port %d), reusing for touch",
                 SPS_TOUCH_I2C_PORT);
        err = ESP_OK;
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "install touch I2C failed: %s", esp_err_to_name(err));
        return err;
    }

    s_i2c_ready = true;
    ESP_LOGI(TAG, "Touch I2C ready at %" PRIu32 " Hz", (uint32_t)SPS_TOUCH_I2C_FREQ_HZ);
    scan_i2c_bus();
    if (s_touch_found) {
        uint8_t raw[6] = {0};
        esp_err_t probe_err = touch_read_regs(0x01, raw, sizeof(raw));
        if (probe_err == ESP_OK) {
            ESP_LOGI(TAG, "Touch probe 0x%02X raw[01..06]=%02X %02X %02X %02X %02X %02X",
                     s_touch_addr, raw[0], raw[1], raw[2], raw[3], raw[4], raw[5]);
        } else {
            ESP_LOGW(TAG, "Touch 0x%02X register probe failed: %s", s_touch_addr,
                     esp_err_to_name(probe_err));
            s_touch_found = false;
        }
    }
    return s_touch_found ? ESP_OK : ESP_ERR_NOT_FOUND;
}

esp_err_t touch_test_read(bool *pressed, uint16_t *x, uint16_t *y)
{
    if (pressed == NULL || x == NULL || y == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    *pressed = false;
    if (!s_i2c_ready || !s_touch_found) {
        return ESP_ERR_INVALID_STATE;
    }

    uint8_t raw[6] = {0};
    esp_err_t err = touch_read_regs(0x01, raw, sizeof(raw));
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "touch register read failed: %s", esp_err_to_name(err));
        return err;
    }
    uint8_t fingers = raw[1] & 0x0f;
    *x = (uint16_t)(((raw[2] & 0x0f) << 8) | raw[3]);
    *y = (uint16_t)(((raw[4] & 0x0f) << 8) | raw[5]);
#if SPS_TOUCH_SWAP_XY
    uint16_t swap = *x;
    *x = *y;
    *y = swap;
#endif
#if SPS_TOUCH_INVERT_Y
    if (*y < SPS_DISPLAY_HEIGHT) {
        *y = (SPS_DISPLAY_HEIGHT - 1) - *y;
    }
#endif
    *pressed = fingers > 0;
    if (fingers > 1 || (*pressed && (*x >= SPS_DISPLAY_WIDTH || *y >= SPS_DISPLAY_HEIGHT))) {
        ESP_LOGW(TAG, "unexpected touch data, raw[01..06]=%02X %02X %02X %02X %02X %02X",
                 raw[0], raw[1], raw[2], raw[3], raw[4], raw[5]);
    }
    return ESP_OK;
}
