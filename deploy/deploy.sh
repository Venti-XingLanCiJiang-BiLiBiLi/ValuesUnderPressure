#!/usr/bin/env bash
# ============================================================================
# VUP 一键部署脚本 (Docker Compose)
# ----------------------------------------------------------------------------
# 前置：云服务器已安装 Docker 与 Docker Compose 插件（v2 及以上）
#   curl -fsSL https://get.docker.com | sh   # 或发行版官方方式
#
# 用法（在仓库根目录执行）：
#   ./deploy/deploy.sh             # 拉取代码 + 构建 + 启动 + 健康检查
#   ./deploy/deploy.sh --no-pull   # 不 git pull，仅重新构建并启动
#   ./deploy/deploy.sh --logs      # 部署后跟进前端容器日志（Ctrl+C 退出）
#
# 升级流程：改代码 push 后，服务器上再跑一次 ./deploy/deploy.sh 即可。
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

# --- 参数解析 ----------------------------------------------------------------
PULL=1
FOLLOW_LOGS=0
for arg in "$@"; do
  case "$arg" in
    --no-pull) PULL=0 ;;
    --logs) FOLLOW_LOGS=1 ;;
    *)
      echo "未知参数: $arg" >&2
      echo "用法: ./deploy/deploy.sh [--no-pull] [--logs]" >&2
      exit 1
      ;;
  esac
done

# --- 依赖检查 ----------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "错误: 未找到 docker，请先安装（例如 curl -fsSL https://get.docker.com | sh）" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "错误: 未找到 docker compose 插件，请安装 Docker Compose v2" >&2
  exit 1
fi

# --- 环境文件 ----------------------------------------------------------------
if [ ! -f .env ]; then
  echo "[deploy] 未发现 .env，从 deploy/.env.example 复制一份"
  cp deploy/.env.example .env
fi

# --- 拉取最新代码 ------------------------------------------------------------
if [ "$PULL" = "1" ]; then
  echo "[deploy] git pull ..."
  git pull --ff-only
fi

# --- 构建并启动 --------------------------------------------------------------
echo "[deploy] docker compose up -d --build ..."
docker compose up -d --build --remove-orphans

# --- 健康检查（等待后端健康）--------------------------------------------------
echo "[deploy] 等待后端健康检查就绪 ..."
for i in $(seq 1 30); do
  HEALTH=$(docker compose ps backend --format '{{.Health}}' 2>/dev/null || true)
  if [ "$HEALTH" = "healthy" ]; then
    echo "[deploy] 后端已就绪 ✓"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[deploy] 警告: 后端未在预期时间内就绪，请排查：" >&2
    echo "  docker compose logs --tail=50 backend" >&2
    echo "  docker compose ps" >&2
  fi
  sleep 3
done

# --- 汇总 --------------------------------------------------------------------
PORT=$(grep -E '^VUP_PORT=' .env 2>/dev/null | tail -n1 | cut -d= -f2 | tr -d '[:space:]"' || true)
PORT=${PORT:-8080}
echo ""
echo "====================== 部署完成 ======================"
echo "  前端页面:   http://<服务器IP>:$PORT"
echo "  API 文档:   http://<服务器IP>:$PORT/docs"
echo "  健康检查:   http://<服务器IP>:$PORT/api/health"
echo "  ----------"
echo "  数据卷:     docker volume ls | grep vup"
echo "  备份:       ./deploy/backup.sh"
echo "  查看日志:   docker compose logs -f [frontend|backend]"
echo "  升级:       ./deploy/deploy.sh"
echo "======================================================"

if [ "$FOLLOW_LOGS" = "1" ]; then
  echo "[deploy] 跟进前端日志（Ctrl+C 退出）..."
  docker compose logs -f frontend
fi
