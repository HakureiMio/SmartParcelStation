#include "battery_monitor.h"

#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(battery_monitor, LOG_LEVEL_INF);

/* 以下阈值可根据 CR2450 放电曲线和实测负载进行修正 */
#define BATTERY_HIGH_MV_MIN     2900
#define BATTERY_MEDIUM_MV_MIN   2700
#define BATTERY_LOW_MV_MIN      2500

static battery_state_t g_state = BATTERY_STATE_HIGH;

static uint16_t adc_sample_battery_mv(void)
{
    /* 骨架：后续对接 ADC 驱动与分压换算 */
    return 3000;
}

static battery_state_t convert_mv_to_state(uint16_t mv)
{
    if (mv >= BATTERY_HIGH_MV_MIN) {
        return BATTERY_STATE_HIGH;
    }
    if (mv >= BATTERY_MEDIUM_MV_MIN) {
        return BATTERY_STATE_MEDIUM;
    }
    if (mv >= BATTERY_LOW_MV_MIN) {
        return BATTERY_STATE_LOW;
    }
    return BATTERY_STATE_CRITICAL;
}

void battery_monitor_init(void)
{
    LOG_INF("battery monitor init (ADC pin TODO)");
}

battery_state_t battery_monitor_sample_once_mv(uint16_t *out_mv)
{
    uint16_t mv = adc_sample_battery_mv();
    g_state = convert_mv_to_state(mv);

    if (out_mv) {
        *out_mv = mv;
    }

    LOG_INF("battery sample: %u mV, state=%d", mv, (int)g_state);
    return g_state;
}

battery_state_t battery_monitor_get_state(void)
{
    return g_state;
}
