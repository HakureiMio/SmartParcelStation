#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "clip_state.h"
#include "clip_protocol.h"
#include "ble_clip_service.h"
#include "led_rgb.h"
#include "buzzer.h"
#include "remove_sensor.h"
#include "battery_monitor.h"

LOG_MODULE_REGISTER(main_app, LOG_LEVEL_INF);

static void send_event_simple(uint8_t evt, const uint8_t *payload, uint8_t len)
{
    uint8_t frame[32];
    uint8_t frame_len = clip_protocol_build_event(evt, payload, len, frame, sizeof(frame));

    if (frame_len > 0) {
        ble_clip_service_send_event(frame, frame_len);
    }
}

static void handle_remove_change(bool removed)
{
    if (removed) {
        clip_state_set(CLIP_STATE_REMOVED);
        send_event_simple(CLIP_EVT_CLIP_REMOVED, NULL, 0);
    } else {
        clip_state_set(CLIP_STATE_CONFIRMED);
        send_event_simple(CLIP_EVT_CLIP_RETURNED, NULL, 0);
    }
}

static void handle_command_frame(const uint8_t *data, uint8_t len)
{
    clip_command_frame_t cmd = {0};
    if (!clip_protocol_parse_command(data, len, &cmd)) {
        LOG_WRN("invalid command frame");
        return;
    }

    LOG_INF("command recv: 0x%02x len=%u", cmd.cmd, cmd.len);

    switch (cmd.cmd) {
    case CLIP_CMD_ALERT_START:
        clip_state_set(CLIP_STATE_ALERTING);
        led_rgb_effect_finding();
        buzzer_play(BUZZER_PATTERN_ALERT);
        break;
    case CLIP_CMD_ALERT_STOP:
        clip_state_set(CLIP_STATE_AUTHORIZED);
        buzzer_stop();
        led_rgb_set_level((rgb_level_t){0, 0, 0});
        break;
    case CLIP_CMD_SET_COLOR:
        if (cmd.len >= 3) {
            led_rgb_set_level((rgb_level_t){cmd.payload[0], cmd.payload[1], cmd.payload[2]});
        }
        break;
    case CLIP_CMD_BEEP_SUCCESS:
        buzzer_play(BUZZER_PATTERN_SUCCESS);
        led_rgb_effect_success();
        break;
    case CLIP_CMD_BEEP_ERROR:
        buzzer_play(BUZZER_PATTERN_ERROR);
        led_rgb_effect_error();
        break;
    case CLIP_CMD_BATTERY_CHECK: {
        uint16_t mv = 0;
        battery_state_t s = battery_monitor_sample_once_mv(&mv);
        uint8_t p[2] = {(uint8_t)s, (uint8_t)(mv / 10)};
        send_event_simple(CLIP_EVT_BATTERY_STATE_CHANGED, p, sizeof(p));
        break;
    }
    case CLIP_CMD_SLEEP:
        /* 真实项目中可在此触发更深睡眠策略 */
        clip_state_set(CLIP_STATE_IDLE);
        break;
    default:
        clip_state_set(CLIP_STATE_EXCEPTION);
        break;
    }

    uint8_t ack[2] = {cmd.cmd, 0x00};
    send_event_simple(CLIP_EVT_COMMAND_ACK, ack, sizeof(ack));
}

int main(void)
{
    LOG_INF("clip node boot");

    clip_state_init();
    led_rgb_init();
    buzzer_init();
    remove_sensor_init(handle_remove_change);
    battery_monitor_init();

    if (ble_clip_service_init(handle_command_frame) != 0) {
        clip_state_set(CLIP_STATE_EXCEPTION);
    }

    send_event_simple(CLIP_EVT_BOOT, NULL, 0);

    while (1) {
        /* 骨架策略：周期轮询传感器，后续可改为 GPIO 中断 + workqueue */
        remove_sensor_poll_once();
        k_sleep(K_MSEC(200));
    }

    return 0;
}
