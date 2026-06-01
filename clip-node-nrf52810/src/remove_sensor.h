#ifndef REMOVE_SENSOR_H
#define REMOVE_SENSOR_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*remove_sensor_cb_t)(bool removed);

void remove_sensor_init(remove_sensor_cb_t cb);
void remove_sensor_poll_once(void);

#ifdef __cplusplus
}
#endif

#endif
