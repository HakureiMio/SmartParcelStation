# SmartParcel Gateway

`smartparcel-gateway` 是 SmartParcelStation 的本地网关项目，运行在 Linux 或开发电脑，用于局域网阶段联调：
- 本地 SQLite 离线数据存储
- 通过 HTTP/HTTPS 与 `smartparcel-server` 同步
- 通过 MQTT（EMQX）接收服务器命令与上报网关事件
- 预留 PN532 NFC / BLE 智能寻物标签接口，当前提供 mock 实现

## 1. 项目说明

核心能力：
- 本地数据库 7 张核心表（parcels/tags/bindings/nfc credentials/pickup events/tasks/sync queue）
- 网关签名鉴权（HMAC-SHA256）
- sync pull / sync push
- heartbeat
- MQTT 发布与订阅
- mock NFC 刷卡触发 TAG_WAKE
- 智能寻物标签 gateway-local-first 管理：标签完整状态只保存在本地 SQLite

## 2. 局域网验证部署方式

1. 安装 Python 3.11+
2. 创建虚拟环境并安装依赖：

```bash
pip install -r requirements.txt
```

3. 复制 `.env.example` 为 `.env` 并修改局域网地址
4. 初始化数据库
5. 启动网关

## 3. .env 配置说明

- `GATEWAY_CODE`: 网关唯一编码
- `GATEWAY_SECRET`: 网关签名密钥
- `STATION_ID`: 所属站点
- `SERVER_BASE_URL`: 服务器地址（局域网可用 `http://ip:port`）
- `MQTT_HOST` / `MQTT_PORT`: EMQX 地址
- `MQTT_USERNAME` / `MQTT_PASSWORD`: MQTT 凭证
- `SQLITE_PATH`: SQLite 文件路径
- `MOCK_NFC_ENABLED` / `MOCK_BLE_ENABLED`: mock 开关
- `LOG_LEVEL`: 日志等级

## 4. SQLite 初始化方式

```bash
python -m gateway.main init-db
```

## 5. 如何连接服务器

```bash
python -m gateway.main health
python -m gateway.main heartbeat
```

网关请求会自动附带：
- `X-Gateway-Code`
- `X-Gateway-Timestamp`
- `X-Gateway-Nonce`
- `X-Gateway-Signature`

签名串：`method + path + timestamp + nonce + body_hash`。

### 5.1 使用短期注册凭证激活网关

正式公网实验推荐使用“短期注册凭证 → 激活 → 长期密钥”的流程，不再把长期 `GATEWAY_SECRET` 手工同时填入 server 和 gateway。

测试流程：

1. 在 server 面板进入“网关管理”，创建网关短期注册凭证。
2. 当前手机 App / 微信小程序 / 蓝牙或热点配置界面暂未实现，先用 CLI 模拟管理员把凭证写入网关。
3. 在 gateway 执行：

```bash
python -m gateway.main bootstrap-activate \
  --gateway-code GW001 \
  --station-id 1 \
  --registration-token ABCD-1234-EFGH-5678 \
  --server-base-url http://127.0.0.1:18000
```

命令会调用 `/api/v1/gateways/bootstrap/activate`，成功后把以下配置写入 `.env`，并先备份原文件为 `.env.bak`：

```env
GATEWAY_CODE=GW001
GATEWAY_SECRET=********
STATION_ID=1
SERVER_BASE_URL=http://127.0.0.1:18000
```

注意：

- 控制台默认只显示脱敏后的长期密钥；如需手动复制，可加 `--no-write-env`，长期密钥只显示一次。
- `.env` 不要提交到 Git。
- 手动配置 `GATEWAY_CODE=GW001`、`GATEWAY_SECRET=gw-secret-demo` 仍可用于本地开发调试。
- 正式公网实验推荐使用短期注册凭证激活流程，后续微信小程序或管理员 App 可替代当前 CLI。

## 6. 如何连接 EMQX

网关启动后自动连接并使用主题：
- 发布 `gateway/{gateway_code}/status`
- 发布 `gateway/{gateway_code}/events`
- 订阅 `server/{gateway_code}/commands`

## 7. 如何运行 gateway

```bash
python -m gateway.main run
```

启动动作：
- 初始化 DB
- 健康检查
- MQTT 连接
- heartbeat / sync pull / sync push 定时循环

## 8. 如何使用 mock-nfc 测试门禁刷卡

```bash
python -m gateway.main mock-nfc CARD_UID
```

流程：
- 查 `local_nfc_credentials`
- 查用户待取件包裹
- 查绑定标签
- 创建 TAG_WAKE 任务并调用 mock BLE
- 写入 pickup event + sync queue

## 9. 如何执行 sync-pull 和 sync-push

```bash
python -m gateway.main sync-pull
python -m gateway.main sync-push
```

## 10. 阶段 A：gateway 侧 mock 闭环流程

当前阶段条形码扫描用工作人员手动输入代替；自助扫码取件暂不实现，只做人工确认取件和 `TAG_NFC_FAST` 结构预留。智能寻物标签真实管理在 gateway，server 只接收标签异常摘要和取件审计。

### 10.1 初始化 gateway

```powershell
cd smartparcel-gateway
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env` 示例：

```env
GATEWAY_CODE=GW001
GATEWAY_SECRET=gw-secret-demo
STATION_ID=1
SERVER_BASE_URL=http://127.0.0.1:18000
```

执行：

```powershell
python -m gateway.main init-db
python -m gateway.main health
python -m gateway.main heartbeat
```

### 10.2 模拟快递实到入站

```powershell
python -m gateway.main inbound-parcel --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --receiver-user-id 2 --receiver-name-masked "张*"
python -m gateway.main sync-push
```

该命令会写入本地 `local_parcels`，并加入 `sync_queue`。上传事件类型为 `GATEWAY_INBOUND`。server 收到后会按 `parcel_code` 匹配预录入包裹，匹配成功则更新为待取件，匹配失败则新建来源为 `GATEWAY_INBOUND` 的中心包裹。

### 10.3 模拟本地标签注册与绑定

```powershell
python -m gateway.main register-tag --tag-id TAG001 --hw-model E73-2G4M04S1A
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001
```

`register-tag` 写入或更新本地 `local_tags`；`bind-tag` 写入本地 `local_parcel_tag_bindings`，默认不上传 server。开发测试如需兼容旧审计，可显式增加 `bind-tag --upload-audit`；实体智能寻物标签阶段不依赖 server 查询标签状态。

### 10.4 模拟人工确认取件

```powershell
python -m gateway.main confirm-pickup --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --pickup-method OFFLINE_MANUAL
python -m gateway.main sync-push
```

gateway 本地核对快递号、手机号或取件码，成功后生成 pickup event。server 收到 `OFFLINE_PICKUP` / `PICKUP_CONFIRMED` 类事件后更新包裹为 `PICKED_UP`。

### 10.5 保留 mock NFC / 寻物流程

```powershell
python -m gateway.main mock-nfc CARD_UID
python -m gateway.main sync-push
```

现有流程继续保留：gateway 本地认证通过后创建 `TAG_WAKE` task，并调用 mock BLE 执行亮灯/蜂鸣。

## 11. 智能寻物标签本地管理流程

智能寻物标签采用 `gateway-local-first` 管理模式：`local_tags` 是标签完整状态的唯一主数据表，`local_parcel_tag_bindings` 是标签与包裹绑定关系的本地主数据表。标签日常状态不上云，标签异常才上报；标签控制不上云，取件结果才上报。

- `register-tag`：本地注册智能寻物标签，写入/更新 `local_tags`，不上传 server。
- `bind-tag`：默认要求标签已注册，只更新 `local_parcel_tag_bindings` 和 `local_tags`；`--auto-register` 仅用于开发测试。
- `mock-nfc` / `TAG_WAKE` / `TAG_STOP`：寻物亮灯、蜂鸣、停止提醒和状态查询都在 gateway 本地执行；未来 mock BLE 替换为真实 BLE 后 server 职责不变。
- `release-tag`：取件后或人工释放标签，只更新本地绑定和标签状态；释放动作本身默认不上传 server。
- `report-tag-exception`：把 `TAG_EXCEPTION_REPORTED` 写入 `sync_queue`，payload 只包含 `tag_ref`、异常类型、严重级别、消息和发生时间，不包含完整标签状态。
- `confirm-pickup --pickup-method TAG_NFC_FAST`：用于高级用户通过智能寻物标签 NFC 快速取件；上传取件审计时保留 `pickup_method = TAG_NFC_FAST`。

本地保留但不作为 server 常规同步事件的内容包括：标签注册、标签 UID、硬件型号、固件版本、BLE 地址、在线/离线、电量、最后心跳、当前状态、绑定/释放关系、`TAG_WAKE`、`TAG_STOP`、`TAG_STATUS_QUERY`、`TAG_BATTERY_UPDATED`。`sync-push` 不上传完整标签状态；只上传标签异常摘要和取件完成审计。

示例：

```powershell
python -m gateway.main register-tag --tag-id TAG001 --hw-model E73-2G4M04S1A
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001
python -m gateway.main report-tag-exception --tag-id TAG001 --exception-type LOW_BATTERY --severity WARNING --message "智能寻物标签电量过低"
python -m gateway.main confirm-pickup --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --pickup-method TAG_NFC_FAST
python -m gateway.main sync-push
```

## 12. 公网 HTTPS 与 HMAC 签名

公网实验时推荐把 `SERVER_BASE_URL` 改为 HTTPS 域名，例如：

```env
SERVER_BASE_URL=https://sps.example.com
GATEWAY_CODE=GW001
GATEWAY_SECRET=change-me-generate-random
```

每台 gateway 必须使用独立强随机 `GATEWAY_SECRET`。生成示例：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

gateway 请求会自动附带：

- `X-Gateway-Code`
- `X-Gateway-Timestamp`
- `X-Gateway-Nonce`
- `X-Gateway-Body-SHA256`
- `X-Gateway-Signature`

签名原文为 `METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + BODY_SHA256`。JSON body 使用稳定序列化；GET 请求 body 为空。ARM 网关需要保持时间同步，建议启用 NTP / `systemd-timesyncd`。

普通 HTTPS 用来验证服务器证书并加密传输；HMAC 用来证明 gateway 身份并保证消息完整性。mTLS 后续可选，本阶段不强制。

## 13. 与 smartparcel-server 接口约定

已封装：
- `GET /api/v1/health`
- `POST /api/v1/gateways/heartbeat`
- `GET /api/v1/gateways/{gateway_id}/sync/pull`
- `POST /api/v1/gateways/{gateway_id}/sync/push`
- `POST /api/v1/gateways/{gateway_id}/events`
- `POST /api/v1/tags/status-report`（兼容旧 mock，不作为实体智能寻物标签阶段常规事件）
- `POST /api/v1/pickup/confirm`（预留）

## 14. 迁移公网服务器时只需修改

- `SERVER_BASE_URL` 改为 `https://...`
- `MQTT_HOST` / `MQTT_PORT` 指向公网 Broker
- 如启用 TLS，再扩展 MQTT TLS 配置（当前结构已预留可扩展）

## CLI 命令清单

- `python -m gateway.main init-db`
- `python -m gateway.main health`
- `python -m gateway.main sync-pull`
- `python -m gateway.main sync-push`
- `python -m gateway.main heartbeat`
- `python -m gateway.main inbound-parcel`
- `python -m gateway.main register-tag`
- `python -m gateway.main bind-tag`
- `python -m gateway.main release-tag`
- `python -m gateway.main report-tag-exception`
- `python -m gateway.main confirm-pickup`
- `python -m gateway.main run`
- `python -m gateway.main mock-nfc CARD_UID`
- `python -m gateway.main list-parcels`
- `python -m gateway.main list-tags`
- `python -m gateway.main list-tasks`

## 测试

```bash
pytest -q tests
```
