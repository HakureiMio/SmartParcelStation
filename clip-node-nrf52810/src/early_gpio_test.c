#include <zephyr/init.h>
#include <hal/nrf_gpio.h>
#include <hal/nrf_power.h>

#define TEST_RGB_R_PIN 11
#define TEST_RGB_G_PIN 12
#define TEST_RGB_B_PIN 15
#define POWER_ON_RESET_MAGIC 0xA5U

static int early_gpio_test_init(void)
{
    uint32_t reset_marker = nrf_power_gpregret_get(NRF_POWER, 0U);

    if (reset_marker != POWER_ON_RESET_MAGIC) {
        nrf_power_gpregret_set(NRF_POWER, 0U, POWER_ON_RESET_MAGIC);
        NVIC_SystemReset();
    }

    nrf_power_gpregret_set(NRF_POWER, 0U, 0U);

    nrf_gpio_cfg_output(TEST_RGB_R_PIN);
    nrf_gpio_cfg_output(TEST_RGB_G_PIN);
    nrf_gpio_cfg_output(TEST_RGB_B_PIN);
    nrf_gpio_pin_clear(TEST_RGB_R_PIN);
    nrf_gpio_pin_clear(TEST_RGB_G_PIN);
    nrf_gpio_pin_clear(TEST_RGB_B_PIN);

    return 0;
}

SYS_INIT(early_gpio_test_init, PRE_KERNEL_1, 0);
