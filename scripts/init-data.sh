#!/usr/bin/env bash
# 导入数据快照（发给组员的那个 .sql.gz）+ 建图。
#
# 用法：  bash scripts/init-data.sh /path/to/herbmind_data.sql.gz
#
# 前置：中间件已起（docker compose -f docker/docker-compose.infra.yml up -d）
#       —— 首次启动会自动建好 41 张表（database/pg/00→04）
set -euo pipefail

SNAP="${1:-}"
CONTAINER="${PG_CONTAINER:-herbmind-v2-pg}"
DB="${PG_DB:-herbmind}"
DBUSER="${PG_USER:-postgres}"

if [ -z "$SNAP" ] || [ ! -f "$SNAP" ]; then
  echo "用法：bash scripts/init-data.sh <herbmind_data.sql.gz>"
  exit 1
fi

echo "== 1/3 导入快照 =="
echo "  文件：$SNAP"
gunzip -c "$SNAP" | docker exec -i -e PGCLIENTENCODING=UTF8 "$CONTAINER" \
  psql -q -v ON_ERROR_STOP=1 -U "$DBUSER" -d "$DB" > /dev/null
echo "  已导入"

echo "== 2/3 校验计数 =="
docker exec "$CONTAINER" psql -U "$DBUSER" -d "$DB" -t -c \
  "SELECT '  formula='||(SELECT count(*) FROM formula)
        ||'  case_record='||(SELECT count(*) FROM case_record)
        ||'  classic_quote='||(SELECT count(*) FROM classic_quote)
        ||'  content_unit='||(SELECT count(*) FROM content_unit)
        ||'  向量='||(SELECT count(*) FROM content_unit WHERE embedding IS NOT NULL);"

echo "== 3/3 建图（Neo4j）=="
HERE="$(cd "$(dirname "$0")/.." && pwd -W)"
(cd "$HERE/database/etl" && python build_graph.py)

echo
echo "完成 ✅  下一步：bash scripts/run-dev.sh 起后端，frontend 里 npm i && npm run dev"
