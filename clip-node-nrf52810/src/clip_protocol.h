#ifndef CLIP_PROTOCOL_H
#define CLIP_PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CLIP_PROTO_MAX_PAYLOAD_LEN 16
#define CLIP_PROTO_FRAME_HEADER    0xA5

typedef enum {
    CLIP_CMD_ALERT_START  = 0x01,
    CLIP_CMD_ALERT_STOP   = 0x02,
    CLIP_CMD_SET_COLOR    = 0x03,
    CLIP_CMD_BEEP_SUCCESS = 0x04,
    CLIP_CMD_BEEP_ERROR   = 0x05,
    CLIP_CMD_BATTERY_CHECK = 0x06,
    CLIP_CMD_SLEEP        = 0x07,
} clip_command_t;

typedef enum {
    CLIP_EVT_BOOT                = 0x81,
    CLIP_EVT_COMMAND_ACK         = 0x82,
    CLIP_EVT_CLIP_REMOVED        = 0x83,
    CLIP_EVT_CLIP_RETURNED       = 0x84,
    CLIP_EVT_BATTERY_LOW         = 0x85,
    CLIP_EVT_BATTERY_STATE_CHANGED = 0x86,
} clip_event_t;

typedef struct {
    uint8_t cmd;
    uint8_t len;
    uint8_t payload[CLIP_PROTO_MAX_PAYLOAD_LEN];
} clip_command_frame_t;

bool clip_protocol_parse_command(const uint8_t *data, uint8_t size, clip_command_frame_t *out_cmd);
uint8_t clip_protocol_build_event(uint8_t evt, const uint8_t *payload, uint8_t len, uint8_t *out_buf, uint8_t out_size);

#ifdef __cplusplus
}
#endif

#endif
