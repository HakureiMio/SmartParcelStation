#include "wifi_client.h"

#include <string.h>

#include "app_config.h"
#include "esp_check.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

static const char *TAG = "sps_wifi";
static EventGroupHandle_t s_wifi_event_group;
static const int WIFI_CONNECTED_BIT = BIT0;
static const int WIFI_FAIL_BIT = BIT1;
static int s_retry_count;

static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    (void)arg;

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "Wi-Fi connecting");
        esp_wifi_connect();
        return;
    }

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_count < 10) {
            s_retry_count++;
            ESP_LOGW(TAG, "Wi-Fi disconnected, retry %d", s_retry_count);
            esp_wifi_connect();
        } else {
            ESP_LOGE(TAG, "Wi-Fi connection failed");
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
        }
        return;
    }

    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        s_retry_count = 0;
        ESP_LOGI(TAG, "Wi-Fi connected, IP = " IPSTR, IP2STR(&event->ip_info.ip));
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

esp_err_t wifi_client_start(void)
{
    s_wifi_event_group = xEventGroupCreate();
    if (s_wifi_event_group == NULL) {
        return ESP_ERR_NO_MEM;
    }

    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "esp_netif_init failed");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG, "event loop create failed");
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&cfg), TAG, "esp_wifi_init failed");

    ESP_RETURN_ON_ERROR(
        esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL),
        TAG,
        "register Wi-Fi handler failed");
    ESP_RETURN_ON_ERROR(
        esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, NULL),
        TAG,
        "register IP handler failed");

    wifi_config_t wifi_config = {0};
    strlcpy((char *)wifi_config.sta.ssid, SPS_WIFI_SSID, sizeof(wifi_config.sta.ssid));
    strlcpy((char *)wifi_config.sta.password, SPS_WIFI_PASSWORD, sizeof(wifi_config.sta.password));
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "set Wi-Fi mode failed");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &wifi_config), TAG, "set Wi-Fi config failed");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "start Wi-Fi failed");

    return ESP_OK;
}

esp_err_t wifi_client_wait_connected(void)
{
    EventBits_t bits = xEventGroupWaitBits(
        s_wifi_event_group,
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
        pdFALSE,
        pdFALSE,
        portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        return ESP_OK;
    }
    return ESP_FAIL;
}
