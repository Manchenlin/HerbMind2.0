# -*- coding: utf-8 -*-
"""jieba 版的召回对照：用 jieba 切分模拟"分词索引 + 短语匹配"，与子串匹配比命中数。

模拟的是 PG 里 `tsv @@ to_tsquery('...')` 的语义：查询被切成词元序列后，文档侧必须
存在同样的**连续**词元序列才算命中。这样可以在不搭第二套 PG 的情况下，
直接得到"换 jieba 会不会漏"的数字。

运行：python jieba_recall.py corpus.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "_libs"))
import jieba  # noqa: E402

jieba.setLogLevel(60)

QUERIES = ["桂枝汤", "小柴胡汤", "脉浮", "恶寒", "太阳中风", "清营汤", "桂枝"]


def contains_run(doc_tokens: list[str], query_tokens: list[str]) -> bool:
    n = len(query_tokens)
    if n == 0:
        return False
    return any(doc_tokens[i : i + n] == query_tokens for i in range(len(doc_tokens) - n + 1))


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("corpus.jsonl")
    docs = []
    for line in src.open(encoding="utf-8"):
        t = (json.loads(line).get("text") or "").strip()
        if t:
            docs.append(t)

    tokenized = [[w for w in jieba.lcut(d) if w.strip()] for d in docs]
    print(f"语料 {len(docs)} 段，jieba 已切分\n")
    print(f"{'查询词':10s}{'子串命中':>10s}{'jieba 词元命中':>16s}{'漏检率':>10s}")
    for q in QUERIES:
        qseg = [w for w in jieba.lcut(q) if w.strip()]
        str_hits = sum(1 for d in docs if q in d)
        idx_hits = sum(1 for tk in tokenized if contains_run(tk, qseg))
        miss = (str_hits - idx_hits) / str_hits * 100 if str_hits else 0
        print(f"{q:10s}{str_hits:>10d}{idx_hits:>16d}{miss:>9.1f}%")
        print(f"{'':10s}查询侧切分 -> {' / '.join(qseg)}")

    # 打印一个典型漏检
    print("\n典型漏检（子串含'小柴胡汤'但 jieba 词元序列不含）前 3 条：")
    qseg = [w for w in jieba.lcut("小柴胡汤") if w.strip()]
    shown = 0
    for d, tk in zip(docs, tokenized):
        if "小柴胡汤" in d and not contains_run(tk, qseg):
            hit = [w for w in tk if "小柴胡" in w or "汤" in w][:4]
            print(f"  {' / '.join(hit)}  <- {d[:40]}")
            shown += 1
            if shown >= 3:
                break


if __name__ == "__main__":
    main()
