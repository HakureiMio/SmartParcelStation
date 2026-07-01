#include <stdbool.h>
#include <stdio.h>
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

/* ── Stack water mark helper ─────────────────────────────────── */

static void log_stack_watermark(const char *label)
{
    UBaseType_t words = uxTaskGetStackHighWaterMark(NULL);
    ESP_LOGI(TAG, "stack HWM @ %s: %u words (%u bytes)",
             label, (unsigned)words, (unsigned)(words * sizeof(StackType_t)));
}

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

/* ── Static globals (avoid stack allocation of large structs) ── */

static gateway_qr_session_t    s_qr_session;
static gateway_access_result_t s_card_result;
static gateway_access_result_t s_auth_result;

/* ═══════════════════════════════════════════════════════════════
 * QR DISPLAY TEST MODE
 * ═══════════════════════════════════════════════════════════════ */

#if SPS_DEMO_QR_DISPLAY_TEST

static void run_qr_display_test(void)
{
    ESP_LOGI(TAG, "=== QR DISPLAY TEST MODE ===");
    ESP_LOGI(TAG, "No WiFi, no PN532, no gateway — display + QR only.");

    ESP_ERROR_CHECK(display_ui_init());
    log_stack_watermark("display_ui_init done");

    const char *test_payload =
        "sps://gate-qr?v=1&gateway_code=GW001&reader_id=GATE01"
        "&station_id=1&session_id=qr_test_0001&nonce=abcdef"
        "&expires_at=1780000000&signature=test";

    ESP_LOGI(TAG, "QR test payload bytes=%u", (unsigned)strlen(test_payload));
    esp_err_t err = display_ui_show_qr(test_payload);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "QR_READY: displayed on screen");
    } else {
        ESP_LOGE(TAG, "QR display failed: %s", esp_err_to_name(err));
    }
    log_stack_watermark("display_ui_show_qr done");

    ESP_LOGI(TAG, "QR test running — screen should show QR code. Idle loop with 2s watermark.");
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(2000));
        log_stack_watermark("QR test idle");
        ESP_LOGI(TAG, "free heap=%" PRIu32 " free internal=%" PRIu32,
                 esp_get_free_heap_size(), esp_get_free_internal_heap_size());
    }
}

#endif /* SPS_DEMO_QR_DISPLAY_TEST */

/* ═══════════════════════════════════════════════════════════════
 * DISPLAY-FIRST DEBUG MODE
 * ═══════════════════════════════════════════════════════════════ */

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
#define SPS_CARD_LATCH_TIMEOUT_MS  3000

static void pn532_uid_test_task(void *arg)
{
    (void)arg;
    char latched_uid[32] = {0};
    bool  card_latched = false;
    int64_t last_read_us = 0;
    unsigned poll_errors  = 0;

    ESP_LOGI(TAG, "=== PN532 continuous UID test ===");
    ESP_LOGI(TAG, "Present a card at any time; UID auto-clears after %dms",
             SPS_CARD_LATCH_TIMEOUT_MS);

    esp_err_t err = pn532_reader_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PN532 init failed: %s", esp_err_to_name(err));
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    while (true) {
        if (err != ESP_OK) {
            err = pn532_reader_init();
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "PN532 re-init failed: %s", esp_err_to_name(err));
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
            ESP_LOGI(TAG, "PN532 re-initialized");
        }

        char uid_hex[32] = {0};
        bool card_present = false;
        err = pn532_reader_poll_uid(uid_hex, sizeof(uid_hex), &card_present);

        if (err == ESP_ERR_TIMEOUT) {
            card_present = false;
            poll_errors++;
        } else if (err != ESP_OK) {
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
                display_ui_show_card_id_numeric(uid_hex);
            }
        } else if (card_latched) {
            int64_t elapsed_ms = (esp_timer_get_time() - last_read_us) / 1000;
            if (elapsed_ms >= SPS_CARD_LATCH_TIMEOUT_MS) {
                ESP_LOGI(TAG, "CARD TIMEOUT: UID=%s (absent for %lldms)",
                         latched_uid, elapsed_ms);
                display_ui_fill_color(SPS_STANDBY_COLOR_RGB565, "BLUE-GREEN (standby)");
                latched_uid[0] = '\0';
                card_latched = false;
            }
        }

        if (poll_errors >= 5) {
            ESP_LOGW(TAG, "PN532 %u consecutive errors; reinitializing", poll_errors);
            poll_errors = 0;
            err = ESP_FAIL;
            continue;
        }

        vTaskDelay(pdMS_TO_TICKS(SPS_CARD_POLL_INTERVAL_MS));
    }
}
#endif /* SPS_DEMO_PN532_UID_TEST */

static void run_display_first(void)
{
    ESP_LOGI(TAG, "=== Display-first debug mode ===");
    ESP_LOGI(TAG, "SPS_DEMO_DISPLAY_FIRST=%d SPS_DEMO_TOUCH_COLOR_TEST=%d SPS_DEMO_PN532_UID_TEST=%d",
             SPS_DEMO_DISPLAY_FIRST, SPS_DEMO_TOUCH_COLOR_TEST, SPS_DEMO_PN532_UID_TEST);

    /* Step 1: Init touch + I2C scan (installs I2C driver on IO7/IO8) */
    ESP_LOGI(TAG, "--- Init touch + I2C scan ---");
    esp_err_t touch_err = touch_test_init();
    bool touch_available = (touch_err == ESP_OK);

    /* Step 2: Init display */
    ESP_LOGI(TAG, "--- Init display ---");
    ESP_ERROR_CHECK(display_ui_init());
    display_ui_show_booting();
    if (!touch_available) {
        ESP_LOGW(TAG, "Touch unavailable: %s", esp_err_to_name(touch_err));
    } else {
        ESP_LOGI(TAG, "Touch available");
    }

    /* Step 3: Probe PCA9536 registers */
    ESP_LOGI(TAG, "--- PCA9536 @ 0x41 register probe ---");
    display_board_ctrl_probe_registers();

#if SPS_DEMO_PN532_UID_TEST
    ESP_LOGI(TAG, "--- Start PN532 continuous UID reader ---");
    xTaskCreate(pn532_uid_test_task, "pn532_uid_test", 4096, NULL, 5, NULL);
#endif

#if SPS_DEMO_WIFI_ENABLE
    ESP_LOGI(TAG, "--- Init ESP8266 WiFi ---");
    display_ui_fill_color(0xFFFF, "WHITE (WiFi init)");
    ESP_LOGI(TAG, "ESP8266 UART: port=%d TX=GPIO%d RX=GPIO%d BAUD=%d",
             SPS_ESP8266_UART_PORT, SPS_ESP8266_UART_TX_GPIO,
             SPS_ESP8266_UART_RX_GPIO, SPS_ESP8266_UART_BAUD);
    ESP_LOGI(TAG, "WiFi target: SSID=\"%s\"", SPS_WIFI_SSID);
    esp_err_t wifi_err = network_client_start();
    if (wifi_err == ESP_OK) {
        ESP_LOGI(TAG, "ESP8266 WiFi connected");
        display_ui_fill_color(0x07E0, "GREEN (WiFi OK)");
    } else {
        ESP_LOGE(TAG, "WiFi failed: %s", esp_err_to_name(wifi_err));
        display_ui_fill_color(0xF800, "RED (WiFi FAIL)");
    }
#endif

#if SPS_DEMO_FORCE_WHITE_SCREEN
    ESP_LOGI(TAG, "=== FORCE WHITE SCREEN mode ===");
    while (true) { display_ui_fill_color(0xFFFF, "white"); vTaskDelay(pdMS_TO_TICKS(200)); }

#elif SPS_DEMO_TOUCH_COLOR_TEST
    ESP_LOGI(TAG, "=== Color cycle test (5 colors x 1s) ===");
    for (size_t i = 0; i < sizeof(s_color_cycle) / sizeof(s_color_cycle[0]); i++) {
        display_ui_fill_color(s_color_cycle[i].rgb565, s_color_cycle[i].name);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    ESP_LOGI(TAG, "=== Touch dual-zone color switch ===");
    display_ui_fill_color(0xFFFF, "WHITE (ready)");
    bool was_pressed = false;
    unsigned read_failures = 0;
    while (true) {
        if (touch_available) {
            bool pressed = false; uint16_t x = 0, y = 0;
            esp_err_t err = touch_test_read(&pressed, &x, &y);
            if (err != ESP_OK) {
                if ((read_failures++ % 50) == 0) ESP_LOGW(TAG, "Touch read failed");
            } else {
                read_failures = 0;
                if (pressed && !was_pressed) {
                    bool upper = y < (SPS_DISPLAY_HEIGHT / 2);
                    display_ui_fill_color(upper ? 0xF800 : 0x001F,
                                          upper ? "RED (upper)" : "BLUE (lower)");
                    ESP_LOGI(TAG, "TOUCH x=%u y=%u %s", x, y, upper ? "UPPER" : "LOWER");
                } else if (!pressed && was_pressed) {
                    display_ui_fill_color(0xFFFF, "WHITE (restore)");
                }
                was_pressed = pressed;
            }
        } else {
            display_ui_fill_color(0xFFFF, "WHITE (no touch)");
            vTaskDelay(pdMS_TO_TICKS(2000));
        }
        vTaskDelay(pdMS_TO_TICKS(SPS_TOUCH_POLL_INTERVAL_MS));
    }
#else
    ESP_LOGI(TAG, "=== Color cycle test (looping) ===");
    while (true) {
        for (size_t i = 0; i < sizeof(s_color_cycle) / sizeof(s_color_cycle[0]); i++) {
            display_ui_fill_color(s_color_cycle[i].rgb565, s_color_cycle[i].name);
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
#endif
}

#endif /* SPS_DEMO_DISPLAY_FIRST */

/* ═══════════════════════════════════════════════════════════════
 * NORMAL GATE FLOW — runs in dedicated task with large stack
 * ═══════════════════════════════════════════════════════════════ */

#if !SPS_DEMO_DISPLAY_FIRST && !SPS_DEMO_QR_DISPLAY_TEST && !SPS_DIAG_PN532_ONLY

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

static esp_err_t refresh_gate_qr(void)
{
    memset(&s_qr_session, 0, sizeof(s_qr_session));
    esp_err_t err = gateway_client_fetch_qr_session(&s_qr_session);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "QR session refresh failed: %s", esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "QR session received: session_id=%s payload_bytes=%u",
             s_qr_session.session_id, (unsigned)strlen(s_qr_session.qr_payload));
    err = display_ui_show_qr(s_qr_session.qr_payload);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "display_ui_show_qr failed: %s", esp_err_to_name(err));
    }
    return err;
}

/* Touch counter — used to generate distinct local QR payloads */
static unsigned s_touch_count = 0;
static bool s_card_showing = false;
static bool s_touch_active = false;   /* touch-down color is on screen */
static int64_t s_card_show_start_us = 0;
#define SPS_CARD_SHOW_MS  2000

static void show_local_qr(void)
{
    char payload[256];
    snprintf(payload, sizeof(payload),
             "sps://gate-qr?v=1&reader_id=%s&status=offline&seq=%u",
             SPS_READER_ID, s_touch_count);
    display_ui_show_qr(payload);
    ESP_LOGI(TAG, "QR refresh #%u", s_touch_count);
}

static void gate_main_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "=== Gate main task started (stack %u bytes) ===",
             (unsigned)(12288));

    /* ── Init display ──────────────────────────────────────── */
    ESP_ERROR_CHECK(display_ui_init());
    log_stack_watermark("display_ui_init done");
    display_ui_show_booting();

    /* Visible startup: brief color cycle so user knows screen works */
    static const uint16_t startup_colors[] = {0xF800, 0x07E0, 0x001F, 0xFFFF};
    static const char *startup_names[] = {"RED", "GREEN", "BLUE", "WHITE"};
    for (int c = 0; c < 4; c++) {
        display_ui_fill_color(startup_colors[c], startup_names[c]);
        vTaskDelay(pdMS_TO_TICKS(300));
    }

    /* ── Init touch ────────────────────────────────────────── */
    esp_err_t touch_err = touch_test_init();
    bool touch_ok = (touch_err == ESP_OK);
    ESP_LOGI(TAG, "Touch %s", touch_ok ? "ready — tap to refresh QR" : "unavailable");

    /* ── Init WiFi ─────────────────────────────────────────── */
    ESP_LOGI(TAG, "Connecting WiFi: SSID=\"%s\"", SPS_WIFI_SSID);
    esp_err_t net_err = network_client_start();
    ESP_LOGI(TAG, "WiFi %s", net_err == ESP_OK ? "ready" : "FAIL");
    log_stack_watermark("network_client_start done");

    /* ── Init PN532 (card reader) ──────────────────────────── */
    esp_err_t pn532_err = pn532_reader_init();
    ESP_LOGI(TAG, "PN532 %s", pn532_err == ESP_OK ? "ready" : "init failed");
    log_stack_watermark("pn532_reader_init done");

    /* ── Initial QR ────────────────────────────────────────── */
    esp_err_t qr_err = refresh_gate_qr();
    if (qr_err != ESP_OK) {
        show_local_qr();
    }
    s_touch_count++;

    char last_uid[32] = {0};
    TickType_t last_uid_tick = 0;
    int64_t last_qr_refresh_us = esp_timer_get_time();
    int64_t last_auth_poll_us = 0;
    bool was_touched = false;

    int loop_count = 0;
    while (true) {
        int64_t now_us = esp_timer_get_time();
        loop_count++;

        /* ── Card showing timeout → return to QR ──────────── */
        if (s_card_showing && !s_touch_active &&
            (now_us - s_card_show_start_us) / 1000 >= SPS_CARD_SHOW_MS) {
            s_card_showing = false;
            if (net_err == ESP_OK && s_qr_session.qr_payload[0]) {
                display_ui_show_qr(s_qr_session.qr_payload);
            } else {
                show_local_qr();
            }
            ESP_LOGI(TAG, "Card timeout → QR");
        }

        /* ── Touch → upper/lower half color switch ────────── */
        if (touch_ok) {
            bool pressed = false; uint16_t tx = 0, ty = 0;
            if (touch_test_read(&pressed, &tx, &ty) == ESP_OK) {
                if (pressed && !was_touched) {
                    s_touch_count++;
                    s_touch_active = true;
                    bool upper = ty < (SPS_DISPLAY_HEIGHT / 2);
                    display_ui_fill_color(upper ? 0xF800 : 0x001F,
                                          upper ? "RED (upper)" : "BLUE (lower)");
                    ESP_LOGI(TAG, "TOUCH #%u: x=%u y=%u zone=%s",
                             s_touch_count, tx, ty, upper ? "UPPER" : "LOWER");
                } else if (!pressed && was_touched) {
                    s_touch_active = false;
                    if (!s_card_showing) {
                        if (net_err == ESP_OK && s_qr_session.qr_payload[0]) {
                            display_ui_show_qr(s_qr_session.qr_payload);
                        } else {
                            show_local_qr();
                        }
                    }
                    ESP_LOGI(TAG, "TOUCH release → back to QR");
                }
                was_touched = pressed;
            }
        }

        /* ── Poll PN532 for card (every loop) ─────────────── */
        if (pn532_err == ESP_OK) {
            char uid_hex[32] = {0};
            bool card_present = false;
            pn532_err = pn532_reader_poll_uid(uid_hex, sizeof(uid_hex), &card_present);

            if (pn532_err == ESP_ERR_TIMEOUT) {
                pn532_err = ESP_OK;
            } else if (pn532_err != ESP_OK) {
                ESP_LOGW(TAG, "PN532 poll error: %s", esp_err_to_name(pn532_err));
            }

            if (card_present && uid_hex[0] != '\0') {
                ESP_LOGI(TAG, "Card detected UID=%s", uid_hex);
                display_ui_show_card_id_numeric(uid_hex);
                s_card_showing = true;
                s_card_show_start_us = now_us;

                if (should_upload_uid(uid_hex, last_uid, &last_uid_tick)) {
                    strlcpy(last_uid, uid_hex, sizeof(last_uid));
                    memset(&s_card_result, 0, sizeof(s_card_result));
                    gateway_client_post_access_card(uid_hex, &s_card_result);
                }
            }
        } else if (loop_count % 20 == 0) {
            /* Retry PN532 init every ~2 seconds */
            pn532_err = pn532_reader_init();
        }

        /* ── Periodic QR + auth poll (every ~30 loops = 3s) ─ */
        if (loop_count % 30 == 0) {
            if (net_err == ESP_OK && (now_us - last_qr_refresh_us) / 1000 >= SPS_QR_REFRESH_MS) {
                qr_err = refresh_gate_qr();
                if (qr_err != ESP_OK && !s_card_showing) { show_local_qr(); }
                last_qr_refresh_us = now_us;
            }
            if (net_err == ESP_OK && (now_us - last_auth_poll_us) / 1000 >= SPS_GATE_AUTH_POLL_MS) {
                memset(&s_auth_result, 0, sizeof(s_auth_result));
                gateway_client_poll_auth_result(&s_auth_result);
                last_auth_poll_us = now_us;
            }
            if (net_err != ESP_OK) {
                net_err = network_client_start();
                if (net_err == ESP_OK) { qr_err = refresh_gate_qr(); }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(SPS_CARD_POLL_INTERVAL_MS));
    }
}

#endif /* !SPS_DEMO_DISPLAY_FIRST && !SPS_DEMO_QR_DISPLAY_TEST && !SPS_DIAG_PN532_ONLY */

/* ═══════════════════════════════════════════════════════════════
 * app_main — lightweight entry point
 * ═══════════════════════════════════════════════════════════════ */

void app_main(void)
{
    ESP_LOGI(TAG, "ESP32P4 boot");
    ESP_ERROR_CHECK(init_nvs());
    log_stack_watermark("after init_nvs");

#if SPS_DIAG_PN532_ONLY
    ESP_LOGI(TAG, "=== PN532 DIAGNOSTIC MODE ===");
    pn532_uart_diag_run();
    return;
#endif

#if SPS_DEMO_QR_DISPLAY_TEST
    run_qr_display_test();
    return;
#endif

#if SPS_DEMO_DISPLAY_FIRST
    run_display_first();
    return;
#endif

    /* Normal gate flow: offload to dedicated task with 12 KB stack */
    ESP_LOGI(TAG, "Starting gate_main_task (12 KB stack)...");
    BaseType_t ret = xTaskCreatePinnedToCore(gate_main_task, "gate_main",
                                              12288, NULL, 5, NULL, 0);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create gate_main_task");
        return;
    }

    /* app_main() returns — IDF main task is free */
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        log_stack_watermark("app_main idle");
    }
}
