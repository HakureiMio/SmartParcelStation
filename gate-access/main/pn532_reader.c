#include "pn532_reader.h"

#include <string.h>

#include "app_config.h"
#include "driver/uart.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "pn532";
static bool s_uart_driver_installed;

/*
 * HSU wake preamble — must be sent before EVERY command when the PN532
 * may have been idle.  The PN532 auto-baud detects from the 0x55 pattern
 * and the following bytes (including the command frame itself) serve as
 * dummy bytes to complete the baud-rate lock.
 *
 * libnfc uses 5 bytes (55 55 00 00 00); the Linux kernel driver uses
 * 16 bytes (55 55 + 14×00).  Either works — we use 6 to keep overhead low.
 */
static const uint8_t PN532_WAKE[] = {0x55, 0x55, 0x00, 0x00, 0x00, 0x00};

#define PN532_PREAMBLE          0x00
#define PN532_STARTCODE1        0x00
#define PN532_STARTCODE2        0xFF
#define PN532_POSTAMBLE         0x00
#define PN532_HOST_TO_PN532     0xD4
#define PN532_PN532_TO_HOST     0xD5
#define PN532_CMD_GET_FIRMWARE  0x02
#define PN532_CMD_SAM_CONFIG    0x14
#define PN532_CMD_IN_LIST       0x4A

static const uint8_t PN532_ACK[] = {0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00};

static esp_err_t pn532_uart_configure(void)
{
    uart_config_t uart_config = {
        .baud_rate = SPS_PN532_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    if (!s_uart_driver_installed) {
        ESP_RETURN_ON_ERROR(uart_driver_install(SPS_PN532_UART_PORT,
                                                 SPS_PN532_UART_BUF_SIZE,
                                                 SPS_PN532_UART_BUF_SIZE,
                                                 0, NULL, 0),
                            TAG, "PN532 UART driver install failed");
        s_uart_driver_installed = true;
    }
    ESP_RETURN_ON_ERROR(uart_param_config(SPS_PN532_UART_PORT, &uart_config), TAG,
                        "PN532 UART config failed");
    ESP_RETURN_ON_ERROR(uart_set_pin(SPS_PN532_UART_PORT,
                                     SPS_PN532_UART_TX_GPIO,
                                     SPS_PN532_UART_RX_GPIO,
                                     UART_PIN_NO_CHANGE,
                                     UART_PIN_NO_CHANGE),
                        TAG, "PN532 UART pin config failed");
    return ESP_OK;
}

static uint8_t checksum(const uint8_t *data, size_t len)
{
    uint8_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum = (uint8_t)(sum + data[i]);
    }
    return (uint8_t)(~sum + 1);
}

static esp_err_t uart_read_exact(uint8_t *buffer, size_t length, int timeout_ms)
{
    size_t received = 0;
    int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    while (received < length && esp_timer_get_time() < deadline) {
        int remaining_ms = (int)((deadline - esp_timer_get_time()) / 1000);
        if (remaining_ms < 1) {
            remaining_ms = 1;
        }
        int count = uart_read_bytes(SPS_PN532_UART_PORT, buffer + received,
                                    length - received,
                                    pdMS_TO_TICKS(remaining_ms > 50 ? 50 : remaining_ms));
        if (count > 0) {
            received += (size_t)count;
        }
    }
    return received == length ? ESP_OK : ESP_ERR_TIMEOUT;
}

static esp_err_t uart_find_sequence(const uint8_t *sequence, size_t sequence_len, int timeout_ms)
{
    size_t matched = 0;
    uint8_t received[32] = {0};
    size_t received_len = 0;
    int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    while (esp_timer_get_time() < deadline) {
        uint8_t byte = 0;
        int count = uart_read_bytes(SPS_PN532_UART_PORT, &byte, 1, pdMS_TO_TICKS(20));
        if (count <= 0) {
            continue;
        }
        if (received_len < sizeof(received)) {
            received[received_len++] = byte;
        }
        if (byte == sequence[matched]) {
            if (++matched == sequence_len) {
                return ESP_OK;
            }
        } else {
            matched = byte == sequence[0] ? 1 : 0;
        }
    }
    if (received_len > 0) {
        ESP_LOGW(TAG, "PN532 UART received %u byte(s), but expected sequence was absent:",
                 (unsigned)received_len);
        ESP_LOG_BUFFER_HEX_LEVEL(TAG, received, received_len, ESP_LOG_WARN);
    } else {
        ESP_LOGW(TAG, "PN532 UART RX remained silent for %dms", timeout_ms);
    }
    return ESP_ERR_TIMEOUT;
}

static esp_err_t pn532_read_ack(void)
{
    return uart_find_sequence(PN532_ACK, sizeof(PN532_ACK), SPS_PN532_UART_TIMEOUT_MS);
}

static esp_err_t pn532_send_command(const uint8_t *cmd, size_t cmd_len)
{
    uint8_t frame[80] = {0};
    size_t len = cmd_len + 1;
    if (len > 0xFF || cmd_len + 8 > sizeof(frame)) {
        return ESP_ERR_INVALID_SIZE;
    }

    frame[0] = PN532_PREAMBLE;
    frame[1] = PN532_STARTCODE1;
    frame[2] = PN532_STARTCODE2;
    frame[3] = (uint8_t)len;
    frame[4] = (uint8_t)(~len + 1);
    frame[5] = PN532_HOST_TO_PN532;
    memcpy(&frame[6], cmd, cmd_len);
    frame[6 + cmd_len] = checksum(&frame[5], len);
    frame[7 + cmd_len] = PN532_POSTAMBLE;

    /*
     * Always prepend the HSU wake preamble.  Without it, PN532 will
     * miss commands after even brief idle periods (< 100 ms).
     * Do NOT flush between wake and command — the PN532 uses the
     * command bytes as part of its baud-rate auto-detection.
     *
     * Continuous write:  wake (6 B) + frame (cmd_len+8 B)
     */
    size_t total = sizeof(PN532_WAKE) + cmd_len + 8;
    uint8_t combined[sizeof(PN532_WAKE) + 80];
    memcpy(combined, PN532_WAKE, sizeof(PN532_WAKE));
    memcpy(combined + sizeof(PN532_WAKE), frame, cmd_len + 8);

    int written = uart_write_bytes(SPS_PN532_UART_PORT, combined, total);
    ESP_RETURN_ON_FALSE(written == (int)total, ESP_FAIL, TAG,
                        "PN532 UART write failed: %d/%u", written, (unsigned)total);
    ESP_RETURN_ON_ERROR(uart_wait_tx_done(SPS_PN532_UART_PORT, pdMS_TO_TICKS(100)), TAG,
                        "PN532 UART TX timeout");

    ESP_RETURN_ON_ERROR(pn532_read_ack(), TAG, "PN532 ACK timeout");
    return ESP_OK;
}

static esp_err_t pn532_read_response(uint8_t expected_cmd, uint8_t *payload, size_t payload_size, size_t *payload_len)
{
    const uint8_t start_code[] = {PN532_PREAMBLE, PN532_STARTCODE1, PN532_STARTCODE2};
    ESP_RETURN_ON_ERROR(uart_find_sequence(start_code, sizeof(start_code), SPS_PN532_UART_TIMEOUT_MS),
                        TAG, "PN532 response timeout");

    uint8_t header[2] = {0};
    ESP_RETURN_ON_ERROR(uart_read_exact(header, sizeof(header), 100), TAG,
                        "PN532 response header incomplete");
    if ((uint8_t)(header[0] + header[1]) != 0) {
        return ESP_ERR_INVALID_CRC;
    }

    size_t len = header[0];
    if (len < 2 || len + 2 > 96) {
        return ESP_ERR_INVALID_SIZE;
    }

    uint8_t body[96] = {0};
    ESP_RETURN_ON_ERROR(uart_read_exact(body, len + 2, 200), TAG,
                        "PN532 response body incomplete");
    if (body[0] != PN532_PN532_TO_HOST || body[1] != (uint8_t)(expected_cmd + 1)) {
        return ESP_ERR_INVALID_RESPONSE;
    }
    if (checksum(body, len + 1) != 0 || body[len + 1] != PN532_POSTAMBLE) {
        return ESP_ERR_INVALID_CRC;
    }

    size_t data_len = len - 2;
    if (data_len > payload_size) {
        return ESP_ERR_INVALID_SIZE;
    }

    memcpy(payload, &body[2], data_len);
    *payload_len = data_len;
    return ESP_OK;
}

static esp_err_t pn532_command(uint8_t cmd_code, const uint8_t *args, size_t args_len, uint8_t *payload, size_t payload_size, size_t *payload_len)
{
    uint8_t cmd[32] = {0};
    if (args_len + 1 > sizeof(cmd)) {
        return ESP_ERR_INVALID_SIZE;
    }
    cmd[0] = cmd_code;
    if (args_len > 0) {
        memcpy(&cmd[1], args, args_len);
    }

    ESP_RETURN_ON_ERROR(pn532_send_command(cmd, args_len + 1), TAG, "send command failed");
    return pn532_read_response(cmd_code, payload, payload_size, payload_len);
}

static void uid_to_hex(const uint8_t *uid, size_t uid_len, char *uid_hex, size_t uid_hex_size)
{
    static const char HEX[] = "0123456789ABCDEF";
    size_t out = 0;

    for (size_t i = 0; i < uid_len && out + 2 < uid_hex_size; i++) {
        uid_hex[out++] = HEX[(uid[i] >> 4) & 0x0F];
        uid_hex[out++] = HEX[uid[i] & 0x0F];
    }
    uid_hex[out] = '\0';
}

esp_err_t pn532_reader_uart_loopback_test(void)
{
    static const uint8_t pattern[] = {
        0x55, 0xAA, 0x00, 0xFF, 0x12, 0x34, 0x56, 0x78,
        'P', 'N', '5', '3', '2', '-', 'U', '2',
    };
    uint8_t received[sizeof(pattern)] = {0};

    ESP_RETURN_ON_ERROR(pn532_uart_configure(), TAG, "configure UART2 loopback failed");
    ESP_LOGI(TAG, "=== PN532 UART2 LOOPBACK TEST ===");
    ESP_LOGI(TAG, "Disconnect PN532 and short GPIO%d(TX) directly to GPIO%d(RX)",
             SPS_PN532_UART_TX_GPIO, SPS_PN532_UART_RX_GPIO);
    uart_flush_input(SPS_PN532_UART_PORT);

    int written = uart_write_bytes(SPS_PN532_UART_PORT, pattern, sizeof(pattern));
    ESP_RETURN_ON_FALSE(written == sizeof(pattern), ESP_FAIL, TAG,
                        "UART2 loopback write failed: %d/%u", written, (unsigned)sizeof(pattern));
    ESP_RETURN_ON_ERROR(uart_wait_tx_done(SPS_PN532_UART_PORT, pdMS_TO_TICKS(100)), TAG,
                        "UART2 loopback TX timeout");

    esp_err_t err = uart_read_exact(received, sizeof(received), 1000);
    if (err != ESP_OK) {
        size_t buffered = 0;
        uart_get_buffered_data_len(SPS_PN532_UART_PORT, &buffered);
        ESP_LOGE(TAG, "UART2 LOOPBACK FAIL: RX timeout (remaining buffered=%u)",
                 (unsigned)buffered);
        return err;
    }
    if (memcmp(received, pattern, sizeof(pattern)) != 0) {
        ESP_LOGE(TAG, "UART2 LOOPBACK FAIL: received bytes differ");
        ESP_LOG_BUFFER_HEX_LEVEL(TAG, received, sizeof(received), ESP_LOG_ERROR);
        return ESP_ERR_INVALID_RESPONSE;
    }

    ESP_LOGI(TAG, "UART2 LOOPBACK PASS: %u bytes matched on GPIO%d/GPIO%d",
             (unsigned)sizeof(pattern), SPS_PN532_UART_TX_GPIO, SPS_PN532_UART_RX_GPIO);
    return ESP_OK;
}

esp_err_t pn532_reader_init(void)
{
#if SPS_PN532_USE_RESET
    {
        gpio_config_t reset_config = {
            .pin_bit_mask = 1ULL << SPS_PN532_RST_GPIO,
            .mode = GPIO_MODE_OUTPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
        };
        ESP_RETURN_ON_ERROR(gpio_config(&reset_config), TAG, "configure PN532 reset failed");
        gpio_set_level(SPS_PN532_RST_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(20));
        gpio_set_level(SPS_PN532_RST_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        ESP_LOGI(TAG, "PN532 hardware reset complete: GPIO%d low 20ms -> high",
                 SPS_PN532_RST_GPIO);
    }
#endif

    ESP_RETURN_ON_ERROR(pn532_uart_configure(), TAG, "configure PN532 HSU failed");

    ESP_LOGI(TAG, "PN532 HSU: UART%d TX=GPIO%d RX=GPIO%d baud=%d 8N1",
             SPS_PN532_UART_PORT, SPS_PN532_UART_TX_GPIO,
             SPS_PN532_UART_RX_GPIO, SPS_PN532_UART_BAUD);

    /* Per-command wake is now prepended inside pn532_send_command().
     * Just flush any stray RX bytes and send the first command. */
    uart_flush_input(SPS_PN532_UART_PORT);

    uint8_t payload[16] = {0};
    size_t payload_len = 0;
    /* PN532 application note C106 and libnfc require SAMConfiguration as
     * the first command after leaving LowVbat mode. */
    uint8_t sam_args[] = {0x01, 0x14, 0x01};
    esp_err_t err = pn532_command(PN532_CMD_SAM_CONFIG, sam_args, sizeof(sam_args),
                                  payload, sizeof(payload), &payload_len);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PN532 wake SAMConfiguration failed: %s", esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "PN532 wake SAMConfiguration OK");

    err = pn532_command(PN532_CMD_GET_FIRMWARE, NULL, 0, payload, sizeof(payload), &payload_len);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PN532 firmware query failed: %s", esp_err_to_name(err));
        return err;
    }
    if (payload_len >= 4) {
        ESP_LOGI(TAG, "PN532 firmware: IC=0x%02X Ver=%u.%u Support=0x%02X",
                 payload[0], payload[1], payload[2], payload[3]);
    }

    ESP_LOGI(TAG, "PN532 init ok");
    return ESP_OK;
}

esp_err_t pn532_reader_poll_uid(char *uid_hex, size_t uid_hex_size, bool *card_present)
{
    if (uid_hex == NULL || card_present == NULL || uid_hex_size < 3) {
        return ESP_ERR_INVALID_ARG;
    }

    *card_present = false;
    uid_hex[0] = '\0';

    uint8_t args[] = {0x01, 0x00};
    uint8_t payload[32] = {0};
    size_t payload_len = 0;
    esp_err_t err = pn532_command(PN532_CMD_IN_LIST, args, sizeof(args), payload, sizeof(payload), &payload_len);
    if (err == ESP_ERR_TIMEOUT) {
        return ESP_OK;
    }
    if (err != ESP_OK) {
        return err;
    }

    if (payload_len < 7 || payload[0] == 0) {
        return ESP_OK;
    }

    size_t uid_len_index = 5;
    uint8_t uid_len = payload[uid_len_index];
    if (uid_len == 0 || uid_len > 10 || uid_len_index + 1 + uid_len > payload_len) {
        return ESP_ERR_INVALID_RESPONSE;
    }
    if ((size_t)uid_len * 2 + 1 > uid_hex_size) {
        return ESP_ERR_INVALID_SIZE;
    }

    uid_to_hex(&payload[uid_len_index + 1], uid_len, uid_hex, uid_hex_size);
    *card_present = true;
    return ESP_OK;
}
