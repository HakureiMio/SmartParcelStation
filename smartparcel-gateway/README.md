# SmartParcel Gateway

`smartparcel-gateway` 是 SmartParcelStation 的本地网关项目，运行在 Linux 或开发电脑，用于局域网阶段联调：
- 本地 SQLite 离线数据存储
- 通过 HTTP/HTTPS 与 `smartparcel-server` 同步
- 通过 MQTT（EMQX）接收服务器命令与上报网关事件
- 预留 PN532 NFC / BLE 标签接口，当前提供 mock 实现

## 1. 项目说明

核心能力：
- 本地数据库 7 张核心表（parcels/tags/bindings/nfc credentials/pickup events/tasks/sync queue）
- 网关签名鉴权（HMAC-SHA256）
- sync pull / sync push
- heartbeat
- MQTT 发布与订阅
- mock NFC 刷卡触发 TAG_WAKE

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

## 10. 与 smartparcel-server 接口约定

已封装：
- `GET /api/v1/health`
- `POST /api/v1/gateways/heartbeat`
- `GET /api/v1/gateways/{gateway_id}/sync/pull`
- `POST /api/v1/gateways/{gateway_id}/sync/push`
- `POST /api/v1/gateways/{gateway_id}/events`
- `POST /api/v1/tags/status-report`
- `POST /api/v1/pickup/confirm`（预留）

## 11. 迁移公网服务器时只需修改

- `SERVER_BASE_URL` 改为 `https://...`
- `MQTT_HOST` / `MQTT_PORT` 指向公网 Broker
- 如启用 TLS，再扩展 MQTT TLS 配置（当前结构已预留可扩展）

## CLI 命令清单

- `python -m gateway.main init-db`
- `python -m gateway.main health`
- `python -m gateway.main sync-pull`
- `python -m gateway.main sync-push`
- `python -m gateway.main heartbeat`
- `python -m gateway.main run`
- `python -m gateway.main mock-nfc CARD_UID`
- `python -m gateway.main list-parcels`
- `python -m gateway.main list-tags`
- `python -m gateway.main list-tasks`

## 测试

```bash
pytest -q tests
```
