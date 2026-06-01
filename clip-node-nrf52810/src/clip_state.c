#include "clip_state.h"

#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(clip_state, LOG_LEVEL_INF);

static clip_state_t g_state = CLIP_STATE_IDLE;

void clip_state_init(void)
{
    g_state = CLIP_STATE_IDLE;
    LOG_INF("state init: %s", clip_state_to_string(g_state));
}

clip_state_t clip_state_get(void)
{
    return g_state;
}

void clip_state_set(clip_state_t new_state)
{
    if (new_state == g_state) {
        return;
    }

    LOG_INF("state change: %s -> %s",
            clip_state_to_string(g_state),
            clip_state_to_string(new_state));
    g_state = new_state;
}

const char *clip_state_to_string(clip_state_t state)
{
    switch (state) {
    case CLIP_STATE_IDLE: return "idle";
    case CLIP_STATE_BOUND: return "bound";
    case CLIP_STATE_AUTHORIZED: return "authorized";
    case CLIP_STATE_ALERTING: return "alerting";
    case CLIP_STATE_REMOVED: return "removed";
    case CLIP_STATE_CONFIRMED: return "confirmed";
    case CLIP_STATE_LOW_BATTERY: return "low_battery";
    case CLIP_STATE_EXCEPTION: return "exception";
    default: return "unknown";
    }
}
