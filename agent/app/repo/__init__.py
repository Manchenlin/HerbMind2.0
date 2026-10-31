"""数据访问层（Agent 自己的表：`agent_conversation` / `agent_message` / `agent_tool_call`）。

为什么不放 `app/db.py`：`db.py` 只管"连接池"这类资源生命周期；
具体 SQL 归各 `repo/*.py`，一个主题一个文件，便于单测时按模块替换。
"""

from __future__ import annotations

from app.repo.conversation import (
    append_message,
    ensure_conversation,
    list_conversations,
    recent_messages,
    record_tool_call,
)

__all__ = [
    "append_message",
    "ensure_conversation",
    "list_conversations",
    "recent_messages",
    "record_tool_call",
]
