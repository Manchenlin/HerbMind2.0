# -*- coding: utf-8 -*-
"""底本 docx 结构提取（零依赖，仅标准库）。

用途：为 T-01／T-02／T-03 与中文分词实验提供可复算的输入。
不依赖 python-docx：docx 就是 zip + XML，直接解析 word/document.xml。
只负责"取出段落与表格的原始文本和样式名"，不做任何清洗与归一。

用法：
    python extract_docx.py <docx路径> <输出jsonl路径>
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _text_of(elem: ET.Element) -> str:
    """提取一个 w:p 内的可见文本：w:t 拼接，w:br/w:cr 视为换行，w:tab 视为制表符。"""
    parts: list[str] = []
    for node in elem.iter():
        tag = node.tag
        if tag == W + "t":
            parts.append(node.text or "")
        elif tag in (W + "br", W + "cr"):
            parts.append("\n")
        elif tag == W + "tab":
            parts.append("\t")
    return "".join(parts)


def _style_of(elem: ET.Element) -> str:
    ppr = elem.find(W + "pPr")
    if ppr is None:
        return ""
    style = ppr.find(W + "pStyle")
    if style is None:
        return ""
    return style.get(W + "val") or ""


def extract(docx_path: Path) -> list[dict]:
    records: list[dict] = []
    with zipfile.ZipFile(docx_path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    if body is None:
        raise SystemExit("document.xml 中没有 w:body，文件可能不是 docx")

    para_no = 0
    table_no = 0
    for child in body:
        if child.tag == W + "p":
            text = _text_of(child)
            records.append(
                {
                    "seq": len(records),
                    "kind": "p",
                    "para": para_no,
                    "table": None,
                    "style": _style_of(child),
                    "text": text,
                }
            )
            para_no += 1
        elif child.tag == W + "tbl":
            # 表格内每个 w:p 单独成行，保留行列坐标，便于后续判断伪表/真表
            for ri, tr in enumerate(child.findall(W + "tr")):
                for ci, tc in enumerate(tr.findall(W + "tc")):
                    for p in tc.findall(W + "p"):
                        records.append(
                            {
                                "seq": len(records),
                                "kind": "tc",
                                "para": para_no,
                                "table": table_no,
                                "row": ri,
                                "col": ci,
                                "style": _style_of(p),
                                "text": _text_of(p),
                            }
                        )
            table_no += 1
    return records


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("用法: python extract_docx.py <docx路径> <输出jsonl路径>")
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    dst.parent.mkdir(parents=True, exist_ok=True)

    records = extract(src)
    with dst.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    body_ps = [r for r in records if r["kind"] == "p"]
    nonempty_ps = [r for r in body_ps if r["text"].strip()]
    tables = {r["table"] for r in records if r["kind"] == "tc"}
    chars = sum(len(r["text"]) for r in body_ps)
    styles = {}
    for r in body_ps:
        styles[r["style"]] = styles.get(r["style"], 0) + 1
    top_styles = sorted(styles.items(), key=lambda kv: -kv[1])[:8]

    print(f"输出：{dst}（{len(records)} 行）")
    print(f"正文段落：{len(body_ps)}，非空 {len(nonempty_ps)}，总字数 {chars}")
    print(f"表格：{len(tables)} 个，表内段落 {sum(1 for r in records if r['kind'] == 'tc')}")
    print(f"样式分布前 8：{top_styles}")


if __name__ == "__main__":
    main()
