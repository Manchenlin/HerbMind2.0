"""Agent 工具集（一期）。

纪律（`CODEBUDDY.md` §五 设计红线）：
- 工具只做**查证与检索**：不推断功效、不给剂量、不生成新方；
- 查不到就返回 `hit=false` + 具体 hint，不说"一般来说""临床上多用于"；
- 能用规则/SQL/Cypher 算的一律不交大模型 —— 工具内部没有任何 LLM 调用。

一期只挂 **5 个**有真实数据支撑的工具。设计文档（`project_plan/08` §4）列的
`dosage_convert` 暂不挂，原因是库里没有依据：`dosage_rule` 0 行 ——
挂着只会让模型选错工具后编出一个"换算结果"，违反红线二。数据补齐后再加，
工具总数仍控制在 6~8 个（工具越多选择准确率越低）。

`syndrome_score` 于 2026-11-11 补上：原先不挂的理由是"`syndrome`/`symptom`/`formula_syndrome_rel`
都是 0 行、没有证候字典"，但实核发现**参考答案根本不需要字典**——`formula.syndrome_text`
232/245、`case_record.syndrome_text` 276/290 都是可用的证候自由文本，比对本来就是对两段
文本做语义判断（见 `tools/score.py` 模块注释）。字典缺的是"方-证-症"结构化关系，
那是图谱查询的事，不影响对比打分。

数据源（2026-10-31 起）：四个检索类工具全部走各 svc 的 `/internal/**`，不再直连 PG / Neo4j，
所以**全部是 async**（HTTP 客户端是 `httpx.AsyncClient`）。调用方统一用 `ainvoke`；
不要用 `invoke` —— 纯 async 工具在同步入口里会直接报「coroutine was never awaited」类错误。

`syndrome_score` 是唯一**内部调 LLM** 的工具：证候语义比对按设计红线四属"该交模型"的部分
（药味/剂量/Jaccard 仍全部用规则），分数本身仍由代码用集合运算算，不由模型报。

为什么不让工具直连库：同一个问题，前端经 BFF 查一次、Agent 经工具查一次，两套 SQL 必然漂移，
最后没人说得清哪个结果对。迁到 svc 的 `/internal` 后，检索口径只有一份实现。
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from app.tools.catalog import search_case, search_formula
from app.tools.graph import graph_neighbors
from app.tools.recall import semantic_recall
from app.tools.score import syndrome_score

# 挂给模型用的工具列表：顺序固定，便于测试与日志比对
ALL_TOOLS: list[BaseTool] = [
    search_formula,
    search_case,
    semantic_recall,
    graph_neighbors,
    syndrome_score,
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
    "syndrome_score",
    "tool_names",
]
