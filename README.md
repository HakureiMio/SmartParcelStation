# SmartParcelStation

## 第一阶段 BLE 硬件闭环

当前仓库已加入第一阶段本地硬件控制闭环：

```text
smartparcel-miniprogram 员工端 BLE 标签管理页
  -> smartparcel-gateway local API
  -> BLE_BACKEND mock/real 服务
  -> nRF52810 标签 GATT Service
  -> RGB LED / buzzer
```

启动 gateway：

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main init-db
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

mock 测试：

```env
BLE_BACKEND=mock
```

小程序操作：员工端 -> BLE 标签管理 -> 扫描 -> 注册 -> 连接 -> 亮灯/蜂鸣 -> 停止。

真实 BLE 测试：

```env
BLE_BACKEND=real
```

真机调试时，把小程序里的 gateway 地址改为网关所在电脑/设备的局域网 IP：

```js
gatewayBaseUrl: 'http://网关局域网IP:19000'
```

真机上 `127.0.0.1` 指向手机本机，不是电脑或网关；员工手机和 gateway 必须在同一局域网。完整流程见 `docs/tag_ble_gateway_flow.md`。

SmartParcelStation（SPS）是一个面向小型快递站的智能包裹管理与辅助取件系统。当前处于局域网验证和毕业设计验证阶段，重点验证 `server + gateway + mock NFC/BLE` 的软件闭环，不追求生产级完整认证。

## 项目结构

```text
SmartParcelStation/
├── smartparcel-server/        # FastAPI + MySQL + Alembic + SQLAlchemy + EMQX
├── smartparcel-gateway/       # Python 网关 + SQLite + HTTP/MQTT + mock NFC/BLE
├── smartparcel-miniprogram/   # 微信小程序原型，验证用户端/员工端交互流程
├── clip-node-nrf52810/        # 智能寻物标签固件，面向 E73/nRF52810 节点
└── README.md
```

## 职责边界

### server 负责

- 服务器手动预录入快递信息，用来代替当前阶段尚未接入的快递公司上传。
- 用户账号、站点、网关注册与授权管理。
- 中心包裹记录、用户查询接口、通知记录。
- 网关同步事件审计、异常状态汇总。
- 仅接收智能寻物标签异常摘要事件，用于生成站点工作人员通知。
- 仅记录取件完成审计；高级用户通过标签 NFC 快速取件时记录 `pickup_method = TAG_NFC_FAST`。

### server 不负责

- 不直接控制 BLE 标签亮灯、蜂鸣或停止提醒。
- 不作为现场入站的唯一入口。
- 不替代 gateway 做本地取件认证。
- 不把服务器终端面板做成正式标签管理后台。
- 不保存智能寻物标签完整实时状态、BLE 地址、电量、固件版本、心跳或绑定主数据。
- 不直接参与标签注册、绑定、释放或状态查询。

### gateway 负责

- 快递实到入站、工作人员现场录入、本地 SQLite 离线缓存。
- 本地包裹与标签绑定、NFC/门禁识别、mock/真实 BLE 标签控制。
- 本地优先取件认证，生成 pickup event。
- 智能寻物标签注册、绑定、释放、在线/离线、电量、异常判断与状态查询。
- 本地 SQLite 保存完整标签信息和标签-包裹绑定主数据。
- `sync-push` 上传入站、取件审计和标签异常摘要到 server。
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
5. 标签绑定：gateway 负责本地注册和绑定智能寻物标签；默认不把 `TAG_BOUND` 作为 server 常规同步事件。
6. 人工取件：gateway 本地核对快递号、手机号或取件码，生成 pickup event，上传后 server 更新为 `PICKED_UP`；标签 NFC 快速取件统一使用 `pickup_method = TAG_NFC_FAST`。
7. NFC/寻物：保留现有 `mock-nfc CARD_UID` 流程，通过本地认证后创建 `TAG_WAKE` task 并调用 mock BLE。

## 智能寻物标签管理边界

SPS 采用 `gateway-local-first` 的智能寻物标签管理模式：标签日常状态只在站点 gateway 可见，server 不再作为标签管理后台。

核心原则：**标签日常状态不上云，标签异常才上报；标签控制不上云，取件结果才上报。**

- gateway 是智能寻物标签唯一管理者：负责标签注册、绑定、释放、在线/离线、电量、状态、异常判断、BLE 寻物控制和本地 SQLite 主数据。
- server 不保存完整标签状态：不保存在线/离线、电量、BLE 地址、固件版本、最后心跳、实时绑定状态镜像。
- server 只处理两类标签相关业务：`TAG_EXCEPTION_REPORTED` 异常摘要通知，以及包含 `pickup_method = TAG_NFC_FAST` 的取件审计。
- server 侧 `/api/v1/tags*` 历史管理接口已删除；标签注册、绑定、释放、状态查询全部通过 gateway 本地完成。
- `TAG_REGISTERED`、`TAG_ONLINE`、`TAG_OFFLINE`、`TAG_BATTERY_UPDATED`、`TAG_WAKE`、`TAG_STOP`、`TAG_STATUS_QUERY`、`TAG_BIND_LOCAL`、`TAG_RELEASE_LOCAL` 只留在 gateway 本地。
- 兼容旧 mock 流程时可保留 `TAG_BOUND` / `TAG_RELEASED` 审计语义，但实体智能寻物标签阶段不依赖 server 查询标签状态。

## 门禁直连网关与本地寻物流程

门禁 NFC 读卡器作为 gateway 的本地外设/本地子终端，直接调用 gateway 本地 API 或 CLI。门禁放行不等待 server，用户也不需要连接站点 Wi-Fi；员工设备可以连接站点 gateway，用于入库、标签绑定、门禁联调和维护。

现场闭环：

1. 门禁读卡器读取实体 NFC 卡 UID、手机 NFC 模拟卡 ID 或其他本地 credential。
2. 门禁把 `reader_id`、`credential_type`、`credential_value` 发给 gateway。
3. gateway 查询本地 `local_nfc_credentials`，确认用户身份。
4. gateway 查询该用户在本站点的待取包裹与本地标签绑定。
5. gateway 创建 `pickup_session`，为本次取件会话分配统一颜色。
6. gateway 创建多个 `TAG_WAKE` task，并通过 mock BLE 或真实 BLE 唤醒多个智能寻物标签。
7. 门禁小屏显示待取数量、统一颜色和多个货架号。
8. gateway 异步 `sync-push` 上传 `NFC_ACCESS_GRANTED` / `NFC_ACCESS_DENIED` / `TAG_WAKE_STARTED` 审计事件。
9. server 只保存异步审计，不参与实时放行，不保存完整标签状态。

多包裹提示规则：

- 颜色不是包裹唯一编号；颜色是本次取件会话的视觉辅助。
- 货架号是空间定位依据。
- NFC/标签绑定关系是最终确认依据。
- 同一用户多个包裹必须使用同一个颜色闪烁，用 `shelf_code` 区分位置。

小屏示例：

```text
待取 3 件
蓝色闪烁
A03 / B12 / C07
```

### 门禁直连网关测试流程

以下命令用于本地验证“门禁读卡 → gateway 本地放行 → 唤醒标签 → server 异步审计”的闭环。

1. 初始化 gateway 本地库：

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main init-db
```

2. 注册 NFC credential、入站包裹、注册标签并绑定：

```powershell
python -m gateway.main register-nfc-credential --credential-type CARD_UID --credential-value CARD_UID_001 --user-id 2
python -m gateway.main inbound-parcel --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --receiver-user-id 2 --receiver-name-masked "张*" --shelf-code A03
python -m gateway.main register-tag --tag-id TAG001
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001
```

3. 单包裹门禁刷卡：

```powershell
python -m gateway.main gate-access --reader-id GATE01 --credential-type CARD_UID --credential-value CARD_UID_001
```

预期：返回 `access=GRANTED`、`pickup_count=1`、`shelves=["A03"]`、`session_color`，并创建 `TAG_WAKE` task、`NFC_ACCESS_GRANTED` 和 `TAG_WAKE_STARTED` 队列事件。

4. 多包裹统一颜色测试：

```powershell
python -m gateway.main inbound-parcel --parcel-code P20260602002 --receiver-phone 18800000002 --pickup-code 223456 --receiver-user-id 2 --receiver-name-masked "张*" --shelf-code B12
python -m gateway.main inbound-parcel --parcel-code P20260602003 --receiver-phone 18800000002 --pickup-code 323456 --receiver-user-id 2 --receiver-name-masked "张*" --shelf-code C07
python -m gateway.main register-tag --tag-id TAG002
python -m gateway.main register-tag --tag-id TAG003
python -m gateway.main bind-tag --parcel-code P20260602002 --tag-id TAG002
python -m gateway.main bind-tag --parcel-code P20260602003 --tag-id TAG003
python -m gateway.main gate-access --reader-id GATE01 --card-uid CARD_UID_001
```

预期：返回 `pickup_count=3`、`shelves=["A03","B12","C07"]`，所有 `items[].ble_result.led_color` 相同，`display_text` 包含统一颜色和 `A03 B12 C07`。

5. 本地 HTTP API 测试：

```powershell
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

另开终端：

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:19000/local/health"
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:19000/local/gate/access-card" -ContentType "application/json" -Body '{"reader_id":"GATE01","credential_type":"CARD_UID","credential_value":"CARD_UID_001"}'
```

6. 异步上传审计：

```powershell
python -m gateway.main sync-push
```

server 应只看到 `GatewaySyncEvent` 审计，不生成 server 标签状态表或标签管理视图。

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
python -m gateway.main register-tag --tag-id TAG001
python -m gateway.main bind-tag --parcel-code P20260602001 --tag-id TAG001
```

gateway 负责本地注册、绑定和 mock 标签选择；server 不保存标签绑定主数据或实时状态镜像。开发测试如需兼容旧审计，可显式使用 `bind-tag --upload-audit`。

### 6. 模拟用户查询

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/users/2/pickup-list"
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:18000/api/v1/parcel-query?parcel_code=P20260602001"
```

通过快递号或取件信息查询时，server 返回有限字段，手机号会做脱敏。

### 7. 模拟人工确认取件

```powershell
python -m gateway.main confirm-pickup --parcel-code P20260602001 --receiver-phone 18800000002 --pickup-code 123456 --pickup-method OFFLINE_MANUAL
python -m gateway.main sync-push
```

server 收到 `OFFLINE_PICKUP` / `PICKUP_CONFIRMED` 类事件后更新包裹为 `PICKED_UP`。

### 8. 模拟 NFC / 寻物

```powershell
python -m gateway.main mock-nfc CARD_UID
python -m gateway.main sync-push
```

保留现有 mock NFC 流程：gateway 本地认证通过后创建 `TAG_WAKE` task，并调用 mock BLE 执行亮灯/蜂鸣。

### 9. 微信小程序原型测试

小程序用于验证“用户端 + 员工端”前端交互，不保存业务主数据，也不保存任何后端密钥。server/gateway 未启动时，小程序会使用 mock fallback，便于在微信开发者工具中直接演示流程。

#### 9.1 打开小程序

1. 打开微信开发者工具。
2. 选择导入项目，项目目录选择：

```text
SmartParcelStation/smartparcel-miniprogram/
```

3. AppID 可使用测试号或无 AppID 模式。
4. 如果开发者工具提示本地 HTTP 域名校验问题，当前验证阶段可在详情/本地设置中勾选“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。

#### 9.2 纯 mock 演示

不启动 server/gateway 时，直接在小程序中演示：

```text
首页 -> 用户入口 -> 查看待取包裹
首页 -> 用户入口 -> 查看取件状态
首页 -> 员工入口 -> 入库登记
首页 -> 员工入口 -> NFC 读取/写入标签
首页 -> 员工入口 -> 标签绑定包裹
```

预期：页面底部显示 `数据来源：mock`，控制台可能出现 `timeout`，但页面仍能展示 mock 数据和 mock 成功结果。

#### 9.3 连接真实 server 健康检查

先启动 server：

```powershell
cd smartparcel-server
.\.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

然后在小程序中执行：

```text
首页 -> 网关状态 -> 重新检查
```

预期：server 健康检查显示可达；用户包裹、通知、取件状态等接口如尚未补齐，仍会 fallback 到 mock。

#### 9.4 连接真实 gateway 本地 API

先启动 gateway local API：

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main local-api --host 0.0.0.0 --port 19000
```

然后在小程序中执行：

```text
首页 -> 网关状态 -> 重新检查
首页 -> 用户入口 -> 尝试读取本地 gateway 提示
```

预期：`GET /local/health` 使用真实 gateway；`POST /local/gate/access-card` 如果 gateway 本地已准备 NFC credential、包裹与标签绑定，则返回真实门禁提示，否则页面使用 mock fallback 演示。

#### 9.5 小程序 NFC 测试

在微信开发者工具或真机中执行：

```text
首页 -> NFC 测试 -> 读取 NFC
首页 -> NFC 测试 -> 确认写入标签
首页 -> NFC 测试 -> mock NFC
```

预期：

- 不支持 NFC 或权限不足时，页面展示明确原因，并可使用 mock NFC。
- 写入前展示即将写入的 JSON payload。
- 写入能力不可用时，不影响员工通过手动输入 `tag_id` / `tag_nfc_id` 继续绑定标签。

#### 9.6 当前小程序接口状态

已存在真实后端：

- `GET /local/health`
- `POST /local/gate/access-card`
- `GET /api/v1/health`

当前小程序已封装但依赖 mock fallback：

- `POST /local/staff/inbound-parcel`
- `POST /local/staff/tag/bind`
- `POST /local/staff/tag/exception`
- `POST /local/user/tag-nfc-fast-pickup`
- `GET /api/v1/users/{user_id}/parcels`
- `GET /api/v1/users/{user_id}/notifications`
- `GET /api/v1/users/{user_id}/pickup-status`
- `POST /api/v1/pickup/tag-nfc-fast`

## 现阶段明确说明

- 快递公司上传用 server 手动预录入代替。
- 条形码扫描用工作人员手动输入代替。
- 微信小程序当前提供原型工程，用于演示用户端、员工端、gateway 状态和 NFC fallback 流程。
- 自助扫码取件暂不实现，只做人工确认取件，并预留 `NFC_FAST` 等权限语义。
- 标签真实管理在 gateway，server 只保存必要业务审计、标签异常摘要通知和 `TAG_NFC_FAST` 取件方式。

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

## 网关短期注册凭证流程

当前推荐的网关注册链路是：

1. server 生成短期 `registration_token`。
2. 网关管理员在手机端查看凭证；当前手机端暂未实现，先用 server 面板/API 返回值模拟。
3. 管理员通过蓝牙或热点连接 ARM 网关；当前阶段先用 gateway CLI 模拟写入。
4. gateway 调用 `/api/v1/gateways/bootstrap/activate` 激活注册。
5. server 校验 token 后生成长期 `gateway_secret`。
6. gateway 保存 `GATEWAY_CODE`、`GATEWAY_SECRET`、`STATION_ID`、`SERVER_BASE_URL` 到 `.env`。
7. 后续 heartbeat / sync-push / sync-pull 使用长期 `gateway_secret` 做 HMAC-SHA256 签名。

安全约束：短期 token 默认 10 分钟有效、只显示一次、数据库只保存 hash、使用后失效、可由管理员撤销；长期 `gateway_secret` 不能提交到 Git。

详见：`smartparcel-server/README.md` 和 `smartparcel-gateway/README.md`。

## 站点与网关注册测试完整流程

本流程用于本地开发或局域网联调，目标是验证：先创建站点，再创建网关短期注册凭证，最后让 gateway 使用凭证激活并完成 heartbeat。

### 1. 启动 server

```powershell
cd smartparcel-server
.\.venv\Scripts\activate
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 18000 --reload
```

### 2. 打开 server 管理面板

另开一个终端：

```powershell
cd smartparcel-server
.\.venv\Scripts\activate
python -m admin_console.main
```

### 3. 创建或确认站点

在面板中进入：

```text
3 站点管理
```

推荐先选择：

```text
1 查看站点
```

如果已有默认站点，通常会看到：

```text
站点ID | 站点编码 | 站点名称 | 状态
1      | ST001    | 主站点   | ACTIVE
```

如果没有站点，可以选择：

```text
2 创建默认站点 ST001
```

或选择：

```text
3 创建站点
```

站点状态建议使用固定值：

- `ACTIVE`：正常启用，测试时默认使用这个。
- `DISABLED`：停用。
- `MAINTENANCE`：维护中。
- `CLOSED`：已关闭。

注意：创建网关注册凭证时填写的 `站点ID` 必须已经存在。例如只有 `站点ID=1` 时，就不能填写 `2`，否则会报：`station not found`。

### 4. 创建网关短期注册凭证

回到主菜单，进入：

```text
4 网关管理
2 创建网关短期注册凭证
```

示例输入：

```text
网关编码 [GW001]: GW001
站点ID [1]: 1
有效期秒数 [600]: 600
```

成功后面板会显示一次短期注册凭证，例如：

```text
网关短期注册凭证已创建：
网关编码：GW001
站点ID：1
注册凭证：ABCD-1234-EFGH-5678
有效期至：2026-06-03T...
注意：该凭证只显示一次，请妥善保存。
```

说明：

- `registration_token` 默认 10 分钟有效。
- 明文 token 只显示一次。
- server 数据库只保存 token hash。
- token 用过后会变成 `USED`，不能重复激活。

### 5. 使用 gateway CLI 激活网关

切到 gateway 终端：

```powershell
cd smartparcel-gateway
.\.venv\Scripts\activate
python -m gateway.main bootstrap-activate `
  --gateway-code GW001 `
  --station-id 1 `
  --registration-token ABCD-1234-EFGH-5678 `
  --server-base-url http://127.0.0.1:18000
```

激活成功后，gateway 会把以下配置写入 `.env`，并备份原文件为 `.env.bak`：

```env
GATEWAY_CODE=GW001
GATEWAY_SECRET=********
STATION_ID=1
SERVER_BASE_URL=http://127.0.0.1:18000
```

注意：`.env` 和长期 `GATEWAY_SECRET` 不要提交到 Git。

### 6. 初始化 gateway 并验证心跳

```powershell
python -m gateway.main init-db
python -m gateway.main health
python -m gateway.main heartbeat
```

如果 heartbeat 成功，回到 server 面板：

```text
4 网关管理
1 查看网关
```

应该能看到类似：

```text
网关ID | 网关编码 | 站点ID | 状态 | 最近心跳
1      | GW001    | 1      | 在线 | 2026-06-03T...
```

如果关闭 gateway 后再次查看，面板会根据 `最近心跳` 判断展示状态：

- 最近心跳未超时：`在线`
- 最近心跳超过阈值：`离线（心跳超时）`
- 从未心跳：`未连接`

### 7. 查看或撤销注册凭证

在 server 面板进入：

```text
4 网关管理
3 查看网关注册凭证
```

列表不会显示明文 token，只显示状态、过期时间、使用时间等审计信息。

如果要撤销未使用凭证：

```text
4 网关管理
4 撤销网关注册凭证
```

输入凭证 ID 后，状态会变为 `REVOKED`。已撤销凭证不能再激活网关。

### 8. 常见错误

- `station not found`：填写的 `站点ID` 不存在，请先在站点管理里查看或创建站点。
- `Registration token expired`：短期凭证已过期，请重新创建。
- `Registration token already used`：凭证已经激活过，不能重复使用。
- `Registration token revoked`：凭证已被管理员撤销。
- heartbeat 返回 `401`：gateway `.env` 中的 `GATEWAY_SECRET`、`GATEWAY_CODE` 或 server 数据库记录不匹配。
