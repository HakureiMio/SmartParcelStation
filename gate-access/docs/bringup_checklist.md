# gate-access 联调清单

1. 只接 ESP8266，确认 `AT` 返回 `OK`。
2. 确认 ESP8266 能连接 gateway 热点 `SPS_GATEWAY_AP`。
3. 通过 ESP8266 AT 发送简单 TCP/HTTP 请求，先验证 `/local/health` 或 gateway 其他本地接口。
4. 接入 PN532，确认串口日志出现 `PN532 init ok`。
5. 刷卡，确认串口日志打印 `Card detected UID = ...`。
6. 注册真实 UID 后再次刷卡，确认固件发起 `POST /local/gate/access-card`。
7. 查看 HTTP status 和 response body，确认 gateway 返回 `Access granted` 或 `Access denied`。
8. 接入屏幕后，再验证 boot、network、UID、result 文本显示。
9. ESP8266、PN532、HTTP、屏幕分别稳定后，再合并完整流程演示。
