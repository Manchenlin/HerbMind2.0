# -*- coding: utf-8 -*-
"""对照实验：jieba 在"查询侧单说方名"与"文档侧方名 + 加减"两种上下文下的切分。

要回答的问题是：换一个分词器，能不能消除"两侧切分不一致导致短语匹配失败"。
判据不是"jieba 切得好不好看"，而是同一字符串在两种上下文里是否切出相同的词元序列。

运行：python jieba_probe.py
依赖：jieba 装在 ./_libs（--target 安装，不污染环境）
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "_libs"))
import jieba  # noqa: E402

jieba.setLogLevel(60)  # 关闭词典加载日志

PAIRS = [
    ("查询侧（用户只输方名）", "桂枝汤"),
    ("文档侧（原文含加减）", "桂枝汤加桂"),
    ("文档侧（原文含加减）", "桂枝汤加芍药"),
    ("文档侧（原文含加减）", "柴胡桂枝汤加减"),
    ("文档侧（原文含加减）", "小柴胡汤去滓再煎"),
    ("查询侧（用户只输方名）", "小柴胡汤"),
    ("文档侧（对照）", "寒热往来，胸胁苦满，小柴胡汤主之"),
]

# 是否把"汤加"当成一个词
CHECK_WORDS = ["汤加", "桂枝汤", "小柴胡汤", "桂枝", "柴胡桂枝汤"]


def main() -> None:
    print("=== 上下文切分对照 ===")
    seg: dict[str, list[str]] = {}
    for label, text in PAIRS:
        tokens = [t for t in jieba.lcut(text) if t.strip()]
        seg[text] = tokens
        print(f"{label:18s} {text:24s} -> {' / '.join(tokens)}")

    print("\n=== 同一方名在两种上下文里的词元序列是否一致 ===")
    pairs = [("桂枝汤", "桂枝汤加桂"), ("桂枝汤", "桂枝汤加芍药"), ("小柴胡汤", "小柴胡汤去滓再煎")]
    for query, doc in pairs:
        q = seg[query]
        d = seg[doc]
        # 文档侧是否包含查询侧的完整词元序列（子序列）
        ok = any(d[i : i + len(q)] == q for i in range(max(0, len(d) - len(q) + 1)))
        print(f"  查询 {query} -> {' / '.join(q)}")
        print(f"  文档 {doc} -> {' / '.join(d)}")
        print(f"  词元序列可连续包含：{'是' if ok else '否 —— 短语匹配会失败'}\n")

    print("=== jieba 自带词典里这些词是否存在 ===")
    for w in CHECK_WORDS:
        freq = jieba.dt.FREQ.get(w, 0)
        print(f"  {w}: {'在词典中（频次 ' + str(freq) + '）' if freq else '不在词典中'}")


if __name__ == "__main__":
    main()
