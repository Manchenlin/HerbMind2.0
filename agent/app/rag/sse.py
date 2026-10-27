"""SSE（Server-Sent Events）报文拼装。

协议格式（每条消息）：
    event: <事件名>\\n
    data: <单行 JSON>\\n
    \\n

两个容易踩的点，都在这里一次性处理掉：

1. **data 必须是单行**。SSE 用换行分隔字段，JSON 里一旦出现裸换行，
   浏览器会把后半截当成新字段丢掉。`json.dumps` 会把换行转义成 `\\n`，天然安全，
   所以这里禁止手写字符串拼 JSON。

2. **中文不要转 \\uXXXX**。`ensure_ascii=False` 直出中文，配合 UTF-8 编码更省带宽，
   也便于抓包/日志肉眼排查。浏览器 EventSource 按 UTF-8 解码，没问题。

事件名约定（与 project_plan/09_API契约清单.md §13.3 对齐，两处新增字段见下）：

| event    | data                                                       |
| -------- | ---------------------------------------------------------- |
| tool     | {"name":"retrieval","status":"start"}                      |
|          | {"name":"retrieval","status":"done","hits":5}  ← 新增      |
| citation | {"index":1,"id":"cu_14","type":"formula",...}  ← 比契约多 index |
| token    | {"text":"桂枝"}                                            |
| done     | {"conversationId":...,"degraded":false,"usage":{...},      |
|          |  "illegalCitations":[]}                        ← 新增      |

`citation.index` 就是回答正文里 `[n]` 的 n，前端不用自己数顺序。
`illegalCitations` 是模型编造的越界编号（正文里已剔不掉了——token 早发出去了），
前端可按它把这些角标从已渲染文本里去掉，避免"引用了一张不存在的卡"。
"""

from __future__ import annotations

import json
from typing import Any

# 事件名常量：避免各处手写字符串拼错
EVENT_TOOL = "tool"
EVENT_TOKEN = "token"
EVENT_CITATION = "citation"
EVENT_DONE = "done"

# 流式响应必须带上的头，否则会被中间层"攒着一起发"，流式就白做了
# 注意：不要加 Connection: keep-alive —— 它是逐跳头（RFC 7230 §6.1），代理不得转发，
# HTTP/2（RFC 7540 §8.2.2）更是直接禁用；连接保活由 ASGI 服务器自己管。
STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    # nginx 默认会缓冲上游响应，加这个头让它边收边转
    "X-Accel-Buffering": "no",
}


def sse(event: str, data: dict[str, Any]) -> str:
    """拼一条 SSE 消息。"""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def tool(name: str, status: str, **extra: Any) -> str:
    """工具调用轨迹（前端渲染"工具卡"）。"""
    return sse(EVENT_TOOL, {"name": name, "status": status, **extra})


def token(text: str) -> str:
    """正文片段（打字机效果）。"""
    return sse(EVENT_TOKEN, {"text": text})


def citation(index: int, payload: dict[str, Any]) -> str:
    """引用卡。index 对应正文里的 [index]。"""
    return sse(EVENT_CITATION, {"index": index, **payload})


def done(conversation_id: str, degraded: bool, **extra: Any) -> str:
    """流结束。前端收到它就把"生成中"状态收掉。"""
    return sse(EVENT_DONE, {"conversationId": conversation_id, "degraded": degraded, **extra})
