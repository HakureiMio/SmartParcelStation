#include "esp8266_at.h"

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "app_config.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "esp8266_at";
static bool s_uart_installed;
static bool s_first_init = true;  /* skip GPIO toggle on reconnect */

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
    ESP_LOGI(TAG, "AT -> %s", strncmp(cmd, "AT+CWJAP=", 9) == 0 ? "AT+CWJAP=<redacted>" : cmd);
    uart_flush_input(SPS_ESP8266_UART_PORT);
    int written = uart_write_bytes(SPS_ESP8266_UART_PORT, cmd, strlen(cmd));
    if (written != (int)strlen(cmd) || uart_write_bytes(SPS_ESP8266_UART_PORT, "\r\n", 2) != 2) {
        ESP_LOGE(TAG, "AT UART write failed");
        return ESP_FAIL;
    }

    esp_err_t err = uart_read_accum(response, sizeof(response), timeout_ms, expect);
    ESP_LOGI(TAG, "AT response: %s", response[0] == '\0' ? "<empty>" : response);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "AT OK: %s", expect);
    }
    return err;
}

esp_err_t esp8266_at_init(void)
{
    ESP_LOGI(TAG, "ESP8266 init — UART%d TX=GPIO%d RX=GPIO%d BAUD=%d",
             SPS_ESP8266_UART_PORT,
             SPS_ESP8266_UART_TX_GPIO,
             SPS_ESP8266_UART_RX_GPIO,
             SPS_ESP8266_UART_BAUD);

    /*
     * GPIO TX pin verification — only on first init.
     * On reconnects the pin is already claimed by UART, so skip.
     */
    if (s_first_init) {
        ESP_LOGI(TAG, "GPIO TX verification: toggling GPIO%d 3 times (0→1→0, 100ms each)",
                 SPS_ESP8266_UART_TX_GPIO);
        gpio_config_t tx_gpio_conf = {
            .pin_bit_mask = (1ULL << SPS_ESP8266_UART_TX_GPIO),
            .mode = GPIO_MODE_OUTPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
        };
        gpio_config(&tx_gpio_conf);
        for (int i = 0; i < 3; i++) {
            gpio_set_level(SPS_ESP8266_UART_TX_GPIO, 0);
            vTaskDelay(pdMS_TO_TICKS(100));
            gpio_set_level(SPS_ESP8266_UART_TX_GPIO, 1);
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        gpio_set_level(SPS_ESP8266_UART_TX_GPIO, 1); /* idle high */
        ESP_LOGI(TAG, "GPIO toggle done");
        s_first_init = false;
    } else {
        ESP_LOGI(TAG, "GPIO toggle skipped (reconnect)");
    }

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
        ESP_LOGI(TAG, "UART driver installed");
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
    ESP_LOGI(TAG, "UART pins configured: TX=GPIO%d RX=GPIO%d",
             SPS_ESP8266_UART_TX_GPIO, SPS_ESP8266_UART_RX_GPIO);

#if SPS_ESP8266_UART_LOOPBACK_TEST
    /*
     * UART Loopback Test — 用杜邦线短接 TX 和 RX 引脚。
     * 如果回环成功，证明 GPIO 支持 UART；否则该引脚不能做 UART。
     */
    ESP_LOGI(TAG, "=== UART LOOPBACK TEST ===");
    ESP_LOGI(TAG, "Connect GPIO%d(TX) to GPIO%d(RX) with a jumper wire!",
             SPS_ESP8266_UART_TX_GPIO, SPS_ESP8266_UART_RX_GPIO);
    vTaskDelay(pdMS_TO_TICKS(2000));

    uart_flush_input(SPS_ESP8266_UART_PORT);
    const char *test_str = "LOOPBACK_TEST_12345\r\n";
    uart_write_bytes(SPS_ESP8266_UART_PORT, test_str, strlen(test_str));
    ESP_LOGI(TAG, "Sent: %s", test_str);

    char loopback_buf[64] = {0};
    int total = 0;
    int64_t deadline = esp_timer_get_time() + 2000000;
    while (esp_timer_get_time() < deadline && total < (int)sizeof(loopback_buf) - 1) {
        uint8_t byte;
        int len = uart_read_bytes(SPS_ESP8266_UART_PORT, &byte, 1, pdMS_TO_TICKS(100));
        if (len > 0) {
            loopback_buf[total++] = (char)byte;
            loopback_buf[total] = '\0';
        }
    }

    if (total > 0) {
        ESP_LOGI(TAG, "Loopback received (%d bytes): %s", total, loopback_buf);
        if (strstr(loopback_buf, "LOOPBACK_TEST")) {
            ESP_LOGI(TAG, "LOOPBACK PASS — UART TX/RX works on GPIO%d/GPIO%d",
                     SPS_ESP8266_UART_TX_GPIO, SPS_ESP8266_UART_RX_GPIO);
        } else {
            ESP_LOGW(TAG, "LOOPBACK received data but mismatch — check baud rate or wiring");
        }
    } else {
        ESP_LOGE(TAG, "LOOPBACK FAIL — no data received on GPIO%d(RX)", SPS_ESP8266_UART_RX_GPIO);
        ESP_LOGE(TAG, "GPIO%d may not support UART TX, or GPIO%d may not support UART RX",
                 SPS_ESP8266_UART_TX_GPIO, SPS_ESP8266_UART_RX_GPIO);
        ESP_LOGE(TAG, "Try a different TX pin (e.g. GPIO17 or GPIO18)");
    }
    ESP_LOGI(TAG, "=== LOOPBACK TEST END ===");
    /* Don't fail — let the normal AT init continue */
#endif /* SPS_ESP8266_UART_LOOPBACK_TEST */

    /*
     * ESP8266 typically needs 1-2 seconds to boot after power-on.
     * During boot it sends a boot message at 74880 baud (boot ROM),
     * then switches to the configured baud rate.
     * We wait 2 seconds and capture any boot output for diagnostics.
     */
    ESP_LOGI(TAG, "Waiting 2s for ESP8266 boot, capturing any boot output...");
    {
        char boot_msg[256] = {0};
        size_t boot_len = 0;
        int64_t boot_deadline = esp_timer_get_time() + 2000000;
        while (esp_timer_get_time() < boot_deadline) {
            uint8_t byte;
            int len = uart_read_bytes(SPS_ESP8266_UART_PORT, &byte, 1, pdMS_TO_TICKS(100));
            if (len > 0 && boot_len < sizeof(boot_msg) - 1) {
                boot_msg[boot_len++] = (char)byte;
                boot_msg[boot_len] = '\0';
            }
        }
        if (boot_len > 0) {
            ESP_LOGI(TAG, "ESP8266 boot output (%u bytes): %s", (unsigned)boot_len, boot_msg);
        } else {
            ESP_LOGW(TAG, "ESP8266 sent NO boot output — check power (3.3V independent supply), GND, TX=GPIO%d→ESP8266-RX, RX=GPIO%d←ESP8266-TX",
                     SPS_ESP8266_UART_TX_GPIO, SPS_ESP8266_UART_RX_GPIO);
        }
    }

    uart_flush_input(SPS_ESP8266_UART_PORT);
    ESP_LOGI(TAG, "UART flushed, sending AT probe");

    esp_err_t at_err = at_command("AT", "OK", SPS_ESP8266_AT_TIMEOUT_MS);
    if (at_err != ESP_OK) {
        /*
         * Try 9600 baud — many ESP8266 modules ship with 9600 default.
         * Also try 74880 (boot ROM speed) in case the module is stuck in boot mode.
         */
        static const int alt_bauds[] = {9600, 74880};
        for (size_t b = 0; b < sizeof(alt_bauds) / sizeof(alt_bauds[0]); b++) {
            ESP_LOGW(TAG, "Retrying AT probe at %d baud...", alt_bauds[b]);
            uart_set_baudrate(SPS_ESP8266_UART_PORT, alt_bauds[b]);
            vTaskDelay(pdMS_TO_TICKS(300));
            uart_flush_input(SPS_ESP8266_UART_PORT);

            at_err = at_command("AT", "OK", 3000);
            if (at_err == ESP_OK) {
                ESP_LOGI(TAG, "AT OK at %d baud! ESP8266 uses non-standard baud rate.", alt_bauds[b]);
                /* Keep this baud rate for subsequent commands */
                uart_set_baudrate(SPS_ESP8266_UART_PORT, SPS_ESP8266_UART_BAUD);
                /* Send AT+UART_DEF to set ESP8266 to our preferred baud rate */
                char baud_cmd[32];
                snprintf(baud_cmd, sizeof(baud_cmd), "AT+UART_DEF=%d,8,1,0,0", SPS_ESP8266_UART_BAUD);
                uart_set_baudrate(SPS_ESP8266_UART_PORT, alt_bauds[b]);
                at_command(baud_cmd, "OK", 3000);
                vTaskDelay(pdMS_TO_TICKS(500));
                uart_set_baudrate(SPS_ESP8266_UART_PORT, SPS_ESP8266_UART_BAUD);
                vTaskDelay(pdMS_TO_TICKS(500));
                uart_flush_input(SPS_ESP8266_UART_PORT);
                break;
            }
        }

        if (at_err != ESP_OK) {
            /* Restore configured baud */
            uart_set_baudrate(SPS_ESP8266_UART_PORT, SPS_ESP8266_UART_BAUD);

            ESP_LOGE(TAG, "=== ESP8266 AT probe FAILED ===");
            ESP_LOGE(TAG, "  Sent: AT\\r\\n on UART%d GPIO%d(TX) GPIO%d(RX)",
                     SPS_ESP8266_UART_PORT,
                     SPS_ESP8266_UART_TX_GPIO, SPS_ESP8266_UART_RX_GPIO);
            ESP_LOGE(TAG, "  Tried baud rates: %d", SPS_ESP8266_UART_BAUD);
            for (size_t b = 0; b < sizeof(alt_bauds) / sizeof(alt_bauds[0]); b++) {
                ESP_LOGE(TAG, "                      %d", alt_bauds[b]);
            }
            ESP_LOGE(TAG, "  No response at any baud rate");
            ESP_LOGE(TAG, "  Check:");
            ESP_LOGE(TAG, "    1. ESP8266 3.3V power (independent supply, NOT from ESP32-P4 3.3V pin)");
            ESP_LOGE(TAG, "    2. GND connected between ESP32-P4 and ESP8266");
            ESP_LOGE(TAG, "    3. ESP32P4 GPIO%d(TX) -> ESP8266 RX", SPS_ESP8266_UART_TX_GPIO);
            ESP_LOGE(TAG, "    4. ESP32P4 GPIO%d(RX) <- ESP8266 TX", SPS_ESP8266_UART_RX_GPIO);
            ESP_LOGE(TAG, "    5. Verify GPIO%d can output: measure with multimeter during GPIO toggle test above",
                     SPS_ESP8266_UART_TX_GPIO);
            ESP_LOGE(TAG, "    6. If GPIO%d toggles but UART doesn't work: pin may not support UART TX via IO MUX",
                     SPS_ESP8266_UART_TX_GPIO);
            return at_err;
        }
    }

    /* If AT probe failed, it already returned. If we get here, AT works. */
    ESP_LOGI(TAG, "AT OK");
    ESP_RETURN_ON_ERROR(at_command("ATE0", "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "ATE0 failed");
    ESP_RETURN_ON_ERROR(at_command("AT+CWMODE=1", "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "CWMODE failed");
    ESP_LOGI(TAG, "CWMODE station mode set OK");
    ESP_RETURN_ON_ERROR(at_command("AT+CIPMUX=0", "OK", SPS_ESP8266_AT_TIMEOUT_MS), TAG, "CIPMUX failed");

    ESP_LOGI(TAG, "ESP8266 AT init ok");
    return ESP_OK;
}

esp_err_t esp8266_at_join_ap(const char *ssid, const char *password)
{
    if (ssid == NULL || password == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    bool open_ap = password[0] == '\0';
    char cmd[160] = {0};
    snprintf(cmd, sizeof(cmd), "AT+CWJAP=\"%s\",\"%s\"", ssid, password);
    ESP_LOGI(TAG, "Connecting SSID: %s", ssid);
    ESP_LOGI(TAG, "Open AP: %s", open_ap ? "yes" : "no");
    esp_err_t err = at_command(cmd, "WIFI GOT IP", 20000);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "WIFI CONNECTED");
        ESP_LOGI(TAG, "WIFI GOT IP");
    }
    return err;
}

esp_err_t esp8266_at_query_ip(void)
{
    ESP_LOGI(TAG, "Querying ESP8266 IP with CIFSR");
    return at_command("AT+CIFSR", "OK", SPS_ESP8266_AT_TIMEOUT_MS);
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

    /* A server-side "Connection: close" normally produces CLOSED first.
     * Sending CIPCLOSE afterwards only generates a misleading ERROR. */
    if (strstr(response, "CLOSED") == NULL) {
        at_command("AT+CIPCLOSE", "OK", 1000);
    }
    return err;
}
