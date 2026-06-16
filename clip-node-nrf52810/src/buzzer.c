#include "buzzer.h"

#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/util.h>

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
        return;
    }

    (void)gpio_pin_configure_dt(&buzzer_gpio, GPIO_OUTPUT_ACTIVE);
}

void buzzer_play(buzzer_pattern_t pattern)
{
    ARG_UNUSED(pattern);

    set_buzzer_active();
}

void buzzer_stop(void)
{
    set_buzzer_active();
}
