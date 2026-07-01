# 端到端演示脚本

脚本按编号执行。它们使用 Bash、`curl` 和环境变量，不保存 token，也不启动或修改 ESP32 固件。

```bash
export SERVER_BASE_URL="http://127.0.0.1:18000/api/v1"
export GATEWAY_BASE_URL="http://127.0.0.1:19000"
export ADMIN_BOOTSTRAP_TOKEN="change-this"
export GATE_READER_TOKEN="change-this-reader-token"
export USER_TOKEN="<login response token>"
export STAFF_TOKEN="<login response token>"
```

`01`–`03` 检查并初始化 server；`04`–`05` 登录；`06` 同步 gateway；`07`–`10` 检查门禁接口；`11` 发起补卡。完整的小程序 NFC/QR、取件和硬件操作见 [最终演示文档](../../docs/demo_three_gate_auth_methods.md)。
