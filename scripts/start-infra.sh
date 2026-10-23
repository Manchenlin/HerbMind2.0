#!/usr/bin/env bash
# 一键启动 HerbMind v2 中间件（PostgreSQL+pgvector / Neo4j / Redis / Nacos）
#
# 用法：
#   bash scripts/start-infra.sh             # 启动并等到全部就绪（推荐）
#   bash scripts/start-infra.sh --status    # 只看当前状态 + 数据体检，不动容器
#   bash scripts/start-infra.sh --no-wait   # 只发启动命令，不等就绪
#   bash scripts/start-infra.sh --restart   # 先重启容器再等就绪（改了 compose 配置后用）
#
# 前置：Docker Desktop 已启动（右下角图标变绿）
# 安全：只做 up -d / restart，**永不执行 down -v**（不会删数据卷）
#
# 说明：容器名统一 herbmind-v2-*（v1 旧栈 herbmind-pg 等一律不碰）
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.infra.yml"

# 服务名 / 容器名 / 端口，三行一一对应（bash 3 也能跑，不用关联数组）
SERVICES=(postgres neo4j redis nacos)
CONTAINERS=(herbmind-v2-pg herbmind-v2-neo4j herbmind-v2-redis herbmind-v2-nacos)
PORTS=("5432" "7474/7687" "6379" "8848/9848")

PG_CONTAINER=herbmind-v2-pg
PG_DB="${PG_DB:-herbmind}"
PG_USER="${PG_USER:-postgres}"

# ---------------- 参数 ----------------
MODE=up
WAIT=1
for arg in "$@"; do
  case "$arg" in
    --status)  MODE=status ;;
    --no-wait) WAIT=0 ;;
    --restart) MODE=restart ;;
    -h|--help)
      # 只打印文件头的注释块（遇到第一条非注释行就停）
      awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
      exit 0 ;;
    *)
      echo "未知参数：$arg（用 --help 看用法）"
      exit 1 ;;
  esac
done

# ---------------- 0. 前置检查 ----------------
echo "== 0/4 检查环境 =="

if ! command -v docker > /dev/null 2>&1; then
  echo "  ✗ 找不到 docker 命令"
  echo "    请先安装 Docker Desktop 并启动它（右下角图标变绿）"
  exit 1
fi

# docker CLI 装好 ≠ 引擎在跑，这里查的是引擎
if ! docker info > /dev/null 2>&1; then
  echo "  ✗ Docker 引擎没在运行（命令能看到，但连不上引擎）"
  echo "    请打开 Docker Desktop，等右下角图标变绿，再重新执行本脚本"
  exit 1
fi
echo "  ✓ Docker 已运行（$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '版本未知')）"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "  ✗ 找不到编排文件：$COMPOSE_FILE"
  exit 1
fi

# compose：优先插件版 docker compose（v2），退回独立版 docker-compose（v1）
if docker compose version > /dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose > /dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "  ✗ 找不到 docker compose（插件版和独立版都没有）"
  echo "    Docker Desktop 自带 compose；若用的是别的安装方式，请另装 docker-compose"
  exit 1
fi

# Git Bash 下把路径转成 Windows 风格，docker.exe 一定能认；非 Git Bash 保持原样
if WDIR="$(cd "$(dirname "$COMPOSE_FILE")" && pwd -W 2>/dev/null)"; then
  COMPOSE_PATH="$WDIR/$(basename "$COMPOSE_FILE")"
else
  COMPOSE_PATH="$COMPOSE_FILE"
fi

dc() { "${COMPOSE_CMD[@]}" -f "$COMPOSE_PATH" "$@"; }

health_of() {
  # 没在跑就直接报容器状态（exited/created/dead），避免把"已停止但残留 unhealthy"看成就绪失败
  docker inspect -f '{{if ne .State.Status "running"}}{{.State.Status}}{{else if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1" 2>/dev/null || echo "not-found"
}

print_state() {
  local i c s mark
  for i in "${!CONTAINERS[@]}"; do
    c="${CONTAINERS[$i]}"
    s="$(health_of "$c")"
    case "$s" in
      healthy|running)          mark="✓" ;;
      starting)                 mark="…" ;;
      exited|created|dead|paused) mark="✗"; s="已停止" ;;
      not-found)                mark="✗"; s="不存在" ;;
      *)                        mark="✗" ;;
    esac
    printf '  %s %-22s %-10s %s\n' "$mark" "$c" "$s" "端口 ${PORTS[$i]}"
  done
}

# ---------------- 数据体检（只读，不会改数据） ----------------
data_check() {
  if [ "$(health_of "$PG_CONTAINER")" != "healthy" ]; then
    echo "  （跳过：$PG_CONTAINER 还没就绪）"
    return 0
  fi
  local sql out
  sql="SELECT 'tables='||(SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE')
       ||'  formula='||(SELECT count(*) FROM formula)
       ||'  case_record='||(SELECT count(*) FROM case_record)
       ||'  classic_quote='||(SELECT count(*) FROM classic_quote)
       ||'  content_unit='||(SELECT count(*) FROM content_unit)
       ||'  vectors='||(SELECT count(*) FROM content_unit WHERE embedding IS NOT NULL);"
  if out="$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -t -A -c "$sql" 2>&1)"; then
    echo "  $out"
    case "$out" in
      *"formula=0"*)
        echo "  ⚠ 库是空的（41 张表在，但没有数据）→ 导快照："
        echo "      bash scripts/init-data.sh <herbmind_data.sql 或 .sql.gz>" ;;
    esac
  else
    echo "  ⚠ 查询失败（可能首次初始化还没跑完）。10 秒后重跑本脚本即可。原始报错："
    echo "$out" | head -3 | sed 's/^/      /'
  fi
}

# ---------------- 只查状态 ----------------
if [ "$MODE" = "status" ]; then
  echo
  echo "== 容器状态 =="
  print_state
  echo
  echo "== 数据体检（只读） =="
  data_check
  echo
  echo "提示：全量状态用 ${COMPOSE_CMD[*]} -f docker/docker-compose.infra.yml ps"
  exit 0
fi

# ---------------- 1. 启动 ----------------
echo
echo "== 1/4 启动容器 =="
echo "  编排文件：docker/docker-compose.infra.yml（项目名 herbmind-v2）"
if [ "$MODE" = "restart" ]; then
  echo "  模式：restart（重启已有容器）"
  if ! dc restart "${SERVICES[@]}" > /tmp/herbmind-up.log 2>&1; then
    echo "  ✗ 重启失败，原始输出："
    sed 's/^/      /' /tmp/herbmind-up.log
    exit 1
  fi
else
  echo "  模式：up -d（已存在则复用，不存在则创建；只建不删）"
  if ! dc up -d "${SERVICES[@]}" > /tmp/herbmind-up.log 2>&1; then
    echo "  ✗ 启动失败，原始输出："
    sed 's/^/      /' /tmp/herbmind-up.log
    echo
    echo "  常见原因："
    echo "    1) 端口被占用（5432/7474/7687/6379/8848/9848）→ 查占用："
    echo "         netstat -ano | findstr \":5432\""
    echo "    2) 镜像没下载完 / 拉取失败（首次要联网拉 4 个镜像）→ 看上面输出的第 1 行错误"
    echo "    3) 磁盘满 → docker system df 看空间"
    exit 1
  fi
fi
echo "  ✓ 启动命令已下发"

# ---------------- 2. 等待就绪 ----------------
echo
echo "== 2/4 等待就绪 =="
echo "  Nacos / Neo4j 首次启动要 30~60 秒，耐心等；Ctrl+C 可中断（不影响已启动的容器）"

if [ "$WAIT" -eq 0 ]; then
  echo "  （--no-wait：跳过等待）"
else
  TIMEOUT="${WAIT_TIMEOUT:-180}"
  START=$SECONDS
  while :; do
    pending=0
    for c in "${CONTAINERS[@]}"; do
      s="$(health_of "$c")"
      case "$s" in
        healthy|running) ;;
        *) pending=$((pending + 1)) ;;
      esac
    done
    [ "$pending" -eq 0 ] && break
    if [ $((SECONDS - START)) -ge "$TIMEOUT" ]; then
      echo "  ⚠ 等了 ${TIMEOUT} 秒仍有 $pending 个没就绪"
      break
    fi
    sleep 2
  done
fi

print_state

# 有没起来的，把日志尾巴打出来，省得人自己去翻
failed=()
for c in "${CONTAINERS[@]}"; do
  s="$(health_of "$c")"
  case "$s" in
    healthy|running|starting) ;;
    *) failed+=("$c") ;;
  esac
done
if [ "${#failed[@]}" -gt 0 ]; then
  echo
  echo "  ↓ 以下容器没就绪，附最近日志（各 15 行）找原因："
  for c in "${failed[@]}"; do
    echo "  ---- $c ----"
    docker logs --tail 15 "$c" 2>&1 | sed 's/^/      /'
  done
  echo
  echo "  实在不行（⚠ 不会删数据）："
  echo "    ${COMPOSE_CMD[*]} -f docker/docker-compose.infra.yml down    # 只删容器，不删卷"
  echo "    bash scripts/start-infra.sh                                # 再启动"
  exit 1
fi

# ---------------- 3. 容器状态 ----------------
echo
echo "== 3/4 容器状态 =="
dc ps 2>/dev/null | sed 's/^/  /' || true

# ---------------- 4. 数据体检 ----------------
echo
echo "== 4/4 数据体检（只读） =="
data_check

# ---------------- 收尾 ----------------
echo
echo "完成 ✅ 中间件已就绪"
echo "  下一步（二选一）："
echo "    · 库里没数据 → bash scripts/init-data.sh <herbmind_data.sql 或 .sql.gz>"
echo "    · 库里有数据 → bash scripts/run-dev.sh   # 起后端 8082/8090/8080"
echo "  连接串（本地开发）："
echo "    PostgreSQL  jdbc:postgresql://localhost:5432/herbmind     (postgres/postgres)"
echo "    Neo4j       bolt://localhost:7687                         (neo4j/herbmind123)"
echo "    Redis       localhost:6379                                (无密码)"
echo "    Nacos       http://localhost:8848/nacos                   (默认 nacos/nacos)"
