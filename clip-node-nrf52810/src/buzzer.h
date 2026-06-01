#ifndef BUZZER_H
#define BUZZER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BUZZER_PATTERN_SUCCESS = 0,
    BUZZER_PATTERN_ERROR,
    BUZZER_PATTERN_ALERT,
    BUZZER_PATTERN_CRITICAL,
} buzzer_pattern_t;

void buzzer_init(void);
void buzzer_play(buzzer_pattern_t pattern);
void buzzer_stop(void);

#ifdef __cplusplus
}
#endif

#endif
