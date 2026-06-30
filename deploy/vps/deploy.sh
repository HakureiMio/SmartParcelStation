#!/usr/bin/env bash
# =============================================================================
# SmartParcel Station - VPS 首次部署脚本
# =============================================================================
# 使用方式：
#   git clone https://github.com/HakureiMio/SmartParcelStation.git
#   cd SmartParcelStation
#   bash deploy/vps/deploy.sh
#
# 私有仓库克隆说明：
#   VPS 克隆私有仓库需要 GitHub Personal Access Token (PAT) 或 SSH Key。
#   方式一（PAT）：
#     git clone https://<your-username>:<your-pat>@github.com/HakureiMio/SmartParcelStation.git
#   方式二（SSH）：
#     ssh-keygen -t ed25519 -C "vps-deploy"
#     将公钥添加到 GitHub SSH keys，然后：
#     git clone git@github.com:HakureiMio/SmartParcelStation.git
#   不要把 PAT 写进仓库文件！
# =============================================================================

set -euo pipefail

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- 定位仓库根目录 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

info "SmartParcel Station VPS 部署脚本"
info "仓库根目录: $REPO_ROOT"

# ---- 检查依赖 ----
if ! command -v docker &> /dev/null; then
    error "未找到 docker，请先安装 Docker。"
    error "Ubuntu 安装参考: https://docs.docker.com/engine/install/ubuntu/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    error "未找到 docker compose 插件，请先安装 Docker Compose。"
    error "Ubuntu 安装参考: sudo apt-get install docker-compose-plugin"
    exit 1
fi

info "Docker 版本: $(docker --version)"
info "Docker Compose 版本: $(docker compose version)"

# ---- 检查 .env 文件 ----
SERVER_DIR="$REPO_ROOT/smartparcel-server"
ENV_FILE="$SERVER_DIR/.env"
ENV_EXAMPLE="$SERVER_DIR/.env.vps.example"

if [ ! -f "$ENV_FILE" ]; then
    warn ".env 文件不存在，正在从 .env.vps.example 生成..."
    if [ ! -f "$ENV_EXAMPLE" ]; then
        error "找不到 $ENV_EXAMPLE，请确认仓库完整。"
        exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo ""
    warn "============================================================"
    warn "  .env 已从 .env.vps.example 生成。"
    warn "  请立即编辑 .env 文件，修改以下值："
    warn ""
    warn "    MYSQL_ROOT_PASSWORD          - MySQL root 密码"
    warn "    MYSQL_PASSWORD               - 应用数据库密码"
    warn "    DEFAULT_GATEWAY_SECRET       - gateway HMAC 密钥"
    warn "    ADMIN_BOOTSTRAP_TOKEN        - 管理员引导 token"
    warn "    EMQX_DASHBOARD_PASSWORD      - EMQX Dashboard 密码"
    warn "    PUBLIC_BASE_URL              - 你的公网 HTTPS 地址"
    warn ""
    warn "  编辑完成后，重新运行本脚本："
    warn "    nano $ENV_FILE"
    warn "    bash deploy/vps/deploy.sh"
    warn "============================================================"
    echo ""
    info "部署初始化完成，但未启动服务。请先编辑 .env 后再重新运行。"
    exit 0
fi

# ---- 读取配置用于提示 ----
PUBLIC_BASE_URL=$(grep -E '^PUBLIC_BASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || echo "")

info ".env 已存在，开始部署..."

# ---- 启动服务 ----
cd "$SERVER_DIR"

info "构建并启动所有服务..."
docker compose -f docker-compose.vps.yml up -d --build

info "等待服务就绪..."
sleep 5

# ---- 健康检查 ----
HEALTHCHECK_SCRIPT="$REPO_ROOT/deploy/vps/healthcheck.sh"
if [ -f "$HEALTHCHECK_SCRIPT" ]; then
    bash "$HEALTHCHECK_SCRIPT" || warn "健康检查发现问题，请查看上方日志。"
else
    warn "未找到 healthcheck.sh，跳过健康检查。"
fi

# ---- 输出访问信息 ----
echo ""
echo "============================================================"
info "部署完成！"
echo ""
info "本机健康检查:"
echo "  curl -fsS http://127.0.0.1:18000/api/v1/health"
echo "  curl -fsS http://127.0.0.1:18000/api/v1/version"
echo ""

# 从 PUBLIC_BASE_URL 构建提示
if [ -n "$PUBLIC_BASE_URL" ] && [ "$PUBLIC_BASE_URL" != "https://api.example.com" ]; then
    info "公网地址:"
    echo "  ${PUBLIC_BASE_URL}/api/v1/health"
    echo "  ${PUBLIC_BASE_URL}/api/v1/version"
else
    if [ "$PUBLIC_BASE_URL" = "https://api.example.com" ]; then
        warn "PUBLIC_BASE_URL 仍为默认值，请在 .env 中修改为你的真实 HTTPS 域名。"
    fi
fi

echo ""
info "查看日志:"
echo "  cd smartparcel-server"
echo "  docker compose -f docker-compose.vps.yml logs -f server"
echo ""
info "停止服务:"
echo "  cd smartparcel-server"
echo "  docker compose -f docker-compose.vps.yml down"
echo ""
info "容器状态:"
echo "  cd smartparcel-server"
echo "  docker compose -f docker-compose.vps.yml ps"
echo "============================================================"
