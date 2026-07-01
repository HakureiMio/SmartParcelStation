#pragma once

#include <stdint.h>

#include "esp_err.h"
#include "gateway_client.h"

esp_err_t display_ui_init(void);
esp_err_t display_ui_fill_color(uint16_t rgb565, const char *name);
esp_err_t display_ui_show_card_id_numeric(const char *uid_hex);
esp_err_t display_ui_show_qr(const char *payload);
void display_ui_show_gate_state(const char *state, const gateway_access_result_t *result);
void display_ui_show_booting(void);
void display_ui_show_network_status(const char *text);
void display_ui_show_pn532_status(const char *text);
void display_ui_show_wait_card(void);
void display_ui_show_uid(const char *uid);
void display_ui_show_uploading(void);
void display_ui_show_access_result(const gateway_access_result_t *result);
void display_ui_show_error(const char *title, const char *detail);
