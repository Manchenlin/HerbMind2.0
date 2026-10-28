#!/usr/bin/env bash
# 受限网络 / 离线环境的一键拉起（镜像用 tar 导入，绕开 Docker Hub 限速）。
#
# 用法（在仓库根目录）：
#   bash scripts/bootstrap-offline.sh /path/herbmind-images.tar /path/herbmind_data.sql.gz
#   bash scripts/bootstrap-offline.sh "" /path/herbmind_data.sql.gz      # 镜像已在本地
#
# 可选环境变量：
#   OFFLINE_MVN=1   后端用 mvn -o（本地 ~/.m2 已备齐依赖时）
#   OFFLINE_NPM=1   前端用 npm ci --offline
#   SKIP_BUILD=1    只起中间件 + 导数据，不编译
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGES="${1:-}"
DATA="${2:-}"
PG_CONTAINER="${PG_CONTAINER:-herbmind-v2-pg}"

step() { printf '\n\033[1;36m== %s\033[0m\n' "$1"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "未找到 docker：请先安装并启动 Docker Desktop"
docker info >/dev/null 2>&1 || die "Docker 守护进程未运行：先启动 Docker Desktop（等托盘图标变绿）"

if [ -n "$IMAGES" ]; then
  step "1/6 导入镜像：$IMAGES"
  [ -f "$IMAGES" ] || die "镜像包不存在：$IMAGES"
  docker load -i "$IMAGES"
else
  step "1/6 跳过镜像导入（按本地已有镜像启动）"
fi

step "2/6 启动中间件（PostgreSQL / Neo4j / Redis / Nacos）"
docker compose -f "$ROOT/docker/docker-compose.infra.yml" up -d

step "3/6 等待 PostgreSQL 就绪"
for i in $(seq 1 60); do
  if docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
    echo "PostgreSQL 就绪（第 ${i} 次探测）"
    break
  fi
  [ "$i" -eq 60 ] && die "PostgreSQL 60 次探测仍未就绪，看：docker logs $PG_CONTAINER"
  sleep 2
done

if [ -n "$DATA" ]; then
  step "4/6 导入数据快照（会先 --clean 重建）"
  [ -f "$DATA" ] || die "数据快照不存在：$DATA"
  bash "$ROOT/scripts/init-data.sh" "$DATA"
else
  step "4/6 未指定数据快照，跳过导入（可稍后：bash scripts/init-data.sh <gz>）"
fi

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  step "5/6 编译后端"
  if [ "${OFFLINE_MVN:-0}" = "1" ]; then
    (cd "$ROOT/backend" && mvn -o -DskipTests package)
  else
    (cd "$ROOT/backend" && mvn -DskipTests package)
  fi

  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    step "5.1 安装前端依赖"
    if [ "${OFFLINE_NPM:-0}" = "1" ]; then
      (cd "$ROOT/frontend" && npm ci --offline)
    else
      (cd "$ROOT/frontend" && npm install)
    fi
  fi

  step "6/6 起后端五件套"
  bash "$ROOT/scripts/run-dev.sh"
else
  step "5-6/6 SKIP_BUILD=1，跳过编译与启动"
fi

cat <<'EOF'

下一步：
  1) 前端：cd frontend && npm run dev        → http://localhost:5173
  2) 验收：bash scripts/verify-a.sh          → 43 项 curl 检查（域1）
  3) 数据冒烟：python scripts/smoke.py
  4) 日志：logs/svc-catalog.log / svc-search.log / svc-insight.log / herbmind-bff.log

⚠ 不要执行 docker compose down -v（会删数据卷，数据得重导）。
EOF
