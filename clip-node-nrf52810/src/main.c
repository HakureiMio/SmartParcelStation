#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "battery_monitor.h"
#include "ble_clip_service.h"
#include "buzzer.h"
#include "clip_protocol.h"
#include "clip_state.h"
#include "led_rgb.h"
#include "remove_sensor.h"

LOG_MODULE_REGISTER(main_app, LOG_LEVEL_INF);

#define ALERT_MAX_DURATION_MS 30000U
#define BINDING_TOKEN_MAX_LEN 8U

typedef struct {
    uint32_t tag_id;
    uint8_t binding_token[BINDING_TOKEN_MAX_LEN];
    uint8_t binding_token_len;
    uint8_t device_config;
    clip_state_t last_state;
    bool bound;
} clip_runtime_store_t;

static clip_runtime_store_t runtime_store = {
    .tag_id = 0x00000001,
};

static struct k_work_delayable alert_timeout_work;

static void send_event_simple(uint8_t event_id, const uint8_t *payload, uint8_t len)
{
    uint8_t frame[32];
    uint8_t frame_len = clip_protocol_build_event(event_id, payload, len, frame, sizeof(frame));

    if (frame_len > 0) {
        ble_clip_service_send_event(frame, frame_len);
    }
}

static clip_state_t default_non_alert_state(void)
{
    return runtime_store.bound ? CLIP_STATE_BOUND : CLIP_STATE_IDLE;
}

static void set_state(clip_state_t new_state)
{
    clip_state_set(new_state);
    runtime_store.last_state = new_state;
}

static void stop_alert_outputs(void)
{
    k_work_cancel_delayable(&alert_timeout_work);
    buzzer_stop();
    led_rgb_off();
}

static void stop_alert_and_restore_state(void)
{
    stop_alert_outputs();
    set_state(default_non_alert_state());
}

static void alert_timeout_handler(struct k_work *work)
{
    ARG_UNUSED(work);
    LOG_INF("WAKE_TAG timeout reached, stopping alert");
    stop_alert_and_restore_state();
}

static void start_finding_alert(void)
{
    set_state(CLIP_STATE_ALERTING);
    led_rgb_effect_finding();
    buzzer_play(BUZZER_PATTERN_ALERT);
    k_work_reschedule(&alert_timeout_work, K_MSEC(ALERT_MAX_DURATION_MS));
}

static void send_status_report(void)
{
    uint16_t millivolts = 0;
    battery_state_t battery_state = battery_monitor_sample_once_mv(&millivolts);
    uint8_t battery_payload[3] = {
        (uint8_t)battery_state,
        (uint8_t)(millivolts & 0xFFU),
        (uint8_t)(millivolts >> 8),
    };

    if (battery_state != BATTERY_STATE_OK) {
        set_state(CLIP_STATE_LOW_BATTERY);
        send_event_simple(CLIP_EVT_BATTERY_LOW, battery_payload, sizeof(battery_payload));
    }

    uint8_t payload[8] = {
        (uint8_t)clip_state_get(),
        (uint8_t)battery_state,
        runtime_store.bound ? 1U : 0U,
        remove_sensor_is_removed() ? 1U : 0U,
        (uint8_t)(millivolts & 0xFFU),
        (uint8_t)(millivolts >> 8),
        (uint8_t)(runtime_store.tag_id & 0xFFU),
        (uint8_t)((runtime_store.tag_id >> 8) & 0xFFU),
    };

    send_event_simple(CLIP_EVT_STATUS_REPORT, payload, sizeof(payload));
}

static void send_ack(uint8_t command, uint8_t status)
{
    uint8_t ack[2] = {command, status};
    send_event_simple(CLIP_EVT_COMMAND_ACK, ack, sizeof(ack));
}

static void handle_remove_change(bool removed)
{
    if (removed) {
        set_state(CLIP_STATE_REMOVED);
        send_event_simple(CLIP_EVT_CLIP_REMOVED, NULL, 0);
        return;
    }

    set_state(CLIP_STATE_CONFIRMED);
    send_event_simple(CLIP_EVT_CLIP_RETURNED, NULL, 0);
}

static void set_binding(const clip_command_frame_t *cmd)
{
    uint8_t token_len = cmd->len;

    if (token_len > BINDING_TOKEN_MAX_LEN) {
        token_len = BINDING_TOKEN_MAX_LEN;
    }

    for (uint8_t index = 0; index < token_len; index++) {
        runtime_store.binding_token[index] = cmd->payload[index];
    }

    runtime_store.binding_token_len = token_len;
    runtime_store.bound = true;
    set_state(CLIP_STATE_BOUND);
    LOG_INF("binding token updated, len=%u", token_len);
}

static void clear_binding(void)
{
    for (uint8_t index = 0; index < BINDING_TOKEN_MAX_LEN; index++) {
        runtime_store.binding_token[index] = 0;
    }

    runtime_store.binding_token_len = 0;
    runtime_store.bound = false;
    set_state(CLIP_STATE_IDLE);
    LOG_INF("binding cleared");
}

static void handle_command_frame(const uint8_t *data, uint8_t len)
{
    uint8_t ack_status = 0x00;
    clip_command_frame_t cmd = {0};

    if (!clip_protocol_parse_command(data, len, &cmd)) {
        LOG_WRN("invalid command frame");
        return;
    }

    LOG_INF("command recv: 0x%02x len=%u", cmd.cmd, cmd.len);

    switch (cmd.cmd) {
    case CLIP_CMD_PING:
        send_event_simple(CLIP_EVT_PONG, NULL, 0);
        break;
    case CLIP_CMD_WAKE_TAG:
        start_finding_alert();
        break;
    case CLIP_CMD_STOP_ALERT:
        stop_alert_and_restore_state();
        break;
    case CLIP_CMD_SET_BINDING:
        set_binding(&cmd);
        break;
    case CLIP_CMD_CLEAR_BINDING:
        clear_binding();
        break;
    case CLIP_CMD_READ_STATUS:
        send_status_report();
        break;
    default:
        ack_status = 0x01;
        set_state(CLIP_STATE_EXCEPTION);
        led_rgb_effect_exception();
        break;
    }

    send_ack(cmd.cmd, ack_status);
}

int main(void)
{
    LOG_INF("clip node boot: EWT73-2G4M04S1A / E73-2G4M04S1A");
    LOG_INF("BLE name: %s", CONFIG_BT_DEVICE_NAME);

    k_work_init_delayable(&alert_timeout_work, alert_timeout_handler);

    clip_state_init();
    led_rgb_init();
    buzzer_init();
    remove_sensor_init(handle_remove_change);
    battery_monitor_init();

    runtime_store.last_state = clip_state_get();

    if (ble_clip_service_init(handle_command_frame) != 0) {
        set_state(CLIP_STATE_EXCEPTION);
    }

    send_event_simple(CLIP_EVT_BOOT, NULL, 0);

    while (1) {
        remove_sensor_poll_once();
        k_sleep(K_MSEC(200));
    }

    return 0;
}
