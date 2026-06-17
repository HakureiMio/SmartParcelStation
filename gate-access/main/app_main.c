#include <stdbool.h>
#include <string.h>

#include "app_config.h"
#include "display_ui.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "gateway_client.h"
#include "network_client.h"
#include "nvs_flash.h"
#include "pn532_reader.h"

static const char *TAG = "sps_gate";

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

static esp_err_t init_nvs(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    return err;
}

void app_main(void)
{
    ESP_LOGI(TAG, "ESP32P4 boot");
    ESP_ERROR_CHECK(init_nvs());

    ESP_ERROR_CHECK(display_ui_init());
    display_ui_show_booting();

    display_ui_show_network_status("ESP8266 init...");
    display_ui_show_network_status("Connecting SPS_GATEWAY_AP...");
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
            display_ui_show_network_status("Connecting SPS_GATEWAY_AP...");
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
}
