"""svc-graph（:8085）客户端：知识图谱查询。

`/internal/graph/neighbors` 返回**裸 DTO**：

    {"center":{id,label,name,props},
     "nodes":[{id,label,name,props}...],   // 不含 center，按 label 再按 name 升序
     "edges":[{source,target,rel,props}...],
     "truncated":false}

错误口径（与 svc-catalog 一致，但多了 4040）：
- 4000 参数错误（entity 为空 / label 不支持 / hops 越界）→ HTTP 400
- 4040 实体不存在 → HTTP 404（这是**查不到**，不是故障；工具层要转 hit=false）
- 5000 Neo4j/PG 不可用 → HTTP 500
"""

from __future__ import annotations

from typing import Any

from app.clients.base import get_json


async def neighbors(
    *,
    entity: str,
    label: str | None = None,
    hops: int = 1,
    limit: int = 50,
) -> dict[str, Any]:
    """GET /internal/graph/neighbors —— 单实体邻居子图。"""
    return await get_json(
        "graph",
        "/internal/graph/neighbors",
        {"entity": entity, "label": label, "hops": hops, "limit": limit},
    )


async def subgraph(
    *,
    entity: str | None = None,
    label: str | None = None,
    hops: int = 2,
    types: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """GET /internal/graph/subgraph —— 多起点子图（暂未接工具，留作后续图谱问答）。"""
    return await get_json(
        "graph",
        "/internal/graph/subgraph",
        {"entity": entity, "label": label, "hops": hops, "types": types, "limit": limit},
    )
