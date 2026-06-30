#include "display_board_ctrl.h"

#include <inttypes.h>

#include "app_config.h"
#include "driver/i2c.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "board_ctrl";

/*
 * PCA9536 registers:
 *   0x00 — Input Port  (read-only)
 *   0x01 — Output Port (read/write)
 *   0x02 — Polarity    (read/write)
 *   0x03 — Config      (read/write, 1=input, 0=output)
 */
#define PCA9536_REG_INPUT    0x00
#define PCA9536_REG_OUTPUT   0x01
#define PCA9536_REG_POLARITY 0x02
#define PCA9536_REG_CONFIG   0x03

static bool s_initialized;
static bool s_pca9536_present;

/*
 * Current output and config shadow.
 * Power-on: output=0x00, config=0x0F (all inputs).
 */
static uint8_t s_output_shadow;
static uint8_t s_config_shadow = 0x0F;

/* ── Low-level I2C helpers ─────────────────────────────────── */

static esp_err_t pca9536_read_reg(uint8_t reg, uint8_t *value)
{
    return i2c_master_write_read_device(
        SPS_DISPLAY_BOARD_I2C_PORT,
        SPS_PCA9536_I2C_ADDR,
        &reg, 1,
        value, 1,
        pdMS_TO_TICKS(50));
}

static esp_err_t pca9536_write_reg(uint8_t reg, uint8_t value)
{
    uint8_t buf[2] = {reg, value};
    return i2c_master_write_to_device(
        SPS_DISPLAY_BOARD_I2C_PORT,
        SPS_PCA9536_I2C_ADDR,
        buf, sizeof(buf),
        pdMS_TO_TICKS(50));
}

/* ── Public API ────────────────────────────────────────────── */

esp_err_t display_board_ctrl_probe_registers(void)
{
    if (!s_pca9536_present) {
        ESP_LOGW(TAG, "PCA9536 not present, skip register probe");
        return ESP_ERR_NOT_FOUND;
    }

    ESP_LOGI(TAG, "=== PCA9536 register probe @ 0x%02X ===", SPS_PCA9536_I2C_ADDR);

    for (uint8_t reg = 0; reg <= 0x03; reg++) {
        uint8_t val = 0;
        esp_err_t err = pca9536_read_reg(reg, &val);
        if (err == ESP_OK) {
            const char *name = (reg == 0) ? "Input" :
                               (reg == 1) ? "Output" :
                               (reg == 2) ? "Polarity" : "Config";
            ESP_LOGI(TAG, "  reg 0x%02X (%s) = 0x%02X", reg, name, val);
        } else {
            ESP_LOGE(TAG, "  reg 0x%02X read failed: %s", reg, esp_err_to_name(err));
        }
    }

    ESP_LOGI(TAG, "=== PCA9536 probe done ===");
    return ESP_OK;
}

esp_err_t display_board_ctrl_init(void)
{
    if (s_initialized) {
        return ESP_OK;
    }

    /*
     * I2C bus should already be installed by touch_test_init() which
     * runs before display_ui_init() in display-first mode.
     * If not, try a quick install as fallback.
     */
    ESP_LOGI(TAG, "Initializing display board control...");
    ESP_LOGI(TAG, "  I2C port: %d, SDA: %d, SCL: %d",
             SPS_DISPLAY_BOARD_I2C_PORT,
             SPS_DISPLAY_BOARD_I2C_SDA_GPIO,
             SPS_DISPLAY_BOARD_I2C_SCL_GPIO);

    /* Quick probe to check if I2C bus is alive (driver already installed) */
    i2c_cmd_handle_t test_cmd = i2c_cmd_link_create();
    i2c_master_start(test_cmd);
    i2c_master_write_byte(test_cmd, (SPS_PCA9536_I2C_ADDR << 1) | I2C_MASTER_WRITE, true);
    i2c_master_stop(test_cmd);
    esp_err_t i2c_err = i2c_master_cmd_begin(SPS_DISPLAY_BOARD_I2C_PORT, test_cmd, pdMS_TO_TICKS(20));
    i2c_cmd_link_delete(test_cmd);

    if (i2c_err == ESP_ERR_INVALID_STATE) {
        /* I2C driver not installed — install as fallback */
        ESP_LOGI(TAG, "  I2C driver not yet installed, installing...");
        i2c_config_t i2c_conf = {
            .mode = I2C_MODE_MASTER,
            .sda_io_num = SPS_DISPLAY_BOARD_I2C_SDA_GPIO,
            .scl_io_num = SPS_DISPLAY_BOARD_I2C_SCL_GPIO,
            .sda_pullup_en = GPIO_PULLUP_ENABLE,
            .scl_pullup_en = GPIO_PULLUP_ENABLE,
            .master.clk_speed = SPS_DISPLAY_BOARD_I2C_FREQ_HZ,
            .clk_flags = 0,
        };
        i2c_err = i2c_param_config(SPS_DISPLAY_BOARD_I2C_PORT, &i2c_conf);
        if (i2c_err == ESP_OK) {
            i2c_err = i2c_driver_install(SPS_DISPLAY_BOARD_I2C_PORT,
                                         I2C_MODE_MASTER, 0, 0, 0);
        }
        if (i2c_err == ESP_OK) {
            ESP_LOGI(TAG, "  I2C driver installed (port %d)", SPS_DISPLAY_BOARD_I2C_PORT);
        } else {
            ESP_LOGE(TAG, "  I2C driver install failed: %s", esp_err_to_name(i2c_err));
            s_initialized = true;
            return i2c_err;
        }
    } else if (i2c_err == ESP_OK) {
        ESP_LOGI(TAG, "  I2C bus alive, PCA9536 probe OK");
    } else {
        ESP_LOGE(TAG, "  PCA9536 probe failed: %s", esp_err_to_name(i2c_err));
        goto not_found;
    }

    ESP_LOGI(TAG, "display board ctrl device found at 0x%02X (PCA9536)", SPS_PCA9536_I2C_ADDR);
    s_pca9536_present = true;

    /* Read initial state */
    esp_err_t reg_err;
    reg_err = pca9536_read_reg(PCA9536_REG_OUTPUT, &s_output_shadow);
    if (reg_err != ESP_OK) {
        ESP_LOGW(TAG, "read initial Output reg failed: %s", esp_err_to_name(reg_err));
        s_output_shadow = 0x00;
    }
    reg_err = pca9536_read_reg(PCA9536_REG_CONFIG, &s_config_shadow);
    if (reg_err != ESP_OK) {
        ESP_LOGW(TAG, "read initial Config reg failed: %s", esp_err_to_name(reg_err));
        s_config_shadow = 0x0F;
    }
    ESP_LOGI(TAG, "PCA9536 initial state: Output=0x%02X Config=0x%02X",
             s_output_shadow, s_config_shadow);

    /*
     * Configure IO0/IO1/IO2 as outputs, IO3 as input (default).
     * Config bit = 1 means input, 0 means output.
     *   IO0 (LCD_RST):  output -> bit0=0
     *   IO1 (TP_RST):   output -> bit1=0
     *   IO2 (BL_EN):    output -> bit2=0
     *   IO3 (reserved): input  -> bit3=1
     */
    s_config_shadow &= ~((1 << SPS_PCA9536_PIN_LCD_RST) |
                         (1 << SPS_PCA9536_PIN_TP_RST) |
                         (1 << SPS_PCA9536_PIN_BL_EN));
    s_config_shadow |= (1 << SPS_PCA9536_PIN_RESERVED);

    reg_err = pca9536_write_reg(PCA9536_REG_CONFIG, s_config_shadow);
    if (reg_err != ESP_OK) {
        ESP_LOGE(TAG, "write Config reg failed: %s", esp_err_to_name(reg_err));
        s_pca9536_present = false;
        return reg_err;
    }
    ESP_LOGI(TAG, "PCA9536 pins configured: IO0/IO1/IO2=output, IO3=input (Config=0x%02X)",
             s_config_shadow);

not_found:
    s_initialized = true;

    if (!s_pca9536_present) {
        ESP_LOGW(TAG, "PCA9536 @ 0x%02X NOT found", SPS_PCA9536_I2C_ADDR);
        ESP_LOGW(TAG, "display backlight control: unknown, via PCA9536 @ 0x%02X (not present)",
                 SPS_PCA9536_I2C_ADDR);
        ESP_LOGW(TAG, "display reset control: unknown, via PCA9536 @ 0x%02X (not present)",
                 SPS_PCA9536_I2C_ADDR);
        ESP_LOGW(TAG, "display board ctrl 0x%02X not present, cannot configure backlight/reset",
                 SPS_PCA9536_I2C_ADDR);
        ESP_LOGW(TAG, "TODO: check FPC connection, 0x41 power, and PCA9536 orientation on WLK2802MIPI-15P adapter board");
        return ESP_ERR_NOT_FOUND;
    }

    return ESP_OK;
}

esp_err_t display_board_ctrl_set_backlight(bool on)
{
    if (!s_pca9536_present) {
        ESP_LOGW(TAG, "backlight set skipped: PCA9536 not present");
        return ESP_ERR_NOT_FOUND;
    }

    uint8_t bit = (uint8_t)(1 << SPS_PCA9536_PIN_BL_EN);
    if (on) {
        s_output_shadow |= bit;
    } else {
        s_output_shadow &= ~bit;
    }

    esp_err_t err = pca9536_write_reg(PCA9536_REG_OUTPUT, s_output_shadow);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "backlight %s (Output=0x%02X, BL_EN IO%d=%d)",
                 on ? "ON" : "OFF",
                 s_output_shadow,
                 SPS_PCA9536_PIN_BL_EN,
                 on ? 1 : 0);
    } else {
        ESP_LOGE(TAG, "backlight write failed: %s", esp_err_to_name(err));
    }
    return err;
}

esp_err_t display_board_ctrl_panel_reset(void)
{
    if (!s_pca9536_present) {
        ESP_LOGW(TAG, "panel reset skipped: PCA9536 not present");
        return ESP_ERR_NOT_FOUND;
    }

    uint8_t bit = (uint8_t)(1 << SPS_PCA9536_PIN_LCD_RST);

    /* Assert reset low */
    s_output_shadow &= ~bit;
    ESP_RETURN_ON_ERROR(
        pca9536_write_reg(PCA9536_REG_OUTPUT, s_output_shadow),
        TAG, "panel reset LOW failed");
    ESP_LOGI(TAG, "panel reset: LOW (Output=0x%02X)", s_output_shadow);
    vTaskDelay(pdMS_TO_TICKS(20));

    /* Release reset high */
    s_output_shadow |= bit;
    ESP_RETURN_ON_ERROR(
        pca9536_write_reg(PCA9536_REG_OUTPUT, s_output_shadow),
        TAG, "panel reset HIGH failed");
    ESP_LOGI(TAG, "panel reset: HIGH (Output=0x%02X)", s_output_shadow);
    vTaskDelay(pdMS_TO_TICKS(120));

    ESP_LOGI(TAG, "panel reset sequence complete (IO%d: low 20ms -> high 120ms)",
             SPS_PCA9536_PIN_LCD_RST);
    return ESP_OK;
}

esp_err_t display_board_ctrl_touch_reset(void)
{
    if (!s_pca9536_present) {
        ESP_LOGW(TAG, "touch reset skipped: PCA9536 not present");
        return ESP_ERR_NOT_FOUND;
    }

    uint8_t bit = (uint8_t)(1 << SPS_PCA9536_PIN_TP_RST);

    /* Assert reset low */
    s_output_shadow &= ~bit;
    ESP_RETURN_ON_ERROR(
        pca9536_write_reg(PCA9536_REG_OUTPUT, s_output_shadow),
        TAG, "touch reset LOW failed");
    ESP_LOGI(TAG, "touch reset: LOW (Output=0x%02X)", s_output_shadow);
    vTaskDelay(pdMS_TO_TICKS(10));

    /* Release reset high */
    s_output_shadow |= bit;
    ESP_RETURN_ON_ERROR(
        pca9536_write_reg(PCA9536_REG_OUTPUT, s_output_shadow),
        TAG, "touch reset HIGH failed");
    ESP_LOGI(TAG, "touch reset: HIGH (Output=0x%02X)", s_output_shadow);
    vTaskDelay(pdMS_TO_TICKS(50));

    ESP_LOGI(TAG, "touch reset sequence complete (IO%d: low 10ms -> high 50ms)",
             SPS_PCA9536_PIN_TP_RST);
    return ESP_OK;
}
