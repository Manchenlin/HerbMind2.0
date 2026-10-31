"""同步问答 `/api/agent/ask/sync` 的降级与校验测试。

这条链路的对外承诺（`agent/app/routers/ask.py` 顶部注释）：
**永远给前端一个能显示的答案**，检索失败、模型失败都不许抛 500。
所以这里逐个固定四种分支：命中 / 无命中 / 检索异常 / 模型异常。

零外部依赖：`retrieve` 与 `chat_with_messages` 全部用替身替换，不联网、不烧额度。
"""

from __future__ import annotations

import asyncio

from helpers import make_unit

from app.agent.runner import ToolTrace
from app.repo.conversation import anon_scope
from app.routers import ask as ask_router

HEADERS = {"X-User-Id": "u_test"}


def _patch_retrieve(monkeypatch, units=None, raises: Exception | None = None) -> dict:
    """替换检索函数，返回 spy（记录调用参数）。"""
    spy: dict = {}

    async def _fake(question, top_k=None, ref_type=None):
        spy.update(question=question, top_k=top_k, ref_type=ref_type)
        if raises is not None:
            raise raises
        return units or []

    monkeypatch.setattr(ask_router, "retrieve", _fake)
    return spy


def _patch_chat(monkeypatch, answer: str = "", usage: dict | None = None, raises=None) -> dict:
    """替换大模型调用，返回 spy（记录是否被调用、传入的 messages）。"""
    spy: dict = {"called": 0, "messages": None}

    async def _fake(messages):
        spy["called"] += 1
        spy["messages"] = messages
        if raises is not None:
            raise raises
        return answer, (usage if usage is not None else {})

    monkeypatch.setattr(ask_router, "chat_with_messages", _fake)
    return spy


# ==================== 正常命中 ====================


def test_hit_returns_citations_and_clamps_illegal_tags(client, monkeypatch) -> None:
    """命中时：引用卡齐全、越界角标被剔除、字段是 camelCase。"""
    units = [make_unit(id="cu_1", ref_id="f_1"), make_unit(id="cu_2", ref_id="cs_3", ref_type="case")]
    _patch_retrieve(monkeypatch, units)
    _patch_chat(monkeypatch, answer="麻黄汤由麻黄、桂枝组成 [1][3]。", usage={"input_tokens": 10})

    resp = client.post("/api/agent/ask/sync", json={"question": "麻黄汤的组成"}, headers=HEADERS)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 0
    data = payload["data"]

    # 资料只有 2 条，模型写的 [3] 属编造 → 必须剔除；[1] 保留
    assert "[3]" not in data["answer"]
    assert "[1]" in data["answer"]
    assert data["degraded"] is False
    assert [c["refId"] for c in data["citations"]] == ["f_1", "cs_3"]
    # camelCase 出参（snake_case 不许漏出来）
    assert {"id", "refType", "refId", "title", "snippet", "score"} == set(data["citations"][0])
    assert set(data["usage"]) == {
        "promptTokens",
        "completionTokens",
        "totalTokens",
        "retrieveMs",
        "llmMs",
        "toolsMs",
    }
    # 工具被关掉时（conftest 默认关）工具轨迹必须是空数组，耗时 0
    assert data["toolCalls"] == []
    assert data["usage"]["toolsMs"] == 0
    # 续接会话靠这个字段：同步端点也必须回传 conversationId
    assert data["conversationId"]
    # 新会话 ID 必须带 user 指纹（`c_<scope>_<rand>`）：登录上线前会话匿名落库，
    # 没有指纹的话 history 会把全库匿名会话都返回给同一个人
    assert data["conversationId"].startswith(f"c_{anon_scope(HEADERS['X-User-Id'])}_")


def test_usage_total_falls_back_to_sum(client, monkeypatch) -> None:
    """模型没返回 total_tokens 时，用 input + output 兜底（前端别显示 0）。"""
    _patch_retrieve(monkeypatch, [make_unit()])
    _patch_chat(monkeypatch, answer="回答 [1]", usage={"input_tokens": 10, "output_tokens": 5})

    data = client.post(
        "/api/agent/ask/sync", json={"question": "麻黄汤的组成"}, headers=HEADERS
    ).json()["data"]

    assert data["usage"]["totalTokens"] == 15


def test_top_k_and_question_are_passed_through(client, monkeypatch) -> None:
    """topK 与问题（去掉首尾空白）应原样传给检索层。"""
    spy = _patch_retrieve(monkeypatch, [make_unit()])
    _patch_chat(monkeypatch, answer="回答 [1]")

    client.post(
        "/api/agent/ask/sync",
        json={"question": "  麻黄汤的组成  ", "topK": 3},
        headers=HEADERS,
    )

    assert spy["question"] == "麻黄汤的组成"
    assert spy["top_k"] == 3


# ==================== 无命中：连模型都不该调 ====================


def test_no_hit_skips_llm_entirely(client, monkeypatch) -> None:
    """检索为空 → 直接回提示，**不调大模型**（这是省钱省时的关键：问天气不该烧 token）。"""
    _patch_retrieve(monkeypatch, [])
    # 别用抛异常当哨兵：ask.py 是宽泛的 except Exception，异常会被当成"模型故障"吞掉，
    # 用例会静默走降级分支仍然"通过"。只有 called 计数才是硬证据。
    chat_spy = _patch_chat(monkeypatch, answer="不该出现的回答")

    resp = client.post("/api/agent/ask/sync", json={"question": "今天天气怎么样"}, headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert chat_spy["called"] == 0
    assert data["degraded"] is True
    assert data["answer"] == ask_router.NO_HIT_ANSWER
    assert data["citations"] == []


# ==================== 检索异常：不抛 500，降级返回 ====================


def test_retrieve_failure_degrades_without_500(client, monkeypatch) -> None:
    """检索炸了 → 200 + degraded，answer 说明原因（前端能显示，而不是白屏）。"""
    _patch_retrieve(monkeypatch, raises=RuntimeError("PG 连接池未初始化"))
    chat_spy = _patch_chat(monkeypatch)

    resp = client.post("/api/agent/ask/sync", json={"question": "麻黄汤的组成"}, headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["degraded"] is True
    assert "检索服务异常（RuntimeError）" in data["answer"]
    assert data["citations"] == []
    assert chat_spy["called"] == 0


# ==================== 模型异常：降级成资料摘要 ====================


def test_llm_failure_degrades_to_material_summary(client, monkeypatch) -> None:
    """模型挂了 → 把检索到的资料摘要摆出来，引用卡照样给（不许编造内容填空）。"""
    _patch_retrieve(monkeypatch, [make_unit(id="cu_1"), make_unit(id="cu_2", title="桂枝汤")])
    _patch_chat(monkeypatch, raises=TimeoutError("主模型超时"))

    resp = client.post("/api/agent/ask/sync", json={"question": "麻黄汤的组成"}, headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["degraded"] is True
    assert "大模型服务暂时不可用" in data["answer"]
    assert len(data["citations"]) == 2
    assert data["usage"]["llmMs"] >= 0


# ==================== 限流与落库健壮性 ====================


def test_ask_sync_is_rate_limited(client, monkeypatch) -> None:
    """回归钉子：`/ask` 有滑动窗口限流，`/ask/sync` 成本相同，必须一起挡。

    X-User-Id 是网关信任头、可被伪造，8091 不挡就只能靠网关——多一层防护不吃亏。
    """
    _patch_retrieve(monkeypatch, [])  # 无命中分支直接返回，不碰模型
    ask_router._rate_hits.clear()

    for _ in range(ask_router._RATE_MAX):
        resp = client.post("/api/agent/ask/sync", json={"question": "问题"}, headers=HEADERS)
        assert resp.status_code == 200

    resp = client.post("/api/agent/ask/sync", json={"question": "问题"}, headers=HEADERS)

    # HTTPException 被统一成 R 外壳（code/msg），不是 FastAPI 默认的 {"detail": ...}
    body = resp.json()
    assert resp.status_code == 429
    assert body["code"] == 429
    assert "过于频繁" in body["msg"]


def test_persist_keeps_traces_when_assistant_message_fails(monkeypatch) -> None:
    """回归钉子：assistant 消息落库失败时，工具轨迹仍要以 `message_id=NULL` 写进去。

    否则这一轮"为什么这样回答"的唯一依据（调了哪个工具、命中几条）会整段消失。
    """
    recorded: list[tuple[str | None, str]] = []

    async def _ensure(_conv_id, _user_id, _title):
        return True

    async def _append(_conv_id, role, _content):
        return "m_user" if role == "user" else None  # 只有 assistant 写失败

    async def _record(message_id, name, _args, _summary, _ms):
        recorded.append((message_id, name))
        return True

    monkeypatch.setattr(ask_router, "ensure_conversation", _ensure)
    monkeypatch.setattr(ask_router, "append_message", _append)
    monkeypatch.setattr(ask_router, "record_tool_call", _record)

    trace = ToolTrace(
        name="search_formula", args={"herb": "麻黄"}, ok=True, hit=True, count=3, ms=12
    )

    asyncio.run(ask_router._persist_ask("c_1", "u_1", "问题", "答案", [trace]))

    assert recorded == [(None, "search_formula")]
