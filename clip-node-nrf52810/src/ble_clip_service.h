#ifndef BLE_CLIP_SERVICE_H
#define BLE_CLIP_SERVICE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*ble_clip_cmd_handler_t)(const uint8_t *data, uint8_t len);

int ble_clip_service_init(ble_clip_cmd_handler_t handler);
int ble_clip_service_send_event(const uint8_t *data, uint8_t len);

/* 用于早期联调：模拟收到网关命令 */
void ble_clip_service_mock_receive_cmd(const uint8_t *data, uint8_t len);

#ifdef __cplusplus
}
#endif

#endif
