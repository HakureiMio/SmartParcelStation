#include "esp8266_at.h"

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "app_config.h"
#include "driver/uart.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "esp8266_at";
static bool s_uart_installed;

static esp_err_t uart_read_accum(char *buffer, size_t buffer_size, int timeout_ms, const char *expect)
{
    if (buffer == NULL || buffer_size == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    size_t used = strlen(buffer);
    int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;

    while (esp_timer_get_time() < deadline) {
        uint8_t chunk[128] = {0};
        int remain_ms = (int)((deadline - esp_timer_get_time()) / 1000);
        if (remain_ms < 1) {
            remain_ms = 1;
        }

        int len = uart_read_bytes(
            SPS_ESP8266_UART_PORT,
            chunk,
            sizeof(chunk) - 1,
            pdMS_TO_TICKS(remain_ms > 100 ? 100 : remain_ms));
        if (len > 0) {
            size_t copy_len = (size_t)len;
            if (copy_len > buffer_size - used - 1) {
                copy_len = buffer_size - used - 1;
            }
            if (copy_len > 0) {
                memcpy(buffer + used, chunk, copy_len);
                used += copy_len;
                buffer[used] = '\0';
            }

            if (expect != NULL && strstr(buffer, expect) != NULL) {
                return ESP_OK;
            }
            if (strstr(buffer, "\r\nERROR\r\n") != NULL || strstr(buffer, "\r\nFAIL\r\n") != NULL) {
                ESP_LOGW(TAG, "AT failure response: %s", buffer);
                return ESP_FAIL;
            }
        }
    }

    ESP_LOGW(TAG, "AT wait timeout, buffered response: %s", buffer);
    return ESP_ERR_TIMEOUT;
}

static esp_err_t at_command(const char *cmd, const char *expect, int timeout_ms)
{
    char response[512] = {0};
    ESP_LOGI(TAG, "AT -> %s", cmd);
    uart_flush_input(SPS_ESP8266_UART_PORT);
    uart_write_bytes(SPS_ESP8266_UART_PORT, cmd, strlen(cmd));
    uart_write_bytes(SPS_ESP8266_UART_PORT, "\r\n", 2);

    esp_err_t err = uart_read_accum(response, sizeof(response), timeout_ms, expect);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "AT OK: %s", expect);
    }
    return err;
}

esp_err_t esp8266_at_init(void)
{
    uart_config_t uart_config = {
        .baud_rate = SPS_ESP8266_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    if (!s_uart_installed) {
        ESP_RETURN_ON_ERROR(uart_driver_install(
                                SPS_ESP8266_UART_PORT,
                                SPS_ESP8266_UART_BUF_SIZE,
                                SPS_ESP8266_UART_BUF_SIZE,
                                0,
                                NULL,
                                0),
                            TAG,
                            "UART driver install failed");
        s_uart_installed = true;
    }
    ESP_RETURN_ON_ERROR(uart_param_config(SPS_ESP8266_UART_PORT, &uart_config), TAG, "UART param config failed");
    ESP_RETURN_ON_ERROR(
        uart_set_pin(
            SPS_ESP8266_UART_PORT,
            SPS_ESP8266_UART_TX_GPIO,
            SPS_ESP8266_UART_RX_GPIO,
            SPS_ESP8266_UART_RTS_GPIO,
            SPS_ESP8266_UART_CTS_GPIO),
        TAG,
        "UART pin config failed");

    vTaskDelay(pdMS_TO_TICKS(300));
    uart_flush_input(SPS_ESP8266_UART_PORT);

    ESP_RETURN_ON_ERROR(at_command("AT", "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "AT probe failed");
    ESP_RETURN_ON_ERROR(at_command("ATE0", "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "ATE0 failed");
    ESP_RETURN_ON_ERROR(at_command("AT+CWMODE=1", "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "CWMODE failed");
    ESP_RETURN_ON_ERROR(at_command("AT+CIPMUX=0", "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "CIPMUX failed");

    ESP_LOGI(TAG, "ESP8266 AT init ok");
    return ESP_OK;
}

esp_err_t esp8266_at_join_ap(const char *ssid, const char *password)
{
    if (ssid == NULL || password == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    char cmd[160] = {0};
    snprintf(cmd, sizeof(cmd), "AT+CWJAP=\"%s\",\"%s\"", ssid, password);
    ESP_LOGI(TAG, "Connecting %s...", ssid);
    return at_command(cmd, "WIFI GOT IP", 20000);
}

esp_err_t esp8266_at_tcp_transact(
    const char *host,
    int port,
    const char *request,
    size_t request_len,
    char *response,
    size_t response_size)
{
    if (host == NULL || request == NULL || response == NULL || response_size == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    response[0] = '\0';

    char cmd[128] = {0};
    snprintf(cmd, sizeof(cmd), "AT+CIPSTART=\"TCP\",\"%s\",%d", host, port);
    ESP_RETURN_ON_ERROR(at_command(cmd, "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "CIPSTART failed");

    snprintf(cmd, sizeof(cmd), "AT+CIPSEND=%u", (unsigned)request_len);
    ESP_LOGI(TAG, "AT -> %s", cmd);
    uart_flush_input(SPS_ESP8266_UART_PORT);
    uart_write_bytes(SPS_ESP8266_UART_PORT, cmd, strlen(cmd));
    uart_write_bytes(SPS_ESP8266_UART_PORT, "\r\n", 2);
    ESP_RETURN_ON_ERROR(uart_read_accum(response, response_size, SPS_ESP8266_AT_TIMEOUT_MS, ">"), TAG, "CIPSEND prompt failed");

    uart_write_bytes(SPS_ESP8266_UART_PORT, request, request_len);
    esp_err_t err = uart_read_accum(response, response_size, SPS_ESP8266_AT_TIMEOUT_MS, "CLOSED");
    if (err == ESP_ERR_TIMEOUT && strstr(response, "HTTP/1.") != NULL) {
        err = ESP_OK;
    }
    ESP_LOGI(TAG, "TCP response bytes buffered=%u", (unsigned)strlen(response));

    at_command("AT+CIPCLOSE", "OK", 1000);
    return err;
}
