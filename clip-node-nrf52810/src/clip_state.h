#ifndef CLIP_STATE_H
#define CLIP_STATE_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CLIP_STATE_IDLE = 0,
    CLIP_STATE_BOUND,
    CLIP_STATE_AUTHORIZED,
    CLIP_STATE_ALERTING,
    CLIP_STATE_REMOVED,
    CLIP_STATE_CONFIRMED,
    CLIP_STATE_LOW_BATTERY,
    CLIP_STATE_EXCEPTION,
} clip_state_t;

void clip_state_init(void);
clip_state_t clip_state_get(void);
void clip_state_set(clip_state_t new_state);
const char *clip_state_to_string(clip_state_t state);

#ifdef __cplusplus
}
#endif

#endif
