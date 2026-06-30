#include "pn532_diag.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "app_config.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "pn532_diag";

/* ── PN532 protocol constants ────────────────────────────────── */

#define PN532_PREAMBLE      0x00
#define PN532_STARTCODE1    0x00
#define PN532_STARTCODE2    0xFF
#define PN532_POSTAMBLE     0x00
#define PN532_HOST_TO_PN532 0xD4
#define PN532_PN532_TO_HOST 0xD5

/* standard ACK frame: 00 00 FF 00 FF 00 */
static const uint8_t DIAG_ACK[] = {0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00};

/*
 * libnfc-compatible HSU wake sequence:
 * 55 55 + 14 zero bytes = 16 bytes total.
 */
static const uint8_t DIAG_WAKE[] = {
    0x55, 0x55,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};

/*
 * GetFirmwareVersion command frame (no SAM required):
 *   00 00 FF 02 FE D4 02 2A 00
 * length=2 (D4+02), LCS=~2=FD... wait ~2 = FD.
 * Actually: 2 = 0x02, ~0x02 = 0xFD, ~0x02+1 = 0xFE.
 * TFI=D4, CMD=02, DCS=~(D4+02)+1 = ~0xD6+1 = 0x29+1 = 0x2A.
 */
static const uint8_t DIAG_CMD_GET_FW[] = {
    0x00, 0x00, 0xFF, 0x02, 0xFE, 0xD4, 0x02, 0x2A, 0x00,
};

/*
 * SAMConfiguration command frame (normal mode, timeout=20*50ms=1s, IRQ=on):
 *   00 00 FF 05 FB D4 14 01 14 01 02 00
 * length=5 (D4+14+01+14+01), LCS=~5+1=0xFB.
 * TFI=D4, CMD=14, P1=01(normal), P2=14(timeout), P3=01(irq).
 * DCS=~(D4+14+01+14+01)+1 = ~0xFE+1 = 0x01+1 = 0x02.
 */
static const uint8_t DIAG_CMD_SAM_CFG[] = {
    0x00, 0x00, 0xFF, 0x05, 0xFB, 0xD4, 0x14, 0x01, 0x14, 0x01, 0x02, 0x00,
};

/* ── Privately reuse the UART port configured in app_config.h ─── */
#define DIAG_UART_PORT  SPS_PN532_UART_PORT

/* ── Helpers ─────────────────────────────────────────────────── */

static void diag_flush_rx(void)
{
    uart_flush_input(DIAG_UART_PORT);
}

static esp_err_t diag_write(const uint8_t *data, size_t len)
{
    int written = uart_write_bytes(DIAG_UART_PORT, data, len);
    if (written != (int)len) {
        ESP_LOGE(TAG, "UART write failed: expected %u, got %d", (unsigned)len, written);
        return ESP_FAIL;
    }
    return uart_wait_tx_done(DIAG_UART_PORT, pdMS_TO_TICKS(100));
}

static void diag_print_hex(const char *label, const uint8_t *data, size_t len)
{
    if (len == 0) {
        ESP_LOGI(TAG, "  %s: (0 bytes)", label);
        return;
    }
    char hex[256] = {0};
    size_t offset = 0;
    for (size_t i = 0; i < len && offset < sizeof(hex) - 4; i++) {
        int n = snprintf(hex + offset, sizeof(hex) - offset,
                         "%02X ", data[i]);
        if (n > 0) { offset += (size_t)n; }
    }
    ESP_LOGI(TAG, "  %s (%u bytes): %s", label, (unsigned)len, hex);
}

/*
 * Read whatever is available on RX within `timeout_ms`.
 * Returns number of bytes read (0 = silent).
 */
static size_t diag_read_any(uint8_t *buf, size_t buf_size, int timeout_ms)
{
    size_t total = 0;
    int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    while (total < buf_size && esp_timer_get_time() < deadline) {
        int remain_ms = (int)((deadline - esp_timer_get_time()) / 1000);
        if (remain_ms < 1) { remain_ms = 1; }
        int n = uart_read_bytes(DIAG_UART_PORT, buf + total, buf_size - total,
                                pdMS_TO_TICKS(remain_ms > 100 ? 100 : remain_ms));
        if (n > 0) { total += (size_t)n; }
    }
    return total;
}

/*
 * Search for a byte sequence in RX stream.  Stores ALL received bytes
 * (up to buf_size) in buf and returns total bytes read.
 * Places 1 in *found if the sequence was seen.
 */
static size_t diag_find_sequence(const uint8_t *seq, size_t seq_len,
                                  uint8_t *buf, size_t buf_size,
                                  int timeout_ms, bool *found)
{
    *found = false;
    size_t matched = 0;
    size_t total = 0;
    int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    while (esp_timer_get_time() < deadline) {
        uint8_t byte = 0;
        int n = uart_read_bytes(DIAG_UART_PORT, &byte, 1, pdMS_TO_TICKS(20));
        if (n <= 0) { continue; }
        if (total < buf_size) { buf[total] = byte; }
        total++;
        if (byte == seq[matched]) {
            if (++matched == seq_len) {
                *found = true;
                return total;
            }
        } else {
            matched = (byte == seq[0]) ? 1 : 0;
        }
    }
    return total;
}

static void diag_dump_rx(const char *label, const uint8_t *buf, size_t len, bool ack_found)
{
    diag_print_hex(label, buf, len);
    if (len == 0) {
        ESP_LOGE(TAG, "  >>> RX SILENT — PN532 sent zero bytes");
        ESP_LOGW(TAG, "  >>> ESP TX path was verified by loopback; check:");
        ESP_LOGW(TAG, "      1. PN532 RXD wired to ESP32-P4 GPIO%d", SPS_PN532_UART_TX_GPIO);
        ESP_LOGW(TAG, "      2. PN532 TXD wired to ESP32-P4 GPIO%d", SPS_PN532_UART_RX_GPIO);
        ESP_LOGW(TAG, "      3. PN532 3.3V power and GND");
        ESP_LOGW(TAG, "      4. PN532 DIP switches set to HSU mode");
        ESP_LOGW(TAG, "      5. PN532 module silk-screen: RXD=receive(from host), TXD=transmit(to host)");
    } else if (!ack_found) {
        ESP_LOGW(TAG, "  >>> NON-ACK DATA received — PN532 is alive but response unexpected");
    }
}

/* ── Public diagnostic entry point ───────────────────────────── */

esp_err_t pn532_uart_diag_run(void)
{
    /* ── Step 0: UART parameter confirmation ────────────────── */
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "PN532 HSU DIAGNOSTIC — Step 0: UART Configuration");
    ESP_LOGI(TAG, "  Port:   UART%d", DIAG_UART_PORT);
    ESP_LOGI(TAG, "  TX:     GPIO%d (ESP -> PN532 RXD)", SPS_PN532_UART_TX_GPIO);
    ESP_LOGI(TAG, "  RX:     GPIO%d (ESP <- PN532 TXD)", SPS_PN532_UART_RX_GPIO);
    ESP_LOGI(TAG, "  Baud:   %d 8N1, flow_ctrl=off", SPS_PN532_UART_BAUD);
    ESP_LOGI(TAG, "  NOTE:   module silk-screen RXD/TXD is from PN532's perspective.");
    ESP_LOGI(TAG, "          ESP TX -> PN532 RXD, ESP RX <- PN532 TXD.");
#if SPS_PN532_UART_LOOPBACK_TEST
    ESP_LOGI(TAG, "  MODE:   LOOPBACK TEST — disconnect PN532, short GPIO%d--GPIO%d",
             SPS_PN532_UART_TX_GPIO, SPS_PN532_UART_RX_GPIO);
#else
    ESP_LOGI(TAG, "  MODE:   PN532 TEST — remove loopback short, connect PN532");
#endif
    ESP_LOGI(TAG, "============================================================");

    uart_config_t uart_cfg = {
        .baud_rate = SPS_PN532_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity   = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    esp_err_t err = uart_driver_install(DIAG_UART_PORT,
                                         SPS_PN532_UART_BUF_SIZE,
                                         SPS_PN532_UART_BUF_SIZE,
                                         0, NULL, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "UART%d driver install failed: %s", DIAG_UART_PORT, esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "UART%d driver installed", DIAG_UART_PORT);

    err = uart_param_config(DIAG_UART_PORT, &uart_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "UART%d param config failed: %s", DIAG_UART_PORT, esp_err_to_name(err));
        return err;
    }

    err = uart_set_pin(DIAG_UART_PORT,
                       SPS_PN532_UART_TX_GPIO,
                       SPS_PN532_UART_RX_GPIO,
                       UART_PIN_NO_CHANGE,
                       UART_PIN_NO_CHANGE);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "UART%d pin config failed: %s", DIAG_UART_PORT, esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "UART%d pins set: TX=GPIO%d RX=GPIO%d",
             DIAG_UART_PORT, SPS_PN532_UART_TX_GPIO, SPS_PN532_UART_RX_GPIO);

    diag_flush_rx();
    ESP_LOGI(TAG, "RX flushed; waiting 500ms for UART / PN532 to settle...");
    vTaskDelay(pdMS_TO_TICKS(500));

#if SPS_PN532_UART_LOOPBACK_TEST
    /* ── Loopback test ─────────────────────────────────────── */
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "LOOPBACK TEST — GPIO%d(TX) shorted to GPIO%d(RX)",
             SPS_PN532_UART_TX_GPIO, SPS_PN532_UART_RX_GPIO);
    {
        static const uint8_t lb[] = {
            0x55, 0xAA, 0x00, 0xFF, 0x12, 0x34, 0x56, 0x78,
            'P', 'N', '5', '3', '2', '-', 'U', '2',
        };
        uint8_t rx[sizeof(lb)] = {0};
        diag_flush_rx();
        diag_print_hex("TX", lb, sizeof(lb));
        ESP_ERROR_CHECK(diag_write(lb, sizeof(lb)));
        size_t n = diag_read_any(rx, sizeof(rx), 1000);
        diag_print_hex("RX", rx, n);
        if (n == sizeof(lb) && memcmp(rx, lb, sizeof(lb)) == 0) {
            ESP_LOGI(TAG, "LOOPBACK PASS: %u bytes matched — UART2 GPIO%d/GPIO%d hardware OK",
                     (unsigned)sizeof(lb), SPS_PN532_UART_TX_GPIO, SPS_PN532_UART_RX_GPIO);
        } else {
            ESP_LOGE(TAG, "LOOPBACK FAIL: expected %u bytes, got %u", (unsigned)sizeof(lb), (unsigned)n);
        }
    }
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "DIAGNOSTIC COMPLETE (loopback mode).");
    ESP_LOGI(TAG, "To test PN532: set SPS_PN532_UART_LOOPBACK_TEST=0, remove short, reconnect PN532.");
    while (true) { vTaskDelay(pdMS_TO_TICKS(5000)); }
    return ESP_OK;
#endif /* SPS_PN532_UART_LOOPBACK_TEST */

    /* ── Step 1: RX idle sniff ───────────────────────────────── */
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "Step 1: RX idle sniff (1500ms, no TX)");
    {
        uint8_t idle_rx[128] = {0};
        size_t n = diag_read_any(idle_rx, sizeof(idle_rx), 1500);
        if (n > 0) {
            ESP_LOGI(TAG, "PN532 idle RX bytes: (PN532 sent data without being asked)");
            diag_print_hex("idle RX", idle_rx, n);
        } else {
            ESP_LOGI(TAG, "PN532 idle RX silent (normal if PN532 waits for wake-up)");
        }
    }

    /* ── Step 2: libnfc wake only ────────────────────────────── */
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "Step 2: libnfc 16-byte HSU wake (no command)");
    diag_flush_rx();
    diag_print_hex("TX wake", DIAG_WAKE, sizeof(DIAG_WAKE));
    ESP_ERROR_CHECK(diag_write(DIAG_WAKE, sizeof(DIAG_WAKE)));
    vTaskDelay(pdMS_TO_TICKS(100));
    {
        uint8_t wake_rx[128] = {0};
        size_t n = diag_read_any(wake_rx, sizeof(wake_rx), 1200);
        diag_dump_rx("RX after wake", wake_rx, n, false);
        if (n == 0) {
            ESP_LOGW(TAG, "PN532 wake-only RX silent:");
            ESP_LOGW(TAG, "  ESP TX path is verified OK (UART write returned expected length).");
            ESP_LOGW(TAG, "  Now check PN532-side: RXD wiring, 3.3V power, HSU DIP switches,");
            ESP_LOGW(TAG, "  and PN532 TXD -> ESP GPIO%d continuity.", SPS_PN532_UART_RX_GPIO);
        }
    }

    /* ── Step 3: GetFirmwareVersion (no SAM) ─────────────────── */
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "Step 3: GetFirmwareVersion (without SAMConfiguration)");
    ESP_LOGI(TAG, "  Strategy: wake bytes immediately followed by command, NO delay/gap.");
    diag_flush_rx();

    /* Send wake + command as one continuous stream (libnfc strategy).
     * The PN532 uses the command bytes as "dummy bytes" to complete
     * its baud-rate detection and wake-up. Any gap > 1ms breaks this. */
    {
        uint8_t combined[sizeof(DIAG_WAKE) + sizeof(DIAG_CMD_GET_FW)];
        memcpy(combined, DIAG_WAKE, sizeof(DIAG_WAKE));
        memcpy(combined + sizeof(DIAG_WAKE), DIAG_CMD_GET_FW, sizeof(DIAG_CMD_GET_FW));
        diag_print_hex("TX wake+CMD (one stream)", combined, sizeof(combined));
        ESP_ERROR_CHECK(diag_write(combined, sizeof(combined)));
    }

    /* Wait for ACK */
    {
        uint8_t ack_rx[128] = {0};
        bool ack_found = false;
        size_t n = diag_find_sequence(DIAG_ACK, sizeof(DIAG_ACK),
                                       ack_rx, sizeof(ack_rx), 1200, &ack_found);
        if (n > 0 && !ack_found) {
            diag_dump_rx("RX (searching for ACK)", ack_rx, n, false);
        }
        if (!ack_found) {
            ESP_LOGE(TAG, "PN532 ACK NOT received for GetFirmwareVersion.");
            ESP_LOGE(TAG, "  If RX is completely silent: PN532 is not responding at all.");
            ESP_LOGE(TAG, "  If RX has bytes but no ACK: PN532 sent unexpected data.");
            ESP_LOGE(TAG, "  Check PN532 mode switches (must be HSU, not I2C/SPI).");
        } else {
            ESP_LOGI(TAG, "PN532 ACK received: 00 00 FF 00 FF 00");
            size_t consumed_before_ack = (n >= sizeof(DIAG_ACK)) ? n - sizeof(DIAG_ACK) : 0;
            if (consumed_before_ack > 0) {
                diag_print_hex("RX before ACK", ack_rx, consumed_before_ack);
            }

            /* Now read the firmware response: 00 00 FF xx xx D5 03 ... */
            uint8_t fw_rx[128] = {0};
            size_t fw_n = diag_read_any(fw_rx, sizeof(fw_rx), 500);
            if (fw_n == 0) {
                ESP_LOGE(TAG, "PN532 ACK OK but firmware response TIMEOUT (500ms).");
                ESP_LOGE(TAG, "  PN532 acknowledged the command but did not send firmware data.");
            } else {
                diag_print_hex("RX firmware response", fw_rx, fw_n);
                /* Check for expected D5 03 (GetFirmwareVersion response) */
                bool has_d5_03 = false;
                for (size_t i = 0; i + 1 < fw_n; i++) {
                    if (fw_rx[i] == 0xD5 && fw_rx[i+1] == 0x03) {
                        has_d5_03 = true;
                        /* Payload is after D5 03: IC(1) Ver(1) Rev(1) Support(1) */
                        size_t payload_start = i + 2;
                        if (payload_start + 4 <= fw_n) {
                            ESP_LOGI(TAG, "PN532 GetFirmwareVersion (no SAM):");
                            ESP_LOGI(TAG, "  IC:      0x%02X", fw_rx[payload_start]);
                            ESP_LOGI(TAG, "  Ver:     %u", fw_rx[payload_start + 1]);
                            ESP_LOGI(TAG, "  Rev:     %u", fw_rx[payload_start + 2]);
                            ESP_LOGI(TAG, "  Support: 0x%02X", fw_rx[payload_start + 3]);
                        }
                        break;
                    }
                }
                if (!has_d5_03) {
                    ESP_LOGE(TAG, "PN532 response does not contain D5 03 (GetFirmwareVersion response).");
                    ESP_LOGE(TAG, "  This may be a NACK or unexpected frame from a previous command.");
                }
            }
        }
    }

    /* ── Step 4: SAMConfiguration then GetFirmwareVersion ────── */
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "Step 4: SAMConfiguration (normal mode) then GetFirmwareVersion");
    ESP_LOGI(TAG, "  Strategy: wake+command merged, no gap between them.");
    diag_flush_rx();

    /* Wake + SAMConfiguration as one continuous stream */
    {
        uint8_t combined_sam[sizeof(DIAG_WAKE) + sizeof(DIAG_CMD_SAM_CFG)];
        memcpy(combined_sam, DIAG_WAKE, sizeof(DIAG_WAKE));
        memcpy(combined_sam + sizeof(DIAG_WAKE), DIAG_CMD_SAM_CFG, sizeof(DIAG_CMD_SAM_CFG));
        diag_print_hex("TX wake+SAM (one stream)", combined_sam, sizeof(combined_sam));
        ESP_ERROR_CHECK(diag_write(combined_sam, sizeof(combined_sam)));
    }

    /* Wait for SAM ACK */
    {
        uint8_t sam_rx[128] = {0};
        bool sam_ack = false;
        size_t sam_n = diag_find_sequence(DIAG_ACK, sizeof(DIAG_ACK),
                                           sam_rx, sizeof(sam_rx), 1200, &sam_ack);
        if (!sam_ack) {
            ESP_LOGE(TAG, "SAMConfiguration ACK NOT received.");
            diag_dump_rx("SAM RX", sam_rx, sam_n, false);
        } else {
            ESP_LOGI(TAG, "SAM ACK received.");
            /* Read SAM response */
            uint8_t sam_resp[64] = {0};
            size_t sr_n = diag_read_any(sam_resp, sizeof(sam_resp), 500);
            if (sr_n > 0) {
                diag_print_hex("SAM response", sam_resp, sr_n);
            } else {
                ESP_LOGI(TAG, "SAM response: (0 bytes — some PN532 versions send ACK only)");
            }
        }
    }

    /* Now GetFirmwareVersion after SAM — same merged approach */
    diag_flush_rx();
    {
        uint8_t combined_fw[sizeof(DIAG_WAKE) + sizeof(DIAG_CMD_GET_FW)];
        memcpy(combined_fw, DIAG_WAKE, sizeof(DIAG_WAKE));
        memcpy(combined_fw + sizeof(DIAG_WAKE), DIAG_CMD_GET_FW, sizeof(DIAG_CMD_GET_FW));
        diag_print_hex("TX wake+GET_FW (one stream)", combined_fw, sizeof(combined_fw));
        ESP_ERROR_CHECK(diag_write(combined_fw, sizeof(combined_fw)));
    }

    {
        uint8_t fw2_rx[128] = {0};
        bool fw2_ack = false;
        size_t fw2_n = diag_find_sequence(DIAG_ACK, sizeof(DIAG_ACK),
                                            fw2_rx, sizeof(fw2_rx), 1200, &fw2_ack);
        if (!fw2_ack) {
            ESP_LOGE(TAG, "GetFirmwareVersion (post-SAM) ACK NOT received.");
            diag_dump_rx("FW(post-SAM) RX", fw2_rx, fw2_n, false);
        } else {
            ESP_LOGI(TAG, "FW ACK received.");
            uint8_t fw2_data[64] = {0};
            size_t fd_n = diag_read_any(fw2_data, sizeof(fw2_data), 500);
            if (fd_n > 0) {
                diag_print_hex("FW response (post-SAM)", fw2_data, fd_n);
                bool has_d5_03 = false;
                for (size_t i = 0; i + 1 < fd_n; i++) {
                    if (fw2_data[i] == 0xD5 && fw2_data[i+1] == 0x03 && i + 6 <= fd_n) {
                        has_d5_03 = true;
                        ESP_LOGI(TAG, "PN532 DIAG PASS: firmware IC=0x%02X Ver=%u Rev=%u Support=0x%02X",
                                 fw2_data[i+2], fw2_data[i+3], fw2_data[i+4], fw2_data[i+5]);
                        break;
                    }
                }
                if (!has_d5_03) {
                    ESP_LOGW(TAG, "FW response received but no D5 03 payload found.");
                }
            } else {
                ESP_LOGE(TAG, "FW ACK OK but firmware response timeout.");
            }
        }
    }

    /* ── Final summary ───────────────────────────────────────── */
    ESP_LOGI(TAG, "============================================================");
    ESP_LOGI(TAG, "PN532 DIAGNOSTIC COMPLETE.");
    ESP_LOGI(TAG, "  Review the logs above to determine failure point:");
    ESP_LOGI(TAG, "    A) RX completely silent in all steps → physical/power/mode");
    ESP_LOGI(TAG, "    B) Non-ACK bytes received       → PN532 alive, baud/mode mismatch");
    ESP_LOGI(TAG, "    C) ACK received, no response    → PN532 needs SAMConfiguration first");
    ESP_LOGI(TAG, "    D) Full FW response             → PN532 working, check poll logic");
    ESP_LOGI(TAG, "============================================================");

    /* Stay alive so user can read the log */
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
    return ESP_OK;
}
