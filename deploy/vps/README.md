# SmartParcel Station - VPS 部署指南

## 1. 环境要求

- **操作系统**: Ubuntu 22.04 / 24.04 (推荐)
- **Docker**: 26+
- **Docker Compose Plugin**: v2+
- **Git**: 2.40+
- **最低配置**: 1 vCPU, 1 GB RAM, 10 GB SSD

### 安装 Docker (Ubuntu)

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker $USER
# 重新登录使权限生效

# 安装 Docker Compose Plugin
sudo apt-get update
sudo apt-get install -y docker-compose-plugin

# 验证
docker --version
docker compose version
```

### 安装 Git

```bash
sudo apt-get install -y git
```

## 2. 首次部署

### 2.1 克隆仓库

**公开仓库**：
```bash
git clone https://github.com/HakureiMio/SmartParcelStation.git
cd SmartParcelStation
```

**私有仓库**（需要 GitHub PAT 或 SSH Key）：

方式一 — 使用 Personal Access Token：
```bash
# 在 GitHub Settings > Developer settings > Personal access tokens 创建 token
# 权限: repo (Full control)
git clone https://<your-username>:<your-pat>@github.com/HakureiMio/SmartParcelStation.git
```

方式二 — 使用 SSH Key：
```bash
ssh-keygen -t ed25519 -C "vps-deploy"
cat ~/.ssh/id_ed25519.pub
# 将公钥添加到 GitHub Settings > SSH and GPG keys
git clone git@github.com:HakureiMio/SmartParcelStation.git
```

> ⚠️ **不要把 PAT 写进仓库文件！**

### 2.2 运行部署脚本

```bash
cd SmartParcelStation
bash deploy/vps/deploy.sh
```

首次运行会生成 `smartparcel-server/.env` 文件并提示编辑。

### 2.3 修改配置

```bash
nano smartparcel-server/.env
```

**必须修改的值**（标注了 `CHANGE-ME`）：

| 变量 | 说明 |
|------|------|
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 |
| `MYSQL_PASSWORD` | 应用数据库密码 |
| `DEFAULT_GATEWAY_SECRET` | gateway HMAC 签名密钥 |
| `ADMIN_BOOTSTRAP_TOKEN` | 管理员引导 token |
| `EMQX_DASHBOARD_PASSWORD` | EMQX Dashboard 密码 |
| `PUBLIC_BASE_URL` | 你的公网 HTTPS 域名 |

### 2.4 再次运行部署

```bash
bash deploy/vps/deploy.sh
```

服务启动后，验证：

```bash
curl -fsS http://127.0.0.1:18000/api/v1/health
curl -fsS http://127.0.0.1:18000/api/v1/version
```

## 3. 更新部署

```bash
cd SmartParcelStation
bash deploy/vps/update.sh
```

此脚本会：
1. 拉取最新代码 (`git pull`)
2. 重新构建镜像
3. 执行数据库迁移
4. 重启服务
5. 运行健康检查

## 4. 健康检查

```bash
bash deploy/vps/healthcheck.sh
```

检查内容：
- server health 接口
- server version 接口
- MySQL 容器状态
- EMQX 容器状态

## 5. 查看日志

```bash
cd smartparcel-server
docker compose -f docker-compose.vps.yml logs -f server
```

查看特定容器日志：
```bash
docker compose -f docker-compose.vps.yml logs -f mysql
docker compose -f docker-compose.vps.yml logs -f emqx
```

## 6. 停止服务

```bash
cd smartparcel-server
docker compose -f docker-compose.vps.yml down
```

停止但保留数据卷：
```bash
docker compose -f docker-compose.vps.yml down
```

停止并删除数据卷（⚠️ 数据不可恢复）：
```bash
docker compose -f docker-compose.vps.yml down -v
```

## 7. 容器管理

```bash
cd smartparcel-server

# 查看容器状态
docker compose -f docker-compose.vps.yml ps

# 重启单个服务
docker compose -f docker-compose.vps.yml restart server

# 查看所有日志
docker compose -f docker-compose.vps.yml logs
```

## 8. 端口安全建议

| 端口 | 服务 | 绑定地址 | 公网暴露 |
|------|------|----------|----------|
| 80/443 | Nginx / Caddy | 0.0.0.0 | ✅ 开放 |
| 18000 | Server API | 127.0.0.1 | ❌ 不直接暴露 |
| 3306 | MySQL | 127.0.0.1 | ❌ 不暴露 |
| 1883 | MQTT | 127.0.0.1 | ❌ 不暴露 |
| 18083 | EMQX Dashboard | 127.0.0.1 | ❌ 不暴露 |
| 8080 | phpMyAdmin | 127.0.0.1 | ❌ 默认禁用 |

**规则**：
- 公网只开放 80/443。
- MySQL、EMQX Dashboard、phpMyAdmin 默认绑定本机 (`127.0.0.1`)。
- 如果需要远程访问这些服务，使用 SSH tunnel：
  ```bash
  ssh -L 3306:127.0.0.1:3306 -L 18083:127.0.0.1:18083 user@your-vps
  ```

### EMQX MQTT 公网暴露说明

当前 EMQX MQTT 端口 (1883) 仅绑定 `127.0.0.1`。如果 gateway 需要从公网通过 MQTT 连接，需要：
1. 启用 TLS (8883)
2. 配置客户端证书认证
3. 修改端口绑定为 `0.0.0.0`
4. 在 EMQX Dashboard 中配置认证规则

> ⚠️ **不要将未加密的 MQTT 直接暴露公网。**

## 9. 域名和 HTTPS

### 9.1 配置 DNS

将你的域名（如 `api.example.com`）A 记录指向 VPS IP。

### 9.2 使用 Nginx + Certbot

```bash
# 安装
sudo apt-get install -y nginx certbot python3-certbot-nginx

# 复制配置
sudo cp deploy/vps/nginx.smartparcel.conf.example /etc/nginx/sites-available/smartparcel
# 编辑 server_name
sudo nano /etc/nginx/sites-available/smartparcel

# 启用站点
sudo ln -s /etc/nginx/sites-available/smartparcel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 获取 SSL 证书
sudo certbot --nginx -d api.example.com
```

### 9.3 使用 Caddy (推荐，自动 HTTPS)

```bash
sudo apt-get install -y caddy

# 配置
echo "api.example.com {
    reverse_proxy 127.0.0.1:18000
}" | sudo tee /etc/caddy/Caddyfile

sudo systemctl reload caddy
```

### 9.4 更新 PUBLIC_BASE_URL

证书配置完成后，更新 `.env`：
```bash
nano smartparcel-server/.env
# 修改 PUBLIC_BASE_URL=https://api.example.com
```

然后重启 server：
```bash
cd smartparcel-server
docker compose -f docker-compose.vps.yml up -d --build server
```

## 10. 数据备份提醒

MySQL 数据存储在 Docker volume `mysql_data` 中。

### 备份

```bash
# 导出 SQL
docker exec smartparcel-mysql mysqldump -u root -p smartparcel > smartparcel_backup_$(date +%Y%m%d).sql

# 或备份整个 volume
docker run --rm -v smartparcel-server_mysql_data:/data -v $(pwd):/backup alpine tar czf /backup/mysql_data_backup_$(date +%Y%m%d).tar.gz -C /data .
```

### 升级前建议

1. 备份数据库
2. 记录当前版本号
3. 执行 `bash deploy/vps/update.sh`

## 11. 故障排查

### 查看 server 日志
```bash
cd smartparcel-server
docker compose -f docker-compose.vps.yml logs --tail=100 server
```

### 进入容器调试
```bash
docker exec -it smartparcel-server bash
```

### 手动执行数据库迁移
```bash
docker exec smartparcel-server python -m alembic upgrade head
```

### 检查数据库连接
```bash
docker exec smartparcel-mysql mysqladmin ping -h 127.0.0.1 -u root -p
```

### 重置全部数据
```bash
cd smartparcel-server
docker compose -f docker-compose.vps.yml down -v
docker compose -f docker-compose.vps.yml up -d --build
```

### 私有仓库拉取问题

如果 `git pull` 在 VPS 上失败（认证过期）：
```bash
# PAT 方式
git remote set-url origin https://<your-username>:<your-pat>@github.com/HakureiMio/SmartParcelStation.git

# SSH 方式
git remote set-url origin git@github.com:HakureiMio/SmartParcelStation.git
```

## 12. 安全通信设计概要

```
┌─────────────────┐     HTTPS + HMAC      ┌──────────────────┐
│  smartparcel-    │ ◄──────────────────► │  smartparcel-     │
│  gateway         │   X-Gateway-* 请求头  │  server           │
│  (本地网关)       │                      │  (VPS 中心服务器)  │
└─────────────────┘                      └──────────────────┘
                                                  ▲
                                                  │ HTTPS
                                                  │
                                         ┌────────┴────────┐
                                         │  smartparcel-     │
                                         │  miniprogram      │
                                         │  (微信小程序)      │
                                         └──────────────────┘
```

- **小程序 → Server**: HTTPS + 认证凭证
- **Gateway → Server**: HTTPS + HMAC-SHA256 + Timestamp + Nonce + Body SHA256
- **Server 校验**: 签名、防篡改 (body hash)、防重放 (nonce)、时间有效性 (timestamp)
- **密钥分离**: 小程序不保存 gateway secret、server secret、数据库密码或微信 appsecret

安全演示脚本位于 `smartparcel-server/scripts/security_demo/`。
