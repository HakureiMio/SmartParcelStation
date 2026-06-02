# SmartParcel 公网 HTTPS 实验部署说明

本文档用于阶段 A 之后的公网 HTTPS 实验。当前推荐结构是 HTTPS 负责传输加密与服务器身份认证，HMAC 请求签名负责网关身份认证、消息完整性和重放攻击防护。

## 推荐结构

```text
ARM Gateway
  -> HTTPS
sps.example.com
  -> Caddy / Nginx 反向代理
  -> FastAPI server:18000
  -> MySQL / EMQX 仅本机或内网访问
```

公网只建议开放 `80/443`。不要把 MySQL `3306`、EMQX `1883`、EMQX Dashboard `18083` 暴露到公网。FastAPI `18000` 建议只监听 `127.0.0.1`，或通过防火墙限制为仅反向代理可访问。

## Caddy 示例

```caddyfile
sps.example.com {
    reverse_proxy 127.0.0.1:18000
}
```

Caddy 可以自动申请和续期 Let's Encrypt 证书。部署前需要把域名 A 记录指向服务器公网 IP，并确保服务器开放 `80/443`。

## Nginx 示例

```nginx
server {
    listen 80;
    server_name sps.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name sps.example.com;

    ssl_certificate /etc/letsencrypt/live/sps.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sps.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:18000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

证书可以用 Certbot 或其他成熟 ACME 客户端申请。不要在应用内自己实现 TLS。

## HTTPS 与 HMAC 的分工

普通 HTTPS 让 gateway 验证 server 证书，防止中间人窃听和篡改。它不等于 gateway 身份认证。

gateway 身份认证由应用层 HMAC 完成。每台 gateway 使用独立 `GATEWAY_SECRET`，server 按 `X-Gateway-Code` 找到对应密钥并校验签名。

mTLS 是更强的双向证书认证方案，后续可以加入，但本阶段不强制实现。

## HMAC 签名规范

请求头：

```text
X-Gateway-Code
X-Gateway-Timestamp
X-Gateway-Nonce
X-Gateway-Body-SHA256
X-Gateway-Signature
```

签名原文：

```text
METHOD + "\n" +
PATH + "\n" +
TIMESTAMP + "\n" +
NONCE + "\n" +
BODY_SHA256
```

规则：

- `METHOD` 使用大写，例如 `GET`、`POST`。
- `PATH` 只包含 API path，例如 `/api/v1/gateways/GW001/sync/push`，不包含域名，避免反向代理影响签名。
- JSON body 使用稳定序列化：`sort_keys=True`、`separators=(",", ":")`、UTF-8。
- GET 或无 body 请求使用空字节的 SHA256。
- server 默认允许 `X-Gateway-Timestamp` 与当前时间相差 300 秒，可用 `GATEWAY_SIGNATURE_TOLERANCE_SECONDS` 调整。
- 同一 gateway 在有效窗口内不能重复使用同一个 nonce，重复会返回 `401`。

ARM gateway 需要保持系统时间准确，建议启用 NTP 或 `systemd-timesyncd`。

## 密钥管理

本地示例里的 `gw-secret-demo`、`change-me-local-only` 只能用于开发。公网实验前为每台 gateway 单独生成强随机密钥：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

不要把真实密钥提交到 Git。`.env` 已在 `.gitignore` 中忽略。

当前 `gateways.device_secret_hash` 字段名是早期遗留名，阶段 A 中实际存放共享 HMAC 密钥。HMAC 验证需要原始密钥，不能只存普通 hash 后再验证。后续更正式的方案应改名为 `device_secret` / `shared_secret`，并配合 KMS、加密列或环境隔离做密钥保护。

## 管理端访问控制

server 终端面板建议只在服务器本机或受信网络运行，不通过公网开放。管理接口当前使用开发管理员请求头或 `X-Admin-Bootstrap-Token` 做最小保护，公网实验时不要把 bootstrap token 设为默认值。

正式环境仍需要补充 JWT/微信登录、正式 RBAC、操作审计、集中日志和脱敏策略。

## 实验步骤

1. 在 server 上启动 MySQL / EMQX，但不要把它们暴露公网。
2. 运行 `python -m alembic upgrade head`。
3. 用 Caddy 或 Nginx 把 `https://sps.example.com` 反代到 `127.0.0.1:18000`。
4. server `.env` 设置 `PUBLIC_BASE_URL=https://sps.example.com`，并设置强 `ADMIN_BOOTSTRAP_TOKEN`。
5. 在 gateway `.env` 设置 `SERVER_BASE_URL=https://sps.example.com`、`GATEWAY_CODE`、独立强 `GATEWAY_SECRET`。
6. 在 server 面板或 API 中注册 gateway，`device_secret_hash` 填入该 gateway 的共享密钥。
7. 在 gateway 侧运行 `python -m gateway.main health`、`heartbeat`、`sync-pull`、`sync-push` 验证 HTTPS + HMAC 链路。

临时直接暴露 `18000` 不推荐，仅限短时实验，并且必须启用 HMAC、强密钥和防火墙限制。
