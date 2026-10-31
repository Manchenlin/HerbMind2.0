"""语义召回工具：把问题直接送进混合召回（向量 + 全文 + 词项，RRF 融合）。

数据源（2026-10-31 起）：改走 svc-search 的 `POST /internal/search/recall`，
不再复用 `app/rag/retriever.py`。为什么：
- retriever 只走 pgvector 单腿，条文（classic_quote 没有向量）永远召不回来；
- svc-search 的 recall 是四腿融合，与 BFF 检索页、前端看到的是同一口径。

`app/rag/retriever.py` 本身**不动**：`ask` 主链（问题 → pgvector → 提示词）的检索口径
已按 0.5 阈值 + 方剂 6:4 配额实测校准过，本轮同时改两处会让问答质量不可归因。

⚠️ 阈值语义变了但数值保持不变：svc 的 score 是「单腿最佳分 + 多腿加成」的融合相关度，
向量腿的取值就是余弦相似度，全文/词项腿则按命中程度折算。沿用 `retrieval_min_score`
（0.5）的意图是「宁可少给，也不要塞不相关内容诱发幻觉」，与原来一致。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.clients import SvcError
from app.clients import search as search_client
from app.config import get_settings
from app.tools.common import clamp_int, error_result, miss_result, ok_result

logger = logging.getLogger("herbmind-agent")

# 与 AskRequest.topK 的上限保持一致（1~10），避免工具绕过校验把 prompt 撑爆
MAX_TOP_K = 10


@tool
async def semantic_recall(query: str, top_k: int = 5) -> dict[str, Any]:
    """按语义（而非字面）检索知识库内容单元，返回最相关的方剂/医案/条文片段与相关度。

    什么时候用它：用户描述的是**症状或场景**（如「无汗而喘、脉浮紧」），
    而不知道方名/病名，或 `search_formula` / `search_case` 用关键词没有命中。

    参数：
    - query：用户问题的关键描述（中文原文即可，不需要改写）
    - top_k：召回条数，默认 5，范围 1~10

    返回：内容单元 id、来源类型（formula/case/quote）、来源实体 id、标题、原文片段、相关度，
    以及 `matchedBy`（命中的召回通道：vector / fulltext / fuzzy / quote）。
    相关度低于阈值的会被工具层直接丢掉，所以 hit=false 时说明「语义上也没有相近内容」，
    不要改写成「可能相关」这种模糊说法。
    """
    text = query.strip()
    if not text:
        return error_result("query 不能为空：请先给出要检索的问题或症状描述。")

    k = clamp_int(top_k, default=5, minimum=1, maximum=MAX_TOP_K)
    threshold = get_settings().retrieval_min_score

    try:
        data = await search_client.recall(q=text, size=k)
    except SvcError as exc:
        logger.warning("semantic_recall 调用检索服务失败：%s", exc)
        if exc.unreachable:
            return error_result(
                f"{exc.label}暂时不可用（{exc.msg}），本次没有召回任何内容。"
                "请如实告知用户语义检索暂时不可用、稍后重试，不要凭印象回答。"
            )
        return error_result(f"语义检索失败（{exc.msg}），请稍后重试。")

    kept: list[dict[str, Any]] = []
    for hit in data.get("list") or []:
        score = hit.get("score")
        try:
            value = float(score if score is not None else 0.0)
        except (TypeError, ValueError):
            value = 0.0
        if value < threshold:
            continue
        kept.append(
            {
                "id": hit.get("id") or "",
                "refType": hit.get("refType") or "",
                "refId": hit.get("refId") or "",
                "title": hit.get("title") or "",
                "snippet": hit.get("snippet") or "",
                "score": round(value, 4),
                "matchedBy": list(hit.get("matchedBy") or []),
            }
        )

    if not kept:
        return miss_result(
            f"语义检索没有找到与「{text}」足够相近的内容（相关度均低于阈值 {threshold}）。"
            "请如实告知用户库内未检索到，或建议用方名/病名再问一次。",
            notice="",
        )
    return ok_result(kept)
