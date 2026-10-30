"""Agent 工具集（一期）。

纪律（`CODEBUDDY.md` §五 设计红线）：
- 工具只做**查证与检索**：不推断功效、不给剂量、不生成新方；
- 查不到就返回 `hit=false` + 具体 hint，不说"一般来说""临床上多用于"；
- 能用规则/SQL/Cypher 算的一律不交大模型 —— 工具内部没有任何 LLM 调用。

一期只挂 **4 个**有真实数据支撑的工具。设计文档（`project_plan/08` §4）列的
`syndrome_score` 与 `dosage_convert` 暂不挂，原因是库里没有依据：
`syndrome`/`symptom`/`formula_syndrome_rel` 各 0 行，`dosage_rule` 0 行 ——
挂着也只会让模型选错工具后编出一个"换算结果"，违反红线二。
数据补齐后再加，工具总数仍控制在 6~8 个（工具越多选择准确率越低）。

sync / async 混用是刻意的：PG（psycopg）与 Neo4j 驱动是同步的，只有语义召回要等
异步 embedding 客户端。LangChain 的 `ainvoke` 对两者都能调。
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from app.tools.catalog import search_case, search_formula
from app.tools.graph import graph_neighbors
from app.tools.recall import semantic_recall

# 挂给模型用的工具列表：顺序固定，便于测试与日志比对
ALL_TOOLS: list[BaseTool] = [
    search_formula,
    search_case,
    semantic_recall,
    graph_neighbors,
]


def tool_names() -> list[str]:
    """工具名列表（日志与冒烟检查用）。"""
    return [t.name for t in ALL_TOOLS]


__all__ = [
    "ALL_TOOLS",
    "graph_neighbors",
    "search_case",
    "search_formula",
    "semantic_recall",
    "tool_names",
]
