# BLE 设计草案

当前版本采用简化 BLE 服务骨架，后续可扩展为 Smart Clip GATT Service。

## 1. 角色与链路

- 夹具节点：BLE Peripheral
- 本地网关：BLE Central

## 2. 建议服务结构（后续扩展）

- Service UUID: `Smart Clip Service`（TODO）
- Characteristic A（Write）：命令下发
- Characteristic B（Notify）：事件上报

## 3. 当前骨架行为

- 提供 `ble_clip_service_init()` 初始化入口。
- 提供 `ble_clip_service_send_event()` 事件发送入口（当前为日志 mock）。
- 提供 `ble_clip_service_mock_receive_cmd()` 命令注入入口，用于早期联调。

## 4. 协议约束

- 命令和事件负载使用 `docs/protocol.md` 约定的二进制格式。
- 不使用 JSON。
