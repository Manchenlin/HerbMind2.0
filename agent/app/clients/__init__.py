"""各 svc `/internal/**` 的 HTTP 客户端（Agent 工具的唯一外部数据源）。

分工：
- `base.py`   单例客户端 + 超时 + 「裸 DTO / R 错误」统一解析，失败抛 `SvcError`；
- `search.py` svc-search 的多维检索与混合召回（工具的主检索口径）；
- `catalog.py` svc-catalog 的方剂/医案结构化字段（需要功效、证治原文时补取）；
- `graph.py`  svc-graph 的图谱查询。

为什么工具不再直连 PG/Neo4j：前端经 BFF 查、Agent 经工具查，如果两套查询各写一遍 SQL，
同一问题就会出现两个答案，而且没人说得清哪个对。统一走 svc 的 `/internal` 后，
「检索口径」只有一份实现。
"""

from __future__ import annotations

from app.clients.base import (
    SvcError,
    close_clients,
    get_client,
    init_clients,
    svc_base_url,
)

__all__ = [
    "SvcError",
    "close_clients",
    "get_client",
    "init_clients",
    "svc_base_url",
]
