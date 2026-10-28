#!/usr/bin/env bash
# 域1（内容域）验收脚本 —— 对着 17 号手册 §6 与任务卡 A 的验收点逐条打。
# 用法：bash scripts/verify-a.sh            （服务需已启动：8082 / 8083 / 8086 / 8090）
# 退出码：0 全部通过；1 有失败项。
set -u

PASS=0
FAIL=0
CATALOG="${CATALOG:-http://localhost:8082}"
SEARCH="${SEARCH:-http://localhost:8083}"
INSIGHT="${INSIGHT:-http://localhost:8086}"
BFF="${BFF:-http://localhost:8090}"

ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1"; [ -n "${2:-}" ] && echo "     $2"; FAIL=$((FAIL+1)); }

# check <名称> <url> <必须出现的子串> [额外的 curl 参数...]
check() {
  local name="$1" url="$2" expect="$3"; shift 3
  local body
  body="$(curl -sS --max-time 15 "$@" "$url" 2>&1)" || { bad "$name" "请求失败：$body"; return; }
  if printf '%s' "$body" | grep -q -- "$expect"; then
    ok "$name"
  else
    bad "$name" "响应中没有 [$expect]：$(printf '%s' "$body" | head -c 300)"
  fi
}

echo "== 1. 中间件 / 数据 =="
check "catalog 书架可读" "$CATALOG/internal/catalog/books" '"title"'
check "catalog 统计：245 方" "$CATALOG/internal/catalog/stats" '"formulas":245'
check "catalog 统计：535 向量" "$CATALOG/internal/catalog/stats" '"vectors":535'

echo "== 2. 目录（O2 验收：bk_1 = 27 节点） =="
check "目录树返回" "$CATALOG/internal/catalog/tree?bookId=bk_1" '太阳病'
check "节点详情（含方剂）" "$CATALOG/internal/catalog/node/n_g1/detail" '"formulas"'
check "节点详情（含面包屑）" "$CATALOG/internal/catalog/node/n_g1/detail" '"breadcrumb"'

echo "== 3. 内容详情 =="
check "方剂 f_1 = 麻黄汤" "$CATALOG/internal/catalog/formula/f_1" '麻黄汤'
check "方剂含药味" "$CATALOG/internal/catalog/formula/f_1" '"herbs"'
check "方剂含条文" "$CATALOG/internal/catalog/formula/f_1" '"quotes"'
check "医案 cs_1" "$CATALOG/internal/catalog/case/cs_1" '"sections"'
check "条文 q_1 拆条" "$CATALOG/internal/catalog/quote/q_1" '"items"'
check "条文列表 /quote/list（A1）" "$CATALOG/internal/catalog/quote/list?size=3" '"total"'
check "今日方证" "$CATALOG/internal/catalog/daily" '"herbs"'

echo "== 4. 检索（A2：混合召回） =="
check "分词/词项检索：麻黄汤" "$SEARCH/internal/search?q=%E9%BA%BB%E9%BB%84%E6%B1%A4" '"list"'
check "检索有结果" "$SEARCH/internal/search?q=%E9%BA%BB%E9%BB%84%E6%B1%A4" '"total":[1-9]'
check "自然语言检索" "$SEARCH/internal/search?q=%E6%97%A0%E6%B1%97%E8%80%8C%E5%96%98%E3%80%81%E8%84%89%E6%B5%AE%E7%B4%A7" '"total":[1-9]'
check "按药味过滤" "$SEARCH/internal/search?q=%E9%BA%BB%E9%BB%84&herb=%E9%BA%BB%E9%BB%84" '"total"'
check "分面" "$SEARCH/internal/search/facets?q=%E9%BA%BB%E9%BB%84%E6%B1%A4" '"types"'
check "语义检索 POST" "$SEARCH/internal/search/semantic" '"mode"' \
  -X POST -H "Content-Type: application/json" \
  -d '{"q":"无汗而喘、脉浮紧用什么方","size":5}'
check "条文反向索引" "$SEARCH/internal/search/quote-index?q=%E9%BA%BB%E9%BB%84%E6%B1%A4" '"articleNo"'
check "条文索引含关联方" "$SEARCH/internal/search/quote-index?q=%E9%BA%BB%E9%BB%84%E6%B1%A4" '"formulas"'

echo "== 5. 科研统计（A3 科研页） =="
check "用药频次" "$INSIGHT/internal/insight/herbs?limit=5" '"herb"'
check "证候分布" "$INSIGHT/internal/insight/syndrome?limit=5" '"label"'
check "经典/章节分布" "$INSIGHT/internal/insight/trend" '"books"'
check "CSV 导出头" "$INSIGHT/internal/insight/export?kind=herbs&format=csv" 'herb,count'
check "研究包" "$INSIGHT/internal/insight/research-pack" '"packId"' \
  -X POST -H "Content-Type: application/json" -d '{"topN":5}'

echo "== 6. BFF / 首页（A4） =="
check "首页聚合" "$BFF/api/biz/home" '"today"'
check "首页图谱预览" "$BFF/api/biz/home" '"graph"'
check "BFF 目录树" "$BFF/api/biz/library/tree?bookId=bk_1" '太阳病'
check "BFF 节点详情" "$BFF/api/biz/catalog/node/n_g1" '"formulas"'
check "BFF 方剂页" "$BFF/api/biz/formula/f_1/page" '麻黄汤'
check "BFF 医案页" "$BFF/api/biz/case/cs_1/page" '"sections"'
check "BFF 条文页" "$BFF/api/biz/quote/q_1/page" '"items"'
check "BFF 检索" "$BFF/api/biz/search?q=%E9%BA%BB%E9%BB%84%E6%B1%A4" '"facets"'
check "BFF 导出" "$BFF/api/biz/insight/export?kind=herbs&format=csv" 'herb,count'

echo
echo "结果：通过 $PASS 项，失败 $FAIL 项"
if [ "$FAIL" -gt 0 ]; then
  echo "排查："
  echo "  - 服务是否都在跑：bash scripts/run-dev.sh（日志在 logs/）"
  echo "  - 数据是否导入：bash scripts/init-data.sh <快照>"
  echo "  - pg_jieba 未装时全文腿为 0，但词项腿应仍能命中「麻黄汤」"
  exit 1
fi
