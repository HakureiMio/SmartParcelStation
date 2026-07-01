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
    if (raw == NULL || response == NULL || response_size == 0) {
        return;
    }

    /* ESP-AT prepends command chatter such as "Recv ...\r\n\r\nSEND OK"
     * before +IPD and the real HTTP response. Always anchor parsing at the
     * HTTP status line, otherwise SEND OK is mistaken for a 9-byte body. */
    const char *http_start = strstr(raw, "HTTP/1.");
    if (http_start == NULL) {
        strlcpy(response, raw, response_size);
        return;
    }

    const char *header_end = strstr(http_start, "\r\n\r\n");
    if (header_end == NULL) {
        strlcpy(response, http_start, response_size);
        return;
    }

    const char *body = header_end + 4;
    const char *content_length_header = strstr(http_start, "content-length:");
    if (content_length_header == NULL || content_length_header > header_end) {
        content_length_header = strstr(http_start, "Content-Length:");
    }

    size_t body_length = 0;
    if (content_length_header != NULL && content_length_header < header_end) {
        const char *value = strchr(content_length_header, ':');
        if (value != NULL) {
            body_length = (size_t)strtoul(value + 1, NULL, 10);
        }
    }

    size_t available = strlen(body);
    if (body_length == 0 || body_length > available) {
        body_length = available;
        /* Fallback for responses without Content-Length: remove ESP-AT
         * transport notifications appended after the HTTP body. */
        static const char *trailers[] = {"\r\nCLOSED", "\r\nSEND OK", "\r\n+IPD,"};
        for (size_t i = 0; i < sizeof(trailers) / sizeof(trailers[0]); ++i) {
            const char *trailer = strstr(body, trailers[i]);
            if (trailer != NULL && (size_t)(trailer - body) < body_length) {
                body_length = (size_t)(trailer - body);
            }
        }
    }

    if (body_length >= response_size) {
        body_length = response_size - 1;
    }
    memcpy(response, body, body_length);
    response[body_length] = '\0';
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
    ESP_LOGI(TAG, "HTTP status=%d, body_bytes=%u", *http_status, (unsigned)strlen(response));
    return *http_status > 0 ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}
