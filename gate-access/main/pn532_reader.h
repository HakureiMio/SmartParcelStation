#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "esp_err.h"

#define PN532_CREDENTIAL_TYPE_MAX   16
#define PN532_CREDENTIAL_VALUE_MAX  96
#define PN532_UID_HEX_MAX           32

typedef struct {
    bool present;
    bool iso_dep;
    bool hce;
    char credential_type[PN532_CREDENTIAL_TYPE_MAX];
    char credential_value[PN532_CREDENTIAL_VALUE_MAX];
    char uid_hex[PN532_UID_HEX_MAX];
} pn532_credential_t;

esp_err_t pn532_reader_init(void);
esp_err_t pn532_reader_uart_loopback_test(void);
esp_err_t pn532_reader_poll_uid(char *uid_hex, size_t uid_hex_size, bool *card_present);
esp_err_t pn532_reader_poll_credential(pn532_credential_t *credential);
