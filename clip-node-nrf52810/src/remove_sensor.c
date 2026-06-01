#include "remove_sensor.h"

#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(remove_sensor, LOG_LEVEL_INF);

#define DEBOUNCE_CONFIRM_COUNT 3

static remove_sensor_cb_t g_cb;
static bool g_stable_removed;
static uint8_t g_debounce_cnt;

/* 读取原始 GPIO 电平（骨架阶段返回固定值，后续接入真实 GPIO） */
static bool read_raw_removed_level(void)
{
    return false;
}

void remove_sensor_init(remove_sensor_cb_t cb)
{
    g_cb = cb;
    g_stable_removed = false;
    g_debounce_cnt = 0;
    LOG_INF("remove sensor init (GPIO pin TODO)");
}

void remove_sensor_poll_once(void)
{
    bool raw = read_raw_removed_level();

    if (raw == g_stable_removed) {
        g_debounce_cnt = 0;
        return;
    }

    g_debounce_cnt++;
    if (g_debounce_cnt < DEBOUNCE_CONFIRM_COUNT) {
        return;
    }

    g_stable_removed = raw;
    g_debounce_cnt = 0;
    LOG_INF("remove sensor stable change: removed=%d", (int)g_stable_removed);

    if (g_cb) {
        g_cb(g_stable_removed);
    }
}
