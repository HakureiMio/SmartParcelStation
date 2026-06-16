#pragma once

#include <stdbool.h>

#include "esp_err.h"

typedef struct {
    bool request_ok;
    bool access_granted;
    int http_status;
    int pickup_count;
    char pickup_session_id[80];
    char display_text[160];
    char warnings[256];
} gateway_access_result_t;

esp_err_t gateway_client_post_access_card(const char *uid_hex, gateway_access_result_t *result);
