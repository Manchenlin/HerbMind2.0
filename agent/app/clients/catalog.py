"""svc-catalog（:8082）客户端：方剂 / 医案的权威字段。

工具的**检索**走 svc-search（统一召回口径），只有需要「库里登记的结构化字段」
（功效、证治原文、别名）时才回这里取，避免每个工具自己拼 SQL。
"""

from __future__ import annotations

from typing import Any

from app.clients.base import get_json, post_json


async def formula(formula_id: str) -> dict[str, Any]:
    """GET /internal/catalog/formula/{id} —— 方剂详情（含 alias / efficacy / syndrome / herbs）。"""
    return await get_json("catalog", f"/internal/catalog/formula/{formula_id}")


async def batch(*, ids: list[str] | None = None, names: list[str] | None = None) -> list[dict[str, Any]]:
    """POST /internal/catalog/batch —— 按 id 或方名批量取方剂摘要（一次 HTTP 补齐多条）。"""
    return await post_json(
        "catalog",
        "/internal/catalog/batch",
        {"ids": ids or [], "names": names or []},
    )


async def case_record(case_id: str) -> dict[str, Any]:
    """GET /internal/catalog/case/{id} —— 医案详情（含主方名、证治原文）。"""
    return await get_json("catalog", f"/internal/catalog/case/{case_id}")
