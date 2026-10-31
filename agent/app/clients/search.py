"""svc-search（:8083）客户端：多维检索与混合召回。

两个端点返回同一个 `SearchResultVO`：

    {"list":[SearchHitVO...], "total":245, "page":1, "size":8,
     "mode":"hybrid|fulltext|fuzzy|browse", "tookMs":23, "facets":{...}}

`SearchHitVO` 关键字段：id（content_unit.id）、refType（formula/case/quote）、refId（f_1/cs_3）、
title（方名 / 医案标题）、snippet（正文摘录）、score（0~1 相关度）、herbs（方剂药味，按库内顺序）、
matchedBy（命中的召回腿：vector/fulltext/fuzzy/quote）、page、chapter、section。

⚠️ **q 为空时 svc 不跑任何召回腿**（只返回分面），所以「只按药味查」也必须把药味当 q 传，
否则会拿到一个空列表并被误判成「库内没有」。
"""

from __future__ import annotations

from typing import Any

from app.clients.base import get_json, post_json


async def search(
    *,
    q: str = "",
    ref_type: str | None = None,
    herb: str | None = None,
    page: int = 1,
    size: int = 10,
    node_id: str | None = None,
    book_id: str | None = None,
) -> dict[str, Any]:
    """GET /internal/search —— 多维 / 关键词检索（分面）。"""
    return await get_json(
        "search",
        "/internal/search",
        {
            "q": q,
            "type": ref_type,
            "herb": herb,
            "nodeId": node_id,
            "bookId": book_id,
            "page": page,
            "size": size,
        },
    )


async def recall(*, q: str, size: int = 5, herb: str | None = None) -> dict[str, Any]:
    """POST /internal/search/recall —— 向量 + 全文混合召回（Agent 专用口径）。"""
    body: dict[str, Any] = {"q": q, "page": 1, "size": size}
    if herb:
        body["herb"] = herb
    return await post_json("search", "/internal/search/recall", body)
