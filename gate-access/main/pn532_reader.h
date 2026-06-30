#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "esp_err.h"

esp_err_t pn532_reader_init(void);
esp_err_t pn532_reader_uart_loopback_test(void);
esp_err_t pn532_reader_poll_uid(char *uid_hex, size_t uid_hex_size, bool *card_present);
