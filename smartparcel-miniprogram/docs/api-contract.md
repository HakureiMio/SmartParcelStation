# SPS 小程序 API 契约

## 已在当前仓库存在

- `GET /local/health`：gateway 本地健康检查，见 `smartparcel-gateway/gateway/local_api.py`。
- `POST /local/gate/access-card`：gateway 本地门禁读卡与取件提示，见 `AccessControlService.handle_access_card`。
- `GET /api/v1/health`：server 健康检查。

## 小程序已封装，当前使用 mock fallback 的接口

- `POST /local/staff/inbound-parcel`：员工入库登记，后续可映射 gateway CLI `inbound-parcel`。
- `POST /local/staff/tag/bind`：员工绑定智能寻物标签。
- `POST /local/staff/tag/exception`：员工上报标签异常。
- `POST /local/user/tag-nfc-fast-pickup`：本地 gateway NFC 快速取件确认预留。
- `GET /api/v1/users/{user_id}/parcels`：用户待取包裹。
- `GET /api/v1/users/{user_id}/notifications`：用户通知。
- `GET /api/v1/users/{user_id}/pickup-status`：用户取件状态与门禁提示。
- `POST /api/v1/pickup/tag-nfc-fast`：server 侧 NFC 快速取件确认预留。

## 设计边界

- server 管用户账号、通知、取件记录、审计与 gateway sync-push，不保存完整标签状态。
- gateway 管本地包裹、NFC 凭证、标签注册/绑定/释放、门禁本地 API 与 BLE 寻物。
- 小程序不保存 server secret、gateway secret、微信 appsecret 或数据库密码。
