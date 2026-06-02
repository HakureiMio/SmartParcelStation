# SmartParcelStation

SmartParcelStation（SPS）是一个面向小型快递站的智能包裹管理与辅助取件系统。当前处于局域网验证和毕业设计验证阶段，重点验证 `server + gateway + mock NFC/BLE` 的软件闭环，不追求生产级完整认证。

## 项目结构

```text
SmartParcelStation/
├── smartparcel-server/        # FastAPI + MySQL + Alembic + SQLAlchemy + EMQX
├── smartparcel-gateway/       # Python 网关 + SQLite + HTTP/MQTT + mock NFC/BLE
├── clip-node-nrf52810/        # 后续标签固件，当前不是阶段 A 主改造对象
└── README.md
```

## 职责边界

### server 负责

- 服务器手动预录入快递信息，用来代替当前阶段尚未接入的快递公司上传。
- 用户账号、站点、网关注册与授权管理。
- 中心包裹记录、用户查询接口、通知记录。
- 网关同步事件审计、异常状态汇总。
- 保存标签与包裹绑定关系镜像。

### server 不负责

- 不直接控制 BLE 标签亮灯、蜂鸣或停止提醒。
- 不作为现场入站的唯一入口。
- 不替代 gateway 做本地取件认证。
- 不把服务器终端面板做成正式标签管理后台。

### gateway 负责

- 快递实到入站、工作人员现场录入、本地 SQLite 离线缓存。
- 本地包裹与标签绑定、NFC/门禁识别、mock BLE 标签控制。
- 本地优先取件认证，生成 pickup event。
- `sync-push` 上传入站、绑定、取件事件到 server。
- `sync-pull` 接收 server 下发数据。

### gateway 不负责

- 不承担全局用户中心。
- 不替代 server 做消息发布。
- 不做全局审计中心。

## 当前主流程

1. 快递预报：server 手动预录入快递，状态为 `PRE_REGISTERED`，来源为 `SERVER_MANUAL`，同步状态为 `SERVER_ONLY`。
2. 快递实到：gateway 侧工作人员手动录入快递号、收件手机号等信息，写入本地 SQLite，并生成 `GATEWAY_INBOUND` 同步事件。
3. server 合并：server 收到入站事件后按 `parcel_code` 匹配预录入快递；匹配成功则更新为 `WAITING_PICKUP` 与 `MERGED`，匹配失败则新建 `GATEWAY_INBOUND` 来源包裹。
4. 通知占位：server 为有 `receiver_user_id` 的包裹生成 Notification 记录，当前不接微信订阅消息。
5. 标签绑定：gateway 负责本地 mock 绑定标签，上传 `TAG_BOUND`；server 只保存镜像和审计。
6. 人工取件：gateway 本地核对快递号、手机号或取件码，生成 pickup event，上传后 server 更新为 `PICKED_UP`。
7. NFC/寻物：保留现有 `mock-nfc CARD_UID` 流程，通过本地认证后创建 `TAG_WAKE` task 并调用 mock BLE。

## 阶段 A：软件 mock 闭环测试流程

### 1. 启动 server 依赖

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

### 2. 打开 server 终端面板

另开一个终端：

```powershell
cd smartparcel-server
.\.venv\Scripts\activate
python -m admin_console.main
```

在面板中依次执行：

- 创建默认测试用户：`SERVER_ADMIN`、`USER`、`STAFF`、`GATEWAY_ADMIN`。
- 创建默认站点 `ST001`。
- 注册默认网关 `GW001`。
- 手动预录入一条快递信息。

### 3. 启动 gateway

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

确认 `.env` 至少包含：

```env
GATEWAY_CODE=GW001
GATEWAY_SECRET=gw-secret-demo
STATION_ID=1
SERVER_BASE_URL=http://127.0.0.1:18000
```

然后执行：

```powershell
python -m gateway.main init-db
python -m gateway.main health
python -m gateway.main heartbeat
```

### 4. 模拟快递实到入站

```powershell
python -m gateway.main inbound-parcel --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --receiver-user-id 2 --receiver-name-masked "张*"
python -m gateway.main sync-push
```

server 会尝试按 `parcel_code` 匹配预录入快递。匹配成功则更新为 `WAITING_PICKUP / MERGED`；匹配失败则新建来源为 `GATEWAY_INBOUND` 的包裹。

### 5. 模拟标签绑定

```powershell
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001 --encrypted-token mock-token
python -m gateway.main sync-push
```

gateway 负责本地绑定和 mock 标签选择；server 只保存 `TAG_BOUND` 镜像与审计记录。

### 6. 模拟用户查询

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/users/2/pickup-list"
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/parcel-query?parcel_code=P20260602001"
```

通过快递号或取件信息查询时，server 返回有限字段，手机号会做脱敏。

### 7. 模拟人工确认取件

```powershell
python -m gateway.main confirm-pickup --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456
python -m gateway.main sync-push
```

server 收到 `OFFLINE_PICKUP` / `PICKUP_CONFIRMED` 类事件后更新包裹为 `PICKED_UP`。

### 8. 模拟 NFC / 寻物

```powershell
python -m gateway.main mock-nfc CARD_UID
python -m gateway.main sync-push
```

保留现有 mock NFC 流程：gateway 本地认证通过后创建 `TAG_WAKE` task，并调用 mock BLE 执行亮灯/蜂鸣。

## 现阶段明确说明

- 快递公司上传用 server 手动预录入代替。
- 条形码扫描用工作人员手动输入代替。
- 微信小程序前端暂不实现，只设计账号角色与接口职责。
- 自助扫码取件暂不实现，只做人工确认取件，并预留 `NFC_FAST` 等权限语义。
- 标签真实管理在 gateway，server 只保存镜像与审计。

## 公网 HTTPS 实验准备

本地单机测试和局域网测试可以继续使用 `http://127.0.0.1:18000` 或局域网 IP。VPN/隧道测试是在受控网络中验证远程连通性。公网 HTTPS 测试建议使用域名 + Caddy/Nginx 反向代理 + FastAPI 本机端口。

当前推荐的公网实验安全组合是 `HTTPS + HMAC 网关签名`：

- HTTPS 解决传输加密和服务器身份认证。
- HMAC 解决 gateway 身份认证和消息完整性。
- `timestamp + nonce` 解决基础重放攻击。
- MySQL 和 EMQX 不应直接暴露公网。
- 每台 gateway 必须独立生成 `GATEWAY_SECRET`。
- server 管理面板只建议在本机或受信网络使用。

详细部署说明见 `smartparcel-server/docs/public_https_deployment.md`。

## 子项目文档

- `smartparcel-server/README.md`
- `smartparcel-gateway/README.md`
- `clip-node-nrf52810/README.md`
