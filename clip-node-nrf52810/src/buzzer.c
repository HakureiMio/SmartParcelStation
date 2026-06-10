#include "buzzer.h"

#include <zephyr/devicetree.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(buzzer, LOG_LEVEL_INF);

#define BUZZER_ALERT_ON_MS     120U
#define BUZZER_ALERT_OFF_MS    880U
#define BUZZER_SHORT_ON_MS     120U
#define BUZZER_SHORT_OFF_MS    80U
#define BUZZER_CRITICAL_ON_MS  600U
#define BUZZER_DUTY_DIVIDER    2U

static const struct pwm_dt_spec buzzer_pwm = PWM_DT_SPEC_GET(DT_ALIAS(buzzer_pwm));

static struct k_work_delayable buzzer_work;
static uint32_t buzzer_on_ms;
static uint32_t buzzer_off_ms;
static uint8_t buzzer_pulses_left;
static bool buzzer_is_on;
static bool buzzer_repeat;

static void set_buzzer(bool enabled)
{
    if (pwm_is_ready_dt(&buzzer_pwm)) {
        uint32_t pulse = enabled ? (buzzer_pwm.period / BUZZER_DUTY_DIVIDER) : 0U;
        (void)pwm_set_dt(&buzzer_pwm, buzzer_pwm.period, pulse);
    }

    buzzer_is_on = enabled;
}

static void buzzer_work_handler(struct k_work *work)
{
    ARG_UNUSED(work);

    if (buzzer_is_on) {
        set_buzzer(false);

        if (!buzzer_repeat && buzzer_pulses_left > 0) {
            buzzer_pulses_left--;
            if (buzzer_pulses_left == 0) {
                return;
            }
        }

        k_work_schedule(&buzzer_work, K_MSEC(buzzer_off_ms));
        return;
    }

    set_buzzer(true);
    k_work_schedule(&buzzer_work, K_MSEC(buzzer_on_ms));
}

void buzzer_init(void)
{
    k_work_init_delayable(&buzzer_work, buzzer_work_handler);

    if (!pwm_is_ready_dt(&buzzer_pwm)) {
        LOG_ERR("passive buzzer PWM is not ready");
        return;
    }

    set_buzzer(false);
    LOG_INF("active-low passive buzzer PWM init on P0.16");
}

void buzzer_play(buzzer_pattern_t pattern)
{
    k_work_cancel_delayable(&buzzer_work);
    set_buzzer(false);
    buzzer_repeat = false;

    switch (pattern) {
    case BUZZER_PATTERN_SUCCESS:
        buzzer_on_ms = BUZZER_SHORT_ON_MS;
        buzzer_off_ms = BUZZER_SHORT_OFF_MS;
        buzzer_pulses_left = 2;
        break;
    case BUZZER_PATTERN_ERROR:
        buzzer_on_ms = BUZZER_SHORT_ON_MS;
        buzzer_off_ms = BUZZER_SHORT_OFF_MS;
        buzzer_pulses_left = 3;
        break;
    case BUZZER_PATTERN_ALERT:
        buzzer_on_ms = BUZZER_ALERT_ON_MS;
        buzzer_off_ms = BUZZER_ALERT_OFF_MS;
        buzzer_pulses_left = 0;
        buzzer_repeat = true;
        break;
    case BUZZER_PATTERN_CRITICAL:
        buzzer_on_ms = BUZZER_CRITICAL_ON_MS;
        buzzer_off_ms = BUZZER_SHORT_OFF_MS;
        buzzer_pulses_left = 1;
        break;
    default:
        return;
    }

    k_work_schedule(&buzzer_work, K_NO_WAIT);
    LOG_INF("passive buzzer play pattern=%d", (int)pattern);
}

void buzzer_stop(void)
{
    k_work_cancel_delayable(&buzzer_work);
    set_buzzer(false);
    LOG_INF("passive buzzer stop");
}
