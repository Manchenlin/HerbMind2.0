"""流式问答 `/api/agent/ask`（SSE）的事件序与降级测试。

钉住的核心不变量（`agent/app/routers/ask.py` §流式问答 注释 + `rag/sse.py` 事件表）：
1. 事件序**固定**：`tool(start) → tool(done) → citation×N → token×N → done`
   引用卡必须先于正文，否则前端会出现"角标先到、卡片后到"的闪烁。
2. 流一旦开始就**没有机会改状态码**：检索/模型失败只能写进正文，HTTP 仍是 200。
3. 越界角标在流式下剔不掉（token 已发出），只能在 `done.illegalCitations` 里回传给前端擦。

零外部依赖：检索与模型流全部用替身替换。
"""

from __future__ import annotations

import collections
import time

from helpers import event_names, make_unit, parse_sse

from app.routers import ask as ask_router

HEADERS = {"X-User-Id": "u_sse"}
URL = "/api/agent/ask"


def _patch_retrieve(monkeypatch, units=None, raises: Exception | None = None) -> dict:
    spy: dict = {"called": 0}

    async def _fake(question, top_k=None, ref_type=None):
        spy["called"] += 1
        if raises is not None:
            raise raises
        return units or []

    monkeypatch.setattr(ask_router, "retrieve", _fake)
    return spy


def _patch_stream(monkeypatch, chunks=None, raise_at: int | None = None) -> dict:
    """替换模型流。chunks 形如 [("delta", "文字"), ("usage", {...})]。

    `raise_at=n` 表示"吐到第 n 个分片之前抛异常"；n 等于分片数则表示"吐完再抛"。
    """
    spy: dict = {"called": 0}
    items = list(chunks or [])

    async def _gen(messages):
        spy["called"] += 1
        if raise_at is None:
            for kind, payload in items:
                yield kind, payload
            return
        for idx, (kind, payload) in enumerate(items):
            if idx == raise_at:
                raise RuntimeError("模拟模型中断")
            yield kind, payload
        raise RuntimeError("模拟模型中断")

    monkeypatch.setattr(ask_router, "chat_stream", _gen)
    return spy


def _stream(client, body: dict, headers: dict | None = None):
    # 注意不能写 headers or HEADERS：空字典 falsy，会把"故意不带头"的用例变成带头
    resp = client.post(URL, json=body, headers=HEADERS if headers is None else headers)
    return resp, parse_sse(resp.text)


# ==================== 事件序 ====================


def test_event_order_is_tool_citation_token_done(client, monkeypatch) -> None:
    """完整链路的事件序必须是 tool → tool → citation×N → token×N → done。"""
    _patch_retrieve(monkeypatch, [make_unit(id="cu_1"), make_unit(id="cu_2", ref_type="case", ref_id="cs_3")])
    _patch_stream(monkeypatch, [("delta", "麻黄汤"), ("delta", "由四味组成 [1]"), ("usage", {"input_tokens": 7})])

    resp, events = _stream(client, {"question": "麻黄汤的组成"})

    assert resp.status_code == 200
    assert event_names(events) == [
        "tool",
        "tool",
        "citation",
        "citation",
        "token",
        "token",
        "done",
    ]

    assert events[0]["data"] == {"name": "retrieval", "status": "start"}
    assert events[1]["data"] == {"name": "retrieval", "status": "done", "hits": 2}
    # 引用卡在正文之前，且 index 从 1 连续编号
    assert [e["data"]["index"] for e in events[2:4]] == [1, 2]
    assert [e["data"]["refId"] for e in events[2:4]] == ["f_1", "cs_3"]
    # 正文按 delta 分片，不合并
    assert [e["data"]["text"] for e in events[4:6]] == ["麻黄汤", "由四味组成 [1]"]

    done = events[-1]["data"]
    assert done["degraded"] is False
    assert done["illegalCitations"] == []
    assert done["conversationId"].startswith("c_")


def test_stream_headers_are_sse_friendly(client, monkeypatch) -> None:
    """必须声明 text/event-stream，且禁掉 nginx 缓冲，否则流式名存实亡。"""
    _patch_retrieve(monkeypatch, [make_unit()])
    _patch_stream(monkeypatch, [("delta", "回答 [1]")])

    resp, _ = _stream(client, {"question": "麻黄汤的组成"})

    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["x-accel-buffering"] == "no"
    assert resp.headers["cache-control"] == "no-cache"


def test_conversation_id_is_echoed(client, monkeypatch) -> None:
    """传了 conversationId 就原样回显（当前只回显、不落库，M2 才持久化）。"""
    _patch_retrieve(monkeypatch, [make_unit()])
    _patch_stream(monkeypatch, [("delta", "回答 [1]")])

    _, events = _stream(client, {"question": "麻黄汤的组成", "conversationId": "c_fixed01"})

    assert events[-1]["data"]["conversationId"] == "c_fixed01"


# ==================== 降级：一律 200，不许 500 ====================


def test_no_hit_stream_skips_llm(client, monkeypatch) -> None:
    """检索为空 → 只发一条提示 + done(degraded)，**不调模型**。"""
    _patch_retrieve(monkeypatch, [])
    stream_spy = _patch_stream(monkeypatch, [("delta", "不该出现的正文")])

    resp, events = _stream(client, {"question": "今天天气怎么样"})

    assert resp.status_code == 200
    assert stream_spy["called"] == 0
    assert event_names(events) == ["tool", "tool", "token", "done"]
    assert events[1]["data"]["hits"] == 0
    assert events[2]["data"]["text"] == ask_router.NO_HIT_ANSWER
    assert events[-1]["data"]["degraded"] is True


def test_retrieve_failure_still_returns_200(client, monkeypatch) -> None:
    """检索炸了 → HTTP 200 + 正文说明（流已开始，改不了状态码）。"""
    _patch_retrieve(monkeypatch, raises=RuntimeError("PG 不可用"))
    _patch_stream(monkeypatch, [("delta", "不该出现的正文")])

    resp, events = _stream(client, {"question": "麻黄汤的组成"})

    assert resp.status_code == 200
    assert event_names(events) == ["tool", "token", "done"]
    assert "检索服务异常（RuntimeError）" in events[1]["data"]["text"]
    assert events[-1]["data"]["degraded"] is True


def test_llm_failure_after_partial_output_appends_notice(client, monkeypatch) -> None:
    """已吐了半截就中断：只补一句说明，不能把降级全文再推一遍（会和上文重复）。"""
    _patch_retrieve(monkeypatch, [make_unit()])
    _patch_stream(monkeypatch, [("delta", "麻黄汤")], raise_at=1)

    resp, events = _stream(client, {"question": "麻黄汤的组成"})

    assert resp.status_code == 200
    tokens = [e["data"]["text"] for e in events if e["event"] == "token"]
    assert tokens[0] == "麻黄汤"
    assert "生成中断" in tokens[-1]
    assert events[-1]["data"]["degraded"] is True


def test_llm_failure_before_any_token_pushes_degraded_summary(client, monkeypatch) -> None:
    """一个字都没吐就失败：应当推降级全文（否则用户只看到一句道歉，什么资料都拿不到）。"""
    _patch_retrieve(monkeypatch, [make_unit(title="麻黄汤")])
    _patch_stream(monkeypatch, [("delta", "不该出现的正文")], raise_at=0)

    _, events = _stream(client, {"question": "麻黄汤的组成"})

    tokens = [e["data"]["text"] for e in events if e["event"] == "token"]
    assert len(tokens) == 1
    assert "大模型服务暂时不可用" in tokens[0]
    assert events[-1]["data"]["degraded"] is True


# ==================== 越界角标 ====================


def test_illegal_citations_are_reported_in_done(client, monkeypatch) -> None:
    """资料只有 1 条，模型写了 [7]：token 已发出改不了，必须回传给前端擦。"""
    _patch_retrieve(monkeypatch, [make_unit()])
    _patch_stream(monkeypatch, [("delta", "见 [1] 与 [7]")])

    _, events = _stream(client, {"question": "麻黄汤的组成"})

    assert events[-1]["data"]["illegalCitations"] == [7]
    # 正文里的 [7] 原样保留（无法撤回），这是设计要求，不是 bug
    assert "".join(e["data"]["text"] for e in events if e["event"] == "token") == "见 [1] 与 [7]"


# ==================== 鉴权与限流 ====================


def test_missing_header_is_401_before_any_work(client, monkeypatch) -> None:
    """没有 X-User-Id → 401，且检索一次都不该被调用。"""
    spy = _patch_retrieve(monkeypatch, [make_unit()])

    resp, _ = _stream(client, {"question": "麻黄汤的组成"}, headers={})

    assert resp.status_code == 401
    assert resp.json()["code"] == 401
    assert spy["called"] == 0


def test_rate_limit_returns_429_r_shell(client, monkeypatch) -> None:
    """单窗口打满 20 次 → 429 + R 外壳，且在检索之前就短路。"""
    user = "u_flood"
    ask_router._rate_hits[user] = collections.deque([time.monotonic()] * ask_router._RATE_MAX)
    spy = _patch_retrieve(monkeypatch, [make_unit()])

    resp, _ = _stream(client, {"question": "麻黄汤的组成"}, headers={"X-User-Id": user})

    assert resp.status_code == 429
    assert resp.json()["code"] == 429
    assert spy["called"] == 0


def test_rate_ok_window_expires() -> None:
    """限流窗口滑出后要放行（否则用户等一分钟也回不来）。

    window 传负值 = 所有历史记录立即算过期，用它可以不睡觉、不看真时钟地验证
    "过期条目会被清掉"这条逻辑（忙等 80ms 既烧 CPU 又仍依赖时钟精度）。
    """
    user = "u_window"
    assert ask_router._rate_ok(user, limit=1, window=60) is True
    assert ask_router._rate_ok(user, limit=1, window=60) is False  # 窗口内被拦
    assert ask_router._rate_ok(user, limit=1, window=-1) is True   # 过期即放行
