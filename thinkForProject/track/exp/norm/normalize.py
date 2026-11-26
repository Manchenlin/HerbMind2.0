# -*- coding: utf-8 -*-
"""归一化参考实现 zh-norm-1.0（供 T-01 顺序验证与 T-03 用例使用）。

它只做一件事：证明"规则顺序 + 词组白名单 + 歧义字保护"这套结构能跑通，
并让 T-03 的用例可执行。生产实现应复用同一顺序与同一份表，不允许另写一份。

字符级繁简表在这里只是示例规模（够跑通用例），生产须以 OpenCC STCharacters
全表为来源——这一点写在 rules.v1.json 的 assets 里，不在代码里承诺。

规则顺序（与 rules.v1.json 的 order 一一对应）：
  1 全半角 → 2 零宽 → 3 标点 → 4 空白 → 5 拉丁小写
  → 6 词组白名单（长词优先）→ 7 歧义字保护 → 8 字级繁简 → 9 字级异体
第 6 步必须早于第 8 步：否则"乾"已被字级转成"干"，"乾隆"再无法被保护。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

RULES_VERSION = "zh-norm-1.0"
_BASE = Path(__file__).resolve().parent

PUNCT = set("。，、；：！？“”‘’（）《》〈〉【】〔〕…—·～　!?,.;:()[]{}<>\"'`|-、〃々")
ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u00a0"}

# 示例规模的繁简表（生产取 OpenCC STCharacters 全表）
CHAR_T2S = {
    "陽": "阳", "風": "风", "脈": "脉", "黃": "黄", "湯": "汤", "連": "连",
    "參": "参", "當": "当", "歸": "归", "朮": "术", "薑": "姜", "發": "发",
    "後": "后", "裡": "里", "裏": "里", "臺": "台", "檯": "台", "範": "范",
    "鍾": "钟", "鬆": "松", "僕": "仆", "藥": "药", "醫": "医", "證": "证",
    "陰": "阴", "熱": "热", "虛": "虚", "實": "实", "萬": "万", "與": "与",
    "為": "为", "這": "这", "個": "个", "門": "门", "問": "问", "間": "间",
    "開": "开", "關": "关", "體": "体", "氣": "气", "腎": "肾", "膽": "胆",
    "腸": "肠", "經": "经", "劑": "剂", "稱": "称", "傳": "传",
    "溫": "温", "條": "条", "傷": "伤", "論": "论", "棗": "枣",
    "痺": "痹", "鬱": "郁", "濇": "涩", "濁": "浊", "濕": "湿",
}


def _load_csv(name: str) -> list[dict[str, str]]:
    path = _BASE / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _build_tables() -> tuple[list[tuple[str, str]], set[str], dict[str, str]]:
    whitelist: list[tuple[str, str]] = []
    for row in _load_csv("phrase_whitelist.csv"):
        left, right = row["显示形态"], row["归一形态"]
        if left and right:
            whitelist.append((left, right))
    whitelist.sort(key=lambda kv: -len(kv[0]))  # 长词优先

    ambiguous = {
        row["字"]
        for row in _load_csv("ambiguous_chars.csv")
        if row.get("是否参与字级转换") == "否"
    }

    variant = {row["异体"]: row["正体"] for row in _load_csv("variant_pairs.csv") if row.get("异体")}
    return whitelist, ambiguous, variant


WHITELIST, AMBIGUOUS, VARIANT = _build_tables()


def to_halfwidth(s: str) -> str:
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


def normalize(s: str) -> str:
    """按固定顺序执行 1～9 步。同输入必同输出，且对结果再调用一次不变。"""
    # 1 全半角
    s = to_halfwidth(s)
    # 2 零宽与控制字符
    s = "".join(ch for ch in s if ch not in ZERO_WIDTH and (ord(ch) >= 0x20 or ch in "\n\t"))
    # 3 标点
    s = "".join(ch for ch in s if ch not in PUNCT)
    # 4 空白
    s = "".join(ch for ch in s if not ch.isspace())
    # 5 拉丁小写
    s = s.lower()
    # 6 词组白名单：长词优先，命中即整词替换
    for left, right in WHITELIST:
        if left in s:
            s = s.replace(left, right)
    # 7～8 字级繁简（跳过歧义字）
    s = "".join(CHAR_T2S.get(ch, ch) if ch not in AMBIGUOUS else ch for ch in s)
    # 9 字级异体
    s = "".join(VARIANT.get(ch, ch) for ch in s)
    return s


if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "《桂枝湯》太陽中風，陽浮而陰弱，桂枝湯主之。"
    print(f"rules_version={RULES_VERSION}")
    print(f"in : {text}")
    print(f"out: {normalize(text)}")
    print(f"idempotent: {normalize(normalize(text)) == normalize(text)}")
    print(json.dumps({"whitelist": len(WHITELIST), "ambiguous": sorted(AMBIGUOUS)}, ensure_ascii=False))
