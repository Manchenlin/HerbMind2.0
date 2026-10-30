"""图谱工具：查某实体在 Neo4j 里的邻居子图。

图里的真实结构（`database/etl/build_graph.py` 落库的）：
    (:Formula {id, name, syndrome, page})-[:COMPOSED_OF {dose, unit, role}]->(:Herb {name})

所以只能按 `Formula` / `Herb` 两类节点查；**没有** syndrome / symptom 节点
（`syndrome` 表 0 行，证型未实体化），这里不假装支持。

安全：Cypher 的标签与跳数**不能参数化**（Neo4j 不支持），只能字符串拼接，
因此标签走白名单映射、跳数走整数夹紧 —— 这是本文件唯一拼接的地方，改代码时别放松。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.db import get_neo4j_driver
from app.tools.common import clamp_int, error_result, miss_result, ok_result

logger = logging.getLogger("herbmind-agent")

# 中文/小写别名 → 真实标签。白名单之外的输入一律拒绝，绝不直接拼进 Cypher
_LABEL_ALIASES = {
    "formula": "Formula",
    "方剂": "Formula",
    "方": "Formula",
    "方子": "Formula",
    "herb": "Herb",
    "药": "Herb",
    "药味": "Herb",
    "中药": "Herb",
    "本草": "Herb",
}

MAX_HOPS = 3      # 跳数越多路径爆炸，3 跳足够"方—药—方"的横向联想
MAX_NEIGHBORS = 50


def resolve_label(label: str) -> str | None:
    """把用户/模型给的标签映射成 Neo4j 真实标签；不认识就返回 None。"""
    return _LABEL_ALIASES.get((label or "").strip().lower())


@tool
def graph_neighbors(entity: str, label: str = "Formula", hops: int = 1) -> dict[str, Any]:
    """查询知识图谱中某个实体的邻居子图（只读，事实性查询）。

    适用范围：本图谱只实体化了**方剂**与**药味**两类节点，关系是 COMPOSED_OF（方剂组成）。
    证型/症状/条文都还没有实体化，问"某证型有哪些方"在本工具里查不到，请改用 search_case。

    参数：
    - entity：实体名或 id，如「麻黄汤」或「f_1」；药味传药名，如「桂枝」
    - label：节点类型，只接受 Formula（方剂）或 Herb（药味），默认 Formula
    - hops：跳数 1~3，默认 1。1 跳=直接邻居（方的药味 / 含该药的方），
      2 跳能看到"同药异方"（方—药—方）

    返回：邻居节点的类型、名称、经过的关系类型。hit=false 说明图谱里没有这个实体。
    """
    name = (entity or "").strip()
    if not name:
        return error_result("entity 不能为空：请给出方名/药名或实体 id，例如 entity='麻黄汤'。")

    node_label = resolve_label(label)
    if node_label is None:
        return error_result(
            f"不支持的节点类型「{label}」：本图谱只有 Formula（方剂）与 Herb（药味）两类节点。"
        )

    depth = clamp_int(hops, default=1, minimum=1, maximum=MAX_HOPS)

    # 这里必须拼接（标签与跳数不能参数化），但拼接内容已全部白名单化 + 整数化
    cypher = f"""
    MATCH (c:{node_label})
    WHERE c.name = $name OR c.id = $name
    MATCH path = (c)-[*1..{depth}]-(other)
    WITH other, relationships(path) AS rels
    RETURN labels(other)[0] AS label,
           coalesce(other.name, other.id, '') AS name,
           [r IN rels | type(r)] AS relTypes
    LIMIT $limit
    """

    try:
        with get_neo4j_driver().session() as session:
            records = list(session.run(cypher, name=name, limit=MAX_NEIGHBORS))
    except Exception as exc:  # noqa: BLE001 —— 工具不许抛
        logger.exception("graph_neighbors 查询失败")
        return error_result(f"图谱服务暂时不可用（{type(exc).__name__}），请改为用 search_formula 查。")

    seen: set[tuple[str, str]] = set()
    items: list[dict[str, Any]] = []
    for record in records:
        key = (record["label"] or "", record["name"] or "")
        if key in seen or not key[1]:
            continue
        seen.add(key)
        items.append(
            {"label": key[0], "name": key[1], "relTypes": list(record["relTypes"] or [])}
        )

    if not items:
        return miss_result(
            f"图谱中未找到「{name}」（label={node_label}）：可能是名称写法不同，"
            "或该实体没有建成图谱节点。请如实告知用户，不要凭印象补邻居。"
        )
    return ok_result(items)
