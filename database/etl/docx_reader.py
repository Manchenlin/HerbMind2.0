"""读取 docx 文本块并洗掉页眉页脚。

为什么不用 python-docx：本书只需要「按段落顺序取纯文本」，docx 本质就是 zip + OOXML，
用标准库 `zipfile` + `xml.etree` 足够，还少一个依赖（conda 环境里没有 python-docx）。

实测结构（`D:\\HomeWork\\_KeYanShJian\\中医经典方证原文.docx`）：
- 8710 个非空段落 + 78 个表格；表格里 76 个是目录点线页，正文几乎全是段落；
- 每页页眉重复出现书名 `中医经典方证案例研究` 与当前章标题；
- 页码单独成段（纯数字）。
所以「噪音」分两类：**逐行可判定**的（页码、页眉书名）交给 `is_noise`；
**重复出现才成立**的（章标题）交给 `clean_blocks` 去重 —— 章标题首次出现是正文结构，
必须留给 `docx_outline.parse_outline` 用。
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# 「128」「- 45 -」「（12）」这类整行页码
_PAGE_NO = re.compile(r"^[\s\-—–·.、()（）]*\d{1,4}[\s\-—–·.、()（）]*$")

# 每页都重复的页眉书名（改动前请在 docx 里确认，别凭印象加）
_RUNNING_HEADERS = {"中医经典方证案例研究"}

# 章/节标题：用于「重复只留第一次」的判定
_HEADING = re.compile(r"^第[一二三四五六七八九十]+[章节]")

TABLE_PLACEHOLDER = "[表格]"


def is_noise(text: str) -> bool:
    """逐行就能判定的噪音：空行、纯页码、页眉书名。"""
    t = text.strip()
    if not t:
        return True
    if _PAGE_NO.match(t):
        return True
    return t in _RUNNING_HEADERS


def is_heading(text: str) -> bool:
    """章/节标题（含本书特有的「…方证案例研究」章名）。"""
    t = text.strip()
    if _HEADING.match(t):
        return True
    return "方证案例研究" in t and len(t) < 40


def clean_blocks(raw: list[str]) -> list[str]:
    """去空行、去噪音行，并把重复出现的章标题裁到只剩第一次。

    注意：只对标题去重，正文里重复出现的短句（如「脉浮紧。」）必须原样保留，
    否则会把正常的论述删掉。
    """
    out: list[str] = []
    seen_heading: set[str] = set()
    for text in raw:
        t = text.strip()
        if not t or is_noise(t):
            continue
        if is_heading(t):
            key = re.sub(r"\s+", "", t)
            if key in seen_heading:
                continue
            seen_heading.add(key)
        out.append(t)
    return out


def read_docx_blocks(path: str) -> list[str]:
    """按文档顺序返回非空段落；表格位置留一个占位符。"""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    if body is None:
        return []
    blocks: list[str] = []
    for child in body:
        if child.tag == W + "p":
            text = "".join(node.text or "" for node in child.iter(W + "t")).strip()
            if text:
                blocks.append(text)
        elif child.tag == W + "tbl":
            blocks.append(TABLE_PLACEHOLDER)
    return blocks
