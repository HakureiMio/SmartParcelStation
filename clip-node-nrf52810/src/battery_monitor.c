#include "battery_monitor.h"

#include <zephyr/devicetree.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(battery_monitor, LOG_LEVEL_INF);

#define BATTERY_LOW_MV_MIN       2700
#define BATTERY_CRITICAL_MV_MIN  2400
#define BATTERY_DIVIDER_NUM      2
#define BATTERY_DIVIDER_DEN      1

static const struct adc_dt_spec battery_adc = ADC_DT_SPEC_GET_BY_IDX(DT_ALIAS(bat_adc), 0);
static const struct gpio_dt_spec divider_enable_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(bat_div_en), gpios);

static battery_state_t battery_state = BATTERY_STATE_OK;

static battery_state_t convert_mv_to_state(uint16_t millivolts)
{
    if (millivolts < BATTERY_CRITICAL_MV_MIN) {
        return BATTERY_STATE_CRITICAL;
    }
    if (millivolts < BATTERY_LOW_MV_MIN) {
        return BATTERY_STATE_LOW;
    }
    return BATTERY_STATE_OK;
}

static void set_divider_enabled(bool enabled)
{
    if (gpio_is_ready_dt(&divider_enable_gpio)) {
        (void)gpio_pin_set_dt(&divider_enable_gpio, enabled ? 1 : 0);
    }
}

void battery_monitor_init(void)
{
    if (!gpio_is_ready_dt(&divider_enable_gpio)) {
        LOG_ERR("battery divider GPIO is not ready");
    } else {
        (void)gpio_pin_configure_dt(&divider_enable_gpio, GPIO_OUTPUT_INACTIVE);
    }

    if (!adc_is_ready_dt(&battery_adc)) {
        LOG_ERR("battery ADC is not ready");
    } else {
        int err = adc_channel_setup_dt(&battery_adc);
        if (err) {
            LOG_ERR("battery ADC channel setup failed: %d", err);
        }
    }

    LOG_INF("battery monitor init on P0.02/AIN0, divider enable P0.20");
}

battery_state_t battery_monitor_sample_once_mv(uint16_t *out_mv)
{
    int16_t raw_sample = 0;
    int32_t millivolts = 0;
    int err;
    struct adc_sequence sequence = {
        .buffer = &raw_sample,
        .buffer_size = sizeof(raw_sample),
    };

    set_divider_enabled(true);
    k_sleep(K_MSEC(3));

    err = adc_sequence_init_dt(&battery_adc, &sequence);
    if (err == 0) {
        err = adc_read_dt(&battery_adc, &sequence);
    }

    set_divider_enabled(false);

    if (err) {
        LOG_ERR("battery ADC sample failed: %d", err);
        battery_state = BATTERY_STATE_CRITICAL;
        if (out_mv) {
            *out_mv = 0;
        }
        return battery_state;
    }

    millivolts = raw_sample;
    err = adc_raw_to_millivolts_dt(&battery_adc, &millivolts);
    if (err) {
        LOG_WRN("battery ADC mV conversion fallback, raw=%d err=%d", raw_sample, err);
        millivolts = 0;
    }

    millivolts = (millivolts * BATTERY_DIVIDER_NUM) / BATTERY_DIVIDER_DEN;
    if (millivolts < 0) {
        millivolts = 0;
    }
    if (millivolts > UINT16_MAX) {
        millivolts = UINT16_MAX;
    }

    battery_state = convert_mv_to_state((uint16_t)millivolts);

    if (out_mv) {
        *out_mv = (uint16_t)millivolts;
    }

    LOG_INF("battery sample: %u mV, state=%s",
            (uint16_t)millivolts,
            battery_monitor_state_to_string(battery_state));
    return battery_state;
}

battery_state_t battery_monitor_get_state(void)
{
    return battery_state;
}

const char *battery_monitor_state_to_string(battery_state_t state)
{
    switch (state) {
    case BATTERY_STATE_OK:
        return "OK";
    case BATTERY_STATE_LOW:
        return "LOW";
    case BATTERY_STATE_CRITICAL:
        return "CRITICAL";
    default:
        return "UNKNOWN";
    }
}
