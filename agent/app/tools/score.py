"""辨证（证候）比对评分工具。

## 它解决什么

练习台判分要区分三项：辨证、方剂、治法。方剂是集合运算（药味 F1），可靠；
辨证与治法原先由 `svc-training` 的 `RuleScorer.coverage()` 用**二字词字面覆盖率**
打分——「恶风」与「怕风」不算命中，学生写对了同义词也丢分
（见 `backend/svc-training/.../RuleScorer.java` 类注释）。

本工具把这一步换成**语义比对**，回答"学生答到了参考答案的哪几条证候"。

## 职责分工：切条目与算分归代码，判同义归模型

设计红线四：能用规则算的不交给大模型。所以：

| 环节 | 谁做 | 为什么 |
|---|---|---|
| 参考答案切成证候条目 | 代码（`_segments`，按标点切） | 让模型自己切会把「脉浮缓」拆成「脉浮」+「脉缓」`[实核 2026-11-11]` |
| 每条是否被答到 | 模型 | 判断「恶风」与「怕风」是同一证候，这是它该干的活 |
| 命中/遗漏/多余的组装 | 代码 | 模型只回一份"命中的条目原词"清单，其余全部由集合运算推出 |
| 分数 | 代码（`_score_of`） | `|hit| / (|hit| + |miss|)`，可复现、可解释 |
| 防幻觉 | 代码（`_match_items`） | 模型回的和候选条目逐字对不上就丢弃，不进 hit |

这是对 `project_plan/08` §7 的**有意偏离**（那里把 score 放进结构化输出、让模型自己切条目）。
实测 Qwen2.5-7B 会拆碎参考条目并漏项，因此改成"代码给清单、模型只做二分类"。

## 参考答案从哪来

库里没有 `syndrome` 字典（`syndrome` / `symptom` / `formula_syndrome_rel` 三张表
`[实核 2026-11-11]` 均为 0 行），能用的参考文本是自由文本：

| 来源 | 填充率 `[实核 2026-11-11]` | 形态 |
|---|---|---|
| `formula.syndrome_text` | 232 / 245 | 症状串（「恶风，发热，汗出，头痛，脉浮缓」） |
| `case_record.syndrome_text` | 276 / 290 | 多为舌脉（「舌淡红，苔薄白；脉浮数」） |

所以本工具**入参就是两段文本**，自己不查库：调用方（问答 Agent 或将来的
`/api/agent/grade`）负责把参考答案取好传进来。这样它既能当工具用，
也能被评分端点当纯函数复用。

## 降级

模型未配置、超时、返回结构不合法、或"说全错但字面明明有重合"时，
退回**条目级字面比对**（与语义路径同一套条目与同一套算分口径，只是判断依据
从"是不是同一证候"退化为"字面重合是否过半"），并置 `degraded=true`。
宁可给一个保守分数并说清口径，也不要抛异常或凭空给 0 分。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm import get_chat_model
from app.tools.common import error_result, ok_result

logger = logging.getLogger("herbmind-agent")

# 参考答案与用户解答的长度上限：证候描述本就是短文本，超长说明调用方传错了字段
# （比如把整段医案正文当 syndrome 传进来），截断而不是硬报错，避免整条链路失败。
MAX_TEXT_LEN = 600

# 评分属医学判断，按 08 文档 §12 用 temperature=0
SCORE_TEMPERATURE = 0.0

# 证候描述的条目分隔符：顿号切症状、分号切舌脉、句号切整句
_SEGMENT_SPLIT = re.compile(r"[，,、；;。.！!？?\n\r]+")

# 片段被判为「已表达到」的门槛：片段内半数以上二字词出现在对方文本里
_COVER_RATIO = 0.5

# 降级时 extra 最多回报几项：学生多写的内容通常很长，全量返回只会把工具结果撑爆
MAX_EXTRA = 20

NOTICE_SCORE = (
    "本评分为系统对「用户表述与参考答案是否指同一证候」的比对结果，仅供学习参考，"
    "不构成诊断或处方建议；参考答案本身为库内语料原文，未做推断。"
)

_SYSTEM_PROMPT = """你是中医证候表述的比对员。任务只有一个：判断学生答到了下面参考答案里的哪几条。

严格遵守：
1. 只做比对，不做诊断、不推断病机、不补充参考答案里没有的内容；
2. `matched` 里**只能**放给定条目清单中出现过的条目，且必须**逐字照抄**清单原文
   （不要改写、不要拆分、不要合并两个条目）；
3. 同义改写算答到：「恶风」与「怕风」、「不汗出」与「无汗」是同一证候；
4. 以下情况**不算**答到：
   - 程度不同：「微热」与「高热」、「大汗」与「汗出」；
   - 时间不同：「午后发热」与「发热」；
   - 部位不同：「心下痞」与「腹满」；
   - 舌象/脉象只答对一部分：「脉浮」不等于「脉浮缓」，「苔薄白」不等于「苔白腻」，
     必须整体一致才算答到；
5. 学生答的是方名、治法或方剂组成，一律不算答到任何条目；
6. 一条都没答到就返回空列表，不要为凑数硬匹配；不要输出分数、不要解释。
"""


class SyndromeScore(BaseModel):
    """模型的结构化输出：**只有一份"答到的条目"清单**，没有分数、没有遗漏项。

    遗漏由代码用「候选条目 − 命中条目」推出，多余由代码用学生片段反查推出。
    模型能做的事越少，出错面越小。
    """

    matched: list[str] = Field(
        default_factory=list,
        description="学生答到的参考条目，必须与给定条目清单逐字一致；一条都没有就给空列表",
    )


def _clip(text: str, limit: int = MAX_TEXT_LEN) -> str:
    """去空白并截断。"""
    cleaned = (text or "").strip()
    return cleaned if len(cleaned) <= limit else cleaned[:limit]


def _dedup(items: list[str]) -> list[str]:
    """去空、去重、保序（模型会重复列同一项）。"""
    seen: set[str] = set()
    out: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _score_of(hit: list[str], miss: list[str]) -> int:
    """覆盖率口径：命中 / (命中 + 遗漏)。

    参考答案为空 → 0 分（没有标准答案就不该给分，与 `RuleScorer` 同口径）。
    多余项（extra）不扣分：学生多写了别的证候，说明观察更细，不该因此扣分；
    它只作为提示信息返回，是否算错由调用方（练习台）自己决定。
    """
    total = len(hit) + len(miss)
    if total == 0:
        return 0
    return max(0, min(100, round(100 * len(hit) / total)))


def _bigrams(text: str) -> set[str]:
    """只保留汉字/字母/数字后切二字词（与 `RuleScorer.bigrams` 同口径）。"""
    buf = [c for c in (text or "") if c.isalnum()]
    joined = "".join(buf)
    return {joined[i : i + 2] for i in range(len(joined) - 1)}


def _segments(text: str) -> list[str]:
    """把证候描述按标点切成「证候条目」，去掉 1 字碎屑（如单独的「脉」）。"""
    return [part.strip() for part in _SEGMENT_SPLIT.split(text or "") if len(part.strip()) >= 2]


def _covered(segment: str, other_grams: set[str]) -> bool:
    """该片段是否已被对方文本表达到（字面口径）。"""
    grams = _bigrams(segment)
    if not grams:
        return False
    return len(grams & other_grams) / len(grams) >= _COVER_RATIO


def _claims(segment: str, target: str) -> bool:
    """两个片段是否互为对方的字面说法（双向，取宽的一侧）。

    单向判断会在「脉浮缓」对「脉浮缓而数」这类包含关系上失手，所以两边都测一次。
    """
    return _covered(segment, _bigrams(target)) or _covered(target, _bigrams(segment))


def _norm(text: str) -> str:
    """只留汉字/字母/数字，用于"模型抄条目时多了空格或标点"的容错比较。"""
    return "".join(c for c in (text or "") if c.isalnum())


def _match_items(matched_raw: list[str], items: list[str]) -> list[str]:
    """把模型回的命中清单对齐到候选条目，防幻觉。

    只做**逐字（或去标点后逐字）相等**的匹配，不做包含关系匹配。
    实测 Qwen2.5-7B 会把「脉浮缓」答成「脉浮」`[实核 2026-11-11]`，
    若用包含匹配把它救回来，就等于承认"只答对一半算命中"，分数会虚高；
    宁可丢弃这条（保守扣分），也不能让候选清单外的说法混进 hit。
    """
    by_norm = {_norm(item): item for item in items}
    hits: list[str] = []
    for raw in _dedup(matched_raw):
        if raw in items:
            hits.append(raw)
            continue
        aligned = by_norm.get(_norm(raw))
        if aligned:
            hits.append(aligned)
    return _dedup(hits)


def _literal_match(user_syndrome: str, items: list[str]) -> list[str]:
    """降级口径：条目内过半二字词出现在学生作答里即算命中。"""
    user_grams = _bigrams(user_syndrome)
    return [item for item in items if _covered(item, user_grams)]


def _assemble(
    *,
    items: list[str],
    hit: list[str],
    user_syndrome: str,
    degraded: bool,
    reason: str = "",
) -> dict[str, Any]:
    """用「候选条目 − 命中」推出遗漏，用学生片段反查推出多余，算分。"""
    hit_set = set(hit)
    miss = [item for item in items if item not in hit_set]
    extra = [seg for seg in _segments(user_syndrome) if not any(_claims(seg, h) for h in hit)]
    return {
        "ok": True,
        "hit": hit,
        "miss": miss,
        "extra": extra[:MAX_EXTRA],
        "score": _score_of(hit, miss),
        "degraded": degraded,
        "hint": reason,
    }


async def _llm_match(user_syndrome: str, items: list[str]) -> list[str]:
    """让模型挑出被答到的条目。失败由调用方降级。"""
    model = get_chat_model()
    # 评分必须 temperature=0：model_copy 而不是 bind，因为 with_structured_output 要 ChatModel
    scorer = model.model_copy(update={"temperature": SCORE_TEMPERATURE}).with_structured_output(
        SyndromeScore,
        method="function_calling",
    )
    numbered = "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"参考答案条目：\n{numbered}\n\n学生作答：\n{user_syndrome}",
        },
    ]
    parsed = await scorer.ainvoke(messages)
    matched = getattr(parsed, "matched", None)
    if matched is None:
        raise ValueError("结构化输出缺少 matched 字段")
    return list(matched)


async def score_syndrome(user_syndrome: str, ref_syndrome: str) -> dict[str, Any]:
    """比对两段证候文本，返回 hit / miss / extra / score / degraded。

    是纯函数式的域内实现，**不查库**：`/api/agent/grade` 将来直接复用它，
    不必经由工具调用循环。
    """
    user_text = _clip(user_syndrome)
    ref_text = _clip(ref_syndrome)
    if not user_text:
        return {
            "ok": False,
            "hit": [],
            "miss": [],
            "extra": [],
            "score": 0,
            "degraded": False,
            "hint": "学生作答为空，无法评分：请先给出辨证/证候描述。",
        }
    if not ref_text:
        return {
            "ok": False,
            "hit": [],
            "miss": [],
            "extra": [],
            "score": 0,
            "degraded": False,
            "hint": "参考答案为空，无法评分：没有标准答案时不应给分。",
        }

    items = _segments(ref_text)
    if not items:
        # 参考答案只有标点或单字，切不出条目
        return {
            "ok": False,
            "hit": [],
            "miss": [],
            "extra": [],
            "score": 0,
            "degraded": False,
            "hint": "参考答案无法切分为证候条目，请检查传入的是否为证候描述文本。",
        }

    def fallback(reason: str) -> dict[str, Any]:
        """降级出口：条目级字面比对 + 一句为什么降级。"""
        return _assemble(
            items=items,
            hit=_literal_match(user_text, items),
            user_syndrome=user_text,
            degraded=True,
            reason=f"{reason}已退回字面比对（条目内半数字词重合才算命中，近义表述可能未计入）。",
        )

    if not get_settings().llm_configured:
        return fallback("模型未配置。")

    try:
        matched_raw = await _llm_match(user_text, items)
    except Exception as exc:  # noqa: BLE001 —— 模型超时/额度/结构不合法一律降级
        logger.warning("证候语义比对失败，降级为字面比对：%s", exc)
        return fallback(f"语义比对失败（{type(exc).__name__}）。")

    hit = _match_items(matched_raw, items)
    if not hit and _literal_match(user_text, items):
        # 模型说一条都没答到，但字面明明有重合：这是模型判断失效，不是学生全错。
        # 直接给 0 分等于冤枉学生。
        logger.warning("证候比对判定为全错但字面有重合，降级为字面比对（items=%d）", len(items))
        return fallback("模型判定与字面重合矛盾。")

    return _assemble(items=items, hit=hit, user_syndrome=user_text, degraded=False)


@tool
async def syndrome_score(user_syndrome: str, ref_syndrome: str) -> dict[str, Any]:
    """比对学生的辨证作答与参考答案，返回命中/遗漏/多余的证候清单与得分（0~100）。

    什么时候用它：用户给出**自己的辨证结论**并希望知道哪里对、哪里漏
    （如「我辨的是恶风发热汗出，对不对」「我这个答案能得多少分」），
    且**参考答案已经在手**（方剂或医案原文里的证候描述）。

    什么时候不要用：用户只是问方剂组成、问条文出处、问某方治什么 —— 那些用
    `search_formula` / `search_case` / `semantic_recall`，本工具不是查证工具。

    参数：
    - user_syndrome：学生/用户写的证候描述原文（不要替用户改写或润色）
    - ref_syndrome：参考答案的证候原文（通常是库里方剂或医案的证候段落，原样传入）

    返回：`hit`（答到的证候条目）、`miss`（遗漏的条目）、`extra`（多说且未对应任何条目的内容）、
    `score`（覆盖率得分，无标准答案时为 0）、`degraded`（true 表示本次退回了字面比对，
    此时 `hint` 会说明口径）。
    """
    result = await score_syndrome(user_syndrome, ref_syndrome)

    if not result["ok"]:
        return error_result(str(result.get("hint") or "评分失败"))

    item = {
        "hit": result["hit"],
        "miss": result["miss"],
        "extra": result["extra"],
        "score": result["score"],
        "degraded": result["degraded"],
    }
    hint = str(result.get("hint") or "").strip()
    if not hint:
        hint = (
            "得分＝命中数 ÷（命中数＋遗漏数）；extra 按字面判断、不扣分，"
            "可能包含已命中条目的同义说法（如用「怕风」命中「恶风」后仍被列出）；"
            "参考答案为库内原文，未做推断。"
        )
    return ok_result([item], notice=NOTICE_SCORE, hint=hint)


__all__ = ["SyndromeScore", "score_syndrome", "syndrome_score"]
