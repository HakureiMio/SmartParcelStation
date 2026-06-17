#pragma once

#include <stddef.h>

#include "esp_err.h"

esp_err_t network_client_start(void);
esp_err_t network_client_wait_ready(void);
esp_err_t network_client_http_post_json(
    const char *host,
    int port,
    const char *path,
    const char *json,
    char *response,
    size_t response_size,
    int *http_status);
