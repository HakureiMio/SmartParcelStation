#include "display_ui.h"

#include <stdint.h>

#include "app_config.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_lcd_mipi_dsi.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_ldo_regulator.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "display_ui";

typedef struct {
    uint8_t cmd;
    const uint8_t *data;
    size_t data_len;
    uint16_t delay_ms;
} st7701s_init_cmd_t;

#define ST7701S_CMD(command, delay, ...) \
    {                                    \
        (command),                       \
        (const uint8_t[]){__VA_ARGS__},  \
        sizeof((const uint8_t[]){__VA_ARGS__}), \
        (delay),                         \
    }

#define ST7701S_CMD0(command, delay) \
    {                                \
        (command),                   \
        NULL,                        \
        0,                           \
        (delay),                     \
    }

static const st7701s_init_cmd_t s_st7701s_init_cmds[] = {
    ST7701S_CMD(0xFF, 0, 0x77, 0x01, 0x00, 0x00, 0x13),
    ST7701S_CMD(0xEF, 0, 0x08),
    ST7701S_CMD(0xFF, 0, 0x77, 0x01, 0x00, 0x00, 0x10),
    ST7701S_CMD(0xC0, 0, 0x4F, 0x00),
    ST7701S_CMD(0xC1, 0, 0x10, 0x0C),
    ST7701S_CMD(0xC2, 0, 0x01, 0x14),
    ST7701S_CMD(0xCC, 0, 0x10),
    ST7701S_CMD(0xB0, 0, 0x0A, 0x18, 0x1E, 0x12, 0x16, 0x0C, 0x0E, 0x0D, 0x0C, 0x29, 0x06, 0x14, 0x13, 0x29, 0x33, 0x1C),
    ST7701S_CMD(0xB1, 0, 0x0A, 0x19, 0x21, 0x0A, 0x0C, 0x00, 0x0C, 0x03, 0x03, 0x23, 0x01, 0x0E, 0x0C, 0x27, 0x2B, 0x1C),
    ST7701S_CMD(0xFF, 0, 0x77, 0x01, 0x00, 0x00, 0x11),
    ST7701S_CMD(0xB0, 0, 0x5D),
    ST7701S_CMD(0xB1, 0, 0x61),
    ST7701S_CMD(0xB2, 0, 0x84),
    ST7701S_CMD(0xB3, 0, 0x80),
    ST7701S_CMD(0xB5, 0, 0x4D),
    ST7701S_CMD(0xB7, 0, 0x85),
    ST7701S_CMD(0xB8, 0, 0x20),
    ST7701S_CMD(0xC1, 0, 0x78),
    ST7701S_CMD(0xC2, 0, 0x78),
    ST7701S_CMD(0xD0, 0, 0x88),
    ST7701S_CMD(0xE0, 0, 0x00, 0x00, 0x02),
    ST7701S_CMD(0xE1, 0, 0x06, 0xA0, 0x08, 0xA0, 0x05, 0xA0, 0x07, 0xA0, 0x00, 0x44, 0x44),
    ST7701S_CMD(0xE2, 0, 0x20, 0x20, 0x44, 0x44, 0x96, 0xA0, 0x00, 0x00, 0x96, 0xA0, 0x00, 0x00),
    ST7701S_CMD(0xE3, 0, 0x00, 0x00, 0x22, 0x22),
    ST7701S_CMD(0xE4, 0, 0x44, 0x44),
    ST7701S_CMD(0xE5, 0, 0x0D, 0x91, 0xA0, 0xA0, 0x0F, 0x93, 0xA0, 0xA0, 0x09, 0x8D, 0xA0, 0xA0, 0x0B, 0x8F, 0xA0, 0xA0),
    ST7701S_CMD(0xE6, 0, 0x00, 0x00, 0x22, 0x22),
    ST7701S_CMD(0xE7, 0, 0x44, 0x44),
    ST7701S_CMD(0xE8, 0, 0x0C, 0x90, 0xA0, 0xA0, 0x0E, 0x92, 0xA0, 0xA0, 0x08, 0x8C, 0xA0, 0xA0, 0x0A, 0x8E, 0xA0, 0xA0),
    ST7701S_CMD(0xE9, 0, 0x36, 0x00),
    ST7701S_CMD(0xEB, 0, 0x00, 0x01, 0xE4, 0xE4, 0x44, 0x88, 0x40),
    ST7701S_CMD(0xED, 0, 0xFF, 0x45, 0x67, 0xFA, 0x01, 0x2B, 0xCF, 0xFF, 0xFF, 0xFC, 0xB2, 0x10, 0xAF, 0x76, 0x54, 0xFF),
    ST7701S_CMD(0xEF, 0, 0x10, 0x0D, 0x04, 0x08, 0x3F, 0x1F),
    ST7701S_CMD(0x3A, 0, 0x55),
    ST7701S_CMD0(0x11, 120),
    ST7701S_CMD0(0x29, 20),
    ST7701S_CMD(0x35, 0, 0x00),
};

typedef struct {
    uint16_t rgb565;
    const char *name;
} display_test_color_t;

static const display_test_color_t s_test_colors[] = {
    {0xF800, "red"},
    {0x07E0, "green"},
    {0x001F, "blue"},
    {0x0000, "black"},
    {0xFFFF, "white"},
};

static esp_lcd_panel_handle_t s_panel;
static esp_lcd_panel_io_handle_t s_dbi_io;
static esp_ldo_channel_handle_t s_mipi_phy_ldo;
static uint16_t *s_color_buffer;

static void show_text(const char *text)
{
    ESP_LOGI(TAG, "%s", text);
}

static uint64_t gpio_pin_mask(gpio_num_t gpio_num)
{
    return 1ULL << (uint32_t)gpio_num;
}

static esp_err_t configure_optional_gpio(void)
{
    if (SPS_DISPLAY_RESET_GPIO != GPIO_NUM_NC) {
        gpio_config_t reset_io = {
            .pin_bit_mask = gpio_pin_mask(SPS_DISPLAY_RESET_GPIO),
            .mode = GPIO_MODE_OUTPUT,
        };
        ESP_RETURN_ON_ERROR(gpio_config(&reset_io), TAG, "configure LCD reset GPIO failed");
        gpio_set_level(SPS_DISPLAY_RESET_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(20));
        gpio_set_level(SPS_DISPLAY_RESET_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(120));
    }

    if (SPS_DISPLAY_BACKLIGHT_GPIO != GPIO_NUM_NC) {
        gpio_config_t backlight_io = {
            .pin_bit_mask = gpio_pin_mask(SPS_DISPLAY_BACKLIGHT_GPIO),
            .mode = GPIO_MODE_OUTPUT,
        };
        ESP_RETURN_ON_ERROR(gpio_config(&backlight_io), TAG, "configure LCD backlight GPIO failed");
        gpio_set_level(SPS_DISPLAY_BACKLIGHT_GPIO, 0);
    }

    return ESP_OK;
}

static esp_err_t enable_mipi_dsi_phy_power(void)
{
    if (s_mipi_phy_ldo != NULL) {
        return ESP_OK;
    }

    esp_ldo_channel_config_t ldo_config = {
        .chan_id = SPS_DISPLAY_MIPI_DSI_PHY_LDO_CHAN,
        .voltage_mv = SPS_DISPLAY_MIPI_DSI_PHY_LDO_VOLTAGE_MV,
    };

    return esp_ldo_acquire_channel(&ldo_config, &s_mipi_phy_ldo);
}

static esp_err_t send_st7701s_init_sequence(void)
{
    for (size_t i = 0; i < sizeof(s_st7701s_init_cmds) / sizeof(s_st7701s_init_cmds[0]); i++) {
        const st7701s_init_cmd_t *init_cmd = &s_st7701s_init_cmds[i];
        ESP_RETURN_ON_ERROR(esp_lcd_panel_io_tx_param(s_dbi_io, init_cmd->cmd, init_cmd->data, init_cmd->data_len),
                            TAG,
                            "send ST7701S command 0x%02X failed",
                            init_cmd->cmd);
        if (init_cmd->delay_ms > 0) {
            vTaskDelay(pdMS_TO_TICKS(init_cmd->delay_ms));
        }
    }

    return ESP_OK;
}

static void fill_color_buffer(uint16_t color)
{
    const size_t pixels = SPS_DISPLAY_WIDTH * SPS_DISPLAY_HEIGHT;
    for (size_t i = 0; i < pixels; i++) {
        s_color_buffer[i] = color;
    }
}

static void display_color_test_task(void *arg)
{
    (void)arg;

    while (true) {
        for (size_t i = 0; i < sizeof(s_test_colors) / sizeof(s_test_colors[0]); i++) {
            fill_color_buffer(s_test_colors[i].rgb565);
            esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel,
                                                      0,
                                                      0,
                                                      SPS_DISPLAY_WIDTH,
                                                      SPS_DISPLAY_HEIGHT,
                                                      s_color_buffer);
            if (err == ESP_OK) {
                ESP_LOGI(TAG, "LCD color test: %s", s_test_colors[i].name);
            } else {
                ESP_LOGE(TAG, "draw %s failed: %s", s_test_colors[i].name, esp_err_to_name(err));
            }
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}

esp_err_t display_ui_init(void)
{
    if (s_panel != NULL) {
        return ESP_OK;
    }

    ESP_RETURN_ON_ERROR(enable_mipi_dsi_phy_power(), TAG, "enable MIPI DSI PHY power failed");
    ESP_RETURN_ON_ERROR(configure_optional_gpio(), TAG, "configure LCD optional GPIO failed");

    esp_lcd_dsi_bus_handle_t dsi_bus = NULL;
    esp_lcd_dsi_bus_config_t dsi_bus_config = {
        .bus_id = 0,
        .num_data_lanes = SPS_DISPLAY_MIPI_DSI_LANES,
        .lane_bit_rate_mbps = SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_dsi_bus(&dsi_bus_config, &dsi_bus), TAG, "create MIPI DSI bus failed");

    esp_lcd_dbi_io_config_t dbi_io_config = {
        .virtual_channel = 0,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_dbi(dsi_bus, &dbi_io_config, &s_dbi_io), TAG, "create MIPI DBI IO failed");
    ESP_RETURN_ON_ERROR(send_st7701s_init_sequence(), TAG, "initialize ST7701S failed");

    esp_lcd_dpi_panel_config_t dpi_panel_config = {
        .virtual_channel = 0,
        .dpi_clk_src = MIPI_DSI_DPI_CLK_SRC_DEFAULT,
        .dpi_clock_freq_mhz = SPS_DISPLAY_DPI_CLOCK_MHZ,
        .in_color_format = LCD_COLOR_FMT_RGB565,
        .out_color_format = LCD_COLOR_FMT_RGB565,
        .num_fbs = 1,
        .video_timing = {
            .h_size = SPS_DISPLAY_WIDTH,
            .v_size = SPS_DISPLAY_HEIGHT,
            .hsync_pulse_width = SPS_DISPLAY_HSYNC_PW,
            .hsync_back_porch = SPS_DISPLAY_HSYNC_BP,
            .hsync_front_porch = SPS_DISPLAY_HSYNC_FP,
            .vsync_pulse_width = SPS_DISPLAY_VSYNC_PW,
            .vsync_back_porch = SPS_DISPLAY_VSYNC_BP,
            .vsync_front_porch = SPS_DISPLAY_VSYNC_FP,
        },
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_dpi(dsi_bus, &dpi_panel_config, &s_panel), TAG, "create MIPI DPI panel failed");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_init(s_panel), TAG, "start MIPI DPI panel failed");

    const size_t buffer_size = SPS_DISPLAY_WIDTH * SPS_DISPLAY_HEIGHT * sizeof(uint16_t);
    s_color_buffer = heap_caps_malloc(buffer_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_color_buffer == NULL) {
        s_color_buffer = heap_caps_malloc(buffer_size, MALLOC_CAP_8BIT);
    }
    ESP_RETURN_ON_FALSE(s_color_buffer != NULL, ESP_ERR_NO_MEM, TAG, "allocate LCD color buffer failed");

    if (SPS_DISPLAY_BACKLIGHT_GPIO != GPIO_NUM_NC) {
        gpio_set_level(SPS_DISPLAY_BACKLIGHT_GPIO, 1);
    }

    BaseType_t task_created = xTaskCreate(display_color_test_task, "lcd_color_test", 4096, NULL, 4, NULL);
    ESP_RETURN_ON_FALSE(task_created == pdPASS, ESP_ERR_NO_MEM, TAG, "create LCD color test task failed");
    ESP_LOGI(TAG, "ST7701S color test started (%dx%d)", SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT);

    return ESP_OK;
}

void display_ui_show_booting(void)
{
    show_text("SPS Gate P4 booting...");
}

void display_ui_show_network_status(const char *text)
{
    show_text(text);
}

void display_ui_show_pn532_status(const char *text)
{
    show_text(text);
}

void display_ui_show_wait_card(void)
{
    show_text("Tap card");
}

void display_ui_show_uid(const char *uid)
{
    ESP_LOGI(TAG, "UID: %s", uid);
}

void display_ui_show_uploading(void)
{
    show_text("Uploading UID...");
}

void display_ui_show_access_result(const gateway_access_result_t *result)
{
    if (result != NULL && result->access_granted) {
        show_text("Access granted");
    } else {
        show_text("Access denied");
    }
}

void display_ui_show_error(const char *title, const char *detail)
{
    ESP_LOGE(TAG, "%s: %s", title, detail == NULL ? "" : detail);
}
