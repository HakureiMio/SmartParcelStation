# SmartParcelStation

## 门禁与 NFC 文档索引

- [门禁认证设计](docs/gate_auth_design.md)
- [NFC 标签与门禁卡 payload 契约](docs/nfc_tag_payloads.md)
- [三种门禁认证方式端到端演示](docs/demo_three_gate_auth_methods.md)

## 最终演示闭环

当前演示贯通五端：server 管理账号、包裹、凭证和同步事件；gateway 缓存本地数据并最终判断门禁认证；小程序提供用户扫码、NFC 门禁和取件确认；gate-access 读取卡 UID、显示 QR 与认证结果；nRF52810 标签通过 BLE/GATT 提供寻物反馈。

三种门禁识别方式为 `CARD_UID`、`GATE_NFC_TAG` 和 `GATE_QR`。补办新卡时旧卡变为 `REPLACED`，同步后不能再开门；取件可通过手动按钮或 `sps://pickup` NFC 标签确认。用户没有 `WAITING_PICKUP` 包裹时，三种认证方式均拒绝。

安全边界：server 不直接绕过 gateway 放行；gateway 最终判断是否有待取包裹；gate-access 不保存用户 token；小程序不保存 `gateway_secret` 或 `reader_token`；NFC 标签不保存用户隐私；`LOST / REPLACED / DISABLED` 卡不能开门。

## 1. 项目简介

SmartParcelStation 是面向小型快递站的毕业设计原型系统，用于验证“员工小程序、站点本地网关、智能寻物标签、中心服务端”之间的协作关系。当前仓库定位是局域网验证和硬件闭环演示，不是生产级系统。

当前主线不是完整云端生产链路，而是先把站点内的真实硬件闭环跑通：

```text
员工微信小程序
  -> 局域网调用 smartparcel-gateway local API
  -> gateway 通过 BLE_BACKEND=mock/real 控制智能寻物标签
  -> nRF52810 标签 GATT Service
  -> RGB LED / 蜂鸣器
```

## 2. 当前阶段目标

当前阶段目标是完成毕业设计可演示闭环：

- 员工在微信小程序中进入 `BLE 标签管理`。
- 小程序通过局域网访问 `smartparcel-gateway local API`。
- gateway 使用 `BLE_BACKEND=mock` 做无硬件演示，或使用 `BLE_BACKEND=real` 通过 `bleak` 控制真实标签。
- nRF52810 标签提供 SPS Tag GATT Service，接收 `WAKE_TAG`、`STOP_ALERT`、`READ_STATUS` 等命令。
- 标签通过 RGB LED 和蜂鸣器给出寻物反馈。

## 3. 当前推荐验证闭环

推荐优先验证这条链路：

```text
smartparcel-miniprogram 员工端 BLE 标签管理页
  -> smartparcel-gateway local API
  -> BLE_BACKEND=mock 或 BLE_BACKEND=real
  -> nRF52810 标签 GATT Service
  -> RGB LED / 蜂鸣器
```

`server` 当前不直接扫描、连接或控制 BLE 标签；标签注册、BLE 地址、本地编号、状态、电量和最后连接时间由 gateway 本地维护。

## 4. 项目结构

```text
SmartParcelStation/
├── smartparcel-server/        # FastAPI + MySQL + Alembic，负责中心服务和同步审计
├── smartparcel-gateway/       # Python 本地网关 + SQLite + local API + BLE mock/real
├── smartparcel-miniprogram/   # 微信小程序原型，提供用户端和员工端交互
├── clip-node-nrf52810/        # nRF52810 智能寻物标签固件
├── gate-access/               # ESP32P4 + ESP8266 AT + PN532 + ST7701S 门禁读卡器固件
├── docs/                      # 流程说明、历史归档和联调文档
└── README.md
```

## 5. 子项目职责边界

`smartparcel-server`：

- 负责账号、站点、网关注册、中心包裹、通知和同步审计。
- 接收 gateway 上传的取件审计、门禁审计和标签异常摘要。
- 不直接保存完整标签实时状态。
- 不直接扫描、连接或控制 BLE 标签。

`smartparcel-gateway`：

- 负责本地 SQLite、标签注册、标签本地编号、BLE 标签扫描/连接/控制、本地取件认证、`sync-push` 和 `sync-pull`。
- 是智能寻物标签本地主数据中心和 BLE 控制中心。
- 员工端在同一局域网内访问 gateway。

`smartparcel-miniprogram`：

- 负责用户端和员工端交互。
- 员工端可在同一局域网访问 gateway，当前推荐入口是 `BLE 标签管理`。
- 普通用户默认访问 server，不需要连接站点 Wi-Fi。
- 不保存 `server secret`、`gateway secret`、微信 `appsecret` 或数据库密码等高敏 secret。

`clip-node-nrf52810`：

- 负责 BLE GATT、RGB LED、蜂鸣器、触点检测、电池检测和状态上报。
- 使用轻量二进制协议与 gateway 通信。
- 不保存用户隐私、包裹详情或云端业务主数据。

`gate-access`：

- 负责 ESP32P4 + ESP8266 AT + PN532 门禁读卡、UID 转换和 gateway 本地 API 调用。
- 只作为前端硬件输入设备，不负责本地认证、取件会话、标签唤醒任务或审计同步。
- 当前通过局域网 HTTP 调用 `POST /local/gate/access-card`，业务判断继续由 gateway 完成。

## 6. 最短启动流程

### 6.1 启动 gateway mock BLE 闭环

```powershell
cd smartparcel-gateway
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m gateway.main init-db
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

`.env` 中设置：

```env
BLE_BACKEND=mock
```

验证：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:19000/local/health"
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:19000/local/tags/scan" -ContentType "application/json" -Body '{"timeout_sec":5}'
```

### 6.2 小程序员工端 mock 演示

```text
微信开发者工具打开 smartparcel-miniprogram
登录员工端
进入 BLE 标签管理
扫描附近标签
注册到网关
连接
蓝色亮灯/蜂鸣
停止
读取状态
```

### 6.3 真实 BLE 验证入口

`.env` 中设置：

```env
BLE_BACKEND=real
```

小程序真机调试时，把 `services/config.js` 改为 gateway 所在设备的局域网 IP：

```js
gatewayBaseUrl: 'http://网关局域网IP:19000'
```

真机上的 `127.0.0.1` 是手机自己，不是电脑或 gateway。员工手机和 gateway 必须在同一局域网。

### 6.4 nRF 固件编译入口

必须在 nRF Connect SDK / Nordic Toolchain Terminal 中执行：

```powershell
cd clip-node-nrf52810
west build -b clip_node_nrf52810 . -d build -p always
```

不要使用 `smartparcel-gateway/.venv` 中的 Python 或 `west` 编译 nRF 固件。`smartparcel-gateway/.venv` 只用于 Python 网关项目。

## 7. 当前完成度

- gateway 已提供 BLE 标签管理 local API，并支持 `BLE_BACKEND=mock/real`。
- 小程序员工端已提供 `BLE 标签管理` 页面。
- nRF52810 固件已启用 BLE Peripheral，并提供 SPS Tag GATT Service。
- server 已具备账号、站点、网关注册、同步审计、中心包裹和通知等基础能力。
- 门禁 `gate-access-card` 流程仍以旧 mock BLE 路径为主，后续再迁移到 real BLE。

## 8. 已知限制

- 当前是毕业设计和局域网验证阶段，不包含生产级认证、HTTPS 域名发布、正式微信登录和完整权限体系。
- 小程序真机访问 gateway 时需要同一局域网，并按开发阶段方式处理微信合法域名校验。
- `BLE_BACKEND=real` 依赖 gateway 设备的蓝牙适配器和系统权限。
- nRF52810 RAM 资源有限，固件配置需要保持轻量。
- 当前主要验证单标签扫描、连接和控制；多标签并发调度后续再完善。

## 9. 文档索引

- `smartparcel-gateway/README.md`：本地网关运行和 BLE 标签 API 手册。
- `smartparcel-miniprogram/README.md`：小程序页面和局域网调试手册。
- `clip-node-nrf52810/README.md`：nRF52810 固件和硬件联调手册。
- `gate-access/README.md`：ESP32P4 + ESP8266 AT + PN532 + ST7701S 门禁读卡器固件和 gateway 联调手册。
- `smartparcel-server/README.md`：中心服务端启动、网关注册和同步说明。
- `docs/tag_ble_gateway_flow.md`：BLE 标签与 gateway 闭环详细流程。
- `docs/gate_access_flow.md`：ESP32P4 门禁读卡器与 gateway 联调流程。
- `docs/lan_ble_end_to_end_test_20260610.md`：2026-06-10 局域网 server/gateway/小程序/真实标签闭环测试记录。
- `docs/legacy_stage_a_mock_flow.md`：历史阶段 A 和 mock NFC 流程归档。
- `docs/gateway_gate_access_flow.md`：门禁读卡流程设计和当前状态。
