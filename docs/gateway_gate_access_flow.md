# 门禁读卡流程设计与当前状态

## 1. 定位

门禁读卡流程用于验证 gateway 本地认证、取件会话、小屏提示和同步审计。当前该流程仍以旧 mock BLE 路径为主，尚未完全迁移到真实 BLE 标签。

## 2. 当前流程

```text
门禁读卡器
  -> POST /local/gate/access-card
  -> gateway 查询 local_nfc_credentials
  -> gateway 查询待取包裹和本地标签绑定
  -> gateway 创建 pickup_session
  -> gateway 创建 TAG_WAKE task
  -> mock BLE 唤醒标签
  -> sync-push 上传审计事件
```

## 3. 本地 API

```http
POST /local/gate/access-card
```

请求示例：

```json
{
  "reader_id": "GATE01",
  "credential_type": "CARD_UID",
  "credential_value": "CARD_UID_001"
}
```

## 4. CLI 测试

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main init-db
python -m gateway.main register-nfc-credential --credential-type CARD_UID --credential-value CARD_UID_001 --user-id 2
python -m gateway.main inbound-parcel --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --receiver-user-id 2 --receiver-name-masked "张*" --shelf-code A03
python -m gateway.main register-tag --tag-id TAG001
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001
python -m gateway.main gate-access --reader-id GATE01 --credential-type CARD_UID --credential-value CARD_UID_001
```

## 5. 返回内容

返回字段通常包含：

```text
access
pickup_session_id
pickup_count
session_color
color_display_name
shelves
display_text
items
warnings
```

同一用户多个包裹使用同一个 `session_color`，通过 `shelf_code` 区分位置。

## 6. 与 server 的关系

server 不参与门禁实时放行，只接收审计事件：

```text
NFC_ACCESS_GRANTED
NFC_ACCESS_DENIED
TAG_WAKE_STARTED
```

这些事件不生成 server 标签实时状态，也不代表 server 直接控制 BLE 标签。

## 7. 后续迁移方向

后续可将 `TAG_WAKE` task 的执行端从 mock BLE 迁移到真实 `BLE_BACKEND=real`。迁移前，README 中必须继续区分：

```text
员工 BLE 标签管理：已支持 mock/real。
门禁 gate-access-card：当前仍以旧 mock BLE 流程为主。
```
