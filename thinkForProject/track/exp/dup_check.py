# -*- coding: utf-8 -*-
"""单元级碰撞检查：归一后完全相同的内容单元（DR-12 的另一种形态）。

段级重复有两种来源：底本自身重复（文本框复制、页眉残留），以及归一规则把两句
本不同的文本并成一句。前者是数据质量问题，后者是规则问题，二者的处置不同，
所以这里只报"归一后相同"的组，并打印显示值是否也相同，用于区分两类。

用法：python dup_check.py corpus.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "norm"))
import normalize as N  # noqa: E402


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("corpus.jsonl")
    groups: dict[str, list[str]] = defaultdict(list)
    total = 0
    for line in src.open(encoding="utf-8"):
        r = json.loads(line)
        t = (r.get("text") or "").strip()
        if len(t) < 8:  # 过短的段（标题、页码残留）单独处理，不参与本项统计
            continue
        total += 1
        groups[N.normalize(t)].append(t)

    dup = {k: v for k, v in groups.items() if len(v) > 1}
    display_same = sum(1 for v in dup.values() if len(set(v)) == 1)
    display_diff = len(dup) - display_same
    involved = sum(len(v) for v in dup.values())

    print(f"参与统计的长段（≥8 字）：{total}")
    print(f"归一后重复组：{len(dup)}，涉及 {involved} 段（占比 {involved / total:.2%}）")
    print(f"  其中显示值也相同（底本自身重复）：{display_same} 组")
    print(f"  显示值不同但归一后相同（可疑：规则并合）：{display_diff} 组")

    for k, v in list(sorted(dup.items(), key=lambda kv: -len(kv[1])))[:5]:
        print(f"\n  [{len(v)} 段] 归一值前 40 字：{k[:40]}")
        for t in v[:3]:
            print(f"    - {t[:56]}")

    print("\n显示值不同但归一后相同的组（逐组核对是否只是标点/空白差异）：")
    for k, v in dup.items():
        if len(set(v)) > 1:
            uniq = list(dict.fromkeys(v))
            print(f"  [{len(v)} 段] " + " | ".join(x[:40] for x in uniq[:3]))


if __name__ == "__main__":
    main()
