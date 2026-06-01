#ifndef BATTERY_MONITOR_H
#define BATTERY_MONITOR_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BATTERY_STATE_HIGH = 0,
    BATTERY_STATE_MEDIUM,
    BATTERY_STATE_LOW,
    BATTERY_STATE_CRITICAL,
} battery_state_t;

void battery_monitor_init(void);
battery_state_t battery_monitor_sample_once_mv(uint16_t *out_mv);
battery_state_t battery_monitor_get_state(void);

#ifdef __cplusplus
}
#endif

#endif
