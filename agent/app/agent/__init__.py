"""Agent 编排层：工具调用循环。

与 `app/rag/` 的分工：
- `rag/` 负责「检索 + 提示词 + 引用」这些**无状态**能力；
- `agent/` 负责「模型要不要取证、取几轮、失败了怎么办」这些**有状态**的编排。

工具调用循环刻意手写（不用 `langchain.agents.create_agent`），理由见 `runner.py` 顶部。
"""

from __future__ import annotations

from app.agent.runner import ToolTrace, run_tool_loop, stream_tool_loop

__all__ = ["ToolTrace", "run_tool_loop", "stream_tool_loop"]
