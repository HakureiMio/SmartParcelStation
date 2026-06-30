#include "display_ui.h"

#include <inttypes.h>
#include <stdint.h>

#include "app_config.h"
#include "display_board_ctrl.h"
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

/*
 * ST7701S init sequence control.
 *
 * Software reset (0x01) is sent at runtime ONLY when PCA9536 hardware
 * reset is unavailable. The vendor init txt does not include 0x01 because
 * the factory driver uses a dedicated hardware reset GPIO.
 *
 * ST7701S_EXTRA_PAGE0_ENABLED:
 *   0 = follow vendor init txt exactly
 *   1 = insert 0xFF 0x77 0x01 0x00 0x00 0x00 before sleep out
 */
#define ST7701S_EXTRA_PAGE0_ENABLED 0

/* Inter-command delay when no explicit delay is specified (ms).
 * LP mode DCS transfers need time for the D-PHY to drain between commands. */
#define ST7701S_INTER_CMD_DELAY_MS   5

/* Initial DSI link stabilization delay after DBI IO creation (ms). */
#define ST7701S_DSI_STABILIZE_MS     30

/* Track whether PCA9536 provided a hardware reset before init sequence. */
static bool s_hw_reset_done;

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

/*
 * ST7701S initialization sequence.
 *
 * Source: vendor "4、初始化代码 ST7701S+28-480640_INIT.txt"
 * Aligned command-by-command.
 *
 * Differences from previous code:
 *   - 0xC2 data fixed: 0x01,0x14 (was 0x07,0x14 — typo)
 *   - 0x35 0x00 (TE on) added after 0x29 (was missing)
 *   - 0x01 software reset removed (vendor txt doesn't include it;
 *     hardware reset via PCA9536 is used instead)
 *   - Extra 0xFF page0 before sleep out removed (vendor txt doesn't
 *     include it; if needed, enable ST7701S_EXTRA_PAGE0_ENABLED)
 *
 * Key delays:
 *   - 0x11 (sleep out): 120ms
 *   - 0x29 (display on): delay set to 20ms for DSI LP drain
 */
static const st7701s_init_cmd_t s_st7701s_init_cmds[] = {
    /*
     * NOTE: Software reset (0x01) is NOT in this array.
     * It is sent at runtime via send_st7701s_soft_reset() ONLY when
     * PCA9536 hardware reset is unavailable.
     */

    /* Command page 1 */
    ST7701S_CMD(0xFF, 0, 0x77, 0x01, 0x00, 0x00, 0x13),
    ST7701S_CMD(0xEF, 0, 0x08),

    /* Command page 2 (0xFF 0x77 0x01 0x00 0x00 0x10) */
    ST7701S_CMD(0xFF, 0, 0x77, 0x01, 0x00, 0x00, 0x10),
    ST7701S_CMD(0xC0, 0, 0x4F, 0x00),
    ST7701S_CMD(0xC1, 0, 0x10, 0x0C),
    ST7701S_CMD(0xC2, 0, 0x01, 0x14),  /* Fixed: was 0x07,0x14 — vendor txt says 0x01,0x14 */
    ST7701S_CMD(0xCC, 0, 0x10),
    /* VOP gamma */
    ST7701S_CMD(0xB0, 0, 0x0A, 0x18, 0x1E, 0x12, 0x16, 0x0C, 0x0E, 0x0D, 0x0C, 0x29, 0x06, 0x14, 0x13, 0x29, 0x33, 0x1C),
    /* VON gamma */
    ST7701S_CMD(0xB1, 0, 0x0A, 0x19, 0x21, 0x0A, 0x0C, 0x00, 0x0C, 0x03, 0x03, 0x23, 0x01, 0x0E, 0x0C, 0x27, 0x2B, 0x1C),

    /* Command page 3 (0xFF 0x77 0x01 0x00 0x00 0x11) */
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

#if ST7701S_EXTRA_PAGE0_ENABLED
    /* Switch to command page 0 (safety, not in vendor txt) */
    ST7701S_CMD(0xFF, 0, 0x77, 0x01, 0x00, 0x00, 0x00),
#endif

    /* Sleep Out (0x11) — mandatory 120ms delay per vendor spec */
    ST7701S_CMD0(0x11, 120),

    /* Display On (0x29) */
    ST7701S_CMD0(0x29, 20),

    /* TE On (0x35 0x00) — per vendor init txt, avoids tearing */
    ST7701S_CMD(0x35, 0, 0x00),
};

static esp_lcd_panel_handle_t s_panel;
static esp_lcd_panel_io_handle_t s_dbi_io;
static esp_ldo_channel_handle_t s_mipi_phy_ldo;
static uint16_t *s_color_buffer;

static void show_text(const char *text)
{
    ESP_LOGI(TAG, "%s", text);
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

    esp_err_t err = esp_ldo_acquire_channel(&ldo_config, &s_mipi_phy_ldo);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "MIPI DSI PHY LDO ch%d @ %dmV enabled",
                 SPS_DISPLAY_MIPI_DSI_PHY_LDO_CHAN,
                 SPS_DISPLAY_MIPI_DSI_PHY_LDO_VOLTAGE_MV);
    }
    return err;
}

static esp_err_t send_st7701s_soft_reset(void)
{
    ESP_LOGI(TAG, "ST7701S: sending software reset 0x01 (HW reset unavailable, fallback)");
    esp_err_t err = esp_lcd_panel_io_tx_param(s_dbi_io, 0x01, NULL, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ST7701S software reset 0x01 failed: %s", esp_err_to_name(err));
        return err;
    }
    vTaskDelay(pdMS_TO_TICKS(120));
    ESP_LOGI(TAG, "ST7701S software reset 0x01 done (120ms delay)");
    return ESP_OK;
}

static esp_err_t send_st7701s_init_sequence(void)
{
    size_t cmd_count = sizeof(s_st7701s_init_cmds) / sizeof(s_st7701s_init_cmds[0]);
    ESP_LOGI(TAG, "ST7701S init: sending %u commands, inter-cmd delay=%dms",
             (unsigned)cmd_count, ST7701S_INTER_CMD_DELAY_MS);

    for (size_t i = 0; i < cmd_count; i++) {
        const st7701s_init_cmd_t *init_cmd = &s_st7701s_init_cmds[i];

        /* Log key commands before sending */
        if (init_cmd->cmd == 0x11) {
            ESP_LOGI(TAG, "ST7701S cmd[%u]: 0x%02X Sleep Out (delay %ums)",
                     (unsigned)i, init_cmd->cmd, init_cmd->delay_ms);
        } else if (init_cmd->cmd == 0x29) {
            ESP_LOGI(TAG, "ST7701S cmd[%u]: 0x%02X Display On (delay %ums)",
                     (unsigned)i, init_cmd->cmd, init_cmd->delay_ms);
        } else if (init_cmd->cmd == 0x35) {
            ESP_LOGI(TAG, "ST7701S cmd[%u]: 0x%02X TE On",
                     (unsigned)i, init_cmd->cmd);
        }

        esp_err_t err = esp_lcd_panel_io_tx_param(s_dbi_io, init_cmd->cmd,
                                                    init_cmd->data, init_cmd->data_len);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "ST7701S cmd[%u] 0x%02X failed: %s",
                     (unsigned)i, init_cmd->cmd, esp_err_to_name(err));
            return err;
        }

        if (init_cmd->delay_ms > 0) {
            vTaskDelay(pdMS_TO_TICKS(init_cmd->delay_ms));
        } else {
            vTaskDelay(pdMS_TO_TICKS(ST7701S_INTER_CMD_DELAY_MS));
        }
    }

    ESP_LOGI(TAG, "ST7701S init sequence complete (%u commands sent)", (unsigned)cmd_count);
    return ESP_OK;
}

static void fill_color_buffer(uint16_t color)
{
    const size_t pixels = SPS_DISPLAY_WIDTH * SPS_DISPLAY_HEIGHT;
    for (size_t i = 0; i < pixels; i++) {
        s_color_buffer[i] = color;
    }
}

esp_err_t display_ui_init(void)
{
    if (s_panel != NULL) {
        return ESP_OK;
    }

    ESP_LOGI(TAG, "=== Display initialization start ===");

    /* Step 1: Log configuration */
    ESP_LOGI(TAG, "  Resolution: %dx%d", SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT);
    ESP_LOGI(TAG, "  MIPI DSI lanes: %d, bitrate: %" PRIu32 " Mbps",
             SPS_DISPLAY_MIPI_DSI_LANES, (uint32_t)SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS);
    ESP_LOGI(TAG, "  DPI clock: %" PRIu32 " MHz", (uint32_t)SPS_DISPLAY_DPI_CLOCK_MHZ);
    ESP_LOGI(TAG, "  H: pw=%d bp=%d fp=%d  V: pw=%d bp=%d fp=%d",
             SPS_DISPLAY_HSYNC_PW, SPS_DISPLAY_HSYNC_BP, SPS_DISPLAY_HSYNC_FP,
             SPS_DISPLAY_VSYNC_PW, SPS_DISPLAY_VSYNC_BP, SPS_DISPLAY_VSYNC_FP);
    ESP_LOGI(TAG, "  Timing profile: %d", SPS_DISPLAY_TIMING_PROFILE);
    ESP_LOGI(TAG, "  ST7701S init source: vendor_txt_aligned");
    ESP_LOGI(TAG, "  ST7701S pixel format: RGB565");
    ESP_LOGI(TAG, "  ST7701S soft reset: runtime (fallback when HW reset unavailable)");
    ESP_LOGI(TAG, "  ST7701S extra page0: %d", ST7701S_EXTRA_PAGE0_ENABLED);
    ESP_LOGI(TAG, "  ST7701S sleep out delay: 120ms");
    ESP_LOGI(TAG, "  ST7701S display on delay: 20ms");
    ESP_LOGI(TAG, "  ST7701S inter-cmd delay: %dms", ST7701S_INTER_CMD_DELAY_MS);
    ESP_LOGI(TAG, "  ST7701S DSI stabilize delay: %dms", ST7701S_DSI_STABILIZE_MS);

    /* Step 2: Display board control init (PCA9536 @ 0x41)
     * This must happen before MIPI DSI PHY power, because the PCA9536
     * provides panel reset which should be asserted before DSI init. */
    ESP_LOGI(TAG, "Step 2: Init display board control (PCA9536 @ 0x41)...");
    s_hw_reset_done = false;
    esp_err_t board_err = display_board_ctrl_init();
    if (board_err == ESP_OK) {
        ESP_LOGI(TAG, "  PCA9536 @ 0x41 initialized — backlight and reset available");
        display_board_ctrl_probe_registers();

        /* Panel reset via PCA9536 IO0 BEFORE MIPI DSI init */
        ESP_LOGI(TAG, "  Asserting panel reset via PCA9536 IO%d...",
                 SPS_PCA9536_PIN_LCD_RST);
        board_err = display_board_ctrl_panel_reset();
        if (board_err == ESP_OK) {
            s_hw_reset_done = true;
            ESP_LOGI(TAG, "  Panel hardware reset done (PCA9536 IO%d)", SPS_PCA9536_PIN_LCD_RST);
        } else {
            ESP_LOGW(TAG, "  Panel reset via PCA9536 failed: %s", esp_err_to_name(board_err));
        }
    } else {
        ESP_LOGW(TAG, "  PCA9536 @ 0x41 NOT available — backlight/reset not controlled");
        ESP_LOGW(TAG, "  display backlight control: unknown, PCA9536 @ 0x41 not present");
        ESP_LOGW(TAG, "  display reset control: unknown, PCA9536 @ 0x41 not present");
        ESP_LOGW(TAG, "  display board ctrl 0x41 present but not configured — screen may stay dark");
        ESP_LOGW(TAG, "  Will use software reset (0x01) as fallback before ST7701S init");
    }

    /* Step 3: MIPI DSI PHY power */
    ESP_LOGI(TAG, "Step 3: Enable MIPI DSI PHY power...");
    ESP_RETURN_ON_ERROR(enable_mipi_dsi_phy_power(), TAG, "enable MIPI DSI PHY power failed");

    /* Step 4: Create DSI bus */
    ESP_LOGI(TAG, "Step 4: Create MIPI DSI bus (lanes=%d, bitrate=%" PRIu32 " Mbps)...",
             SPS_DISPLAY_MIPI_DSI_LANES, (uint32_t)SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS);
    esp_lcd_dsi_bus_handle_t dsi_bus = NULL;
    esp_lcd_dsi_bus_config_t dsi_bus_config = {
        .bus_id = 0,
        .num_data_lanes = SPS_DISPLAY_MIPI_DSI_LANES,
        .lane_bit_rate_mbps = SPS_DISPLAY_MIPI_DSI_LANE_BITRATE_MBPS,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_dsi_bus(&dsi_bus_config, &dsi_bus), TAG, "create MIPI DSI bus failed");
    ESP_LOGI(TAG, "  MIPI DSI bus created");

    /* Step 5: Create DBI IO for command mode */
    ESP_LOGI(TAG, "Step 5: Create MIPI DBI IO...");
    esp_lcd_dbi_io_config_t dbi_io_config = {
        .virtual_channel = 0,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_dbi(dsi_bus, &dbi_io_config, &s_dbi_io), TAG, "create MIPI DBI IO failed");
    ESP_LOGI(TAG, "  MIPI DBI IO created");

    /* DSI link stabilization: let D-PHY LP mode settle before first command.
     * Without this, the very first DCS command can hang if the DSI host
     * FIFO doesn't drain because the panel isn't listening yet. */
    ESP_LOGI(TAG, "  Waiting %dms for DSI link stabilization...", ST7701S_DSI_STABILIZE_MS);
    vTaskDelay(pdMS_TO_TICKS(ST7701S_DSI_STABILIZE_MS));

    /* Step 5b: Software reset fallback when PCA9536 HW reset not available.
     * The ST7701S must be in a known state before receiving init commands.
     * Without hardware reset, software reset (0x01) is the fallback.
     * The vendor init txt doesn't include it because the factory driver
     * uses a dedicated hardware reset GPIO. */
    if (!s_hw_reset_done) {
        ESP_LOGI(TAG, "Step 5b: Send software reset (0x01) — HW reset not done");
        esp_err_t sw_reset_err = send_st7701s_soft_reset();
        if (sw_reset_err != ESP_OK) {
            ESP_LOGE(TAG, "ST7701S software reset failed: %s", esp_err_to_name(sw_reset_err));
            ESP_LOGW(TAG, "Continuing init despite software reset failure...");
        }
    } else {
        ESP_LOGI(TAG, "Step 5b: Skip software reset — HW reset already done via PCA9536");
    }

    /* Step 6: Send ST7701S init sequence */
    ESP_LOGI(TAG, "Step 6: Send ST7701S init sequence...");
    ESP_RETURN_ON_ERROR(send_st7701s_init_sequence(), TAG, "initialize ST7701S failed");

    /* Step 7: Create DPI panel for video mode */
    ESP_LOGI(TAG, "Step 7: Create MIPI DPI panel (RGB565, %dx%d)...",
             SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT);
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
    ESP_LOGI(TAG, "  MIPI DPI panel created");

    /* Step 8: Start panel (enables DPI video stream) */
    ESP_LOGI(TAG, "Step 8: Start panel (enable DPI video output)...");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_init(s_panel), TAG, "start MIPI DPI panel failed");
    ESP_LOGI(TAG, "  Panel started — DPI video stream active");

    /* Step 9: Allocate frame buffer */
    ESP_LOGI(TAG, "Step 9: Allocate frame buffer...");
    const size_t buffer_size = SPS_DISPLAY_WIDTH * SPS_DISPLAY_HEIGHT * sizeof(uint16_t);
    ESP_LOGI(TAG, "  Buffer size: %u bytes (%ux%u RGB565)", (unsigned)buffer_size,
             SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT);
    s_color_buffer = heap_caps_malloc(buffer_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_color_buffer == NULL) {
        s_color_buffer = heap_caps_malloc(buffer_size, MALLOC_CAP_8BIT);
    }
    ESP_RETURN_ON_FALSE(s_color_buffer != NULL, ESP_ERR_NO_MEM, TAG, "allocate LCD color buffer failed");
    ESP_LOGI(TAG, "  Frame buffer allocated: addr=%p size=%u", (void *)s_color_buffer,
             (unsigned)buffer_size);

    /* Step 10: Turn on backlight via PCA9536 */
    ESP_LOGI(TAG, "Step 10: Turn on backlight...");
    board_err = display_board_ctrl_set_backlight(true);
    if (board_err == ESP_OK) {
        ESP_LOGI(TAG, "  Backlight ON (via PCA9536 IO%d)", SPS_PCA9536_PIN_BL_EN);
    } else {
        ESP_LOGW(TAG, "  Backlight control failed: %s", esp_err_to_name(board_err));
        ESP_LOGW(TAG, "  BACKLIGHT MAY BE OFF — screen will appear dark even if DSI/panel OK");
    }

    /* Step 11: Touch reset via PCA9536 */
    ESP_LOGI(TAG, "Step 11: Reset touch controller via PCA9536...");
    board_err = display_board_ctrl_touch_reset();
    if (board_err == ESP_OK) {
        ESP_LOGI(TAG, "  Touch reset complete (via PCA9536 IO%d)", SPS_PCA9536_PIN_TP_RST);
    } else {
        ESP_LOGW(TAG, "  Touch reset skipped: %s", esp_err_to_name(board_err));
    }

    ESP_LOGI(TAG, "=== Display initialization complete ===");
    ESP_LOGI(TAG, "ST7701S initialized (%dx%d)", SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT);
    ESP_LOGI(TAG, "draw bitmap returned ESP_OK, but physical backlight/panel visibility must be verified manually");

    return ESP_OK;
}

esp_err_t display_ui_fill_color(uint16_t rgb565, const char *name)
{
    ESP_RETURN_ON_FALSE(s_panel != NULL && s_color_buffer != NULL,
                        ESP_ERR_INVALID_STATE, TAG, "LCD is not initialized");

    ESP_LOGI(TAG, "draw start: color=%s (0x%04X) fb=%p size=%u",
             name == NULL ? "custom" : name,
             rgb565,
             (void *)s_color_buffer,
             (unsigned)(SPS_DISPLAY_WIDTH * SPS_DISPLAY_HEIGHT * sizeof(uint16_t)));

    fill_color_buffer(rgb565);
    esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel, 0, 0,
                                               SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT,
                                               s_color_buffer);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "draw done: color=%s (0x%04X) result=ESP_OK. "
                 "Reminder: ESP_OK means draw command sent; physical visibility depends on backlight + panel state.",
                 name == NULL ? "custom" : name, rgb565);
    } else {
        ESP_LOGE(TAG, "draw failed: color=%s (0x%04X) error=%s",
                 name == NULL ? "custom" : name, rgb565, esp_err_to_name(err));
    }
    return err;
}

/* ── UI text helpers (log-only for now) ────────────────────── */

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
