#include "buzzer.h"

#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(buzzer, LOG_LEVEL_INF);

static const struct gpio_dt_spec buzzer_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(buzzer_gpio), gpios);

static void set_buzzer_active(void)
{
    if (gpio_is_ready_dt(&buzzer_gpio)) {
        (void)gpio_pin_set_dt(&buzzer_gpio, 1);
    }
}

void buzzer_init(void)
{
    if (!gpio_is_ready_dt(&buzzer_gpio)) {
        LOG_ERR("buzzer GPIO is not ready");
        return;
    }

    (void)gpio_pin_configure_dt(&buzzer_gpio, GPIO_OUTPUT_ACTIVE);
    LOG_INF("buzzer test mode active-high output enabled on P0.16");
}

void buzzer_play(buzzer_pattern_t pattern)
{
    ARG_UNUSED(pattern);

    set_buzzer_active();
    LOG_INF("buzzer test mode keeps active-high output enabled");
}

void buzzer_stop(void)
{
    set_buzzer_active();
    LOG_INF("buzzer test mode ignores stop and keeps output enabled");
}
