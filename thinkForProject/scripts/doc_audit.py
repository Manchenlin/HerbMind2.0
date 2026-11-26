# -*- coding: utf-8 -*-
"""跨文档一致性体检（只查机械可查的部分，语义冲突仍需人工）。

查四类：
  ①断链编号   正文引用了从未定义的 FR/NFR/BR/DI/DR/INV/UC/Q/RISK/A/REF 编号
  ②计数不符   各处声明的功能需求条数与 §5 实际定义数不一致
  ③待定残留   已答的 Q 编号旁边仍挂着"待定／待确认／未定"
  ④职责越界   需求文档里出现端点路径或 SQL，设计文档里出现需求定义行

用法：python doc_audit.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Q 编号允许子号（Q-06-2），其余不带子号
ID_RE = re.compile(r"\b(FR|NFR|BR|DI|DR|INV|UC|Q|RISK|A|REF)-(\d{1,3}(?:-\d)?)\b")
DEF_RE = re.compile(r"^\|\s*((?:FR|NFR|BR|DI|DR|INV|UC|Q|RISK|A|REF)-\d{1,3}(?:-\d)?)\s*\|")
COUNT_RE = re.compile(r"(?:共|合计)?\s*(\d{2,3})\s*条功能需求|功能需求[^。|]{0,24}?(\d{2,3})\s*条")
PENDING = ("待定", "待确认", "未定", "待办")


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    files = {p.name: load(p) for p in sorted(DOCS.glob("*.md"))}
    # plan/00 的提问表是 Q-0xx 的权威定义处，必须纳入定义源，否则继承编号会被误报为断链
    plan00 = ROOT / "plan" / "00_全局记忆.md"
    if plan00.exists():
        files["plan/00_全局记忆.md"] = load(plan00)

    defs: dict[str, set[str]] = {}
    refs: dict[str, Counter] = {}
    for name, text in files.items():
        d = set()
        r: Counter = Counter()
        for line in text.splitlines():
            m = DEF_RE.match(line)
            if m:
                d.add(m.group(1))
            # 编号跳号的说明行（如"FR-107～FR-110 未分配"）不算引用
            if "未分配" in line or "跳号" in line:
                continue
            for mm in ID_RE.finditer(line):
                r[mm.group(0)] += 1
        defs[name] = d
        refs[name] = r

    all_defs = set().union(*defs.values()) if defs else set()
    all_refs = Counter()
    for c in refs.values():
        all_refs.update(c)

    print("=== 定义数量 ===")
    per_kind: Counter = Counter(x.split("-")[0] for x in all_defs)
    for k in ("FR", "NFR", "BR", "DI", "DR", "INV", "UC", "Q", "RISK", "A", "REF"):
        print(f"  {k:5s} {per_kind.get(k, 0)}")

    print("\n=== ①断链编号（引用了但从未定义）===")
    dangling = sorted(x for x in all_refs if x not in all_defs)
    # 按 docs/03 §13 的约定，子问题编号 Q-xx-n 的定义写在引用处的答复行里，
    # 不要求有表格定义行，故单独列出而不算断链。
    sub_q = [x for x in dangling if re.match(r"^Q-\d+-\d$", x)]
    dangling = [x for x in dangling if x not in sub_q]
    print("无。" if not dangling else "\n".join(f"  {x}（出现 {all_refs[x]} 次）" for x in dangling))
    if sub_q:
        print("  —— 按 `docs/03` §13 约定豁免的子问题编号：" + "、".join(sub_q))

    fr_defs = per_kind.get("FR", 0)
    print(f"\n=== ②计数不符（实际 FR 定义 {fr_defs} 条）===")
    bad_count = []
    for name, text in files.items():
        for line_no, line in enumerate(text.splitlines(), 1):
            # 变更记录是历史陈述，旧数字不算错；"v1.5 起为 N 条"是刻意保留的基线说明
            if line.startswith("| 2026-") or "起为" in line:
                continue
            for m in COUNT_RE.finditer(line):
                n = int(m.group(1) or m.group(2))
                if not (50 <= n <= 200) or n == fr_defs:
                    continue
                bad_count.append(f"  {name}:{line_no} 写 {n} 条 —— {line.strip()[:60]}")
    print("无。" if not bad_count else "\n".join(bad_count))

    print("\n=== ③待定残留（出现处是否指向已答 Q）===")
    pending = []
    for name, text in files.items():
        for m in re.finditer("|".join(PENDING), text):
            line_no = text[: m.start()].count("\n") + 1
            line = text.splitlines()[line_no - 1].strip()
            # 已答／已关闭的问答行、"证据等级标记 [待确认]"、变更记录里的文字都不算残留
            if "已答" in line or "已关闭" in line or "[待确认]" in line or line.startswith("| 2026-"):
                continue
            pending.append(f"  {name}:{line_no} {line[:80]}")
    print("无。" if not pending else "\n".join(pending[:20]) + (f"\n  ……共 {len(pending)} 处" if len(pending) > 20 else ""))

    print("\n=== ④职责越界 ===")
    over = []
    needs = files.get("03_需求规格说明书.md", "")
    for i, line in enumerate(needs.splitlines(), 1):
        if re.search(r"/api/|SELECT |CREATE TABLE|Spring Boot|MyBatis", line):
            over.append(f"  03:{i} 需求文档出现实现细节 —— {line.strip()[:70]}")
    design = files.get("05_系统设计说明书.md", "")
    for i, line in enumerate(design.splitlines(), 1):
        if DEF_RE.match(line) and re.match(r"^\|\s*FR-\d+\s*\|", line):
            over.append(f"  05:{i} 设计文档定义功能需求 —— {line.strip()[:70]}")
    print("无。" if not over else "\n".join(over))


if __name__ == "__main__":
    main()
