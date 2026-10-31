"""多轮记忆：带 `conversationId` 提问时，历史消息必须真正进入提示词。

要钉住的三点：
1. 有 `conversationId` → 读 `agent_message` 的历史，并按「从旧到新」插到当前问题之前；
2. 没有 `conversationId` → **不查库**（省一次查询，也避免把别人的上下文接进来）；
3. 历史只在 system 里多一条「不得作为依据」的规则，**不能**混进【资料】块——
   否则模型会引用自己上一轮的回答（红线二：只能依据库内原文）。
"""

from __future__ import annotations

from helpers import make_unit

from app.routers import ask as ask_router

HEADERS = {"X-User-Id": "u_test"}

HISTORY = [
    {"role": "user", "content": "麻黄汤是什么"},
    {"role": "assistant", "content": "麻黄汤是《伤寒论》里的方剂 [1]。", "extra": "被忽略的键"},
]


def _patch(monkeypatch, *, history=None, answer: str = "回答 [1]") -> dict:
    """替换检索、模型、历史读取与落库，返回 spy。"""
    spy: dict = {"messages": None, "recent": None, "persist": None, "chat_called": 0}

    async def _retrieve(question, top_k=None, ref_type=None):
        return [make_unit()]

    async def _chat(messages):
        spy["chat_called"] += 1
        spy["messages"] = messages
        return answer, {"input_tokens": 1}

    async def _recent(conv_id, limit=None):
        spy["recent"] = conv_id
        return history or []

    async def _persist(*args, **kwargs):
        spy["persist"] = args

    monkeypatch.setattr(ask_router, "retrieve", _retrieve)
    monkeypatch.setattr(ask_router, "chat_with_messages", _chat)
    monkeypatch.setattr(ask_router, "recent_messages", _recent)
    monkeypatch.setattr(ask_router, "_persist_ask", _persist)
    return spy


def test_history_is_inserted_between_system_and_question(client, monkeypatch) -> None:
    spy = _patch(monkeypatch, history=HISTORY)

    resp = client.post(
        "/api/agent/ask/sync",
        json={"question": "它的组成是什么", "conversationId": "c_test"},
        headers=HEADERS,
    )

    assert resp.status_code == 200
    assert spy["recent"] == "c_test"

    messages = spy["messages"]
    assert messages[0]["role"] == "system"
    assert "历史对话使用规则" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "麻黄汤是什么"}
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"].startswith("麻黄汤是")
    # 最后一轮才是本次问题，且带【资料】
    assert messages[-1]["role"] == "user"
    assert "【资料】" in messages[-1]["content"]
    assert "它的组成是什么" in messages[-1]["content"]


def test_history_extra_keys_are_dropped(client, monkeypatch) -> None:
    """repo 返回的字典可能带额外键，拼进 messages 时只允许 role/content（OpenAI 会拒收多余字段）。"""
    spy = _patch(monkeypatch, history=HISTORY)

    client.post(
        "/api/agent/ask/sync",
        json={"question": "它的组成", "conversationId": "c_test"},
        headers=HEADERS,
    )

    assert set(spy["messages"][2]) == {"role", "content"}


def test_no_conversation_id_skips_history_query(client, monkeypatch) -> None:
    """新会话不该去查历史（也避免把别人的上下文接进来）。"""
    spy = _patch(monkeypatch, history=HISTORY)

    data = client.post(
        "/api/agent/ask/sync", json={"question": "麻黄汤的组成"}, headers=HEADERS
    ).json()["data"]

    assert spy["recent"] is None, "没有 conversationId 时不该调用 recent_messages"
    assert "历史对话使用规则" not in spy["messages"][0]["content"]
    assert len(spy["messages"]) == 2
    # 但响应必须回传一个新生成的 conversationId，供下一次续接
    assert data["conversationId"].startswith("c_")


def test_empty_history_does_not_add_note(client, monkeypatch) -> None:
    """带上 conversationId 但会话还没有历史（第一次问）→ 不加历史规则，保持提示词干净。"""
    spy = _patch(monkeypatch, history=[])

    client.post(
        "/api/agent/ask/sync",
        json={"question": "麻黄汤的组成", "conversationId": "c_new"},
        headers=HEADERS,
    )

    assert "历史对话使用规则" not in spy["messages"][0]["content"]
    assert len(spy["messages"]) == 2


def test_persist_receives_question_and_answer(client, monkeypatch) -> None:
    """落库拿到的必须是本次问题与最终答案（background task 在响应后执行，TestClient 会等它）。"""
    spy = _patch(monkeypatch, answer="麻黄汤由麻黄、桂枝组成 [1]")

    client.post(
        "/api/agent/ask/sync",
        json={"question": "麻黄汤的组成", "conversationId": "c_test"},
        headers=HEADERS,
    )

    args = spy["persist"]
    assert args is not None, "background task 应该已执行"
    assert args[0] == "c_test"
    assert args[1] == "u_test"
    assert args[2] == "麻黄汤的组成"
    assert args[3].startswith("麻黄汤由麻黄")
