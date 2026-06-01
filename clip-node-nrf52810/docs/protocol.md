# 轻量二进制协议说明

本协议用于夹具节点与本地网关之间通信，避免 JSON 带来的内存和解析开销。

## 1. 帧格式

建议固定头 + 长度 + 负载 + 校验：

- Byte0: `0xA5`（帧头）
- Byte1: `cmd`（命令字）
- Byte2: `len`（payload 长度）
- Byte3..N: `payload`
- Last: `checksum`（从 Byte0 到 payload 最后一个字节做 XOR）

## 2. 命令字定义

- `0x01` alert_start
- `0x02` alert_stop
- `0x03` set_color
- `0x04` beep_success
- `0x05` beep_error
- `0x06` battery_check
- `0x07` sleep

## 3. 事件字定义

- `0x81` boot
- `0x82` command_ack
- `0x83` clip_removed
- `0x84` clip_returned
- `0x85` battery_low
- `0x86` battery_state_changed

## 4. set_color 负载

- `payload[0]`: R 档位（0~6）
- `payload[1]`: G 档位（0~6）
- `payload[2]`: B 档位（0~6）

共 7×7×7 = 343 颜色组合。

## 5. command_ack 负载

- `payload[0]`: 原命令字
- `payload[1]`: 执行结果（0=成功，非0=失败原因）
