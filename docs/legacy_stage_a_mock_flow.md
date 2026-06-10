# 历史阶段 A 与 mock NFC 流程归档

本文归档早期 `server + gateway + mock NFC/BLE` 软件闭环内容。该流程仍可用于演示和回归测试，但不再是当前 README 主线。

当前主线见 `docs/tag_ble_gateway_flow.md`。

## 1. 阶段 A 定位

阶段 A 主要验证：

```text
server 手动预录入包裹
  -> gateway 本地入站
  -> gateway sync-push
  -> server 合并包裹
  -> mock NFC / mock BLE 演示取件和寻物
```

该流程用于软件闭环，不代表真实 BLE 标签已经接入门禁刷卡流程。

## 2. server 启动

```powershell
cd smartparcel-server
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d mysql emqx
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

## 3. gateway 启动

```powershell
cd smartparcel-gateway
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m gateway.main init-db
python -m gateway.main health
python -m gateway.main heartbeat
```

## 4. 模拟快递入站和同步

```powershell
python -m gateway.main inbound-parcel --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --receiver-user-id 2 --receiver-name-masked "张*" --shelf-code A03
python -m gateway.main sync-push
```

server 收到 `GATEWAY_INBOUND` 后按 `parcel_code` 合并预录入包裹；匹配失败时创建来源为 `GATEWAY_INBOUND` 的中心包裹。

## 5. 模拟标签注册和绑定

```powershell
python -m gateway.main register-tag --tag-id TAG001
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001
```

该流程属于旧 mock 标签业务，用于本地演示。真实 BLE 标签注册推荐使用 `/local/tags/register-from-ble`。

## 6. mock NFC / 寻物

```powershell
python -m gateway.main register-nfc-credential --credential-type CARD_UID --credential-value CARD_UID_001 --user-id 2
python -m gateway.main mock-nfc CARD_UID_001
python -m gateway.main sync-push
```

gateway 本地认证通过后创建 `TAG_WAKE` task，并调用 mock BLE。server 只接收审计事件，不参与实时放行。

## 7. 当前归档原因

阶段 A 仍有参考价值，但当前硬件主线已经切换为：

```text
员工小程序 BLE 标签管理
  -> gateway local API
  -> BLE_BACKEND=mock/real
  -> nRF52810 GATT Service
```

因此旧 mock NFC 和门禁流程从根 README 中移出，避免读者误以为它仍是当前主线。
