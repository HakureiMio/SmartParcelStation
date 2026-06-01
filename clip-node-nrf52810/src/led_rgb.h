#ifndef LED_RGB_H
#define LED_RGB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t r;
    uint8_t g;
    uint8_t b;
} rgb_level_t;

void led_rgb_init(void);
void led_rgb_set_level(rgb_level_t level);
void led_rgb_blink(rgb_level_t level, uint32_t on_ms, uint32_t off_ms, uint8_t times);
void led_rgb_effect_success(void);
void led_rgb_effect_error(void);
void led_rgb_effect_finding(void);
void led_rgb_effect_exception(void);

#ifdef __cplusplus
}
#endif

#endif
