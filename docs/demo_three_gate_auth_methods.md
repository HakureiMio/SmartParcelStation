# 三种门禁认证端到端演示

## 1. 演示目标

验证实体卡、门禁 NFC 标签、门禁二维码三种认证方式，以及补卡失效、手动/NFC 确认取件和无待取包裹拒绝的完整闭环。

## 2. 五端职责

- `smartparcel-server`：账号、用户、包裹、卡绑定与补办、server→gateway 同步事件、接收 gateway 审计。
- `smartparcel-gateway`：本地凭证与包裹缓存、三种门禁认证最终判断、BLE 控制和门禁结果缓存。
- `smartparcel-miniprogram`：登录、扫码/NFC 门禁、查看包裹、手动/NFC 确认取件、报失卡。
- `gate-access`：PN532 读 UID、显示二维码、轮询并显示允许/拒绝；不保存用户 token，不判断包裹，不保存 `gateway_secret`。
- `clip-node-nrf52810`：BLE 寻物标签，负责 RGB、状态和 GATT，不是门禁 NFC 标签。

## 3. 硬件准备

准备已验证的 ESP32-P4 门禁、ESP8266、PN532、ST7701S、实体测试卡，以及写入 `sps://gate-nfc` 的 NTAG213/NTAG215。包裹 NFC 标签另行写入 `sps://pickup`，二者不可混用。

## 4. 账号准备

默认账号为 `station_admin001 / 123456` 与 `demo_user001 / 123456`。准备 `ADMIN_BOOTSTRAP_TOKEN` 和 `GATE_READER_TOKEN`，不要提交真实 token。

```bash
export SERVER_BASE_URL="http://127.0.0.1:18000/api/v1"
export GATEWAY_BASE_URL="http://127.0.0.1:19000"
export ADMIN_BOOTSTRAP_TOKEN="change-this"
export GATE_READER_TOKEN="change-this-reader-token"
```

## 5. server 启动与初始化

按 `smartparcel-server/README.md` 启动 server 后执行：

```bash
curl -i "http://127.0.0.1:18000/api/v1/health"
curl -i -X POST "http://127.0.0.1:18000/api/v1/dev/default-users" -H "X-Admin-Bootstrap-Token: ${ADMIN_BOOTSTRAP_TOKEN}"
curl -i -X POST "http://127.0.0.1:18000/api/v1/dev/demo-data" -H "X-Admin-Bootstrap-Token: ${ADMIN_BOOTSTRAP_TOKEN}"
```

Demo data 包含 `demo_user001`、`CARD_UID_001`、A03/B01 上两个 `WAITING_PICKUP` 包裹、`SPS-TAG-0001/0002`、`GW001`、`GATE01` 和 `GATE-NFC-001`。

登录并保存响应 token：

```bash
curl -i -X POST "${SERVER_BASE_URL}/auth/login" -H 'Content-Type: application/json' -d '{"role":"client","username":"demo_user001","password":"123456"}'
export USER_TOKEN="<返回的用户 token>"
curl -i -X POST "${SERVER_BASE_URL}/auth/login" -H 'Content-Type: application/json' -d '{"role":"staff","username":"station_admin001","password":"123456"}'
export STAFF_TOKEN="<返回的员工 token>"
```

## 6. gateway 启动与同步

```bash
cd smartparcel-gateway
python -m gateway.main sync-pull
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

预期拉取 `USER_ACCESS_CREDENTIAL_UPSERT`、`PARCEL_UPSERT`、`PARCEL_TAG_BINDING_UPSERT`。另一个终端检查：

```bash
curl -i "http://127.0.0.1:19000/local/health"
```

## 7. gate-access 启动

按 `gate-access/README.md` 使用用户已经验证的固件。上电后确认 Wi-Fi 已连接、屏幕出现二维码且固件持续轮询认证结果。本阶段不重新编译或烧录固件。

## 8. 小程序准备

在微信开发者工具打开 `smartparcel-miniprogram/`，配置 server 地址并以 `demo_user001` 登录。扫码/NFC 请求提交后，小程序只能显示“认证已提交，请查看门禁屏幕”，最终结果看门禁屏幕。

## 9. 演示方式一：刷实体卡 / 手机模拟卡

curl 预检：

```bash
curl -i -X POST "${GATEWAY_BASE_URL}/local/gate/access-card" -H 'Content-Type: application/json' -H 'X-Gate-Reader-Id: GATE01' -H "X-Gate-Reader-Token: ${GATE_READER_TOKEN}" -d '{"reader_id":"GATE01","credential_type":"CARD_UID","credential_value":"CARD_UID_001"}'
```

预期 `GRANTED`、`pickup_count=2`、货架 A03/B01。随后在 PN532 区刷实际绑定卡，门禁显示允许进入、待取数量和货架。

## 10. 演示方式二：手机 NFC 读取门禁标签

标签内容：

```text
sps://gate-nfc?v=1&gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001
```

进入小程序“手机 NFC 门禁”页并读取标签。curl 等价请求：

```bash
curl -i -X POST "${SERVER_BASE_URL}/gate/auth/nfc-confirm" -H 'Content-Type: application/json' -H "Authorization: Bearer ${USER_TOKEN}" -d '{"auth_method":"GATE_NFC_TAG","gateway_code":"GW001","reader_id":"GATE01","station_id":1,"gate_nfc_tag_id":"GATE-NFC-001"}'
cd smartparcel-gateway && python -m gateway.main sync-pull
curl -i -H 'X-Gate-Reader-Id: GATE01' -H "X-Gate-Reader-Token: ${GATE_READER_TOKEN}" "${GATEWAY_BASE_URL}/local/gate/auth-result?reader_id=GATE01"
```

预期 `GRANTED`、`pickup_count=2`。

### URL Link 直接启动模式

在微信平台生成 URL Link，目标页面为：

```text
pages/gate-nfc-auth/gate-nfc-auth
```

页面 query：

```text
gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001
```

把生成后的 `https://wxaurl.cn/xxxxxxxx` 作为 NDEF URI 写入 NTAG213/NTAG215。手机系统读取标签后打开微信小程序；页面从启动参数取门禁信息，并使用当前登录用户 token 自动提交认证。若未登录，参数保存在 `pending_gate_nfc_auth`，客户登录后返回门禁页自动继续。小程序只显示“认证已提交，请查看门禁屏幕”。

演示前人工填写：微信小程序 AppID、上述页面路径与 query、生成后的 URL Link、可访问的 `serverBaseUrl`，并确认用户已登录或可以完成登录。URL Link 过期时重新生成并重写 NFC 标签。

## 11. 演示方式三：扫描门禁屏幕二维码

先取得真实 session：

```bash
curl -i -H 'X-Gate-Reader-Id: GATE01' -H "X-Gate-Reader-Token: ${GATE_READER_TOKEN}" "${GATEWAY_BASE_URL}/local/gate/qr-session?reader_id=GATE01"
```

小程序扫描屏幕二维码并调用 QR 确认接口。curl 模拟如下；实际必须替换为 `qr-session` 返回的真实 `session_id`、`nonce`、`expires_at`、`signature`：

```bash
curl -i -X POST "${SERVER_BASE_URL}/gate/auth/qr-confirm" -H 'Content-Type: application/json' -H "Authorization: Bearer ${USER_TOKEN}" -d '{"auth_method":"GATE_QR","gateway_code":"GW001","reader_id":"GATE01","station_id":1,"session_id":"qr_xxx","nonce":"abc123","expires_at":1780000000,"signature":"test"}'
cd smartparcel-gateway && python -m gateway.main sync-pull
curl -i -H 'X-Gate-Reader-Id: GATE01' -H "X-Gate-Reader-Token: ${GATE_READER_TOKEN}" "${GATEWAY_BASE_URL}/local/gate/auth-result?reader_id=GATE01"
```

预期 gateway 收到 `GATE_USER_AUTH_REQUESTED`，最终返回 `GRANTED`。

## 12. 演示补办新卡，旧卡失效

```bash
curl -i -X POST "${SERVER_BASE_URL}/staff/users/2/cards/bind" -H 'Content-Type: application/json' -H "Authorization: Bearer ${STAFF_TOKEN}" -d '{"station_id":1,"credential_type":"CARD_UID","credential_value":"CARD_UID_002","reason":"REPLACEMENT_DEMO"}'
cd smartparcel-gateway && python -m gateway.main sync-pull
```

然后分别以第 9 节命令测试 `CARD_UID_001` 和 `CARD_UID_002`。预期旧卡 `DENIED / CREDENTIAL_REPLACED`（或 `CREDENTIAL_NOT_ACTIVE`），新卡在仍有待取包裹时 `GRANTED`。

## 13. 演示用户确认取件

手动确认：

```bash
curl -i -X POST "${SERVER_BASE_URL}/pickup/manual-confirm" -H 'Content-Type: application/json' -H "Authorization: Bearer ${USER_TOKEN}" -d '{"parcel_id":1,"confirm_method":"MANUAL_BUTTON"}'
```

包裹 NFC 标签确认：

```bash
curl -i -X POST "${SERVER_BASE_URL}/pickup/nfc-confirm" -H 'Content-Type: application/json' -H "Authorization: Bearer ${USER_TOKEN}" -d '{"tag_id":"SPS-TAG-0001","pickup_binding_id":"PB-0001","encrypted_token":"DEMO-TOKEN-0001"}'
```

预期包裹变为 `PICKED_UP`，server 生成 `PARCEL_PICKUP_CONFIRMED`；再次 sync-pull 后 gateway 本地状态更新。使用实际 demo 数据时，应选择两个不同的待取包裹分别演示手动和 NFC 确认。

## 14. 无待取包裹后再次认证被拒绝

确认两个包裹均已取件并 sync-pull，再重复刷卡、NFC、扫码流程。三种方式都应为 `DENIED / NO_WAITING_PARCEL`，门禁显示“暂无待取包裹”。

## 15. 常见问题

- 401/403：检查相应 Bearer、bootstrap 或 reader token，勿混用。
- QR 过期：重新请求 `qr-session`，不能复用旧签名。
- 门禁一直 PENDING：执行 sync-pull，并检查 reader_id 是否为 GATE01。
- 旧卡仍可用：确认补卡事件已同步到 gateway。
- NFC 失败：确认门禁标签是 `sps://gate-nfc`，包裹标签是 `sps://pickup`。

## 16. 安全边界

Server 不绕过 gateway 直接放行；gateway 最终判断待取包裹；`gate-access` 不保存用户 token；小程序不保存 `gateway_secret` 或 `reader_token`；NFC 标签不保存用户隐私；`LOST / REPLACED / DISABLED` 卡不能开门。日志和演示截图不要暴露真实 token。

## 17. 最终验收 checklist

- [ ] server health ok
- [ ] 默认账号初始化成功
- [ ] demo data 初始化成功
- [ ] demo_user001 登录成功
- [ ] station_admin001 登录成功
- [ ] gateway heartbeat ONLINE
- [ ] gateway sync-pull 成功
- [ ] gate-access 显示二维码
- [ ] CARD_UID_001 刷卡 GRANTED
- [ ] 小程序 NFC 门禁 GRANTED
- [ ] 小程序扫码门禁 GRANTED
- [ ] 补办 CARD_UID_002 后 CARD_UID_001 DENIED
- [ ] CARD_UID_002 GRANTED
- [ ] 用户手动确认取件成功
- [ ] 用户 NFC 包裹标签确认取件成功
- [ ] 无待取包裹后三种门禁方式都 DENIED
