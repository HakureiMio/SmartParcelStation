#pragma once

#include <stddef.h>

#include "esp_err.h"

esp_err_t esp8266_at_init(void);
esp_err_t esp8266_at_join_ap(const char *ssid, const char *password);
esp_err_t esp8266_at_tcp_transact(
    const char *host,
    int port,
    const char *request,
    size_t request_len,
    char *response,
    size_t response_size);
