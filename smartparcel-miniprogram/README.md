# SmartParcel MiniProgram

这是 SPS 微信小程序原型，用于验证“用户端 + 员工端”双入口、server/gateway 双通道访问、NFC 读取/写入智能寻物标签、包裹入库、标签绑定、取件确认等核心流程。它是前端交互入口，不是业务主数据中心。

## 1. 打开方式

1. 使用微信开发者工具打开 `smartparcel-miniprogram/`。
2. 可以使用测试号或无 AppID 模式预览基础页面。
3. 使用 VS Code 编辑代码，微信开发者工具负责运行、预览和真机调试。
4. 当前阶段允许 HTTP 与本地地址，便于开发者工具和局域网验证；正式上线需要配置合法 HTTPS 域名、小程序 AppID 与微信登录/鉴权。

## 2. 当前能力

- 用户端默认访问 server，普通用户不需要连接站点 Wi-Fi。
- 员工端优先访问 gateway，员工设备可连接站点局域网访问本地 gateway。
- 本地 gateway API 只用于站点局域网验证，不作为公网服务。
- 所有接口都有 mock fallback，server/gateway 未启动时仍可演示。
- NFC 读写依赖设备和小程序环境，不保证所有手机可用；不可用时使用手动输入或 mock。
- 小程序只保存普通用户 token、站点配置、本地 gateway 地址等非高敏配置，不保存 server secret、gateway secret、微信 appsecret 或数据库密码。

## 3. 页面清单

用户端页面：

- `pages/user-home`：用户首页，展示待取数量、通知数量和取件提示。
- `pages/user-parcels`：待取包裹列表，展示脱敏收件信息。
- `pages/user-notifications`：用户通知列表。
- `pages/user-pickup-status`：取件流程状态与 gateway 门禁提示。
- `pages/user-nfc-fast-pickup`：高级用户 NFC 快速取件验证。

员工端页面：

- `pages/staff-home`：员工首页与常用操作入口。
- `pages/staff-inbound`：包裹入库登记。
- `pages/staff-tag-nfc`：NFC 标签读取、写入 payload 预览、mock 验证。
- `pages/staff-tag-bind`：智能寻物标签与包裹绑定。
- `pages/staff-exception`：标签异常上报。
- `pages/gateway-status`：server/gateway 健康检查与当前模式展示。

## 4. 服务封装

`services/server-api.js` 封装：

- `getHealth()`
- `getUserParcels(userId)`
- `getUserNotifications(userId)`
- `getPickupStatus(userId)`
- `confirmTagNfcFastPickup(payload)`

`services/gateway-api.js` 封装：

- `getLocalHealth()`
- `gateAccessCard(payload)`
- `inboundParcel(payload)`
- `bindTag(payload)`
- `reportTagException(payload)`
- `tagNfcFastPickup(payload)`

`services/nfc-service.js` 封装：

- `checkNfcAvailable()`
- `readTag()`
- `writeTag(payload)`
- `parseTagPayload(raw)`
- `mockReadTag()`

NFC payload 支持 JSON 文本和 `sps://tag?...` URI。NFC 不可用或写入失败时，页面会展示原因，并保留手动输入兜底。

## 5. 真实接口与 mock fallback

当前已存在真实后端接口：

- `GET /local/health`
- `POST /local/gate/access-card`
- `GET /api/v1/health`

当前小程序已封装但使用 mock fallback 的接口：

- `POST /local/staff/inbound-parcel`
- `POST /local/staff/tag/bind`
- `POST /local/staff/tag/exception`
- `POST /local/user/tag-nfc-fast-pickup`
- `GET /api/v1/users/{user_id}/parcels`
- `GET /api/v1/users/{user_id}/notifications`
- `GET /api/v1/users/{user_id}/pickup-status`
- `POST /api/v1/pickup/tag-nfc-fast`

如果真实 server/gateway 未启动，请求可能在开发者工具控制台显示 `timeout`，随后页面仍会使用 mock 数据演示。

## 6. 演示流程

### 演示 1：用户查看待取包裹

```text
首页 -> 用户入口 -> 查看待取包裹 -> 显示 server 或 mock 数据
```

### 演示 2：员工入库登记

```text
首页 -> 员工入口 -> 入库登记 -> 输入包裹编号/用户 ID/货架号 -> 提交 -> mock 或 gateway 成功
```

### 演示 3：员工 NFC 写标签

```text
首页 -> 员工入口 -> NFC 读取/写入标签 -> 输入 TAG001/NFC_TAG_001 -> 确认写入标签 -> 读取或 mock 验证
```

如果 NFC 不支持：

```text
使用 mock NFC 或手动输入标签 ID。
```

### 演示 4：员工绑定标签

```text
首页 -> 员工入口 -> 标签绑定包裹 -> 输入包裹编号 + 读取/输入标签 ID -> 提交绑定
```

### 演示 5：门禁提示显示

```text
首页 -> 网关状态 -> 检查 gateway
首页 -> 用户入口 -> 查看取件状态 -> 显示 gateway 返回的颜色和货架提示
```

### 演示 6：用户 NFC 快速取件

```text
首页 -> 用户入口 -> NFC 快速取件 -> 读取标签 -> 确认快速取件 -> 显示成功/失败
```

## 7. 常见控制台提示

- `[Deprecation] SharedArrayBuffer...`：微信开发者工具内置 Chromium 的环境警告，可忽略。
- `getSystemInfo API 提示`：微信基础库兼容提醒，不是本项目报错。
- `Error: timeout`：通常表示 `smartparcel-server` 或 `smartparcel-gateway local-api` 未启动；页面会使用 mock fallback。

## 8. 后续需要补齐

- gateway HTTP API：员工入库、标签绑定、标签异常、NFC 快速取件确认。
- server API：用户待取包裹、用户通知、取件状态、NFC 快速取件确认。
- 生产认证：微信登录、token 刷新、角色权限、HTTPS 合法域名。
