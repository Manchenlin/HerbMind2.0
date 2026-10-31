"""图谱工具：查某实体在图谱里的邻居。

图里的真实结构（`database/etl/build_graph.py` 落库的）：
    (:Formula {id, name, syndrome, page})-[:COMPOSED_OF {dose, unit, role}]->(:Herb {name})

所以只能按 `Formula` / `Herb` 两类节点查；**没有** syndrome / symptom 节点
（`syndrome` 表 0 行，证型未实体化），这里不假装支持。

数据源（2026-10-31 起）：改走 svc-graph 的 `/internal/graph/neighbors`，不再自己拼 Cypher。
好处是标签白名单、跳数夹紧、去重这些逻辑只在 svc 里实现一次，前端图谱页与 Agent 看到的是同一张图。

标签白名单**仍然保留在工具层**：非法标签本地直接拦掉，不浪费一次 HTTP，
也避免把「模型传错参数」和「图谱服务坏了」混成同一句提示。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.clients import SvcError
from app.clients import graph as graph_client
from app.tools.common import clamp_int, error_result, miss_result, ok_result

logger = logging.getLogger("herbmind-agent")

# 中文/小写别名 → 真实标签。白名单之外的输入一律拒绝，绝不透传给 svc
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
    """把用户/模型给的标签映射成真实标签；不认识就返回 None。"""
    return _LABEL_ALIASES.get((label or "").strip().lower())


def _rel_types(edges: list[dict[str, Any]], node_id: str, center_id: str) -> list[str]:
    """从边表里取某邻居与中心节点之间的关系类型。

    svc 只返回「一端是 center」的边，所以每个邻居理论上都能找到一条；
    找不到时返回空列表而不是编一个 COMPOSED_OF —— 图里没有的关系不能凭空补。
    """
    out: list[str] = []
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if {source, target} == {node_id, center_id}:
            rel = edge.get("rel")
            if rel and rel not in out:
                out.append(str(rel))
    return out


@tool
async def graph_neighbors(entity: str, label: str = "Formula", hops: int = 1) -> dict[str, Any]:
    """查询知识图谱中某个实体的邻居（只读，事实性查询）。

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

    try:
        data = await graph_client.neighbors(
            entity=name, label=node_label, hops=depth, limit=MAX_NEIGHBORS
        )
    except SvcError as exc:
        # 404（4040）= 实体不存在，属于「查不到」而不是故障：转 hit=false，
        # 让模型如实说"图谱里没有这个实体"，而不是说"图谱坏了"。
        if exc.status == 404:
            return miss_result(
                f"图谱中未找到「{name}」（label={node_label}），服务端说明：{exc.msg}。"
                "可能是名称写法不同，或该实体没有建成图谱节点。请如实告知用户，不要凭印象补邻居。"
            )
        logger.warning("graph_neighbors 调用图谱服务失败：%s", exc)
        if exc.unreachable:
            return error_result(
                f"{exc.label}暂时不可用（{exc.msg}），本次没有查到任何邻居。"
                "请改为用 search_formula / search_case 作答，或如实告知用户稍后重试。"
            )
        return error_result(f"图谱查询失败（{exc.msg}），请调整实体名或节点类型后重试。")

    center = data.get("center") or {}
    center_id = str(center.get("id") or "")
    edges = list(data.get("edges") or [])
    truncated = bool(data.get("truncated"))

    items: list[dict[str, Any]] = []
    for node in data.get("nodes") or []:
        node_name = str(node.get("name") or "").strip()
        if not node_name:
            continue
        node_id = str(node.get("id") or "")
        items.append(
            {
                "id": node_id,
                "label": node.get("label") or "",
                "name": node_name,
                "relTypes": _rel_types(edges, node_id, center_id),
            }
        )

    if not items:
        return miss_result(
            f"图谱中未找到「{name}」（label={node_label}）的邻居：可能是名称写法不同，"
            "或该实体没有建成图谱节点。请如实告知用户，不要凭印象补邻居。"
        )

    hint = (
        f"仅显示前 {len(items)} 个邻居（服务端已截断），如需更多请缩小范围后再查。"
        if truncated
        else ""
    )
    return ok_result(items, hint=hint)
