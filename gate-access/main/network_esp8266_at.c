#include "network_client.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app_config.h"
#include "esp8266_at.h"
#include "esp_log.h"

static const char *TAG = "network";
static bool s_network_ready;

/* Reusable buffers to avoid stack allocation of 2KB+ per HTTP call. */
static char s_http_raw[SPS_HTTP_RESPONSE_MAX];
static char s_http_request[800];

static int parse_http_status(const char *response)
{
    const char *line = strstr(response, "HTTP/1.");
    if (line == NULL) {
        return 0;
    }
    const char *space = strchr(line, ' ');
    if (space == NULL) {
        return 0;
    }
    return atoi(space + 1);
}

static void copy_http_body(const char *raw, char *response, size_t response_size)
{
    const char *body = strstr(raw, "\r\n\r\n");
    if (body != NULL) {
        body += 4;
    } else {
        body = raw;
    }
    strlcpy(response, body, response_size);
}

esp_err_t network_client_start(void)
{
    s_network_ready = false;

    esp_err_t err = esp8266_at_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ESP8266 init failed: %s", esp_err_to_name(err));
        return err;
    }

    err = esp8266_at_join_ap(SPS_WIFI_SSID, SPS_WIFI_PASSWORD);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ESP8266 Wi-Fi join failed: %s", esp_err_to_name(err));
        return err;
    }

    err = esp8266_at_query_ip();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ESP8266 CIFSR failed: %s", esp_err_to_name(err));
        return err;
    }

    s_network_ready = true;
    ESP_LOGI(TAG, "WiFi ready");
    return ESP_OK;
}

esp_err_t network_client_wait_ready(void)
{
    return s_network_ready ? ESP_OK : ESP_ERR_INVALID_STATE;
}

esp_err_t network_client_http_post_json(
    const char *host,
    int port,
    const char *path,
    const char *json,
    char *response,
    size_t response_size,
    int *http_status)
{
    if (host == NULL || path == NULL || json == NULL || response == NULL || response_size == 0 || http_status == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!s_network_ready) {
        return ESP_ERR_INVALID_STATE;
    }

    response[0] = '\0';
    *http_status = 0;

    int request_len = snprintf(
        s_http_request, sizeof(s_http_request),
        "POST %s HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Content-Type: application/json\r\n"
        "X-Gate-Reader-Id: %s\r\n"
        "X-Gate-Reader-Token: %s\r\n"
        "Content-Length: %u\r\n"
        "Connection: close\r\n"
        "\r\n"
        "%s",
        path,
        host,
        port,
        SPS_READER_ID,
        SPS_READER_TOKEN,
        (unsigned)strlen(json),
        json);
    if (request_len < 0 || request_len >= (int)sizeof(s_http_request)) {
        return ESP_ERR_INVALID_SIZE;
    }

    memset(s_http_raw, 0, sizeof(s_http_raw));
    ESP_LOGI(TAG, "POST %s", path);
    esp_err_t err = esp8266_at_tcp_transact(host, port, s_http_request, (size_t)request_len,
                                             s_http_raw, sizeof(s_http_raw));
    if (err != ESP_OK) {
        /* TCP connection failure to gateway — WiFi is still connected.
         * Only mark network ready=false on actual ESP8266 AT failures. */
        ESP_LOGE(TAG, "HTTP POST over ESP8266 failed: %s (WiFi still connected)", esp_err_to_name(err));
        ESP_LOGW(TAG, "Raw response: %s", s_http_raw);
        return err;
    }

    *http_status = parse_http_status(s_http_raw);
    copy_http_body(s_http_raw, response, response_size);
    ESP_LOGI(TAG, "HTTP status=%d, body=%s", *http_status, response);
    return *http_status > 0 ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

esp_err_t network_client_http_get(
    const char *host, int port, const char *path,
    char *response, size_t response_size, int *http_status)
{
    if (host == NULL || path == NULL || response == NULL || response_size == 0 || http_status == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!s_network_ready) return ESP_ERR_INVALID_STATE;
    int request_len = snprintf(s_http_request, sizeof(s_http_request),
        "GET %s HTTP/1.1\r\nHost: %s:%d\r\nConnection: close\r\n"
        "X-Gate-Reader-Id: %s\r\nX-Gate-Reader-Token: %s\r\n\r\n",
        path, host, port, SPS_READER_ID, SPS_READER_TOKEN);
    if (request_len < 0 || request_len >= (int)sizeof(s_http_request)) return ESP_ERR_INVALID_SIZE;
    memset(s_http_raw, 0, sizeof(s_http_raw));
    ESP_LOGI(TAG, "GET %s", path);
    esp_err_t err = esp8266_at_tcp_transact(host, port, s_http_request, (size_t)request_len,
                                             s_http_raw, sizeof(s_http_raw));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "HTTP GET over ESP8266 failed: %s (WiFi still connected)", esp_err_to_name(err));
        return err;
    }
    *http_status = parse_http_status(s_http_raw);
    copy_http_body(s_http_raw, response, response_size);
    ESP_LOGI(TAG, "HTTP status=%d", *http_status);
    return *http_status > 0 ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}
