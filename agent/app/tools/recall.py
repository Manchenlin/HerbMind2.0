"""语义召回工具：把问题/片段直接送进向量检索（复用 `app/rag/retriever.py`）。

为什么不在这里另写一套 SQL：
检索口径（bge-m3 1024 维、方剂 60% + 医案 40% 配额、相似度阈值 0.5）已经在
`retriever.py` 里实测校准过，工具再抄一遍必然漂移，问答页与工具给出不同结果就说不清了。

为什么是 async：embedding 走的是异步客户端；LangChain 的 `ainvoke` 对 sync/async 工具都能调，
所以只有这个工具写成 async，其余保持 sync（PG/Neo4j 驱动本身是同步的）。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.rag.retriever import retrieve
from app.tools.common import clamp_int, error_result, miss_result, ok_result

logger = logging.getLogger("herbmind-agent")

# 与 AskRequest.topK 的上限保持一致（1~10），避免工具绕过校验把 prompt 撑爆
MAX_TOP_K = 10


@tool
async def semantic_recall(query: str, top_k: int = 5) -> dict[str, Any]:
    """按语义（而非字面）检索知识库内容单元，返回最相关的方剂/医案片段与相似度。

    什么时候用它：用户描述的是**症状或场景**（如「无汗而喘、脉浮紧」），
    而不知道方名/病名，或 `search_formula` / `search_case` 用关键词没有命中。

    参数：
    - query：用户问题的关键描述（中文原文即可，不需要改写）
    - top_k：召回条数，默认 5，范围 1~10

    返回：内容单元 id、来源类型（formula/case）、来源实体 id、标题、原文片段、相似度。
    相似度低于阈值的会被检索层直接丢掉，所以 hit=false 时说明「语义上也没有相近内容」，
    不要改写成「可能相关」这种模糊说法。
    """
    text = query.strip()
    if not text:
        return error_result("query 不能为空：请先给出要检索的问题或症状描述。")

    k = clamp_int(top_k, default=5, minimum=1, maximum=MAX_TOP_K)
    try:
        units = await retrieve(text, top_k=k)
    except Exception as exc:  # noqa: BLE001 —— 工具不许抛
        logger.exception("semantic_recall 检索失败")
        return error_result(f"语义检索暂时不可用（{type(exc).__name__}），请稍后重试。")

    items = [
        {
            "id": unit.id,
            "refType": unit.ref_type,
            "refId": unit.ref_id,
            "title": unit.title,
            "snippet": unit.snippet(),
            "score": round(unit.score, 4),
        }
        for unit in units
    ]
    if not items:
        return miss_result(
            f"语义检索没有找到与「{text}」足够相近的内容（相似度均低于阈值）。"
            "请如实告知用户库内未检索到，或建议用方名/病名再问一次。",
            notice="",
        )
    return ok_result(items)
