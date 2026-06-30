#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

esp_err_t touch_test_init(void);
esp_err_t touch_test_read(bool *pressed, uint16_t *x, uint16_t *y);
