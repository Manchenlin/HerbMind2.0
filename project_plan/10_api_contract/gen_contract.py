# -*- coding: utf-8 -*-
"""从课程设计文档生成接口契约骨架（D-068）。

输入（唯一事实源，均在 thinkForProject 内）：
  - `thinkForProject/docs/05_系统设计说明书.md` §10.3：端点、分组、职责说明
  - `thinkForProject/track/02_需求到端点.csv`：端点与需求的对应关系、规则类约束

输出：本目录 `api_contract.generated.md`

三条设计原则：
  1. **不产生新事实**。自动区里的每一句都来自上面两个输入；本文件不是第二份端点表，
     而是它的投影。端点集合与职责有异议，改 `docs/05`，不要改这里。
  2. **手写区受保护**。请求/响应字段写在 `<!-- HAND:BEGIN 方法 路径 -->` 与
     `<!-- HAND:END -->` 之间，重新生成时原样搬回，不会被覆盖。字段这一层 `docs/05`
     本来就没有全写（只定了 3 个关键接口），所以它属于本文件，不构成冲突。
  3. **可判过期**。文件头写入源哈希；源一改、这里没重跑，`trace_check.py` 会报"契约过期"。

用法：python gen_contract.py
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC05 = ROOT / "thinkForProject" / "docs" / "05_系统设计说明书.md"
EDGE = ROOT / "thinkForProject" / "track" / "02_需求到端点.csv"
OUT = Path(__file__).resolve().parent / "api_contract.generated.md"

GROUP_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
EP_RE = re.compile(r"^\|\s*([A-Z]+(?:／[A-Z]+)*)\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$")
# key 必须形如「方法 路径」，否则文件头里那句说明文字也会被当成一个手写块
HAND_RE = re.compile(r"<!-- HAND:BEGIN ([A-Z]+ \S+) -->(.*?)<!-- HAND:END -->", re.S)


def load_sources() -> tuple[str, str]:
    text05 = DOC05.read_text(encoding="utf-8")
    start = text05.find("### 10.3 端点清单")
    end = text05.find("### 10.4")
    if start < 0 or end < 0:
        raise SystemExit("docs/05 里找不到 §10.3／§10.4，章节结构变了，先更新本脚本")
    edge = EDGE.read_text(encoding="utf-8")
    return text05[start:end], edge


def source_hash(block: str, edge: str) -> str:
    return hashlib.sha256((block + "\n" + edge).encode("utf-8")).hexdigest()[:16]


def parse_endpoints(block: str) -> "OrderedDict[str, list[tuple[str, str, str]]]":
    """返回 分组 → [(方法, 路径, 说明)]，顺序与文档一致。"""
    groups: OrderedDict[str, list[tuple[str, str, str]]] = OrderedDict()
    current = "未分组"
    for line in block.splitlines():
        g = GROUP_RE.match(line)
        if g:
            current = g.group(1)
            groups.setdefault(current, [])
            continue
        m = EP_RE.match(line)
        if m:
            methods = m.group(1).split("／")
            path = m.group(2).strip()
            desc = m.group(3).strip()
            for meth in methods:
                groups.setdefault(current, []).append((meth, path, desc))
    return groups


def parse_edge(path: Path) -> tuple[dict[str, list[tuple[str, str, str]]], list[tuple[str, str]]]:
    """返回 端点 → [(FR, coverage, note)]，以及全局规则（无端点的 rule 类）。"""
    by_ep: dict[str, list[tuple[str, str, str]]] = {}
    globals_: list[tuple[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            fid = (r.get("fr_id") or "").strip()
            cov = (r.get("coverage") or "").strip()
            eps = [e.strip() for e in (r.get("endpoints") or "").split(";") if e.strip()]
            note = (r.get("note") or "").strip()
            if cov == "rule" and not eps:
                globals_.append((fid, note))
            for ep in eps:
                by_ep.setdefault(ep, []).append((fid, cov, note))
    return by_ep, globals_


def load_hand(old: Path) -> dict[str, str]:
    if not old.exists():
        return {}
    return {k.strip(): v for k, v in HAND_RE.findall(old.read_text(encoding="utf-8"))}


def main() -> None:
    block, edge_text = load_sources()
    groups = parse_endpoints(block)
    by_ep, globals_ = parse_edge(EDGE)
    hand = load_hand(OUT)
    digest = source_hash(block, edge_text)

    total = sum(len(v) for v in groups.values())
    lines: list[str] = [
        "# 接口契约（生成物）",
        "",
        "> **本文件由脚本生成，自动区不要手改。** 生成器：`project_plan/10_api_contract/gen_contract.py`；",
        "> 重新生成：`python project_plan/10_api_contract/gen_contract.py`。",
        "> 每个端点下的**手写区**（`HAND:BEGIN 方法 路径` 与 `HAND:END` 两条注释之间）会被原样保留，可以放心编辑。",
        "",
        f"<!-- SOURCE_HASH: {digest} -->",
        "",
        "## 事实源与权威边界",
        "",
        "| 内容 | 权威在哪 | 冲突时改哪边 |",
        "|---|---|---|",
        f"| 有哪些端点、如何分组、端点职责 | `thinkForProject/docs/05` §10.3（本文件共投影 {total} 个方法） | 改 `docs/05`，然后重跑本脚本 |",
        "| 每条需求由哪些端点覆盖 | `thinkForProject/track/02_需求到端点.csv` | 改边表 |",
        "| 请求／响应字段、错误码细节 | **本文件的手写区** | 改本文件；`docs/05` 只定义 §10.4 的 3 个关键接口 |",
        "| 端点必须满足的规则类约束 | 边表 `coverage=rule` 的行 | 改边表 |",
        "",
        "本文件**不是**第二份端点表：自动区的内容全部来自上面两个文件，没有新增事实。",
        "曾经存在的 `project_plan/09_API契约清单.md` 之所以作废，是因为它手写维护、与设计文档各自演进；",
        "本文件用生成 + 手写分区来避免同一个问题。",
        "",
        "## 全局约束（不属于单个端点）",
        "",
        "| 编号 | 约束 | 说明 |",
        "|---|---|---|",
    ]
    if globals_:
        for fid, note in globals_:
            lines.append(f"| {fid} | {note} | 见 `docs/03` §5 |")
    else:
        lines.append("| — | 无 | — |")
    lines += [
        "",
        "全局约束由代码审查或横切测试保证，不挂在单个端点上。`FR-801`（`/api/admin/**` 统一角色拦截）",
        "虽也是全局约束，但作用于整棵前缀树，验收用越权用例矩阵覆盖。",
        "",
    ]

    for gname, eps in groups.items():
        if not eps:
            continue
        lines.append(f"## {gname}")
        lines.append("")
        for meth, path, desc in eps:
            key = f"{meth} {path}"
            lines.append(f"### `{key}`")
            lines.append("")
            lines.append(f"{desc}")
            lines.append("")
            related = by_ep.get(key, [])
            api_frs = [fid for fid, cov, _ in related if cov == "api"]
            rules = [(fid, note) for fid, cov, note in related if cov in ("rule", "partial")]
            lines.append(
                "- **覆盖需求**：" + ("、".join(f"`{x}`" for x in api_frs) if api_frs else "无（界面行为或由前端承担）")
            )
            if rules:
                for fid, note in rules:
                    lines.append(f"- **约束 {fid}**：{note}")
            body = hand.get(key, "")
            if not body.strip():
                body = (
                    "\n#### 请求\n\n| 字段 | 类型 | 必填 | 说明 |\n|---|---|---|---|\n\n"
                    "#### 响应 `data`\n\n| 字段 | 类型 | 说明 |\n|---|---|---|\n"
                )
            lines.append("")
            lines.append(f"<!-- HAND:BEGIN {key} -->{body}<!-- HAND:END -->")
            lines.append("")

    lines += [
        "## 变更记录",
        "",
        "| 日期 | 变更 |",
        "|---|---|",
        "| 2026-11-26 | 首次生成。骨架来自 `docs/05` v0.10 §10.3 与边表（82 条需求），手写字段区留空待补。 |",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    kept = sum(1 for k in hand if any(k == f"{m} {p}" for eps in groups.values() for m, p, _ in eps))
    print(f"已生成 {OUT}")
    print(f"端点 {total} 个方法，全局约束 {len(globals_)} 条，保留手写区 {kept} 个，源哈希 {digest}")


if __name__ == "__main__":
    main()
