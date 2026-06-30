#!/usr/bin/env bash
# =============================================================================
# SmartParcel Station - VPS 更新脚本
# =============================================================================
# 使用方式：
#   cd SmartParcelStation
#   bash deploy/vps/update.sh
#
# 说明：
#   拉取最新代码 -> 重新构建镜像 -> 执行迁移 -> 重启服务 -> 健康检查
# =============================================================================

set -euo pipefail

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- 定位仓库根目录 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SERVER_DIR="$REPO_ROOT/smartparcel-server"

info "SmartParcel Station VPS 更新脚本"
info "仓库根目录: $REPO_ROOT"

# ---- 拉取最新代码 ----
info "拉取最新代码..."
cd "$REPO_ROOT"
git pull

# ---- 重新构建并启动 ----
info "重新构建并启动服务..."
cd "$SERVER_DIR"
docker compose -f docker-compose.vps.yml up -d --build

info "等待服务就绪..."
sleep 5

# ---- 执行数据库迁移（以防有新的 migration） ----
info "执行数据库迁移..."
docker compose -f docker-compose.vps.yml exec -T server python -m alembic upgrade head || warn "数据库迁移可能已是最新，继续..."

# ---- 健康检查 ----
HEALTHCHECK_SCRIPT="$REPO_ROOT/deploy/vps/healthcheck.sh"
if [ -f "$HEALTHCHECK_SCRIPT" ]; then
    bash "$HEALTHCHECK_SCRIPT" || warn "健康检查发现问题，请查看上方日志。"
else
    warn "未找到 healthcheck.sh，跳过健康检查。"
fi

# ---- 输出容器状态 ----
echo ""
info "当前容器状态:"
cd "$SERVER_DIR"
docker compose -f docker-compose.vps.yml ps

echo ""
info "更新完成！"
info "查看日志: docker compose -f docker-compose.vps.yml logs -f server"
