#include "ble_clip_service.h"

#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>
#if IS_ENABLED(CONFIG_BT)
#include <zephyr/bluetooth/bluetooth.h>
#endif

LOG_MODULE_REGISTER(ble_clip_service, LOG_LEVEL_INF);

static ble_clip_cmd_handler_t g_cmd_handler;

int ble_clip_service_init(ble_clip_cmd_handler_t handler)
{
    g_cmd_handler = handler;

#if IS_ENABLED(CONFIG_BT)
    int err = bt_enable(NULL);
    if (err) {
        LOG_ERR("bt_enable failed: %d", err);
        return err;
    }
#endif

    LOG_INF("BLE init done (mock service, bt=%d)", IS_ENABLED(CONFIG_BT));
    return 0;
}

int ble_clip_service_send_event(const uint8_t *data, uint8_t len)
{
    ARG_UNUSED(data);
    LOG_INF("BLE event send mock, len=%u", len);
    return 0;
}

void ble_clip_service_mock_receive_cmd(const uint8_t *data, uint8_t len)
{
    if (!g_cmd_handler) {
        return;
    }

    g_cmd_handler(data, len);
}
