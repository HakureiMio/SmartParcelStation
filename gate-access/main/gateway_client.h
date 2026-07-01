#pragma once

#include <stdbool.h>

#include "esp_err.h"

typedef struct {
    bool request_ok;
    bool access_granted;
    int http_status;
    int pickup_count;
    char user_id[32];
    char pickup_session_id[80];
    char display_text[160];
    char warnings[256];
    char status[24];
    char reason[96];
    char shelves[160];
    char parcel_codes[256];
    char session_color[32];
} gateway_access_result_t;

typedef struct {
    bool request_ok;
    int http_status;
    char session_id[128];
    char qr_payload[1024];
} gateway_qr_session_t;

esp_err_t gateway_client_post_access_card(const char *uid_hex, gateway_access_result_t *result);
esp_err_t gateway_client_post_access_credential(const char *credential_type,
                                                const char *credential_value,
                                                gateway_access_result_t *result);
esp_err_t gateway_client_fetch_qr_session(gateway_qr_session_t *result);
esp_err_t gateway_client_poll_auth_result(gateway_access_result_t *result);
