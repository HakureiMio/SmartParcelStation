#!/usr/bin/env bash
# =============================================================================
# SmartParcel Station - VPS 健康检查脚本
# =============================================================================
# 使用方式：
#   bash deploy/vps/healthcheck.sh
#
# 检查内容：
#   - server health 接口
#   - server version 接口
#   - MySQL 容器状态
#   - EMQX 容器状态
# =============================================================================

set -euo pipefail

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[CHECK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[FAIL]${NC} $*"; }

# ---- 定位仓库根目录 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_DIR="$REPO_ROOT/smartparcel-server"

COMPOSE_FILE="$SERVER_DIR/docker-compose.vps.yml"

HEALTH_URL="http://127.0.0.1:18000/api/v1/health"
VERSION_URL="http://127.0.0.1:18000/api/v1/version"

ALL_PASSED=true
FAILURES=()

# ---- 1. Server Health ----
info "检查 server health..."
if curl -fsS --max-time 10 "$HEALTH_URL" > /dev/null 2>&1; then
    RESPONSE=$(curl -fsS --max-time 10 "$HEALTH_URL" 2>&1)
    info "  health: $RESPONSE"
else
    error "server health 检查失败 ($HEALTH_URL)"
    ALL_PASSED=false
    FAILURES+=("server_health")
fi

# ---- 2. Server Version ----
info "检查 server version..."
if curl -fsS --max-time 10 "$VERSION_URL" > /dev/null 2>&1; then
    RESPONSE=$(curl -fsS --max-time 10 "$VERSION_URL" 2>&1)
    info "  version: $RESPONSE"
else
    error "server version 检查失败 ($VERSION_URL)"
    ALL_PASSED=false
    FAILURES+=("server_version")
fi

# ---- 3. MySQL 容器状态 ----
info "检查 MySQL 容器状态..."
if [ -f "$COMPOSE_FILE" ]; then
    if docker compose -f "$COMPOSE_FILE" ps mysql 2>/dev/null | grep -q "healthy\|Up"; then
        info "  MySQL 运行正常"
    else
        warn "  MySQL 可能未运行或状态异常"
        docker compose -f "$COMPOSE_FILE" ps mysql 2>/dev/null || true
    fi
else
    warn "  未找到 $COMPOSE_FILE，跳过 MySQL 检查。"
fi

# ---- 4. EMQX 容器状态 ----
info "检查 EMQX 容器状态..."
if [ -f "$COMPOSE_FILE" ]; then
    if docker compose -f "$COMPOSE_FILE" ps emqx 2>/dev/null | grep -q "Up"; then
        info "  EMQX 运行正常"
    else
        warn "  EMQX 可能未运行或状态异常"
        docker compose -f "$COMPOSE_FILE" ps emqx 2>/dev/null || true
    fi
else
    warn "  未找到 $COMPOSE_FILE，跳过 EMQX 检查。"
fi

# ---- 结果汇总 ----
echo ""
if [ "$ALL_PASSED" = true ]; then
    info "所有检查通过！"
else
    error "以下检查失败: ${FAILURES[*]}"
    echo ""
    warn "最近 server 日志:"
    if [ -f "$COMPOSE_FILE" ]; then
        docker compose -f "$COMPOSE_FILE" logs --tail=80 server 2>/dev/null || warn "无法获取 server 日志。"
    fi
    exit 1
fi
