#include <stdbool.h>
#include <string.h>

#include "app_config.h"
#include "display_board_ctrl.h"
#include "display_ui.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "gateway_client.h"
#include "network_client.h"
#include "nvs_flash.h"
#include "pn532_diag.h"
#include "pn532_reader.h"
#include "touch_test.h"

static const char *TAG = "sps_gate";

#define SPS_STANDBY_COLOR_RGB565 0x07FF

/* ── NVS init ───────────────────────────────────────────────── */

static esp_err_t init_nvs(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    return err;
}

/* ── Display-first debug mode ──────────────────────────────────
 *
 * When SPS_DEMO_DISPLAY_FIRST=1, app_main only does:
 *   1. init_nvs
 *   2. display_ui_init    (DSI + ST7701S + PCA9536 backlight/reset)
 *   3. touch_test_init    (I2C scan IO7/IO8, 0x38 + 0x41 probe)
 *   4. display_board_ctrl_probe_registers  (0x41 register dump)
 *   5. Color cycle or white screen or touch color test
 *
 * No PN532, no ESP8266, no gateway HTTP.
 */

#if SPS_DEMO_DISPLAY_FIRST

typedef struct {
    uint16_t rgb565;
    const char *name;
} demo_color_t;

static const demo_color_t s_color_cycle[] = {
    {0xF800, "red"},
    {0x07E0, "green"},
    {0x001F, "blue"},
    {0xFFFF, "white"},
    {0x0000, "black"},
};

#if SPS_DEMO_PN532_UID_TEST
/*
 * Card latch timeout: after the last successful card read, the displayed
 * UID stays visible for this many milliseconds before automatically
 * returning to standby.  Touch events also reset the latch immediately.
 */
#define SPS_CARD_LATCH_TIMEOUT_MS  3000

static void pn532_uid_test_task(void *arg)
{
    (void)arg;
#if SPS_PN532_UART_LOOPBACK_TEST
    esp_err_t loopback_err = pn532_reader_uart_loopback_test();
    if (loopback_err == ESP_OK) {
        ESP_LOGI(TAG, "PN532 UART2 hardware path verified; disable loopback macro before reconnecting PN532");
    } else {
        ESP_LOGE(TAG, "PN532 UART2 hardware path FAILED: %s", esp_err_to_name(loopback_err));
    }
    vTaskDelete(NULL);
#else
    char latched_uid[32] = {0};
    bool  card_latched = false;
    int64_t last_read_us = 0;    /* timestamp of last successful card read */
    unsigned poll_errors  = 0;

    ESP_LOGI(TAG, "=== PN532 continuous UID test ===");
    ESP_LOGI(TAG, "Present a card at any time; UID auto-clears after %dms",
             SPS_CARD_LATCH_TIMEOUT_MS);

    /* One-time init */
    esp_err_t err = pn532_reader_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PN532 init failed: %s; retrying", esp_err_to_name(err));
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    while (true) {
        /* Re-init if we got here via break from error recovery */
        if (err != ESP_OK) {
            err = pn532_reader_init();
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "PN532 re-init failed: %s", esp_err_to_name(err));
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
            ESP_LOGI(TAG, "PN532 re-initialized; polling ISO14443A every %dms",
                     SPS_CARD_POLL_INTERVAL_MS);
        }

        char uid_hex[32] = {0};
        bool card_present = false;
        err = pn532_reader_poll_uid(uid_hex, sizeof(uid_hex), &card_present);

        if (err == ESP_ERR_TIMEOUT) {
            /* ACK or response timeout → treat as "no card" */
            card_present = false;
            poll_errors++;
        } else if (err != ESP_OK) {
            /* Hard error */
            poll_errors++;
            if ((poll_errors % 5) == 0) {
                ESP_LOGW(TAG, "PN532 poll error: %s (count=%u)",
                         esp_err_to_name(err), poll_errors);
            }
        } else {
            poll_errors = 0;
        }

        if (card_present) {
            last_read_us = esp_timer_get_time();
            if (!card_latched || strcmp(uid_hex, latched_uid) != 0) {
                strlcpy(latched_uid, uid_hex, sizeof(latched_uid));
                card_latched = true;
                ESP_LOGI(TAG, "CARD: UID=%s (%u bytes)",
                         uid_hex, (unsigned)(strlen(uid_hex) / 2));
                esp_err_t draw_err = display_ui_show_card_id_numeric(uid_hex);
                if (draw_err != ESP_OK) {
                    ESP_LOGE(TAG, "Display card ID failed: %s", esp_err_to_name(draw_err));
                }
            }
        } else if (card_latched) {
            /* Card was previously latched — check timeout */
            int64_t elapsed_ms = (esp_timer_get_time() - last_read_us) / 1000;
            if (elapsed_ms >= SPS_CARD_LATCH_TIMEOUT_MS) {
                ESP_LOGI(TAG, "CARD TIMEOUT: UID=%s (absent for %lldms)",
                         latched_uid, elapsed_ms);
                display_ui_fill_color(SPS_STANDBY_COLOR_RGB565, "BLUE-GREEN (standby)");
                latched_uid[0] = '\0';
                card_latched = false;
            }
        }

        /* Recovery: too many consecutive errors → re-init PN532 */
        if (poll_errors >= 5) {
            ESP_LOGW(TAG, "PN532 %u consecutive errors; reinitializing", poll_errors);
            poll_errors = 0;
            err = ESP_FAIL;  /* trigger re-init on next iteration */
            continue;
        }

        vTaskDelay(pdMS_TO_TICKS(SPS_CARD_POLL_INTERVAL_MS));
    }
#endif
}
#endif

static void run_display_first(void)
{
    ESP_LOGI(TAG, "=== Display-first debug mode ===");
    ESP_LOGI(TAG, "SPS_DEMO_DISPLAY_FIRST=%d", SPS_DEMO_DISPLAY_FIRST);
    ESP_LOGI(TAG, "SPS_DEMO_FORCE_WHITE_SCREEN=%d", SPS_DEMO_FORCE_WHITE_SCREEN);
    ESP_LOGI(TAG, "SPS_DEMO_TOUCH_COLOR_TEST=%d", SPS_DEMO_TOUCH_COLOR_TEST);
    ESP_LOGI(TAG, "SPS_DEMO_PN532_UID_TEST=%d", SPS_DEMO_PN532_UID_TEST);

    /* Step 1: Init touch + I2C scan FIRST (installs I2C driver on IO7/IO8).
     * Must run before display_ui_init() because display uses PCA9536 @ 0x41
     * on the same I2C bus. */
    ESP_LOGI(TAG, "--- Init touch + I2C scan (installs I2C bus) ---");
    esp_err_t touch_err = touch_test_init();
    bool touch_available = (touch_err == ESP_OK);

    /* Step 2: Init display (reuses I2C driver for PCA9536 backlight/reset + ST7701S) */
    ESP_LOGI(TAG, "--- Init display ---");
    ESP_ERROR_CHECK(display_ui_init());
    display_ui_show_booting();
    if (!touch_available) {
        ESP_LOGW(TAG, "Touch unavailable: %s", esp_err_to_name(touch_err));
        ESP_LOGW(TAG, "Check: CST826/CST816S power, PCA9536 TP_RST, I2C wiring");
    } else {
        ESP_LOGI(TAG, "Touch available at advertised address");
    }

    /* Step 3: Probe PCA9536 registers again for debug visibility */
    ESP_LOGI(TAG, "--- PCA9536 @ 0x41 register probe ---");
    esp_err_t probe_err = display_board_ctrl_probe_registers();
    if (probe_err != ESP_OK) {
        ESP_LOGW(TAG, "PCA9536 probe failed: %s", esp_err_to_name(probe_err));
    }

#if SPS_DEMO_PN532_UID_TEST
    ESP_LOGI(TAG, "--- Start PN532 continuous UID reader ---");
    BaseType_t pn532_task_ok = xTaskCreate(pn532_uid_test_task, "pn532_uid_test", 4096,
                                           NULL, 5, NULL);
    if (pn532_task_ok != pdPASS) {
        ESP_LOGE(TAG, "Failed to create PN532 UID test task");
    }
#endif

#if SPS_DEMO_WIFI_ENABLE
    /* Step 4: Init ESP8266 WiFi (UART1, GPIO43 TX, GPIO44 RX).
     * WiFi failure must NOT block display/touch — log and continue.
     * Draw white first so the screen is visibly alive during connection. */
    ESP_LOGI(TAG, "--- Init ESP8266 WiFi ---");
    display_ui_fill_color(0xFFFF, "WHITE (WiFi init)");
    ESP_LOGI(TAG, "ESP8266 UART: port=%d TX=GPIO%d RX=GPIO%d BAUD=%d",
             SPS_ESP8266_UART_PORT,
             SPS_ESP8266_UART_TX_GPIO,
             SPS_ESP8266_UART_RX_GPIO,
             SPS_ESP8266_UART_BAUD);
    ESP_LOGI(TAG, "WiFi target: SSID=\"%s\"", SPS_WIFI_SSID);

    esp_err_t wifi_err = network_client_start();
    if (wifi_err == ESP_OK) {
        ESP_LOGI(TAG, "ESP8266 WiFi connected — IP obtained");
        display_ui_show_network_status("WiFi ready");
        display_ui_fill_color(0x07E0, "GREEN (WiFi OK)");
    } else {
        ESP_LOGE(TAG, "ESP8266 WiFi init/connect failed: %s", esp_err_to_name(wifi_err));
        ESP_LOGW(TAG, "Display and touch test will continue despite WiFi failure");
        display_ui_show_network_status("WiFi FAIL");
        display_ui_fill_color(0xF800, "RED (WiFi FAIL)");
    }
#endif /* SPS_DEMO_WIFI_ENABLE */

#if SPS_DEMO_FORCE_WHITE_SCREEN
    /* ── White screen test mode ──────────────────────────────
     * Continuously draw white to verify backlight is on.
     * If screen stays dark even with white drawn, backlight is off.
     */
    ESP_LOGI(TAG, "=== FORCE WHITE SCREEN mode ===");
    ESP_LOGI(TAG, "Screen should show solid WHITE. If dark, backlight is OFF.");
    while (true) {
        esp_err_t err = display_ui_fill_color(0xFFFF, "white");
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "White screen draw failed: %s", esp_err_to_name(err));
        }
        vTaskDelay(pdMS_TO_TICKS(200));
    }

#elif SPS_DEMO_TOUCH_COLOR_TEST
    /* ── Touch color test ────────────────────────────────────
     * Touch upper half -> green, lower half -> blue.
     * Also runs a one-time color cycle on startup.
     */
    ESP_LOGI(TAG, "=== Color cycle test (5 colors x 1s) ===");
    for (size_t i = 0; i < sizeof(s_color_cycle) / sizeof(s_color_cycle[0]); i++) {
        ESP_LOGI(TAG, "Cycle[%u/%u]: %s (0x%04X)",
                 (unsigned)(i + 1),
                 (unsigned)(sizeof(s_color_cycle) / sizeof(s_color_cycle[0])),
                 s_color_cycle[i].name,
                 s_color_cycle[i].rgb565);
        display_ui_fill_color(s_color_cycle[i].rgb565, s_color_cycle[i].name);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    ESP_LOGI(TAG, "=== Touch dual-zone color switch ===");
    ESP_LOGI(TAG, "  Upper half (y < %d)  -> RED   (0xF800)", SPS_DISPLAY_HEIGHT / 2);
    ESP_LOGI(TAG, "  Lower half (y >= %d) -> BLUE  (0x001F)", SPS_DISPLAY_HEIGHT / 2);
    ESP_LOGI(TAG, "  No touch             -> BLUE-GREEN (0x07FF)");

    bool was_pressed = false;
    unsigned read_failures = 0;

    /* Blue-green is the normal idle state. */
    display_ui_fill_color(SPS_STANDBY_COLOR_RGB565, "BLUE-GREEN (standby)");

    while (true) {
        if (touch_available) {
            bool pressed = false;
            uint16_t x = 0;
            uint16_t y = 0;
            esp_err_t err = touch_test_read(&pressed, &x, &y);
            if (err != ESP_OK) {
                if ((read_failures++ % 50) == 0) {
                    ESP_LOGW(TAG, "Touch read failed: %s", esp_err_to_name(err));
                }
            } else {
                read_failures = 0;

                if (pressed && !was_pressed) {
                    /* Touch down: upper→red, lower→blue */
                    bool upper_half = y < (SPS_DISPLAY_HEIGHT / 2);
                    uint16_t color = upper_half ? 0xF800 : 0x001F;
                    const char *name = upper_half ? "RED (upper)" : "BLUE (lower)";
                    err = display_ui_fill_color(color, name);
                    ESP_LOGI(TAG, "TOUCH DOWN  x=%u y=%u zone=%s color=%s draw=%s",
                             x, y,
                             upper_half ? "UPPER" : "LOWER",
                             name,
                             esp_err_to_name(err));
                } else if (!pressed && was_pressed) {
                    /* Touch up: restore the blue-green standby screen. */
                    err = display_ui_fill_color(SPS_STANDBY_COLOR_RGB565, "BLUE-GREEN (standby)");
                    ESP_LOGI(TAG, "TOUCH UP    x=%u y=%u -> restore BLUE-GREEN draw=%s",
                             x, y, esp_err_to_name(err));
                }
                was_pressed = pressed;
            }
        } else {
            /* Touch not available — keep screen white so it's visible.
             * Don't leave it at the last cycle color (black). */
            display_ui_fill_color(SPS_STANDBY_COLOR_RGB565, "BLUE-GREEN (no touch)");
            vTaskDelay(pdMS_TO_TICKS(2000));
            ESP_LOGW(TAG, "Touch still unavailable; screen kept white. Check I2C bus.");
        }
        vTaskDelay(pdMS_TO_TICKS(SPS_TOUCH_POLL_INTERVAL_MS));
    }

#else
    /* ── Color cycle only (no touch needed) ────────────────── */
    ESP_LOGI(TAG, "=== Color cycle test (looping) ===");
    while (true) {
        for (size_t i = 0; i < sizeof(s_color_cycle) / sizeof(s_color_cycle[0]); i++) {
            display_ui_fill_color(s_color_cycle[i].rgb565, s_color_cycle[i].name);
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
#endif /* SPS_DEMO_FORCE_WHITE_SCREEN / SPS_DEMO_TOUCH_COLOR_TEST */
}

#endif /* SPS_DEMO_DISPLAY_FIRST */

/* ── Normal gate flow ──────────────────────────────────────────
 *
 * Only reached when SPS_DEMO_DISPLAY_FIRST=0.
 * Supports SPS_DEMO_TOUCH_COLOR_TEST and SPS_DEMO_ESP8266_OPEN_AP_TEST
 * as before for independent bring-up.
 */

#if !SPS_DEMO_DISPLAY_FIRST

static bool should_upload_uid(const char *uid, const char *last_uid, TickType_t *last_tick)
{
    TickType_t now = xTaskGetTickCount();
    TickType_t debounce_ticks = pdMS_TO_TICKS(SPS_CARD_DEBOUNCE_MS);

    if (strcmp(uid, last_uid) == 0 && (now - *last_tick) < debounce_ticks) {
        return false;
    }

    *last_tick = now;
    return true;
}

#if SPS_DEMO_TOUCH_COLOR_TEST || SPS_DEMO_ESP8266_OPEN_AP_TEST || SPS_ESP8266_CONNECT_ONLY_TEST
typedef struct {
    uint16_t rgb565;
    const char *name;
} demo_color_t;

static const demo_color_t s_demo_colors[] = {
    {0x001F, "blue"},
    {0x07E0, "green"},
    {0x07FF, "blue-green"},
};

static void run_hardware_test(void)
{
    size_t color_index = 0;
    esp_err_t draw_err = display_ui_fill_color(s_demo_colors[color_index].rgb565,
                                                s_demo_colors[color_index].name);
    if (draw_err != ESP_OK) {
        ESP_LOGE(TAG, "Initial LCD color failed: %s", esp_err_to_name(draw_err));
    }

    bool touch_available = false;
#if SPS_DEMO_TOUCH_COLOR_TEST
    esp_err_t touch_err = touch_test_init();
    touch_available = touch_err == ESP_OK;
    if (!touch_available) {
        ESP_LOGW(TAG, "Touch unavailable; LCD and Wi-Fi tests continue: %s", esp_err_to_name(touch_err));
    }
#endif

#if SPS_DEMO_ESP8266_OPEN_AP_TEST || SPS_ESP8266_CONNECT_ONLY_TEST
    display_ui_show_network_status("ESP8266 init...");
    ESP_LOGI(TAG, "ESP8266 test: UART=%d TX=GPIO%d RX=GPIO%d BAUD=%d",
             SPS_ESP8266_UART_PORT,
             SPS_ESP8266_UART_TX_GPIO,
             SPS_ESP8266_UART_RX_GPIO,
             SPS_ESP8266_UART_BAUD);
    ESP_LOGI(TAG, "Wi-Fi connect-only test: SSID=%s, open AP=%s", SPS_WIFI_SSID,
             SPS_WIFI_PASSWORD[0] == '\0' ? "yes" : "no");
    esp_err_t net_err = network_client_start();
    if (net_err == ESP_OK) {
        display_ui_show_network_status("WIFI GOT IP");
    } else {
        ESP_LOGE(TAG, "ESP8266 test failed; touch test continues: %s", esp_err_to_name(net_err));
    }
#endif

    bool was_pressed = false;
    unsigned read_failures = 0;
    while (true) {
        if (touch_available) {
            bool pressed = false;
            uint16_t x = 0;
            uint16_t y = 0;
            esp_err_t err = touch_test_read(&pressed, &x, &y);
            if (err != ESP_OK) {
                if ((read_failures++ % 50) == 0) {
                    ESP_LOGW(TAG, "Touch read failed: %s", esp_err_to_name(err));
                }
            } else {
                read_failures = 0;
                if (pressed && !was_pressed) {
                    bool upper_half = y < (SPS_DISPLAY_HEIGHT / 2);
                    color_index = upper_half ? 1 : 2;
                    err = display_ui_fill_color(s_demo_colors[color_index].rgb565,
                                                s_demo_colors[color_index].name);
                    ESP_LOGI(TAG, "pressed x=%u y=%u region=%s color=%s draw=%s", x, y,
                             upper_half ? "upper" : "lower", s_demo_colors[color_index].name,
                             esp_err_to_name(err));
                }
                was_pressed = pressed;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(SPS_TOUCH_POLL_INTERVAL_MS));
    }
}
#endif /* SPS_DEMO_TOUCH_COLOR_TEST || SPS_DEMO_ESP8266_OPEN_AP_TEST || SPS_ESP8266_CONNECT_ONLY_TEST */

#endif /* !SPS_DEMO_DISPLAY_FIRST */

/* ── app_main ────────────────────────────────────────────────── */

void app_main(void)
{
    ESP_LOGI(TAG, "ESP32P4 boot");

#if SPS_DIAG_PN532_ONLY
    ESP_LOGI(TAG, "=== PN532 DIAGNOSTIC MODE (SPS_DIAG_PN532_ONLY=1) ===");
    ESP_LOGI(TAG, "All display/touch/WiFi/PN532 business logic is DISABLED.");
    ESP_LOGI(TAG, "Only raw PN532 UART diagnostics will run.");
    init_nvs(); /* NVS not used by diag, but avoids init warnings */
    pn532_uart_diag_run();
    return;
#endif

    ESP_ERROR_CHECK(init_nvs());

#if SPS_DEMO_DISPLAY_FIRST
    run_display_first();
    return;
#else
    /* ── Normal gate flow (SPS_DEMO_DISPLAY_FIRST=0) ───────── */

    ESP_ERROR_CHECK(display_ui_init());
    display_ui_show_booting();

#if SPS_DEMO_TOUCH_COLOR_TEST || SPS_DEMO_ESP8266_OPEN_AP_TEST || SPS_ESP8266_CONNECT_ONLY_TEST
    run_hardware_test();
    return;
#endif

    display_ui_show_network_status("ESP8266 init...");
    display_ui_show_network_status("Connecting...");
    esp_err_t net_err = network_client_start();
    if (net_err == ESP_OK) {
        display_ui_show_network_status("WiFi ready");
        display_ui_show_network_status("Gateway ready");
    } else {
        display_ui_show_error("Network error", esp_err_to_name(net_err));
    }

    esp_err_t pn532_err = pn532_reader_init();
    if (pn532_err == ESP_OK) {
        display_ui_show_pn532_status("PN532 ready");
    } else {
        ESP_LOGE(TAG, "PN532 init failed: %s", esp_err_to_name(pn532_err));
        display_ui_show_error("PN532 error", esp_err_to_name(pn532_err));
    }

    char last_uid[32] = {0};
    TickType_t last_uid_tick = 0;
    display_ui_show_wait_card();

    while (true) {
        if (net_err != ESP_OK) {
            display_ui_show_network_status("ESP8266 init...");
            display_ui_show_network_status("Connecting...");
            net_err = network_client_start();
            if (net_err == ESP_OK) {
                display_ui_show_network_status("WiFi ready");
                display_ui_show_network_status("Gateway ready");
            } else {
                display_ui_show_error("Network error", esp_err_to_name(net_err));
            }
        }

        if (pn532_err != ESP_OK) {
            pn532_err = pn532_reader_init();
            if (pn532_err == ESP_OK) {
                display_ui_show_pn532_status("PN532 ready");
                display_ui_show_wait_card();
            } else {
                ESP_LOGW(TAG, "PN532 retry failed: %s", esp_err_to_name(pn532_err));
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
        }

        char uid_hex[32] = {0};
        bool card_present = false;
        pn532_err = pn532_reader_poll_uid(uid_hex, sizeof(uid_hex), &card_present);
        if (pn532_err != ESP_OK) {
            ESP_LOGW(TAG, "PN532 poll failed: %s", esp_err_to_name(pn532_err));
            display_ui_show_error("PN532 error", esp_err_to_name(pn532_err));
            vTaskDelay(pdMS_TO_TICKS(SPS_CARD_POLL_INTERVAL_MS));
            continue;
        }

        if (card_present) {
            ESP_LOGI(TAG, "Card detected UID = %s", uid_hex);
            display_ui_show_uid(uid_hex);

            if (should_upload_uid(uid_hex, last_uid, &last_uid_tick)) {
                strlcpy(last_uid, uid_hex, sizeof(last_uid));
                display_ui_show_uploading();

                gateway_access_result_t result = {0};
                esp_err_t post_err = gateway_client_post_access_card(uid_hex, &result);
                if (post_err == ESP_OK) {
                    display_ui_show_access_result(&result);
                } else {
                    ESP_LOGE(TAG, "Gateway request failed: %s", esp_err_to_name(post_err));
                    display_ui_show_error("Network error", esp_err_to_name(post_err));
                    net_err = network_client_wait_ready();
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(SPS_CARD_POLL_INTERVAL_MS));
    }
#endif /* !SPS_DEMO_DISPLAY_FIRST */
}
