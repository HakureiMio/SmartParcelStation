#include "display_ui.h"

#include <inttypes.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

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
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "qrcodegen.h"

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
static SemaphoreHandle_t s_framebuffer_mutex;

/* Five-pixel-wide, seven-pixel-high decimal digits. Each byte is one row. */
static const uint8_t s_digit_font[10][7] = {
    {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E}, /* 0 */
    {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E}, /* 1 */
    {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F}, /* 2 */
    {0x1E, 0x01, 0x01, 0x0E, 0x01, 0x01, 0x1E}, /* 3 */
    {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02}, /* 4 */
    {0x1F, 0x10, 0x10, 0x1E, 0x01, 0x01, 0x1E}, /* 5 */
    {0x0E, 0x10, 0x10, 0x1E, 0x11, 0x11, 0x0E}, /* 6 */
    {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}, /* 7 */
    {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E}, /* 8 */
    {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x01, 0x0E}, /* 9 */
};

enum {
    CN_SWIPE, CN_CARD, CN_SCAN, CN_CODE, CN_PHONE, CN_DEVICE,
    CN_PASS, CN_THROUGH, CN_FAIL, CN_DEFEAT, CN_PLEASE, CN_RETRY, CN_TRY,
    CN_SCHOOL, CN_GARDEN, CN_TOUCH, CN_ONE, CN_SCAN_DETAIL, CN_TWO, CN_DIMENSION,
    CN_ENTER, CN_STATION, CN_USER, CN_HOUSEHOLD, CN_LETTER, CN_INFO,
    CN_PARCEL, CN_WRAP, CN_NUMBER, CN_QUANTITY, CN_IDENTIFIER, CN_GOODS, CN_SHELF,
};

/* 16x16 monochrome glyphs generated from SimHei for the fixed gate UI text. */
static const uint16_t s_cn_font[][16] = {
    {0x1052,0x1052,0x1FD2,0x1012,0x1112,0x1FD2,0x1952,0x1952,0x3952,0x2942,0x29C2,0x010E,0x0100,0,0,0},
    {0x0180,0x01FC,0x0180,0x0180,0x3FFE,0x0180,0x0180,0x01F0,0x0198,0x0188,0x0180,0x0180,0,0,0,0},
    {0x08FE,0x0802,0x3F02,0x0802,0x0882,0x0EFE,0x1802,0x2802,0x0802,0x0802,0x09FE,0x1802,0,0,0,0},
    {0x3EFC,0x0844,0x0848,0x1048,0x1E48,0x32FE,0x3202,0x3202,0x12FA,0x1E02,0x1204,0x001C,0,0,0,0},
    {0x1FFC,0x0080,0x0080,0x1FFC,0x0080,0x0080,0x0080,0x3FFE,0x0080,0x0080,0x0080,0x0380,0,0,0,0},
    {0x08F8,0x0888,0x3E88,0x0888,0x1888,0x1E88,0x1A88,0x2888,0x2888,0x0888,0x090A,0x0B0E,0,0,0,0},
    {0x1098,0x0870,0x03FC,0x0224,0x3224,0x13FC,0x1224,0x13FC,0x1224,0x122C,0x1C00,0x23FE,0,0,0,0},
    {0x1808,0x0808,0x0FFE,0x0008,0x3988,0x0888,0x0888,0x0808,0x0818,0x0838,0x1E00,0x23FE,0,0,0,0},
    {0x0C80,0x0880,0x0FFC,0x1080,0x3080,0x0080,0x3FFE,0x01C0,0x0160,0x0230,0x0C1C,0x3806,0,0,0,0},
    {0x3F20,0x1120,0x153E,0x1544,0x1564,0x15A4,0x1528,0x3528,0x0C18,0x0A10,0x112C,0x20C6,0,0,0,0},
    {0x19FE,0x0C20,0x01FC,0x0020,0x3BFE,0x19FC,0x1904,0x19FC,0x1904,0x1FFC,0x1904,0x010C,0,0,0,0},
    {0x1FE0,0x0080,0x3FFE,0x0080,0x0FF8,0x0888,0x0FF8,0x0FF8,0x0080,0x1FFC,0x0080,0x3FFE,0,0,0,0},
    {0x1026,0x0824,0x07FE,0x0020,0x3030,0x13D0,0x1090,0x1090,0x1090,0x1CCA,0x1B8A,0x1006,0,0,0,0},
    {0x1020,0x1030,0x13FE,0x7C00,0x1088,0x10CC,0x3106,0x3D08,0x7488,0x50D8,0x5070,0x1020,0x10D8,0x178E,0x0202,0},
    {0x7FFC,0x3FFC,0x2004,0x27E4,0x2004,0x2FF4,0x2244,0x2244,0x2244,0x2654,0x2C74,0x2804,0x3FFC,0x2004,0x6000,0},
    {0x0088,0x0048,0x7C08,0x11FE,0x1050,0x3152,0x3D52,0x6552,0x6554,0x6554,0x2554,0x3C50,0x2450,0x27FE,0,0},
    {0,0,0,0,0,0,0x7FFE,0x7FFE,0,0,0,0,0,0,0,0},
    {0x1088,0x1088,0x13FE,0x1088,0x7C88,0x1000,0x13FC,0x3B24,0x7324,0x13FC,0x1324,0x1324,0x1324,0x33FC,0x0306,0},
    {0,0,0,0x3FF8,0,0,0,0,0,0,0,0x7FFE,0x7FFE,0,0,0},
    {0x10B0,0x3190,0x2100,0x2DFE,0x4B30,0x7B30,0x15FC,0x1130,0x2130,0x79FC,0x0130,0x0130,0x7DFE,0x4100,0x0100,0},
    {0x0090,0x3090,0x1090,0x07FE,0x0090,0x7090,0x1090,0x17FE,0x1110,0x1110,0x1310,0x1210,0x7E00,0x43FE,0,0},
    {0x1020,0x1820,0x0820,0x7E3E,0x0020,0x0420,0x2620,0x24FC,0x3484,0x1484,0x0484,0x1E84,0x70FC,0x0084,0x0080,0},
    {0x1FFC,0x118C,0x118C,0x1FFC,0x118C,0x118C,0x118C,0x1FFC,0x318C,0x318C,0x218C,0x218C,0x6198,0,0,0},
    {0x0180,0x0080,0x0080,0x1FFC,0x1004,0x1004,0x1004,0x1FFC,0x1004,0x1000,0x1000,0x3000,0x2000,0x6000,0,0},
    {0x0840,0x1860,0x17FE,0x1000,0x33FC,0x3000,0x5000,0x53FC,0x1000,0x13FC,0x1304,0x1304,0x13FC,0x1304,0x1000,0},
    {0x0300,0x0200,0x1FF8,0x1008,0x1FF8,0x1008,0x1FF8,0x1008,0x1FF8,0x0080,0x248C,0x2486,0x4412,0x07F0,0,0},
    {0x0400,0x0C00,0x1FF8,0x1008,0x3008,0x7FC8,0x5048,0x1048,0x1FC8,0x1008,0x1038,0x1002,0x1806,0x0FFE,0,0},
    {0x0180,0x7FFE,0,0x1FF8,0x1FF8,0x1088,0x1FF8,0x7FFE,0x0280,0x0D3C,0x7302,0x0678,0x1FB0,0x670E,0,0},
    {0x0C20,0x2D20,0x0F60,0x7FFE,0x1C44,0x3E44,0x6DCC,0x08C8,0x7F28,0x1128,0x3238,0x0E10,0x0D68,0x30C6,0x4000,0},
    {0x1FF8,0x1FF8,0x1008,0x1FF8,0x7FFE,0,0x1FF8,0x1FF8,0x1188,0x1FF8,0x3FF8,0x0180,0x7FFE,0,0,0},
    {0x0FF8,0x0818,0x0818,0x0FF8,0,0x7FFE,0x0400,0x0400,0x0FF8,0x0018,0x0018,0x0010,0x00F0,0x0080,0,0},
    {0x0440,0x0C4C,0x1878,0x39E0,0x6B42,0x087E,0x0800,0x1FF8,0x0FF8,0x0808,0x0988,0x0148,0x0278,0x7C0E,0x2000,0},
    {0x0800,0x087C,0x3F7C,0x0964,0x1964,0x1164,0x337C,0x4180,0x0180,0x7FFE,0x07E0,0x0DB0,0x318E,0x6182,0x0180,0},
};

static const uint8_t s_alpha_font[26][7] = {
    {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},
    {30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
    {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},
    {7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
    {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
    {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
    {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},
    {17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
    {17,17,10,4,4,4,4},{31,1,2,4,8,16,31},
};

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

static esp_err_t uid_hex_to_decimal(const char *hex, char *decimal, size_t decimal_size)
{
    uint8_t digits[32] = {0}; /* little-endian base-10 digits */
    size_t digit_count = 1;

    ESP_RETURN_ON_FALSE(hex != NULL && hex[0] != '\0' && decimal != NULL,
                        ESP_ERR_INVALID_ARG, TAG, "invalid UID");
    for (const char *p = hex; *p != '\0'; ++p) {
        unsigned nibble;
        if (*p >= '0' && *p <= '9') {
            nibble = (unsigned)(*p - '0');
        } else if (*p >= 'A' && *p <= 'F') {
            nibble = (unsigned)(*p - 'A' + 10);
        } else if (*p >= 'a' && *p <= 'f') {
            nibble = (unsigned)(*p - 'a' + 10);
        } else {
            return ESP_ERR_INVALID_ARG;
        }

        unsigned carry = nibble;
        for (size_t i = 0; i < digit_count; ++i) {
            unsigned value = (unsigned)digits[i] * 16U + carry;
            digits[i] = (uint8_t)(value % 10U);
            carry = value / 10U;
        }
        while (carry != 0) {
            ESP_RETURN_ON_FALSE(digit_count < sizeof(digits), ESP_ERR_INVALID_SIZE,
                                TAG, "UID decimal conversion overflow");
            digits[digit_count++] = (uint8_t)(carry % 10U);
            carry /= 10U;
        }
    }

    ESP_RETURN_ON_FALSE(digit_count + 1 <= decimal_size, ESP_ERR_INVALID_SIZE,
                        TAG, "UID decimal output buffer too small");
    for (size_t i = 0; i < digit_count; ++i) {
        decimal[i] = (char)('0' + digits[digit_count - 1 - i]);
    }
    decimal[digit_count] = '\0';
    return ESP_OK;
}

static void draw_decimal_digit(char digit, int x, int y, int scale, uint16_t color)
{
    const uint8_t *glyph = s_digit_font[digit - '0'];
    for (int row = 0; row < 7; ++row) {
        for (int col = 0; col < 5; ++col) {
            if ((glyph[row] & (1U << (4 - col))) == 0) {
                continue;
            }
            for (int dy = 0; dy < scale; ++dy) {
                int py = y + row * scale + dy;
                for (int dx = 0; dx < scale; ++dx) {
                    int px = x + col * scale + dx;
                    if (px >= 0 && px < SPS_DISPLAY_WIDTH && py >= 0 && py < SPS_DISPLAY_HEIGHT) {
                        s_color_buffer[py * SPS_DISPLAY_WIDTH + px] = color;
                    }
                }
            }
        }
    }
}

static void draw_cn_glyph(int glyph, int x, int y, int scale, uint16_t color)
{
    for (int row = 0; row < 16; ++row) {
        for (int col = 0; col < 16; ++col) {
            if ((s_cn_font[glyph][row] & (1U << (15 - col))) == 0) continue;
            for (int dy = 0; dy < scale; ++dy) {
                for (int dx = 0; dx < scale; ++dx) {
                    int px = x + col * scale + dx;
                    int py = y + row * scale + dy;
                    if (px >= 0 && px < SPS_DISPLAY_WIDTH && py >= 0 && py < SPS_DISPLAY_HEIGHT) {
                        s_color_buffer[py * SPS_DISPLAY_WIDTH + px] = color;
                    }
                }
            }
        }
    }
}

static void fill_rect(int x, int y, int width, int height, uint16_t color);

static void draw_ascii_text(const char *text, int x, int y, int scale,
                            int max_chars, uint16_t color)
{
    for (int i = 0; text != NULL && text[i] != '\0' && i < max_chars; ++i) {
        char ch = text[i];
        const uint8_t *rows = NULL;
        if (ch >= 'a' && ch <= 'z') ch = (char)(ch - 'a' + 'A');
        if (ch >= '0' && ch <= '9') rows = s_digit_font[ch - '0'];
        else if (ch >= 'A' && ch <= 'Z') rows = s_alpha_font[ch - 'A'];
        for (int row = 0; row < 7; ++row) {
            uint8_t bits = rows != NULL ? rows[row] : (ch == '-' && row == 3 ? 0x1F : 0);
            if (ch == '.' && row == 6) bits = 0x04;
            if (ch == '/' && row >= 1 && row <= 5) bits = (uint8_t)(1U << (6 - row));
            for (int col = 0; col < 5; ++col) if (bits & (1U << (4 - col))) {
                fill_rect(x + i * 6 * scale + col * scale, y + row * scale,
                          scale, scale, color);
            }
        }
    }
}

static void draw_cn_text(const int *glyphs, int count, int x, int y,
                         int scale, int gap, uint16_t color)
{
    for (int i = 0; i < count; ++i) {
        draw_cn_glyph(glyphs[i], x + i * (16 * scale + gap), y, scale, color);
    }
}

static void fill_rect(int x, int y, int width, int height, uint16_t color)
{
    for (int py = y; py < y + height && py < SPS_DISPLAY_HEIGHT; ++py) {
        for (int px = x; px < x + width && px < SPS_DISPLAY_WIDTH; ++px) {
            if (px >= 0 && py >= 0) s_color_buffer[py * SPS_DISPLAY_WIDTH + px] = color;
        }
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
    s_framebuffer_mutex = xSemaphoreCreateMutex();
    ESP_RETURN_ON_FALSE(s_framebuffer_mutex != NULL, ESP_ERR_NO_MEM, TAG,
                        "create LCD framebuffer mutex failed");
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

    xSemaphoreTake(s_framebuffer_mutex, portMAX_DELAY);
    fill_color_buffer(rgb565);
    esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel, 0, 0,
                                               SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT,
                                               s_color_buffer);
    xSemaphoreGive(s_framebuffer_mutex);
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

esp_err_t display_ui_show_card_id_numeric(const char *uid_hex)
{
    ESP_RETURN_ON_FALSE(s_panel != NULL && s_color_buffer != NULL && s_framebuffer_mutex != NULL,
                        ESP_ERR_INVALID_STATE, TAG, "LCD is not initialized");

    char decimal[32] = {0};
    ESP_RETURN_ON_ERROR(uid_hex_to_decimal(uid_hex, decimal, sizeof(decimal)), TAG,
                        "convert UID to decimal failed");

    const int scale = 8;
    const int glyph_advance = 6 * scale;
    const int glyph_height = 7 * scale;
    const int max_chars_per_line = SPS_DISPLAY_WIDTH / glyph_advance;
    const int digit_count = (int)strlen(decimal);
    const int line_count = (digit_count + max_chars_per_line - 1) / max_chars_per_line;
    const int chars_per_line = (digit_count + line_count - 1) / line_count;
    const int line_gap = 2 * scale;
    const int block_height = line_count * glyph_height + (line_count - 1) * line_gap;
    int source_index = 0;

    xSemaphoreTake(s_framebuffer_mutex, portMAX_DELAY);
    fill_color_buffer(0xFFFF); /* White card-result screen. */
    for (int line = 0; line < line_count; ++line) {
        int remaining = digit_count - source_index;
        int count = remaining < chars_per_line ? remaining : chars_per_line;
        int line_width = count * glyph_advance - scale;
        int x = (SPS_DISPLAY_WIDTH - line_width) / 2;
        int y = (SPS_DISPLAY_HEIGHT - block_height) / 2 + line * (glyph_height + line_gap);
        for (int i = 0; i < count; ++i) {
            draw_decimal_digit(decimal[source_index++], x + i * glyph_advance, y, scale, 0x0000);
        }
    }
    esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel, 0, 0,
                                               SPS_DISPLAY_WIDTH, SPS_DISPLAY_HEIGHT,
                                               s_color_buffer);
    xSemaphoreGive(s_framebuffer_mutex);

    if (err == ESP_OK) {
        ESP_LOGI(TAG, "CARD ID: %s", decimal);
    } else {
        ESP_LOGE(TAG, "draw card ID failed: %s", esp_err_to_name(err));
    }
    return err;
}

esp_err_t display_ui_show_qr(const char *payload)
{
    ESP_RETURN_ON_FALSE(s_panel != NULL && s_color_buffer != NULL && payload != NULL,
                        ESP_ERR_INVALID_STATE, TAG, "display/QR payload unavailable");

    size_t payload_len = strlen(payload);
    if (payload_len == 0 || payload_len > 2048) {
        ESP_LOGE(TAG, "QR payload length %u out of range", (unsigned)payload_len);
        return ESP_ERR_INVALID_SIZE;
    }

    const size_t qr_buffer_len = qrcodegen_BUFFER_LEN_FOR_VERSION(20);
    uint8_t *temp = heap_caps_malloc(qr_buffer_len, MALLOC_CAP_8BIT);
    uint8_t *qr   = heap_caps_malloc(qr_buffer_len, MALLOC_CAP_8BIT);
    if (temp == NULL) { free(qr); return ESP_ERR_NO_MEM; }
    if (qr   == NULL) { free(temp); return ESP_ERR_NO_MEM; }

    bool encoded = qrcodegen_encodeText(payload, temp, qr, qrcodegen_Ecc_MEDIUM,
                                         qrcodegen_VERSION_MIN, 20, qrcodegen_Mask_AUTO, true);
    if (!encoded) {
        ESP_LOGE(TAG, "qrcodegen_encodeText failed for payload len=%u", (unsigned)payload_len);
        free(temp); free(qr);
        return ESP_ERR_INVALID_SIZE;
    }
    int size = qrcodegen_getSize(qr);
    const int quiet = 4;
    int scale = 400 / (size + quiet * 2);
    if (scale < 1) scale = 1;
    int pixels = (size + quiet * 2) * scale;
    int origin_x = (SPS_DISPLAY_WIDTH - pixels) / 2;
    int origin_y = (SPS_DISPLAY_HEIGHT - pixels) / 2;

    ESP_LOGI(TAG, "QR draw: payload_len=%u qr_ver=%d scale=%d origin=(%d,%d) free_heap=%" PRIu32 " free_psram=%" PRIu32,
             (unsigned)payload_len, size, scale, origin_x, origin_y,
             esp_get_free_heap_size(), esp_get_free_internal_heap_size());

    xSemaphoreTake(s_framebuffer_mutex, portMAX_DELAY);
    fill_color_buffer(0xFFFF);
    for (int y = 0; y < size; ++y) {
        for (int x = 0; x < size; ++x) {
            if (!qrcodegen_getModule(qr, x, y)) continue;
            int px0 = origin_x + (x + quiet) * scale;
            int py0 = origin_y + (y + quiet) * scale;
            for (int dy = 0; dy < scale; ++dy) {
                for (int dx = 0; dx < scale; ++dx) {
                    int px = px0 + dx;
                    int py = py0 + dy;
                    if (px >= 0 && px < SPS_DISPLAY_WIDTH && py >= 0 && py < SPS_DISPLAY_HEIGHT) {
                        s_color_buffer[py * SPS_DISPLAY_WIDTH + px] = 0x0000;
                    }
                }
            }
        }
    }
    esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel, 0, 0, SPS_DISPLAY_WIDTH,
                                               SPS_DISPLAY_HEIGHT, s_color_buffer);
    xSemaphoreGive(s_framebuffer_mutex);
    free(temp); free(qr);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "QR_READY: matrix=%dx%d scale=%d origin=(%d,%d)",
                 size, size, scale, origin_x, origin_y);
    }
    return err;
}

esp_err_t display_ui_show_main_menu(void)
{
    ESP_RETURN_ON_FALSE(s_panel != NULL && s_color_buffer != NULL,
                        ESP_ERR_INVALID_STATE, TAG, "LCD is not initialized");
    const int scale = 2, glyph = 32, gap = 6;
    const int panel_x = 24, panel_w = SPS_DISPLAY_WIDTH - 48;
    const int line1[] = {CN_PLEASE, CN_PASS, CN_THROUGH, CN_SCHOOL, CN_GARDEN, CN_CARD};
    const int line2[] = {CN_PHONE, CN_DEVICE, CN_TOUCH, CN_ONE, CN_TOUCH};
    const int line3[] = {CN_SCAN, CN_SCAN_DETAIL, CN_TWO, CN_DIMENSION, CN_CODE, CN_ENTER, CN_STATION};

    xSemaphoreTake(s_framebuffer_mutex, portMAX_DELAY);
    fill_color_buffer(0xE73F);
    fill_rect(panel_x, 64, panel_w, 512, 0xFFFF);
    fill_rect(panel_x, 64, panel_w, 12, 0x047F);
    int w1 = 6 * glyph + 5 * gap, w2 = 5 * glyph + 4 * gap, w3 = 7 * glyph + 6 * gap;
    draw_cn_text(line1, 6, (SPS_DISPLAY_WIDTH - w1) / 2, 145, scale, gap, 0x18E3);
    draw_cn_text(line2, 5, (SPS_DISPLAY_WIDTH - w2) / 2, 300, scale, gap, 0x18E3);
    draw_cn_text(line3, 7, (SPS_DISPLAY_WIDTH - w3) / 2, 455, scale, gap, 0x18E3);
    draw_ascii_text("/", 225, 222, 5, 1, 0x7BEF);
    draw_ascii_text("/", 225, 377, 5, 1, 0x7BEF);

    esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel, 0, 0, SPS_DISPLAY_WIDTH,
                                               SPS_DISPLAY_HEIGHT, s_color_buffer);
    xSemaphoreGive(s_framebuffer_mutex);
    if (err == ESP_OK) ESP_LOGI(TAG, "MAIN_MENU: 刷卡 / 扫码 / 手机 NFC");
    return err;
}

esp_err_t display_ui_show_gate_result(const gateway_access_result_t *result, bool request_ok)
{
    ESP_RETURN_ON_FALSE(s_panel != NULL && s_color_buffer != NULL,
                        ESP_ERR_INVALID_STATE, TAG, "LCD is not initialized");
    bool granted = request_ok && result != NULL && result->access_granted;
    int phrase[3] = {CN_PLEASE, CN_RETRY, CN_TRY};
    int phrase_len = 3;
    uint16_t background = 0xFFE0;
    if (request_ok && granted) {
        phrase[0] = CN_PASS; phrase[1] = CN_THROUGH; phrase_len = 2;
        background = 0x07E0;
    } else if (request_ok) {
        phrase[0] = CN_FAIL; phrase[1] = CN_DEFEAT; phrase_len = 2;
        background = 0xF800;
    }

    const int scale = 4, glyph = 16 * scale, gap = 16;
    int width = phrase_len * glyph + (phrase_len - 1) * gap;
    int x = (SPS_DISPLAY_WIDTH - width) / 2;
    xSemaphoreTake(s_framebuffer_mutex, portMAX_DELAY);
    fill_color_buffer(granted ? 0xFFFF : background);
    for (int i = 0; i < phrase_len; ++i) {
        draw_cn_glyph(phrase[i], x + i * (glyph + gap), granted ? 48 : 225,
                      scale, granted ? 0x0640 : 0xFFFF);
    }

    if (granted) {
        const int user_label[] = {CN_USER, CN_HOUSEHOLD, CN_LETTER, CN_INFO};
        const int count_label[] = {CN_PARCEL, CN_WRAP, CN_NUMBER, CN_QUANTITY};
        const int code_label[] = {CN_GOODS, CN_SHELF, CN_IDENTIFIER, CN_CODE};
        draw_cn_text(user_label, 4, 38, 170, 2, 4, 0x39E7);
        draw_cn_text(count_label, 4, 38, 270, 2, 4, 0x39E7);
        draw_cn_text(code_label, 4, 38, 370, 2, 4, 0x39E7);
        draw_ascii_text(result->user_id[0] ? result->user_id : "-",
                        215, 176, 4, 10, 0x1082);
    }

    if (granted && result->pickup_count >= 0) {
        char count[12];
        snprintf(count, sizeof(count), "%d", result->pickup_count);
        int digit_scale = 4, advance = 6 * digit_scale;
        int count_x = 215;
        for (size_t i = 0; i < strlen(count); ++i) {
            draw_decimal_digit(count[i], count_x + (int)i * advance, 276,
                               digit_scale, 0x1082);
        }
    }
    if (granted) {
        const char *codes = result->shelves[0] ? result->shelves : "-";
        char shown[49];
        size_t len = strlen(codes), copy = len > 48 ? 48 : len;
        memcpy(shown, codes, copy);
        shown[copy] = '\0';
        if (len > 48) memcpy(shown + 45, "...", 4);
        size_t first_len = strlen(shown) > 24 ? 24 : strlen(shown);
        char second[25] = {0};
        if (shown[first_len] != '\0') strlcpy(second, shown + first_len, sizeof(second));
        shown[first_len] = '\0';
        draw_ascii_text(shown, 38, 425, 3, 24, 0x1082);
        if (second[0]) draw_ascii_text(second, 38, 475, 3, 24, 0x1082);
    }

    esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel, 0, 0, SPS_DISPLAY_WIDTH,
                                               SPS_DISPLAY_HEIGHT, s_color_buffer);
    xSemaphoreGive(s_framebuffer_mutex);
    ESP_LOGI(TAG, "RESULT_PAGE: request_ok=%s granted=%s user=%s text=%s pickup_count=%d shelves=%s parcels=%s reason=%s",
             request_ok ? "yes" : "no", granted ? "yes" : "no",
             result != NULL ? result->user_id : "",
             result != NULL ? result->display_text : "",
             result != NULL ? result->pickup_count : -1,
             result != NULL ? result->shelves : "",
             result != NULL ? result->parcel_codes : "",
             result != NULL ? result->reason : "");
    return err;
}

void display_ui_show_gate_state(const char *state, const gateway_access_result_t *result)
{
    uint16_t color = 0x07FF;
    if (state != NULL && strcmp(state, "GRANTED") == 0) color = 0x07E0;
    else if (state != NULL && strcmp(state, "DENIED") == 0) color = 0xF800;
    else if (state != NULL && strcmp(state, "ERROR") == 0) color = 0xFFE0;
    display_ui_fill_color(color, state == NULL ? "READY" : state);
    ESP_LOGI(TAG, "UI state=%s text=%s pickup_count=%d shelves=%s parcels=%s reason=%s color=%s",
             state == NULL ? "READY" : state,
             result != NULL ? result->display_text : "",
             result != NULL ? result->pickup_count : 0,
             result != NULL ? result->shelves : "",
             result != NULL ? result->parcel_codes : "",
             result != NULL ? result->reason : "",
             result != NULL ? result->session_color : "");
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
