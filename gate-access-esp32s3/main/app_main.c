#include <string.h>

#include "app_config.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "gateway_client.h"
#include "nvs_flash.h"
#include "pn532_reader.h"
#include "wifi_client.h"

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

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    ESP_ERROR_CHECK(wifi_client_start());
    ESP_ERROR_CHECK(wifi_client_wait_connected());

    err = pn532_reader_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PN532 init failed: %s", esp_err_to_name(err));
    }

    char last_uid[32] = {0};
    TickType_t last_uid_tick = 0;

    while (true) {
        if (err != ESP_OK) {
            vTaskDelay(pdMS_TO_TICKS(1000));
            err = pn532_reader_init();
            continue;
        }

        char uid_hex[32] = {0};
        bool card_present = false;
        err = pn532_reader_poll_uid(uid_hex, sizeof(uid_hex), &card_present);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "PN532 poll failed: %s", esp_err_to_name(err));
            vTaskDelay(pdMS_TO_TICKS(SPS_CARD_POLL_INTERVAL_MS));
            continue;
        }

        if (card_present) {
            ESP_LOGI(TAG, "Card detected UID = %s", uid_hex);
            if (should_upload_uid(uid_hex, last_uid, &last_uid_tick)) {
                strlcpy(last_uid, uid_hex, sizeof(last_uid));
                gateway_access_result_t result = {0};
                esp_err_t post_err = gateway_client_post_access_card(uid_hex, &result);
                if (post_err == ESP_OK && result.access_granted) {
                    ESP_LOGI(TAG, "Gateway access granted");
                } else if (post_err == ESP_OK) {
                    ESP_LOGW(TAG, "Gateway access denied");
                } else {
                    ESP_LOGE(TAG, "Gateway request failed");
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(SPS_CARD_POLL_INTERVAL_MS));
    }
}
