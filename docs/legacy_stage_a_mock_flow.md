# 历史阶段 A 与 mock NFC 流程归档

本文归档早期 `server + gateway + mock NFC/BLE` 软件闭环内容。该流程仍可用于演示和回归测试，但不再是当前 README 主线。

> **Stage B 更新 (2026-06):** mock BLE / mock NFC 已从生产代码路径移除。mock 实现保存在
> `smartparcel-gateway/gateway/legacy/` 仅供历史参考和测试之用。
> 生产代码默认使用真实 BLE（`BLE_BACKEND=real`），不支持 mock fallback。

当前主线见 `docs/gateway_provisioning_flow.md`（配网绑定流程）和
`docs/tag_ble_gateway_flow.md`（BLE 标签管理流程）。

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

## 3. gateway 启动（阶段 A 方式，已废弃）

> **注意：** 以下命令中的 `mock-nfc` 已从 CLI 中移除。`BLE_BACKEND=mock` 不再被接受。
> 对于 Stage B，请使用 `python -m gateway.main run` 或 `python -m gateway.main provisioning`。

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

## 4. 模拟快递入站和同步（保持不变）

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

## 6. mock NFC / 寻物（CLI 命令已移除）

`mock-nfc` CLI 命令已在 Stage B 中移除。如需演示 NFC 流程，请使用真实 PN532 读卡器通过
`gate-access` 硬件固件调用 `/local/gate/access-card` 接口。

```powershell
# 阶段 A 的方式（已不可用）：
# python -m gateway.main mock-nfc CARD_UID_001

# Stage B 方式：
python -m gateway.main gate-access --card-uid CARD_UID_001
```

## 7. 归档原因

阶段 A 仍有参考价值，但当前硬件主线已经切换为：

```text
员工小程序 BLE 标签管理
  -> gateway local API
  -> BLE_BACKEND=real (bleak)
  -> nRF52810 GATT Service (真实 BLE)
```

mock 实现已移至 `smartparcel-gateway/gateway/legacy/`：

| 原文件 | 归档位置 |
|--------|---------|
| `gateway/services/ble/mock.py` | `gateway/legacy/mock_ble_tag_service.py` |
| `gateway/services/mock_ble_service.py` | `gateway/legacy/mock_ble_service.py` |
| `gateway/services/mock_nfc_service.py` | `gateway/legacy/mock_nfc_service.py` |
