#include "ble_clip_service.h"

#include <string.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>
#if IS_ENABLED(CONFIG_BT)
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/hci.h>
#endif

LOG_MODULE_REGISTER(ble_clip_service, LOG_LEVEL_INF);

static ble_clip_cmd_handler_t g_cmd_handler;

#if IS_ENABLED(CONFIG_BT)

#define BT_UUID_SPS_TAG_SERVICE_VAL \
    BT_UUID_128_ENCODE(0x8f7e9000, 0x5d1b, 0x4c2f, 0x9e8a, 0x5f2f5b7b0001)
#define BT_UUID_SPS_TAG_CMD_WRITE_VAL \
    BT_UUID_128_ENCODE(0x8f7e9001, 0x5d1b, 0x4c2f, 0x9e8a, 0x5f2f5b7b0001)
#define BT_UUID_SPS_TAG_EVENT_NOTIFY_VAL \
    BT_UUID_128_ENCODE(0x8f7e9002, 0x5d1b, 0x4c2f, 0x9e8a, 0x5f2f5b7b0001)
#define BT_UUID_SPS_TAG_STATUS_READ_VAL \
    BT_UUID_128_ENCODE(0x8f7e9003, 0x5d1b, 0x4c2f, 0x9e8a, 0x5f2f5b7b0001)

static struct bt_uuid_128 sps_tag_service_uuid = BT_UUID_INIT_128(BT_UUID_SPS_TAG_SERVICE_VAL);
static struct bt_uuid_128 sps_tag_cmd_write_uuid = BT_UUID_INIT_128(BT_UUID_SPS_TAG_CMD_WRITE_VAL);
static struct bt_uuid_128 sps_tag_event_notify_uuid = BT_UUID_INIT_128(BT_UUID_SPS_TAG_EVENT_NOTIFY_VAL);
static struct bt_uuid_128 sps_tag_status_read_uuid = BT_UUID_INIT_128(BT_UUID_SPS_TAG_STATUS_READ_VAL);

static struct bt_conn *current_conn;
static bool notify_enabled;
static uint8_t last_status_value[] = "SPS:OK";
static uint8_t last_event[20];
static uint8_t last_event_len;

static ssize_t cmd_write(struct bt_conn *conn,
                         const struct bt_gatt_attr *attr,
                         const void *buf,
                         uint16_t len,
                         uint16_t offset,
                         uint8_t flags)
{
    ARG_UNUSED(conn);
    ARG_UNUSED(attr);
    ARG_UNUSED(flags);

    if (offset != 0U) {
        return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
    }

    if (!g_cmd_handler) {
        LOG_WRN("command received before handler registration");
        return len;
    }

    LOG_INF("GATT command write len=%u", len);
    g_cmd_handler((const uint8_t *)buf, (uint8_t)MIN(len, UINT8_MAX));
    return len;
}

static void event_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
    ARG_UNUSED(attr);
    notify_enabled = (value == BT_GATT_CCC_NOTIFY);
    LOG_INF("event notify %s", notify_enabled ? "enabled" : "disabled");
}

static ssize_t status_read(struct bt_conn *conn,
                           const struct bt_gatt_attr *attr,
                           void *buf,
                           uint16_t len,
                           uint16_t offset)
{
    ARG_UNUSED(conn);
    ARG_UNUSED(attr);

    if (last_event_len > 0U) {
        return bt_gatt_attr_read(conn, attr, buf, len, offset, last_event, last_event_len);
    }

    return bt_gatt_attr_read(conn, attr, buf, len, offset, last_status_value, sizeof(last_status_value) - 1U);
}

BT_GATT_SERVICE_DEFINE(sps_tag_svc,
    BT_GATT_PRIMARY_SERVICE(&sps_tag_service_uuid.uuid),
    BT_GATT_CHARACTERISTIC(&sps_tag_cmd_write_uuid.uuid,
                           BT_GATT_CHRC_WRITE | BT_GATT_CHRC_WRITE_WITHOUT_RESP,
                           BT_GATT_PERM_WRITE,
                           NULL,
                           cmd_write,
                           NULL),
    BT_GATT_CHARACTERISTIC(&sps_tag_event_notify_uuid.uuid,
                           BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_NONE,
                           NULL,
                           NULL,
                           NULL),
    BT_GATT_CCC(event_ccc_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
    BT_GATT_CHARACTERISTIC(&sps_tag_status_read_uuid.uuid,
                           BT_GATT_CHRC_READ,
                           BT_GATT_PERM_READ,
                           status_read,
                           NULL,
                           NULL),
);

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, BT_UUID_SPS_TAG_SERVICE_VAL),
};

static const struct bt_data sd[] = {
    BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

static void connected(struct bt_conn *conn, uint8_t err)
{
    if (err) {
        LOG_WRN("BLE connection failed: %u", err);
        return;
    }

    current_conn = bt_conn_ref(conn);
    LOG_INF("BLE connected");
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
    ARG_UNUSED(conn);

    if (current_conn) {
        bt_conn_unref(current_conn);
        current_conn = NULL;
    }

    notify_enabled = false;
    LOG_INF("BLE disconnected, reason=%u", reason);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
    .connected = connected,
    .disconnected = disconnected,
};

#endif

int ble_clip_service_init(ble_clip_cmd_handler_t handler)
{
    g_cmd_handler = handler;

#if IS_ENABLED(CONFIG_BT)
    int err = bt_enable(NULL);
    if (err) {
        LOG_ERR("bt_enable failed: %d", err);
        return err;
    }

    LOG_INF("BLE name: %s", CONFIG_BT_DEVICE_NAME);

    err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
    if (err) {
        LOG_ERR("advertising start failed: %d", err);
        return err;
    }
#endif

    LOG_INF("BLE init done (bt=%d)", IS_ENABLED(CONFIG_BT));
    return 0;
}

int ble_clip_service_send_event(const uint8_t *data, uint8_t len)
{
#if IS_ENABLED(CONFIG_BT)
    if (data && len > 0U) {
        last_event_len = MIN(len, sizeof(last_event));
        memcpy(last_event, data, last_event_len);
    }

    if (!notify_enabled) {
        LOG_INF("BLE event len=%u cached, notify not subscribed", len);
        return 0;
    }

    int err = bt_gatt_notify(NULL, &sps_tag_svc.attrs[4], data, len);
    if (err) {
        LOG_WRN("BLE notify failed: %d", err);
        return err;
    }
#else
    ARG_UNUSED(data);
#endif

    LOG_INF("BLE event sent, len=%u", len);
    return 0;
}

void ble_clip_service_mock_receive_cmd(const uint8_t *data, uint8_t len)
{
    if (!g_cmd_handler) {
        return;
    }

    g_cmd_handler(data, len);
}
