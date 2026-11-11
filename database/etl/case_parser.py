"""把方证案例的文本块切成「案例单元 → 章节片段 → 药味剂量」。

本书的结构（实测，以麻黄汤单元为例）：

    现病史：……
    查体：舌质淡暗，苔薄白，脉浮紧。
    治法：……方拟麻黄汤加味治之。麻黄、桂枝各 18g，杏仁、荆芥各10g……
    治疗效果：……
    【问题】1.…… 2.……
    【原文回顾】1.太阳之为病……（1）
    【提要】……【讨论】……【证治归纳】……【问题解答】……

两个反直觉的点：

1. **医案段在 `【问题】` 之前**。切单元必须以 `【问题】` 为锚**向前**回溯到上一个单元结束，
   而不是从 `【问题】` 往后切 —— 后者会把现病史、治法切到上一个单元里。
2. **剂量是合并写法**。「麻黄、桂枝各 18g」表示两味药各 18g，按逗号硬切会多出
   「各 18g」这种假药，或者把「桂枝各」当成药名。
"""

from __future__ import annotations

import re

Q_MARK = "【问题】"
QA_MARK = "【问题解答】"

_MARKER = re.compile(r"^【(.+?)】$")
# 标记前段落的「首词」类别（决定 case_section.kind）
_LEAD_KINDS = ("现病史", "主诉", "查体", "辨证", "治法", "处方", "治疗效果", "按语", "按", "讨论")

# 只有这些首词代表「下一个医案开始了」——「按/按语/讨论」属于本单元结尾，不能当边界
_CASE_START = ("现病史", "主诉", "查体", "辨证", "治法", "处方", "治疗效果")
# 从治法里抽方名：方拟XXX加味/治之/主之
_FORMULA = re.compile(r"方拟([\u4e00-\u9fa5]{2,10}?)(?:加味|治之|主之|[，,。；;]|$)")

_DOSE = r"(\d+(?:\.\d+)?)\s*(g|克|两)"
_COMBINED_DOSE = re.compile(r"([\u4e00-\u9fa5]+(?:、[\u4e00-\u9fa5]+)*)各\s*" + _DOSE)
_SINGLE_DOSE = re.compile(r"([\u4e00-\u9fa5]{2,4})\s*" + _DOSE)


def _norm_unit(unit: str) -> str:
    return "g" if unit == "克" else unit


def guess_title(blocks: list[str], seq: int) -> str:
    """案例标题：优先取治法里的方名，其次第一个短标题段，最后退回「案例 N」。"""
    for block in blocks:
        match = _FORMULA.search(block)
        if match:
            return match.group(1)
    for block in blocks:
        text = block.strip()
        if len(text) <= 20 and "：" not in text and not text.startswith("【"):
            return text
    return f"案例 {seq}"


def split_units(blocks: list[str]) -> list[dict]:
    """按 `【问题】` 锚点切案例单元，医案段回溯进本单元。"""
    q_index = [i for i, b in enumerate(blocks) if b.strip() == Q_MARK]
    if not q_index:
        return []

    units: list[dict] = []
    prev_end = -1
    for n, q in enumerate(q_index):
        start = prev_end + 1
        next_q = q_index[n + 1] if n + 1 < len(q_index) else len(blocks)
        end = next_q - 1
        # 「解答」正文吞到「下一个医案开始」为止：两个单元之间没有任何分隔标记，
        # 只能靠下一段是不是以「现病史/治法/查体…」开头来判边界。
        qa_pos = next((j for j in range(q, next_q) if blocks[j].strip() == QA_MARK), None)
        if qa_pos is not None:
            last, k = qa_pos, qa_pos + 1
            while k < next_q:
                text = blocks[k].strip()
                if text.startswith("【") or text.startswith(_CASE_START):
                    break
                last, k = k, k + 1
            end = last
        unit_blocks = blocks[start : end + 1]
        units.append(
            {"index": start, "blocks": unit_blocks, "title_guess": guess_title(unit_blocks, len(units) + 1)}
        )
        prev_end = end
    return units


def split_sections(blocks: list[str]) -> list[dict]:
    """按 `【X】` 标记与首词切 case_section。"""
    sections: list[dict] = []
    kind: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            sections.append({"kind": kind or "正文", "content": "\n".join(buf)})
            buf = []

    for block in blocks:
        text = block.strip()
        marker = _MARKER.match(text)
        if marker:
            flush()
            kind = marker.group(1)
            continue
        lead = next((k for k in _LEAD_KINDS if text.startswith(k)), None)
        if lead:
            flush()
            kind = lead
        buf.append(text)
    flush()
    return sections


def parse_herbs(text: str) -> list[dict]:
    """从「治法/处方」段抽药味与剂量；剂量保持字符串，避免浮点误差。"""
    if not text:
        return []

    found: list[tuple[int, str, str, str]] = []
    covered: list[tuple[int, int]] = []

    for match in _COMBINED_DOSE.finditer(text):
        names = [n.strip() for n in match.group(1).split("、") if n.strip()]
        dose, unit = match.group(2), _norm_unit(match.group(3))
        for name in names:
            found.append((match.start(), name, dose, unit))
        covered.append((match.start(), match.end()))

    for match in _SINGLE_DOSE.finditer(text):
        if any(start <= match.start() < end for start, end in covered):
            continue
        found.append((match.start(), match.group(1), match.group(2), _norm_unit(match.group(3))))

    found.sort(key=lambda item: item[0])
    herbs: list[dict] = []
    seen: set[str] = set()
    for _, name, dose, unit in found:
        if name in seen:
            continue
        seen.add(name)
        herbs.append({"name": name, "dose": dose, "unit": unit})
    return herbs
