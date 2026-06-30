# Security Demo — Gateway HMAC 安全通信演示

演示 server-gateway 通信的 HMAC-SHA256 签名、防篡改、防重放能力。

## 前提条件

1. Server 已部署并运行（本地或 VPS）。
2. 已在 server 上创建 gateway 并获取 `GATEWAY_CODE` 和 `GATEWAY_SECRET`。

创建 gateway 的方法：

```bash
# 方式一：使用 bootstrap token 通过 API 注册
# 需要先有 station，然后调用 POST /api/v1/dev/default-users 初始化账号

# 方式二：使用注册凭证流程
# 1. server admin 创建 registration token
# 2. gateway 调用 /api/v1/gateways/bootstrap/activate 激活
# 3. 保存返回的 gateway_secret
```

## 配置环境变量

```bash
# 本地 server
export SERVER_BASE_URL=http://127.0.0.1:18000

# VPS server（配置了域名和 HTTPS 后）
# export SERVER_BASE_URL=https://api.example.com

# 替换为真实的 gateway 信息
export GATEWAY_CODE=GW-DEV-001
export GATEWAY_SECRET=<your-gateway-secret>
```

## 运行演示

### 1. 正常请求

```bash
python scripts/security_demo/valid_gateway_request.py
```

预期：`200 OK`。server 接受心跳，更新 gateway 最后在线时间。

### 2. 篡改 Body 攻击

```bash
python scripts/security_demo/tampered_body_request.py
```

脚本用 body-A 计算了哈希和签名，但实际发送 body-B。
预期：`401 Invalid gateway body hash`。

**安全原理**：签名包含了 `X-Gateway-Body-SHA256`，如果 body 被篡改，哈希不匹配，签名验证也无法通过。

### 3. Nonce 重放攻击

```bash
python scripts/security_demo/replay_nonce_request.py
```

脚本使用相同的 timestamp 和 nonce 发送两次请求。
预期：第一次 `200 OK`，第二次 `401 Replay gateway nonce`。

**安全原理**：server 在 `gateway_nonces` 表中记录已使用的 nonce，重复使用会被拒绝。过期的 nonce 会被自动清理（按 `GATEWAY_SIGNATURE_TOLERANCE_SECONDS`）。

### 4. 错误签名攻击

```bash
python scripts/security_demo/invalid_signature_request.py
```

脚本使用错误的 secret（模拟攻击者猜测的密钥）计算签名。
预期：`401 Invalid gateway signature`。

**安全原理**：签名由 `HMAC-SHA256(secret, method + path + timestamp + nonce + body_sha256)` 生成，不知道真实 secret 无法生成有效签名。

## 签名算法

```
签名内容 = METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + BODY_SHA256
签名结果 = HMAC-SHA256(secret, 签名内容) → hex digest
```

请求头：

| Header | 说明 |
|--------|------|
| `X-Gateway-Code` | gateway 标识 |
| `X-Gateway-Timestamp` | Unix 秒级时间戳 |
| `X-Gateway-Nonce` | 随机一次性字符串 |
| `X-Gateway-Body-SHA256` | 请求体 SHA256 hex |
| `X-Gateway-Signature` | 以上所有字段 + secret 的 HMAC-SHA256 |

## 安全审计

所有认证失败事件会记录到 `security_audit_events` 表，包括：
- 事件类型 (`gateway_auth_failure`)
- 来源 IP
- gateway code
- 请求路径
- 失败原因 (missing_header / unknown_gateway / expired_timestamp / invalid_body_hash / invalid_signature / replay_nonce)
- 时间戳

可以通过数据库查询查看安全审计记录：

```bash
docker exec smartparcel-mysql mysql -u smartparcel -p smartparcel -e \
  "SELECT * FROM security_audit_events ORDER BY created_at DESC LIMIT 20;"
```
