#!/usr/bin/env bash
# 导入数据快照（.sql 或 .sql.gz 均可）+ 建图。
#
# 用法：
#   bash scripts/init-data.sh <快照文件>            # 直接导入（表已存在会报错）
#   bash scripts/init-data.sh <快照文件> --reset    # 先清空库再导入（推荐用于重来）
#
# 前置：中间件已起（docker compose -f docker/docker-compose.infra.yml up -d）
#       —— 首次启动会自动建好 41 张表（database/pg/00→04）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 解析参数：第一个非 -- 开头的是快照路径，--reset 走重置分支
SNAP=""
RESET=0
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=1 ;;
    -*)      echo "未知参数：$arg"; exit 1 ;;
    *)       [ -z "$SNAP" ] && SNAP="$arg" ;;
  esac
done

CONTAINER="${PG_CONTAINER:-herbmind-v2-pg}"
DB="${PG_DB:-herbmind}"
DBUSER="${PG_USER:-postgres}"

if [ -z "$SNAP" ] || [ ! -f "$SNAP" ]; then
  echo "用法：bash scripts/init-data.sh <herbmind_data.sql | herbmind_data.sql.gz> [--reset]"
  exit 1
fi

# ---------- 前置检查：容器必须在跑，否则报错只给一串容器 ID，新手看不懂 ----------
echo "== 0/3 检查容器 =="
if ! docker inspect "$CONTAINER" > /dev/null 2>&1; then
  echo "  ✗ 找不到容器 $CONTAINER"
  echo "    请先执行：docker compose -f docker/docker-compose.infra.yml up -d"
  exit 1
fi
STATUS="$(docker inspect -f '{{.State.Status}}' "$CONTAINER")"
if [ "$STATUS" != "running" ]; then
  echo "  ✗ 容器 $CONTAINER 当前状态是 $STATUS，没有在运行"
  echo "    请先执行：docker start $CONTAINER"
  echo "    或（若容器不存在）：docker compose -f docker/docker-compose.infra.yml up -d"
  exit 1
fi
echo "  ✓ $CONTAINER 运行中"

# 等数据库真正可接受连接（容器 Up ≠ 数据库就绪）
for i in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -U "$DBUSER" -d "$DB" > /dev/null 2>&1; then
    echo "  ✓ 数据库已就绪"
    break
  fi
  [ "$i" -eq 30 ] && { echo "  ✗ 等待数据库超时（60 秒）"; exit 1; }
  sleep 2
done

# ---------- 可选：清空库 ----------
if [ "$RESET" -eq 1 ]; then
  echo "== 重置库（--reset）=="
  # 把 client_min_messages 调到 warning，屏蔽 DROP CASCADE 那一大串 NOTICE
  docker exec "$CONTAINER" psql -U "$DBUSER" -d "$DB" -q \
    -c "SET client_min_messages = warning;" \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" > /dev/null
  echo "  已清空（41 张表已删除，将由快照重建）"
fi

# ---------- 第 1 步：导入 ----------
# 自动识别 .gz / .sql：压缩包解压后喂给 psql，纯文本直接喂
echo "== 1/3 导入快照 =="
echo "  文件：$SNAP（$(du -h "$SNAP" | cut -f1)）"
case "$SNAP" in
  *.gz)
    echo "  格式：gzip 压缩"
    DECOMPRESS=(gunzip -c)
    ;;
  *.sql)
    echo "  格式：纯文本 SQL"
    DECOMPRESS=(cat)
    ;;
  *)
    echo "  ✗ 不认识的格式：$SNAP（只支持 .sql 或 .sql.gz）"
    exit 1
    ;;
esac
"${DECOMPRESS[@]}" "$SNAP" | docker exec -i -e PGCLIENTENCODING=UTF8 "$CONTAINER" \
  psql -q -v ON_ERROR_STOP=1 -U "$DBUSER" -d "$DB" > /dev/null || {
    echo
    echo "  ✗ 导入失败。最常见的原因是【库里已经有数据了】，重复导入会撞主键/唯一约束。"
    echo "    如果想清空重来，加 --reset 参数："
    echo "      bash scripts/init-data.sh $SNAP --reset"
    echo "    （--reset 会删掉全部 41 张表再按快照重建，不可恢复）"
    exit 1
  }
echo "  已导入"

# ---------- 第 2 步：校验计数 ----------
echo "== 2/3 校验计数 =="
docker exec "$CONTAINER" psql -U "$DBUSER" -d "$DB" -t -c \
  "SELECT '  formula='||(SELECT count(*) FROM formula)
        ||'  case_record='||(SELECT count(*) FROM case_record)
        ||'  classic_quote='||(SELECT count(*) FROM classic_quote)
        ||'  content_unit='||(SELECT count(*) FROM content_unit)
        ||'  向量='||(SELECT count(*) FROM content_unit WHERE embedding IS NOT NULL);"

# ---------- 第 3 步：建图 ----------
echo "== 3/3 建图（Neo4j）=="
# Python 解释器：优先 python3（Linux/macOS），退回 python（Windows Git Bash）
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "  ✗ 找不到 python / python3，请确认已安装并加入 PATH"
  exit 1
fi
(cd "$ROOT_DIR/database/etl" && "$PY" build_graph.py)

echo
echo "完成 ✅  下一步：bash scripts/run-dev.sh 起后端，frontend 里 npm i && npm run dev"
