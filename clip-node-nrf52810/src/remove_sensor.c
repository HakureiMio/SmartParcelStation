#include "remove_sensor.h"

#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(remove_sensor, LOG_LEVEL_INF);

#define DEBOUNCE_CONFIRM_COUNT 3

static const struct gpio_dt_spec remove_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(remove_sense), gpios);

static remove_sensor_cb_t sensor_callback;
static bool stable_removed;
static uint8_t debounce_count;

static bool read_raw_removed_level(void)
{
    int value;

    if (!gpio_is_ready_dt(&remove_gpio)) {
        return stable_removed;
    }

    value = gpio_pin_get_dt(&remove_gpio);
    if (value < 0) {
        LOG_WRN("remove sensor read failed: %d", value);
        return stable_removed;
    }

    return value != 0;
}

void remove_sensor_init(remove_sensor_cb_t cb)
{
    sensor_callback = cb;
    stable_removed = false;
    debounce_count = 0;

    if (!gpio_is_ready_dt(&remove_gpio)) {
        LOG_ERR("remove sensor GPIO is not ready");
        return;
    }

    (void)gpio_pin_configure_dt(&remove_gpio, GPIO_INPUT);
    stable_removed = read_raw_removed_level();
    LOG_INF("remove sensor init on P0.19, removed=%d", (int)stable_removed);
}

void remove_sensor_poll_once(void)
{
    bool raw_removed = read_raw_removed_level();

    if (raw_removed == stable_removed) {
        debounce_count = 0;
        return;
    }

    debounce_count++;
    if (debounce_count < DEBOUNCE_CONFIRM_COUNT) {
        return;
    }

    stable_removed = raw_removed;
    debounce_count = 0;
    LOG_INF("remove sensor stable change: removed=%d", (int)stable_removed);

    if (sensor_callback) {
        sensor_callback(stable_removed);
    }
}

bool remove_sensor_is_removed(void)
{
    return stable_removed;
}
