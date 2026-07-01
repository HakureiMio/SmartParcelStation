# 门禁认证设计

## 三种识别方式

- `CARD_UID`：PN532 读取用户实体卡或手机模拟卡 UID，由 gateway 查询本地有效凭证。
- `GATE_NFC_TAG`：用户手机读取 `sps://gate-nfc` 标签，小程序通过 server 提交用户认证请求。
- `GATE_QR`：`gate-access` 显示 gateway 签发的二维码，小程序扫码后通过 server 提交用户认证请求。

职责边界：server 识别小程序用户；gateway 最终判断是否放行；`gate-access` 只显示二维码、读取 UID、轮询并显示结果。小程序不显示最终“已放行”，只提示“认证已提交，请查看门禁屏幕”。

## 卡补办流程

1. 员工给用户绑定新卡。
2. Server 将旧 `ACTIVE` 卡改为 `REPLACED`。
3. Server 下发 `USER_ACCESS_CREDENTIAL_DISABLED` 与 `USER_ACCESS_CREDENTIAL_UPSERT`。
4. Gateway 执行 sync-pull，更新本地凭证。
5. 旧卡刷卡返回 `DENIED`。
6. 新卡仅在用户仍有 `WAITING_PICKUP` 包裹时返回 `GRANTED`。

门禁 NFC、门禁 QR 和用户门禁卡最终遵循相同的 gateway 放行规则，但它们的用户识别来源不同。详细 payload 契约见 [nfc_tag_payloads.md](nfc_tag_payloads.md)。
