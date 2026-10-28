"""SSE 报文工厂的单元测试（不经过 HTTP，纯字符串）。

钉住的三件事（都是踩过的坑，见 `agent/app/rag/sse.py` 顶部注释）：
1. data 必须**单行** —— JSON 里一旦有裸换行，浏览器会把后半截当成新字段丢掉；
2. 中文**不许转成 \\uXXXX** —— 直出中文，便于抓包与日志排查；
3. 响应头必须带 `X-Accel-Buffering: no`，且**不能**手写 `Connection: keep-alive`（逐跳头，HTTP/2 禁用）。
"""

from __future__ import annotations

import json

from app.rag import sse


def _data(frame: str) -> dict:
    """从一条报文里取出 data 部分并解析。"""
    for line in frame.split("\n"):
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    # 不用 next(生成器)：缺 data 时只会抛 StopIteration，看不出是哪条报文差在哪
    raise AssertionError(f"报文里没有 data 字段：{frame!r}")


def test_token_frame_exact_format() -> None:
    """一条报文的格式固定为 `event: X\\ndata: {..}\\n\\n`。"""
    assert sse.token("桂枝") == 'event: token\ndata: {"text":"桂枝"}\n\n'


def test_chinese_is_not_escaped() -> None:
    """中文直出（ensure_ascii=False），不用 \\u 转义。"""
    frame = sse.token("麻黄汤")
    assert "麻黄汤" in frame
    assert "\\u" not in frame


def test_newline_inside_text_stays_single_line() -> None:
    """正文里的换行必须被转义，整条报文仍只占 3 个换行（协议换行）。"""
    frame = sse.token("第一行\n第二行")

    assert frame.count("\n") == 3
    assert frame.endswith("\n\n")
    assert _data(frame)["text"] == "第一行\n第二行"


def test_tool_frame_carries_extra_fields() -> None:
    """tool 事件的附加信息（如 hits）要能透传，前端据此显示"检索到 N 条"。"""
    start = _data(sse.tool("retrieval", "start"))
    done = _data(sse.tool("retrieval", "done", hits=5))

    assert start == {"name": "retrieval", "status": "start"}
    assert done == {"name": "retrieval", "status": "done", "hits": 5}


def test_citation_frame_puts_index_in_front() -> None:
    """citation 的 index 是正文 [n] 里的 n，必须原样带上。"""
    card = _data(sse.citation(2, {"id": "cu_14", "refType": "formula"}))

    assert card["index"] == 2
    assert card["id"] == "cu_14"
    assert card["refType"] == "formula"


def test_done_frame_shape() -> None:
    """done 必须带 conversationId 与 degraded，其余字段透传。"""
    payload = _data(sse.done("c_abc", False, illegalCitations=[6]))

    assert payload == {
        "conversationId": "c_abc",
        "degraded": False,
        "illegalCitations": [6],
    }


def test_stream_headers() -> None:
    """流式响应头：要禁 nginx 缓冲，且不得出现逐跳头 Connection。"""
    assert sse.STREAM_HEADERS["X-Accel-Buffering"] == "no"
    assert sse.STREAM_HEADERS["Cache-Control"] == "no-cache"
    assert not any(k.lower() == "connection" for k in sse.STREAM_HEADERS)
