#include "led_rgb.h"

#include <zephyr/devicetree.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(led_rgb, LOG_LEVEL_INF);

#define RGB_LEVEL_MAX 6
#define RGB_RAINBOW_STEP_MS 300U

static const struct pwm_dt_spec red_pwm = PWM_DT_SPEC_GET(DT_ALIAS(led_red_pwm));
static const struct pwm_dt_spec green_pwm = PWM_DT_SPEC_GET(DT_ALIAS(led_green_pwm));
static const struct pwm_dt_spec blue_pwm = PWM_DT_SPEC_GET(DT_ALIAS(led_blue_pwm));

static const uint8_t level_to_duty[7] = {0, 2, 5, 10, 20, 40, 70};
static const rgb_level_t rainbow_levels[] = {
    {.r = 6, .g = 0, .b = 0},
    {.r = 6, .g = 2, .b = 0},
    {.r = 5, .g = 5, .b = 0},
    {.r = 0, .g = 6, .b = 0},
    {.r = 0, .g = 4, .b = 4},
    {.r = 0, .g = 0, .b = 6},
    {.r = 3, .g = 0, .b = 5},
    {.r = 5, .g = 0, .b = 3},
};

static struct k_work_delayable blink_work;
static rgb_level_t blink_level;
static uint32_t blink_on_ms;
static uint32_t blink_off_ms;
static uint8_t blink_cycles_left;
static bool blink_is_on;
static bool rainbow_enabled;
static uint8_t rainbow_index;

static int set_one_pwm(const struct pwm_dt_spec *pwm, uint8_t level)
{
    uint32_t pulse_ns;

    if (!pwm_is_ready_dt(pwm)) {
        return -ENODEV;
    }

    pulse_ns = (pwm->period * level_to_duty[level]) / 100U;
    return pwm_set_dt(pwm, pwm->period, pulse_ns);
}

static void apply_level(rgb_level_t level)
{
    if (level.r > RGB_LEVEL_MAX) {
        level.r = RGB_LEVEL_MAX;
    }
    if (level.g > RGB_LEVEL_MAX) {
        level.g = RGB_LEVEL_MAX;
    }
    if (level.b > RGB_LEVEL_MAX) {
        level.b = RGB_LEVEL_MAX;
    }

    (void)set_one_pwm(&red_pwm, level.r);
    (void)set_one_pwm(&green_pwm, level.g);
    (void)set_one_pwm(&blue_pwm, level.b);

    LOG_DBG("RGB set R%d(%d%%) G%d(%d%%) B%d(%d%%)",
            level.r, level_to_duty[level.r],
            level.g, level_to_duty[level.g],
            level.b, level_to_duty[level.b]);
}

static void start_rainbow(void)
{
    rainbow_enabled = true;
    blink_is_on = false;
    k_work_schedule(&blink_work, K_NO_WAIT);
}

static void blink_work_handler(struct k_work *work)
{
    ARG_UNUSED(work);

    if (rainbow_enabled) {
        apply_level(rainbow_levels[rainbow_index]);
        rainbow_index++;
        if (rainbow_index >= ARRAY_SIZE(rainbow_levels)) {
            rainbow_index = 0;
        }
        k_work_schedule(&blink_work, K_MSEC(RGB_RAINBOW_STEP_MS));
        return;
    }

    if (blink_is_on) {
        apply_level((rgb_level_t){0, 0, 0});
        blink_is_on = false;

        if (blink_cycles_left > 0) {
            blink_cycles_left--;
            if (blink_cycles_left == 0) {
                return;
            }
        }

        k_work_schedule(&blink_work, K_MSEC(blink_off_ms));
        return;
    }

    apply_level(blink_level);
    blink_is_on = true;
    k_work_schedule(&blink_work, K_MSEC(blink_on_ms));
}

void led_rgb_init(void)
{
    k_work_init_delayable(&blink_work, blink_work_handler);
    start_rainbow();
    LOG_INF("RGB init on P0.11/P0.12/P0.15, test rainbow enabled");
}

void led_rgb_set_level(rgb_level_t level)
{
    k_work_cancel_delayable(&blink_work);
    rainbow_enabled = false;
    blink_is_on = false;
    apply_level(level);
}

void led_rgb_off(void)
{
    k_work_cancel_delayable(&blink_work);
    start_rainbow();
    LOG_INF("RGB test mode keeps rainbow enabled");
}

void led_rgb_blink(rgb_level_t level, uint32_t on_ms, uint32_t off_ms, uint8_t times)
{
    k_work_cancel_delayable(&blink_work);
    rainbow_enabled = false;

    blink_level = level;
    blink_on_ms = on_ms;
    blink_off_ms = off_ms;
    blink_cycles_left = times;
    blink_is_on = false;

    k_work_schedule(&blink_work, K_NO_WAIT);
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
    led_rgb_blink((rgb_level_t){.r = 0, .g = 0, .b = 5}, 150, 350, 0);
}

void led_rgb_effect_exception(void)
{
    led_rgb_blink((rgb_level_t){.r = 6, .g = 2, .b = 0}, 200, 200, 10);
}
