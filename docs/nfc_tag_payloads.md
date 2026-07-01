# NFC 标签与门禁卡 payload 契约

本文定义 SmartParcelStation 中用户门禁卡、门禁 NFC 标签、包裹取件 NFC 标签以及 BLE 智能寻物标签的边界。不同类型不能混用，也不能通过标签写入用户隐私或系统密钥。

## 1. 用户门禁卡 / 手机模拟卡 UID

示例：

```text
04A1B2C3D4
CARD_UID_001
```

PN532 读取 UID 后，由 `gate-access` 将 `CARD_UID` 上传给 `smartparcel-gateway`。Gateway 查询本地状态为 `ACTIVE` 的凭证，并判断绑定用户是否存在 `WAITING_PICKUP` 包裹：有待取包裹才放行，否则拒绝。

绑定规则：

- 一张卡同一时间只能绑定一个用户。
- 一个用户在同一站点同一时间最多有一张 `ACTIVE CARD_UID`。
- 遗忘、丢卡或补办后，旧卡变为 `LOST`、`REPLACED` 或 `DISABLED`，新卡为 `ACTIVE`。
- 旧卡不能再开门；历史记录保留，不物理删除。

## 2. 门禁 NFC 标签

推荐使用外贴 NTAG213 或 NTAG215，写入 NDEF URI：

```text
sps://gate-nfc?v=1&gateway_code=GW001&reader_id=GATE01&station_id=1&gate_nfc_tag_id=GATE-NFC-001
```

字段：

| 字段 | 含义 |
|---|---|
| `v` | payload 协议版本 |
| `gateway_code` | 网关编号 |
| `reader_id` | 门禁读卡器编号 |
| `station_id` | 站点 ID |
| `gate_nfc_tag_id` | 门禁 NFC 标签编号 |

用户在小程序“手机 NFC 门禁”页读取标签。小程序携带用户 Bearer token 和 payload 参数调用 server；server 识别用户并生成 `GATE_USER_AUTH_REQUESTED` 事件；gateway 最终判断该用户是否有待取包裹；`gate-access` 轮询 gateway 并显示结果。

该标签只标识门禁 reader、gateway 和 station，不代表用户身份。不得包含用户姓名、手机号、包裹详情、`gateway_secret`、`reader_token`、server token、数据库密码或 `ADMIN_BOOTSTRAP_TOKEN`。

## 3. 包裹取件 NFC 标签

推荐使用外贴 NTAG213 或 NTAG215，写入 NDEF URI：

```text
sps://pickup?v=1&tag_id=SPS-TAG-0001&binding=PB-0001&token=DEMO-TOKEN-0001
```

字段：

| 字段 | 含义 |
|---|---|
| `v` | payload 协议版本 |
| `tag_id` | 包裹寻物标签 ID |
| `binding` | 取件绑定 ID / `pickup_binding_id` |
| `token` | 绑定校验 token / `encrypted_token` |

用户进入快递站后读取包裹标签，小程序调用 `/pickup/nfc-confirm`。Server 校验 `tag_id`、`pickup_binding_id` 和 `encrypted_token`，成功后将包裹置为 `PICKED_UP`，并生成 `PARCEL_PICKUP_CONFIRMED` 事件下发 gateway。

该标签只代表包裹绑定，不授予开门权限。不得包含用户姓名、手机号、完整包裹详情、`gateway_secret`、`reader_token`、server secret 或数据库密码。

## 4. 类型对比

| 类型 | 被谁读取 | 用途 | payload / 数据 | 是否代表用户身份 | 是否可开门 |
|---|---|---|---|---|---|
| 用户门禁卡 | PN532 | 门禁身份识别 | `CARD_UID` | 是，必须绑定用户 | 有待取包裹才可开门 |
| 门禁 NFC 标签 | 用户手机 | 请求门禁认证 | `sps://gate-nfc` | 否，用户身份来自小程序 token | Gateway 判断后才可开门 |
| 包裹取件 NFC 标签 | 用户手机 | 确认取件 | `sps://pickup` | 否，只代表包裹绑定 | 不用于开门 |
| BLE 智能标签 | Gateway BLE | 寻物提醒 | GATT | 否 | 不用于开门 |

`clip-node-nrf52810` 是 BLE 智能寻物标签，负责广播、GATT、RGB、状态和电池信息；它不是上述两种 NFC 标签，也不直接参与门禁用户身份识别。
