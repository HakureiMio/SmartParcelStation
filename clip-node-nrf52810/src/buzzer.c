#include "buzzer.h"

#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(buzzer, LOG_LEVEL_INF);

#define BUZZER_MAX_MS 10000U

void buzzer_init(void)
{
    LOG_INF("buzzer init (GPIO pin TODO)");
}

void buzzer_play(buzzer_pattern_t pattern)
{
    /* 关键约束：所有蜂鸣模式都应有最大持续时间限制，防止异常耗电 */
    switch (pattern) {
    case BUZZER_PATTERN_SUCCESS:
        LOG_INF("buzzer success: 2 short beeps");
        break;
    case BUZZER_PATTERN_ERROR:
        LOG_INF("buzzer error: 3 short beeps");
        break;
    case BUZZER_PATTERN_ALERT:
        LOG_INF("buzzer alert: periodic short beeps");
        break;
    case BUZZER_PATTERN_CRITICAL:
        LOG_INF("buzzer critical: 1 long beep");
        break;
    default:
        return;
    }

    LOG_INF("buzzer max duration guard: %u ms", BUZZER_MAX_MS);
}

void buzzer_stop(void)
{
    LOG_INF("buzzer stop");
}
