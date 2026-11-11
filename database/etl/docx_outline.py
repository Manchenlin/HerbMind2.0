"""从清洗后的文本块里解析章/节骨架，并纠正本书的 OCR 错字。

本书疑似由扫描件转出，章标题存在三种写法（实测）：

    第二章《伤寒论》方证案例研究
    第二章《伤寒论》万证杂例研究      ← 错字
    第二章《徬寒论》方证案例研究      ← 错字
    第四章《金匮要略》方证案例研究消失。  ← 编辑批注混进正文

纠正依据是《伤寒论》《金匮要略》《温病学》的通行书名与本书自身的章标题重复出现，
不是凭印象改字。错字表只收录**能由上下文互相印证**的项，宁可漏改也不猜。
"""

from __future__ import annotations

import re

# 错字 → 正字（每一项都有同书其它章节的正确写法作证）
_OCR_FIXES = {
    "徬寒论": "伤寒论",
    "万证杂例": "方证案例",
}

# 编辑批注残片，直接删掉
_NOTE_FRAGMENTS = ("消失。",)

_CHAPTER = re.compile(r"^第[一二三四五六七八九十]+章")
_SECTION = re.compile(r"^第[一二三四五六七八九十]+节")
_SECTION_PREFIX = re.compile(r"^第[一二三四五六七八九十]+节\s*")
_BOOK = re.compile(r"《(.+?)》")

# 标题段落的长度上限：目录页会把整章标题压进一个上千字的长段落
_HEADING_MAX_LEN = 40


def fix_ocr(text: str) -> str:
    """纠正已知 OCR 错字与批注残片。"""
    fixed = text
    for wrong, right in _OCR_FIXES.items():
        fixed = fixed.replace(wrong, right)
    for fragment in _NOTE_FRAGMENTS:
        fixed = fixed.replace(fragment, "")
    return fixed.strip()


def parse_outline(blocks: list[str]) -> list[dict]:
    """解析出 `[{title, book, sections: [{title, start_index}]}]`。

    - `book`：章标题里《…》的书名（第一章理论部分没有书名 → None）
    - `start_index`：该节标题在 `blocks` 中的下标，用于把案例单元挂到正确的节下

    正文起点 = 第一个「长度 ≤ 40 且以 `第X章` 开头」的块 —— 目录页那些被压成长段落的
    章标题因此被跳过。
    """
    start = -1
    for i, block in enumerate(blocks):
        text = block.strip()
        if len(text) <= _HEADING_MAX_LEN and _CHAPTER.match(text):
            start = i
            break
    if start < 0:
        return []

    chapters: list[dict] = []
    by_key: dict[str, dict] = {}
    current: dict | None = None

    for i in range(start, len(blocks)):
        text = fix_ocr(blocks[i].strip())
        if len(text) > _HEADING_MAX_LEN:
            continue
        chapter_match = _CHAPTER.match(text)
        if chapter_match:
            book = _BOOK.search(text)
            book_name = book.group(1) if book else None
            # 按「章号 + 书名」判同一章：书中错字版章标题、以及只写「第一章」的段落
            # 都会落到同一个 key 上，合并到第一次出现的完整标题里，节继续追加进去。
            key = chapter_match.group(0) + (book_name or "")
            if key in by_key:
                current = by_key[key]
                continue
            node = {"title": text, "book": book_name, "sections": []}
            by_key[key] = node
            chapters.append(node)
            current = node
        elif _SECTION.match(text) and current is not None:
            current["sections"].append(
                {"title": _SECTION_PREFIX.sub("", text).strip(), "start_index": i}
            )
    return chapters
