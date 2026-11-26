# -*- coding: utf-8 -*-
"""需求→端点对账（D-067）。

不做的事：不复制需求正文、不复制端点定义。只做三边比对：
  ①`docs/03` 定义的功能需求编号
  ②`docs/05` §10.3 定义的端点
  ③`track/02_需求到端点.csv` 这张"边表"

输出五类问题，任一非空即退出码 1：
  断链-FR    边表引用了 03 里不存在的需求编号
  断链-端点  边表引用了 05 §10.3 里不存在的端点
  漏登记     03 里有这条需求，边表里没有它
  无主端点   05 定义了端点，但没有任何需求认领
  漏设计     边表里 coverage=missing，即"需求存在、应有接口、但没有"

用法：python trace_check.py [--report 输出路径]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EDGE = ROOT / "track" / "02_需求到端点.csv"

FR_RE = re.compile(r"^\|\s*(FR-\d+)\s*\|")
# 端点行：| GET | `path` | 说明 |   方法可能是 GET／POST 这种全角合并写法
EP_RE = re.compile(r"^\|\s*([A-Z]+(?:／[A-Z]+)*)\s*\|\s*`([^`]+)`\s*\|")

COVERAGE = {"api", "ui", "rule", "deferred", "partial", "missing"}


def load_fr(path: Path) -> dict[str, str]:
    """返回 FR 编号 → 首句（截断）"""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = FR_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        out[m.group(1)] = cells[1][:40] if len(cells) > 1 else ""
    return out


def load_endpoints(path: Path) -> dict[str, str]:
    """只解析 §10.3 段落；返回 'METHOD path' → 说明"""
    text = path.read_text(encoding="utf-8")
    start = text.find("### 10.3 端点清单")
    end = text.find("### 10.4")
    if start < 0 or end < 0:
        raise SystemExit("在 docs/05 里找不到 §10.3 或 §10.4，章节结构变了请先更新脚本")
    block = text[start:end]

    out: dict[str, str] = {}
    for line in block.splitlines():
        m = EP_RE.match(line)
        if not m:
            continue
        methods = m.group(1).split("／")
        path_tpl = m.group(2).strip()
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        desc = cells[2] if len(cells) > 2 else ""
        for meth in methods:
            out[f"{meth} {path_tpl}"] = desc
    return out


def load_edge(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def contract_status() -> tuple[bool, str]:
    """检查实现期接口契约是否与课程文档同步（契约由 docs/05 §10.3 + 边表生成）。

    契约在 project_plan/10_api_contract/，不在 thinkForProject 内：课程文档不能依赖
    实现文件，实现文件可以派生自课程文档，方向只能是这一个。
    """
    contract = ROOT.parent / "project_plan" / "10_api_contract" / "api_contract.generated.md"
    if not contract.exists():
        return False, "契约文件不存在：project_plan/10_api_contract/api_contract.generated.md"

    text05 = (DOCS / "05_系统设计说明书.md").read_text(encoding="utf-8")
    start, end = text05.find("### 10.3 端点清单"), text05.find("### 10.4")
    if start < 0 or end < 0:
        return False, "docs/05 里找不到 §10.3／§10.4，无法校验契约"
    digest = hashlib.sha256(
        (text05[start:end] + "\n" + EDGE.read_text(encoding="utf-8")).encode("utf-8")
    ).hexdigest()[:16]

    m = re.search(r"<!-- SOURCE_HASH: ([0-9a-f]{16}) -->", contract.read_text(encoding="utf-8"))
    if not m:
        return False, "契约文件缺少 SOURCE_HASH 标记"
    if m.group(1) != digest:
        return False, f"契约过期：文件记录 {m.group(1)}，当前源 {digest}；请重跑 gen_contract.py"
    return True, f"契约与源同步（{digest}）"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(ROOT / "track" / "02_需求到端点_对账报告.md"))
    args = ap.parse_args()

    frs = load_fr(DOCS / "03_需求规格说明书.md")
    eps = load_endpoints(DOCS / "05_系统设计说明书.md")
    rows = load_edge(EDGE)

    bad_fr: list[str] = []
    bad_ep: list[str] = []
    missing_row: list[str] = []
    claimed: set[str] = set()
    missing_design: list[tuple[str, str]] = []
    partial_gap: list[tuple[str, str]] = []
    rule_items: list[str] = []
    bad_coverage: list[str] = []

    seen_fr: set[str] = set()
    for r in rows:
        fid = (r.get("fr_id") or "").strip()
        cov = (r.get("coverage") or "").strip()
        ep_field = (r.get("endpoints") or "").strip()
        note = (r.get("note") or "").strip()

        if cov not in COVERAGE:
            bad_coverage.append(f"{fid}：coverage={cov!r} 不在 {sorted(COVERAGE)} 内")
        if fid in frs:
            seen_fr.add(fid)
        else:
            bad_fr.append(fid)

        for ep in [e.strip() for e in ep_field.split(";") if e.strip()]:
            claimed.add(ep)
            if ep not in eps:
                bad_ep.append(f"{fid} -> {ep}")

        if cov == "missing":
            missing_design.append((fid, note))
        elif cov == "partial":
            partial_gap.append((fid, note))
        elif cov == "rule":
            rule_items.append(f"`{fid}` — {note}")

    for fid in frs:
        if fid not in seen_fr:
            missing_row.append(fid)

    orphan_ep = [ep for ep in eps if ep not in claimed]

    lines = [
        "# 需求→端点对账报告",
        "",
        "由 `scripts/trace_check.py` 生成，不要手改。",
        "",
        f"- `docs/03` 功能需求：**{len(frs)}** 条",
        f"- `docs/05` §10.3 端点：**{len(eps)}** 个方法",
        f"- 边表登记：**{len(rows)}** 行，认领端点 **{len(claimed)}** 个",
        "",
    ]

    def section(title: str, items: list[str], empty: str = "无。") -> None:
        lines.append(f"## {title}（{len(items)}）")
        lines.append("")
        if not items:
            lines.append(empty)
        else:
            for it in items:
                lines.append(f"- {it}")
        lines.append("")

    section("漏设计：需求存在但无端点", [f"`{f}` {n}" for f, n in missing_design])
    section("部分覆盖：端点存在但能力不足", [f"`{f}` {n}" for f, n in partial_gap])
    section("无主端点：已定义但无需求认领", [f"`{e}` — {eps[e]}" for e in orphan_ep])
    section("断链：边表引用了不存在的需求", bad_fr)
    section("断链：边表引用了不存在的端点", bad_ep)
    section("漏登记：需求没进边表", missing_row)
    section("边表格式问题", bad_coverage)
    section("规则类需求：无端点，靠测试或代码审查保证（不计入失败数，需人工确认）", rule_items)

    ok_contract, contract_msg = contract_status()
    if ok_contract:
        lines.append(f"> 实现期接口契约：{contract_msg}（见 `project_plan/10_api_contract/`）")
    else:
        section("实现期接口契约未同步", [contract_msg])

    report = "\n".join(lines)
    Path(args.report).write_text(report + "\n", encoding="utf-8")
    print(report)

    problems = (
        len(missing_design)
        + len(partial_gap)
        + len(orphan_ep)
        + len(bad_fr)
        + len(bad_ep)
        + len(missing_row)
        + len(bad_coverage)
        + (0 if ok_contract else 1)
    )
    print(f"\n共 {problems} 项待处理，报告写入 {args.report}")
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
