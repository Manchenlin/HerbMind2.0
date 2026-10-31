"""目录类工具：按方名/药味/证治查方剂，按病证/方名/症状查医案。

两个都只做**库内事实检索**（设计红线一：只查证 + 引用）：
返回的是库里 `formula` / `case_record` 的原文摘录，不生成、不推断、不排序"哪个更好"。

数据源（2026-10-31 起）：不再直连 PG 跑 SQL，改走 svc-search 的 `/internal/search`。
为什么改：BFF 与 Agent 各写一套查询，同一个问题会出现两个答案，而且没人说得清哪个对；
统一到 svc 之后「检索口径」只有一份实现（向量 + 全文 + 词项混合召回，RRF 融合）。

**口径变化必须如实告诉模型**（红线二：查不到就说查不到，不许把"相近"说成"确证"）：
- 旧实现是库内原文**子串匹配**，命中即确证；
- 新实现是**混合召回**，会带回语义相近、但关键词并未出现的条目。
所以每条结果都补两个字段：
    `exact`        —— 本次给出的关键词是否**都能**在 title / herbs / snippet 里找到（本地确定性校验）
    `matchedTerms` —— 具体命中了哪几个关键词
**exact=false 的条目只能表述为「与问题语义相近」，不得说成「库内有此记载」。**
服务端返回的 `matchedBy`（命中的召回腿：vector / fulltext / fuzzy）原样保留，与 exact 含义不同，别混用。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.clients import SvcError
from app.clients import search as search_client
from app.tools.common import NOTICE_FACT, error_result, miss_result, ok_result

logger = logging.getLogger("herbmind-agent")

# 单次返回上限：工具给模型看的，不是给前端翻页的，多了只会稀释上下文
MAX_ITEMS = 8


def _decorate(items: list[dict[str, Any]], terms: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """给每条命中补 `exact` / `matchedTerms`。

    Returns:
        (装饰后的 items, 没能匹配上的关键词列表)
    """
    lowered = [t.strip().lower() for t in terms if t and t.strip()]
    # 用集合累加而不是逐条覆盖：只要有任意一条没命中某个词，这个词就必须出现在提示里，
    # 否则模型会把"部分条目才命中的词"当成全部命中（红线二：近似不得表述为确证）
    missed: set[str] = set()
    for item in items:
        haystack = " ".join(
            [
                str(item.get("title") or ""),
                "、".join(str(h) for h in (item.get("herbs") or [])),
                str(item.get("snippet") or ""),
            ]
        ).lower()
        matched = [t for t in lowered if t in haystack]
        item["exact"] = not lowered or len(matched) == len(lowered)
        item["matchedTerms"] = matched
        missed.update(t for t in lowered if t not in matched)
    # 按关键词原顺序输出，提示词读起来稳定，测试也能直接断言顺序
    unmatched = [t for t in lowered if t in missed]
    return items, unmatched


def _exact_hint(unmatched: list[str], total: int) -> str:
    """部分条目只是语义相近时，给模型一句必须照做的提醒。"""
    if not unmatched:
        return ""
    words = "、".join(f"「{w}」" for w in unmatched[:3])
    return (
        f"注意：{total} 条结果里部分条目 exact=false，即 {words} 并未出现在其标题/药味/摘录中，"
        "只是语义相近。表述时只能说「与问题相关的记载」，不得当作「库内确有该记载」的确证。"
    )


def _map_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """把 svc 的 SearchHitVO 收敛成工具对外的精简结构。"""
    return {
        "id": hit.get("refId") or hit.get("id"),
        "title": hit.get("title") or "",
        "herbs": list(hit.get("herbs") or []),
        "snippet": hit.get("snippet") or "",
        "page": hit.get("page") or "",
        "score": hit.get("score"),
        # 召回腿（vector/fulltext/fuzzy），由 svc 给出，原样保留
        "matchedBy": list(hit.get("matchedBy") or []),
    }


@tool
async def search_formula(name: str = "", herb: str = "", syndrome: str = "") -> dict[str, Any]:
    """按方名、药味、证治原文关键词检索方剂（只读事实检索，不推断功效）。

    参数（至少给一个，多个条件之间是 AND）：
    - name：方名关键词，如「桂枝」能命中桂枝汤、桂枝加葛根汤；
    - herb：药味名，如「麻黄」，查含该药的方剂；
    - syndrome：证治/主治原文里的关键词，如「无汗而喘」「太阳病」。

    返回：方剂 id、方名、药味（按库内顺序）、正文摘录（含证治原文）、出处页、相关度，
    以及 `exact`（关键词是否真的命中）与 `matchedBy`（命中的检索通道）。
    `exact=false` 表示只是语义相近，不要当成"库内确有记载"。
    查不到时 hit=false + hint，请如实告知用户「库内未见记载」，不要凭印象补全。
    """
    name, herb, syndrome = name.strip(), herb.strip(), syndrome.strip()
    if not (name or herb or syndrome):
        return error_result("至少提供 name / herb / syndrome 之一：例如 name='桂枝汤' 或 herb='麻黄'。")

    # svc-search 在 q 为空时不跑任何召回腿（只返回分面统计），所以只给药味时
    # 必须把药味同时当关键词传（herb 参数仍然单独作为过滤条件），否则会拿到空列表
    # 并被误判成「库内没有」。
    q = " ".join(x for x in (name, syndrome) if x) or herb

    try:
        data = await search_client.search(q=q, ref_type="formula", herb=herb or None, size=MAX_ITEMS)
    except SvcError as exc:
        logger.warning("search_formula 调用检索服务失败：%s", exc)
        if exc.unreachable:
            return error_result(
                f"{exc.label}暂时不可用（{exc.msg}），本次没有查到任何方剂。"
                "请如实告知用户检索服务异常、稍后重试，不要凭印象回答。"
            )
        return error_result(f"检索失败（{exc.msg}），请调整关键词后重试。")

    hits = [h for h in (data.get("list") or []) if (h.get("refType") or "formula") == "formula"]
    items = [_map_hit(h) for h in hits]
    if not items:
        return miss_result(
            f"库内没有符合（name={name or '-'}，herb={herb or '-'}，syndrome={syndrome or '-'}）的方剂。"
            "可以只用药味或证治关键词再试一次；仍无结果就如实告知用户未收录。"
        )

    items, unmatched = _decorate(items, [name, herb, syndrome])
    return ok_result(items, notice=NOTICE_FACT, hint=_exact_hint(unmatched, len(items)))


@tool
async def search_case(diagnosis: str = "", formula: str = "", symptom: str = "") -> dict[str, Any]:
    """检索医案（只读事实检索，不做辨证推断）。

    参数（至少给一个，多个条件之间是 AND）：
    - diagnosis：病证/治法关键词，匹配医案的证治原文，如「太阳病」「阳明腑实」；
    - formula：方名关键词，匹配医案记载的用方，如「小承气汤」；
    - symptom：症状关键词，匹配医案正文，如「大便不通」。

    返回：医案 id、标题、正文摘录（含证治与症状原文）、出处页、相关度，
    以及 `exact`（关键词是否真的命中）与 `matchedBy`（命中的检索通道）。
    查不到时 hit=false + hint；不要用医案原文去反推"应当用某方"。
    """
    diagnosis, formula, symptom = diagnosis.strip(), formula.strip(), symptom.strip()
    if not (diagnosis or formula or symptom):
        return error_result(
            "至少提供 diagnosis / formula / symptom 之一：例如 formula='小承气汤' 或 symptom='大便不通'。"
        )

    q = " ".join(x for x in (diagnosis, formula, symptom) if x)

    try:
        data = await search_client.search(q=q, ref_type="case", size=MAX_ITEMS)
    except SvcError as exc:
        logger.warning("search_case 调用检索服务失败：%s", exc)
        if exc.unreachable:
            return error_result(
                f"{exc.label}暂时不可用（{exc.msg}），本次没有查到任何医案。"
                "请如实告知用户检索服务异常、稍后重试，不要凭印象回答。"
            )
        return error_result(f"检索失败（{exc.msg}），请调整关键词后重试。")

    hits = [h for h in (data.get("list") or []) if (h.get("refType") or "case") == "case"]
    items = [_map_hit(h) for h in hits]
    if not items:
        return miss_result(
            f"库内没有符合（diagnosis={diagnosis or '-'}，formula={formula or '-'}，symptom={symptom or '-'}）的医案。"
            "可以换同义说法，或用 semantic_recall 做语义召回；仍无结果就如实告知未收录。"
        )

    items, unmatched = _decorate(items, [diagnosis, formula, symptom])
    return ok_result(items, notice=NOTICE_FACT, hint=_exact_hint(unmatched, len(items)))
