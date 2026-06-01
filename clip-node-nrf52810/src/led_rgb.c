#include "led_rgb.h"

#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(led_rgb, LOG_LEVEL_INF);

#define RGB_LEVEL_MAX 6

/* 7 档亮度映射到 PWM 占空比百分比（0~100） */
static const uint8_t level_to_duty[7] = {0, 2, 5, 10, 20, 40, 70};

void led_rgb_init(void)
{
    LOG_INF("RGB init (PWM pins TODO)");
}

void led_rgb_set_level(rgb_level_t level)
{
    if (level.r > RGB_LEVEL_MAX) level.r = RGB_LEVEL_MAX;
    if (level.g > RGB_LEVEL_MAX) level.g = RGB_LEVEL_MAX;
    if (level.b > RGB_LEVEL_MAX) level.b = RGB_LEVEL_MAX;

    LOG_INF("RGB set R%d(%d%%) G%d(%d%%) B%d(%d%%)",
            level.r, level_to_duty[level.r],
            level.g, level_to_duty[level.g],
            level.b, level_to_duty[level.b]);
}

void led_rgb_blink(rgb_level_t level, uint32_t on_ms, uint32_t off_ms, uint8_t times)
{
    /* 当前骨架仅记录行为，后续替换为 k_work_delayable + PWM 实际输出 */
    LOG_INF("RGB blink r=%u g=%u b=%u on=%u off=%u times=%u",
            level.r, level.g, level.b, on_ms, off_ms, times);
}

void led_rgb_effect_success(void)
{
    led_rgb_blink((rgb_level_t){.r = 0, .g = 5, .b = 0}, 100, 80, 2);
}

void led_rgb_effect_error(void)
{
    led_rgb_blink((rgb_level_t){.r = 6, .g = 0, .b = 0}, 120, 80, 3);
}

void led_rgb_effect_finding(void)
{
    led_rgb_blink((rgb_level_t){.r = 0, .g = 0, .b = 5}, 150, 350, 20);
}

void led_rgb_effect_exception(void)
{
    led_rgb_blink((rgb_level_t){.r = 6, .g = 2, .b = 0}, 200, 200, 10);
}
