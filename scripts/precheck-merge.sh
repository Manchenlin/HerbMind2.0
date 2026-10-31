#!/usr/bin/env bash
# 合并前预检：把若干分支依次合进一个临时分支，跑 agent 全量单测，跑完自动回滚。
#
# 为什么需要它：仓库没有 CI 时，GitHub 只能发现"同一段代码被两人改"的**文本冲突**；
# 两个人改了同一文件的不同函数（能自动合并，PR 显示绿色）时，只有真正合起来跑一遍测试
# 才看得出逻辑有没有打架。典型场景：有人把限流挪到中间件，另一个人又在端点里加了一次。
#
# 用法：
#   bash scripts/precheck-merge.sh feat/agent-tool-calling
#   bash scripts/precheck-merge.sh feat/a feat/b feat/c          # 多条一起试合
#   bash scripts/precheck-merge.sh --base origin/master feat/a   # 换基底（默认 origin/master）
#   bash scripts/precheck-merge.sh --offline feat/a              # 连不上 origin 时用本地引用
#   HERBMIND_PYTHON=/d/soft/anaconda/envs/herbmind/python.exe bash scripts/precheck-merge.sh feat/a
#
# 前置：工作区必须干净（脚本要切分支，怕误伤未提交改动）；能连 origin。
# 安全：只创建/删除一个临时分支，退出时无条件切回原分支；不改已有分支、不 push、不碰远端。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

BASE="origin/master"
BRANCHES=()
OFFLINE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --base)
      [ $# -ge 2 ] || { echo "❌ --base 后面要跟分支名" >&2; exit 1; }
      BASE="$2"
      shift 2
      ;;
    --offline)
      OFFLINE=1
      shift
      ;;
    -h|--help)
      # 只打印文件头注释块
      awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
      exit 0
      ;;
    *)
      BRANCHES+=("$1")
      shift
      ;;
  esac
done

if [ ${#BRANCHES[@]} -eq 0 ]; then
  echo "❌ 至少给一个要试合的分支，例如：bash scripts/precheck-merge.sh feat/agent-tool-calling" >&2
  exit 1
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "❌ 工作区有未提交的**已跟踪文件**改动，请先 commit 或 stash（脚本会切分支）" >&2
  git status --short --untracked-files=no >&2
  exit 1
fi

ORIG_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
TEMP_BRANCH="precheck-merge-$$"

cleanup() {
  # 无论成功失败都回到原分支并删掉临时分支，避免把工作区留在半合并状态
  git merge --abort 2>/dev/null || true
  git checkout -q "$ORIG_BRANCH" 2>/dev/null || true
  git branch -D "$TEMP_BRANCH" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [ "$OFFLINE" -eq 1 ]; then
  echo "== 跳过 fetch（--offline，用本地引用） =="
elif ! git fetch origin --prune; then
  # fetch 失败不该让预检彻底跑不了：本地引用通常够用，但必须说清楚"没拉到最新"
  echo "⚠️  fetch 失败（网络/代理问题）。继续用**本地已有**的远端引用。" >&2
  echo "    要保证合的是最新代码，请先 git fetch origin 成功，或加 --offline 明确跳过。" >&2
fi

if ! git rev-parse --verify --quiet "$BASE" >/dev/null; then
  echo "❌ 基底 $BASE 不存在" >&2
  exit 1
fi

echo
echo "== 基底：$BASE（$(git rev-parse --short "$BASE")） =="
echo "== 试合：${BRANCHES[*]} =="
git checkout -q -B "$TEMP_BRANCH" "$BASE"

for branch in "${BRANCHES[@]}"; do
  ref="$branch"
  if ! git rev-parse --verify --quiet "$branch" >/dev/null; then
    if git rev-parse --verify --quiet "origin/$branch" >/dev/null; then
      ref="origin/$branch"
    else
      echo "❌ 分支不存在：$branch（本地与 origin/ 都没有）" >&2
      exit 1
    fi
  fi

  short="$(git rev-parse --short "$ref")"
  echo
  echo "-- 合入 $ref（$short）"
  if ! git merge --no-ff --no-edit "$ref" >/dev/null 2>&1; then
    echo "❌ 与 $ref 有**文本冲突**，需要手工解决：" >&2
    git merge --abort 2>/dev/null || true
    echo "   建议：git switch -c fix/merge-$TEMP_BRANCH $BASE && git merge $ref" >&2
    exit 1
  fi
  echo "   OK（无文本冲突）"
done

echo
echo "== 跑 agent 单测 =="
PY="${HERBMIND_PYTHON:-python}"
if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
  echo "❌ 找不到 python：$PY（可用 HERBMIND_PYTHON 指定解释器路径）" >&2
  exit 1
fi
echo "   解释器：$PY"
if ! ( cd agent && "$PY" -m pytest tests -q ); then
  echo
  echo "❌ 合并后单测不通过——这说明是**语义冲突**（GitHub 不会提示，但合进去就是坏的）" >&2
  exit 1
fi

echo
echo "✅ 预检通过：${BRANCHES[*]} 可以按顺序合并到 $BASE"
