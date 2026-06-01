#include "clip_protocol.h"

static uint8_t protocol_xor_checksum(const uint8_t *data, uint8_t len)
{
    uint8_t v = 0;

    for (uint8_t i = 0; i < len; i++) {
        v ^= data[i];
    }

    return v;
}

bool clip_protocol_parse_command(const uint8_t *data, uint8_t size, clip_command_frame_t *out_cmd)
{
    if (!data || !out_cmd || size < 4) {
        return false;
    }

    if (data[0] != CLIP_PROTO_FRAME_HEADER) {
        return false;
    }

    uint8_t payload_len = data[2];
    if (payload_len > CLIP_PROTO_MAX_PAYLOAD_LEN) {
        return false;
    }

    uint8_t expected_size = (uint8_t)(4 + payload_len);
    if (size != expected_size) {
        return false;
    }

    uint8_t checksum = protocol_xor_checksum(data, (uint8_t)(3 + payload_len));
    if (checksum != data[3 + payload_len]) {
        return false;
    }

    out_cmd->cmd = data[1];
    out_cmd->len = payload_len;
    for (uint8_t i = 0; i < payload_len; i++) {
        out_cmd->payload[i] = data[3 + i];
    }

    return true;
}

uint8_t clip_protocol_build_event(uint8_t evt, const uint8_t *payload, uint8_t len, uint8_t *out_buf, uint8_t out_size)
{
    if (!out_buf || len > CLIP_PROTO_MAX_PAYLOAD_LEN) {
        return 0;
    }

    uint8_t total = (uint8_t)(4 + len);
    if (out_size < total) {
        return 0;
    }

    out_buf[0] = CLIP_PROTO_FRAME_HEADER;
    out_buf[1] = evt;
    out_buf[2] = len;

    for (uint8_t i = 0; i < len; i++) {
        out_buf[3 + i] = payload ? payload[i] : 0;
    }

    out_buf[3 + len] = protocol_xor_checksum(out_buf, (uint8_t)(3 + len));
    return total;
}
