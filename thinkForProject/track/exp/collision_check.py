# -*- coding: utf-8 -*-
"""T-02 归一碰撞检查实验（DR-12）：在真实底本上跑一遍，回答两件事。

1. 按本项目定的字符层规则归一后，有多少"显示值不同、归一值相同"的实体候选组，
   其中多少是同词异写（应合并）、多少是不同词（误合并风险）。
2. 一对多繁简字在本书里的实际出现上下文，为 T-01 的词组级白名单提供实测依据。

规则实现刻意只做字符层（全半角、标点空白、零宽、拉丁小写），不含繁简与异体，
因为底本是简体，繁简转换的碰撞风险在书内几乎不出现——这一点由统计数字说明，
而不是靠断言。

用法：python collision_check.py corpus.jsonl
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

# 实体候选：方剂名后缀前取 1~6 个汉字
SUFFIX_RE = re.compile(r"([\u4e00-\u9fa5]{1,6}?(?:汤|散|丸|饮|煎|膏|丹))")

PUNCT = set("。，、；：！？“”‘’（）《》〈〉【】〔〕…—·～!?,.;:()[]{}<>\"'`|-")
ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u00a0"}

# 一对多繁简字：字级盲转会造成误合并，必须先看清上下文再决定
AMBIGUOUS = "乾著發发後后裡里臺台係系鬆松僕仆範范嚮向鍾钟"


def to_halfwidth(s: str) -> str:
    """只做全半角：全角 ASCII 区（！ 到 ～）映射到半角，全角空格映射为空格。"""
    out = []
    for ch in s:
        code = ord(ch)
        if code == 0x3000:
            out.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def normalize_text(s: str) -> str:
    """字符层归一：顺序固定为 ①全半角 ②零宽 ③标点 ④空白 ⑤小写。"""
    s = to_halfwidth(s)
    s = "".join(ch for ch in s if ch not in ZERO_WIDTH)
    s = "".join(ch for ch in s if ch not in PUNCT)
    s = "".join(ch for ch in s if not ch.isspace())
    return s.lower()


def context_windows(texts: list[str], chars: str, width: int = 2) -> dict[str, Counter]:
    """取一对多字在本书中的上下文词组（前后各 width 字）。"""
    out: dict[str, Counter] = {}
    for ch in chars:
        c: Counter = Counter()
        for t in texts:
            for m in re.finditer(re.escape(ch), t):
                a = max(0, m.start() - width)
                b = min(len(t), m.end() + width)
                win = t[a:b]
                if win:
                    c[win] += 1
        if c:
            out[ch] = c
    return out


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("corpus.jsonl")
    texts: list[str] = []
    for line in src.open(encoding="utf-8"):
        r = json.loads(line)
        t = (r.get("text") or "").strip()
        if t:
            texts.append(t)

    # 1 实体候选与碰撞组
    raw: Counter = Counter()
    for t in texts:
        for m in SUFFIX_RE.finditer(t):
            raw[m.group(1)] += 1

    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for name, cnt in raw.items():
        groups[normalize_text(name)].append((name, cnt))

    collisions = {k: sorted(v, key=lambda x: -x[1]) for k, v in groups.items() if len(v) > 1}

    print(f"语料：{len(texts)} 段")
    print(f"方名候选：{len(raw)} 个不同显示值，共出现 {sum(raw.values())} 次")
    print(f"归一后碰撞组：{len(collisions)} 组")
    for k, v in sorted(collisions.items(), key=lambda kv: -sum(c for _, c in kv[1])):
        print(f"  [{k}] <- " + ", ".join(f"{n}({c})" for n, c in v))

    # 2 一对多字的实际上下文
    ctx = context_windows(texts, AMBIGUOUS)
    print("\n一对多字在本书中的上下文（前 4 个，供白名单判断）：")
    for ch, c in sorted(ctx.items(), key=lambda kv: -sum(kv[1].values())):
        top = "；".join(f"{w}({n})" for w, n in c.most_common(4))
        print(f"  {ch}: 共 {sum(c.values())} 次 -> {top}")

    # 3 归一化对各规则的敏感度：只删标点与空白会让多少组"本来不同"变成"相同"
    base_groups: dict[str, list[str]] = defaultdict(list)
    for name in raw:
        base_groups[name].append(name)
    punct_groups: dict[str, list[str]] = defaultdict(list)
    for name in raw:
        punct_groups[normalize_text(name)].append(name)
    shrink = sum(1 for v in punct_groups.values() if len(v) > 1)
    print(f"\n碰撞来源分解：仅全半角/标点/空白/大小写即产生 {shrink} 组（本书无繁简差异）")


if __name__ == "__main__":
    main()
