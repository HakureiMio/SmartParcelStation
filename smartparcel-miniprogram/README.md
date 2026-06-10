# SmartParcel MiniProgram

## 1. 小程序定位

`smartparcel-miniprogram` 是 SmartParcelStation 的微信小程序原型，负责用户端和员工端交互。它不是业务主数据中心，也不保存高敏 secret。

当前推荐硬件演示入口是：

```text
员工端 -> BLE 标签管理
```

入库并绑定标签、NFC 标签读写、异常处理仍保留为业务演示入口；当前硬件闭环优先验证员工端通过 gateway 控制 BLE 标签。

## 2. 打开方式

```text
微信开发者工具
打开目录：smartparcel-miniprogram/
可使用测试号或无 AppID 模式进行基础页面预览
```

当前局域网 HTTP 适合毕业设计和开发调试；正式发布需要合法 HTTPS 域名、正式 AppID、微信登录和平台配置。

## 3. 当前页面清单

用户端页面：

- `pages/user-home`：用户首页。
- `pages/user-parcels`：待取包裹列表。
- `pages/user-notifications`：通知列表。
- `pages/user-pickup-status`：取件状态和门禁提示。
- `pages/user-nfc-fast-pickup`：NFC 快速取件原型。

员工端页面：

- `pages/staff-home`：员工工作台。
- `pages/staff-inbound`：包裹入库登记。
- `pages/staff-tag-nfc`：NFC 标签读取和写入原型。
- `pages/staff-tag-bind`：标签与包裹绑定。
- `pages/staff-ble-tags`：BLE 标签管理，支持扫描、注册、连接、亮灯/蜂鸣、停止和读取状态。
- `pages/staff-exception`：标签异常上报。
- `pages/gateway-status`：server/gateway 健康检查。

## 4. 当前推荐演示入口

当前推荐硬件闭环：

```text
首页 -> 员工入口 -> 员工登录 -> BLE 标签管理
```

该入口对应：

```text
小程序员工端
  -> gatewayBaseUrl
  -> smartparcel-gateway local API
  -> BLE_BACKEND=mock/real
  -> nRF52810 标签
```

## 5. 员工 BLE 标签管理流程

### 5.1 mock 流程

```text
1. 启动 smartparcel-gateway local API。
2. 确认 BLE_BACKEND=mock。
3. 打开小程序。
4. 进入员工端登录。
5. 进入 BLE 标签管理。
6. 点击扫描附近标签。
7. 看到 SPS-F01-20260610-0001。
8. 点击注册到网关。
9. 在已注册标签列表看到 标签 001。
10. 点击 标签 001 进入详情。
11. 点击连接。
12. 点击蓝色亮灯/蜂鸣。
13. 点击停止。
14. 点击读取状态。
```

### 5.2 真实硬件流程

```text
1. 烧录并上电 nRF52810 标签。
2. 确认 RTT 日志显示 BLE name: SPS-F01-20260610-0001。
3. gateway .env 设置 BLE_BACKEND=real。
4. 重启 gateway local API。
5. 手机与 gateway 位于同一局域网。
6. 小程序 gatewayBaseUrl 改为 http://网关局域网IP:19000。
7. 员工端进入 BLE 标签管理。
8. 扫描附近标签。
9. 注册真实标签。
10. 点击连接。
11. 点击蓝色亮灯/蜂鸣。
12. 观察标签 RGB LED 与蜂鸣器是否工作。
13. 点击停止。
14. 观察 RGB LED 与蜂鸣器是否停止。
```

## 6. gatewayBaseUrl 配置

配置文件：

```text
services/config.js
```

开发者工具运行在电脑本机时：

```js
gatewayBaseUrl: 'http://127.0.0.1:19000'
```

真机调试时必须改成 gateway 的局域网 IP：

```js
gatewayBaseUrl: 'http://192.168.x.x:19000'
```

说明：

```text
手机上的 127.0.0.1 是手机自己，不是电脑。
员工手机和 gateway 必须在同一局域网。
当前局域网 HTTP 适合毕业设计/开发调试，正式发布需要合法 HTTPS 域名和微信平台配置。
```

## 7. mock fallback 机制

小程序保留 mock fallback，用于 server/gateway 未启动时演示页面流程。真实联调时建议临时关闭 fallback，避免请求失败后误以为真实链路成功。

配置项：

```js
useMockWhenRequestFail: true
```

真实硬件联调时可改为：

```js
useMockWhenRequestFail: false
```

## 8. 真机调试注意事项

- 微信开发者工具中需要按开发阶段要求处理合法域名校验。
- 手机和 gateway 必须在同一 Wi-Fi 或同一局域网。
- Windows 防火墙需要允许 `19000` 端口入站。
- `BLE_BACKEND=real` 时，标签不要被电脑蓝牙设置或其他手机持续连接占用。
- 小程序不保存 `server secret`、`gateway secret`、微信 `appsecret` 或数据库密码。

## 9. 当前未完成能力

- 正式微信登录、token 刷新和生产级权限矩阵。
- 正式 HTTPS 域名发布。
- 用户端全部接口的真实 server 数据闭环。
- 入库、绑定、异常上报等部分页面仍可能依赖 mock fallback。
- 门禁刷卡流程尚未完全迁移到 real BLE。
