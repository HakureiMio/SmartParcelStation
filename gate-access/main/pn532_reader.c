#include "pn532_reader.h"

#include <string.h>

#include "app_config.h"
#include "driver/i2c.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "pn532";
static bool s_i2c_driver_installed;

#define PN532_PREAMBLE          0x00
#define PN532_STARTCODE1        0x00
#define PN532_STARTCODE2        0xFF
#define PN532_POSTAMBLE         0x00
#define PN532_HOST_TO_PN532     0xD4
#define PN532_PN532_TO_HOST     0xD5
#define PN532_I2C_READY         0x01

#define PN532_CMD_GET_FIRMWARE  0x02
#define PN532_CMD_SAM_CONFIG    0x14
#define PN532_CMD_IN_LIST       0x4A

static const uint8_t PN532_ACK[] = {0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00};

static uint8_t checksum(const uint8_t *data, size_t len)
{
    uint8_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum = (uint8_t)(sum + data[i]);
    }
    return (uint8_t)(~sum + 1);
}

static esp_err_t pn532_wait_ready(TickType_t timeout_ticks)
{
    TickType_t start = xTaskGetTickCount();
    uint8_t status = 0;

    while ((xTaskGetTickCount() - start) < timeout_ticks) {
        esp_err_t err = i2c_master_read_from_device(
            SPS_PN532_I2C_PORT,
            SPS_PN532_I2C_ADDR,
            &status,
            1,
            pdMS_TO_TICKS(100));
        if (err == ESP_OK && status == PN532_I2C_READY) {
            return ESP_OK;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }

    return ESP_ERR_TIMEOUT;
}

static esp_err_t pn532_read_raw(uint8_t *buffer, size_t buffer_len)
{
    ESP_RETURN_ON_ERROR(pn532_wait_ready(pdMS_TO_TICKS(1000)), TAG, "PN532 not ready");

    uint8_t tmp[96] = {0};
    if (buffer_len + 1 > sizeof(tmp)) {
        return ESP_ERR_INVALID_SIZE;
    }

    ESP_RETURN_ON_ERROR(
        i2c_master_read_from_device(SPS_PN532_I2C_PORT, SPS_PN532_I2C_ADDR, tmp, buffer_len + 1, pdMS_TO_TICKS(1000)),
        TAG,
        "PN532 read failed");

    if (tmp[0] != PN532_I2C_READY) {
        return ESP_ERR_INVALID_RESPONSE;
    }
    memcpy(buffer, &tmp[1], buffer_len);
    return ESP_OK;
}

static esp_err_t pn532_read_ack(void)
{
    uint8_t ack[sizeof(PN532_ACK)] = {0};
    ESP_RETURN_ON_ERROR(pn532_read_raw(ack, sizeof(ack)), TAG, "read ACK failed");
    if (memcmp(ack, PN532_ACK, sizeof(PN532_ACK)) != 0) {
        ESP_LOG_BUFFER_HEX_LEVEL(TAG, ack, sizeof(ack), ESP_LOG_WARN);
        return ESP_ERR_INVALID_RESPONSE;
    }
    return ESP_OK;
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

    ESP_RETURN_ON_ERROR(
        i2c_master_write_to_device(SPS_PN532_I2C_PORT, SPS_PN532_I2C_ADDR, frame, cmd_len + 8, pdMS_TO_TICKS(1000)),
        TAG,
        "PN532 write failed");

    return pn532_read_ack();
}

static esp_err_t pn532_read_response(uint8_t expected_cmd, uint8_t *payload, size_t payload_size, size_t *payload_len)
{
    uint8_t frame[96] = {0};
    ESP_RETURN_ON_ERROR(pn532_read_raw(frame, sizeof(frame)), TAG, "read response failed");

    if (frame[0] != PN532_PREAMBLE || frame[1] != PN532_STARTCODE1 || frame[2] != PN532_STARTCODE2) {
        return ESP_ERR_INVALID_RESPONSE;
    }
    if ((uint8_t)(frame[3] + frame[4]) != 0) {
        return ESP_ERR_INVALID_CRC;
    }

    size_t len = frame[3];
    if (len < 2 || len + 7 > sizeof(frame)) {
        return ESP_ERR_INVALID_SIZE;
    }
    if (frame[5] != PN532_PN532_TO_HOST || frame[6] != (uint8_t)(expected_cmd + 1)) {
        return ESP_ERR_INVALID_RESPONSE;
    }
    if (checksum(&frame[5], len + 1) != 0) {
        return ESP_ERR_INVALID_CRC;
    }

    size_t data_len = len - 2;
    if (data_len > payload_size) {
        return ESP_ERR_INVALID_SIZE;
    }

    memcpy(payload, &frame[7], data_len);
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

esp_err_t pn532_reader_init(void)
{
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = SPS_PN532_I2C_SDA_GPIO,
        .scl_io_num = SPS_PN532_I2C_SCL_GPIO,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = SPS_PN532_I2C_FREQ_HZ,
    };

    if (!s_i2c_driver_installed) {
        ESP_RETURN_ON_ERROR(i2c_param_config(SPS_PN532_I2C_PORT, &conf), TAG, "I2C config failed");
        ESP_RETURN_ON_ERROR(i2c_driver_install(SPS_PN532_I2C_PORT, conf.mode, 0, 0, 0), TAG, "I2C driver install failed");
        s_i2c_driver_installed = true;
    }

    vTaskDelay(pdMS_TO_TICKS(100));

    uint8_t payload[16] = {0};
    size_t payload_len = 0;
    esp_err_t err = pn532_command(PN532_CMD_GET_FIRMWARE, NULL, 0, payload, sizeof(payload), &payload_len);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PN532 firmware query failed: %s", esp_err_to_name(err));
        return err;
    }

    uint8_t sam_args[] = {0x01, 0x14, 0x01};
    err = pn532_command(PN532_CMD_SAM_CONFIG, sam_args, sizeof(sam_args), payload, sizeof(payload), &payload_len);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PN532 SAMConfiguration failed: %s", esp_err_to_name(err));
        return err;
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
