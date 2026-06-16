#pragma once

#include "esp_err.h"

esp_err_t wifi_client_start(void);
esp_err_t wifi_client_wait_connected(void);
