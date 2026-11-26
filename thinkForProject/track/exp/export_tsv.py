# -*- coding: utf-8 -*-
"""把 corpus.jsonl 中非空正文段落导出为 COPY 用的 TSV（\\t 分隔，转义 \\ 与换行）。

用法：python export_tsv.py corpus.jsonl units.tsv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    n = 0
    with src.open(encoding="utf-8") as f, dst.open("w", encoding="utf-8", newline="\n") as out:
        for line in f:
            r = json.loads(line)
            text = (r.get("text") or "").strip()
            if not text:
                continue
            out.write(f"{r['seq']}\t{esc(text)}\n")
            n += 1
    print(f"导出 {n} 行 -> {dst}")


if __name__ == "__main__":
    main()
