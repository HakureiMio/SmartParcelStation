# NFC 设计说明

## 标签 payload

优先写入 JSON 文本：

```json
{
  "type": "SPS_SMART_TAG",
  "payload_version": 1,
  "station_id": "1",
  "tag_id": "TAG001",
  "tag_nfc_id": "NFC_TAG_001"
}
```

也支持 URI：

```text
sps://tag?station_id=1&tag_id=TAG001&tag_nfc_id=NFC_TAG_001
```

## fallback 原则

- 不假设所有手机都能读写 NFC。
- NFC 不可用时，页面提供 mock 与手动输入。
- 写入失败不阻断员工通过手动输入绑定标签。
- 写入前展示 payload 并要求员工确认；写入后尝试读取验证。
