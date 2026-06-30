#pragma once

#include "esp_err.h"

/*
 * pn532_diag — standalone PN532 HSU/UART diagnostic.
 *
 * Runs step-by-step raw-UART tests designed to isolate:
 *   - ESP32-P4 UART2 TX/RX hardware path
 *   - PN532 power / wiring / HSU mode
 *   - PN532 ACK / response presence and correctness
 *
 * This is a blocking diagnostic; it does not depend on display,
 * touch, WiFi, or any other subsystem.
 */
esp_err_t pn532_uart_diag_run(void);
