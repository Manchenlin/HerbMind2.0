"""工具调用循环（`app/agent/runner.py`）的行为测试。

全部用假模型 + 假工具，零外部依赖。要钉住的四件事：

1. **事件顺序**：tool start 必须早于 tool done，且两者都在 finish 之前；
2. **轮次上限**：模型反复要求调工具时，必须在上限处停下（否则网关 60s 兜不住）；
3. **预算上限**：累计耗时超预算后不再取证，剩下的调用如实告诉模型"没执行"；
4. **降级**：工具抛异常 / 超时 / 名字不存在 / 模型决策失败，都不能让整条问答崩掉。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agent import runner
from app.config import get_settings

OK_RESULT = {
    "ok": True,
    "hit": True,
    "count": 1,
    "items": [{"id": "f_1", "title": "麻黄汤"}],
    "hint": "",
    "notice": "免责声明",
}


class _FakeTool:
    """最小工具替身：只实现 runner 用到的那一个方法。"""

    def __init__(
        self,
        name: str = "search_formula",
        *,
        result: dict | None = None,
        exc: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.name = name
        self.result = result if result is not None else dict(OK_RESULT)
        self.exc = exc
        self.delay = delay
        self.calls: list[dict[str, Any]] = []

    async def ainvoke(self, args: dict[str, Any]) -> dict:
        self.calls.append(args)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc is not None:
            raise self.exc
        return self.result


class _Bound:
    """`bind_tools` 的产物：记录本次绑定的 tool_choice，再委托给假模型。"""

    def __init__(self, model: "_FakeModel", tool_choice: Any) -> None:
        self.model = model
        self.tool_choice = tool_choice

    async def ainvoke(self, messages):
        self.model.choices.append(self.tool_choice)
        return await self.model.ainvoke(messages)


class _FakeModel:
    """按预设脚本返回 AIMessage；`bind_tools` 行为与真实模型一致（返回新对象）。"""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[list[Any]] = []
        self.bound_tools: list[Any] | None = None
        # 每次 ainvoke 使用的 tool_choice，用于断言"清单类问题首轮被强制"
        self.choices: list[Any] = []

    def bind_tools(self, tools, **kwargs) -> _Bound:
        self.bound_tools = list(tools)
        return _Bound(self, kwargs.get("tool_choice", "auto"))

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        if isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        return self.responses.pop(0)


def _tool_call(name: str = "search_formula", args: dict | None = None, call_id: str = "call_1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args or {"name": "麻黄汤"}, "id": call_id}],
    )


def _enable(monkeypatch, *, rounds: int = 3, budget_ms: int = 15000, timeout: float = 5.0) -> None:
    """打开工具开关，并把上限调到用例需要的值。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_tools_enabled", True)
    monkeypatch.setattr(settings, "agent_max_tool_rounds", rounds)
    monkeypatch.setattr(settings, "agent_tool_budget_ms", budget_ms)
    monkeypatch.setattr(settings, "agent_tool_timeout", timeout)


def _patch_tool(monkeypatch, tool: _FakeTool) -> _FakeTool:
    monkeypatch.setitem(runner._TOOL_MAP, tool.name, tool)
    return tool


def _run(messages: list[Any] | None = None) -> tuple[dict, list[tuple[str, Any]]]:
    """跑完循环，返回 (finish 载荷, 全部事件)。"""

    async def _inner():
        events: list[tuple[str, Any]] = []
        final: dict = {}
        async for kind, payload in runner.stream_tool_loop(list(messages or [{"role": "user", "content": "麻黄汤的组成"}])):
            events.append((kind, payload))
            if kind == "finish":
                final = payload
        return final, events

    return asyncio.run(_inner())


# ==================== 不需要工具的路径 ====================


def test_no_tool_calls_leaves_messages_untouched(monkeypatch) -> None:
    """模型直接回答 → messages 原样返回，调用方接着 astream 生成。"""
    _enable(monkeypatch)
    model = _FakeModel([AIMessage(content="麻黄汤由麻黄、桂枝组成。")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    final, events = _run()

    assert final.used is False
    assert final.traces == []
    assert len(final.messages) == 1
    assert [kind for kind, _ in events] == ["finish"]


def test_tools_disabled_never_calls_model(monkeypatch) -> None:
    """`AGENT_TOOLS_ENABLED=false` 是回退开关：连 bind_tools 都不该发生。"""
    monkeypatch.setattr(get_settings(), "agent_tools_enabled", False)
    model = _FakeModel([AIMessage(content="不该被调用")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    final, _events = _run()

    assert final.used is False
    assert model.calls == []
    assert model.bound_tools is None


def test_bind_tools_failure_falls_back(monkeypatch) -> None:
    """没有 key / 模型不支持工具时，退回单轮 RAG 而不是报错。"""
    _enable(monkeypatch)

    class _Boom(_FakeModel):
        def bind_tools(self, tools, **_kwargs):
            raise RuntimeError("模型不支持 tools")

    monkeypatch.setattr(runner, "get_chat_model", lambda: _Boom([]))

    final, _events = _run()

    assert final.used is False
    assert final.traces == []


# ==================== 正常取证 ====================


def test_single_round_executes_tool_and_feeds_result_back(monkeypatch) -> None:
    """一次工具调用：start→done 事件顺序正确，结果以 ToolMessage(JSON) 回给模型。"""
    _enable(monkeypatch)
    tool = _patch_tool(monkeypatch, _FakeTool())
    model = _FakeModel([_tool_call(), AIMessage(content="够了")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    final, events = _run()

    assert final.used is True
    assert len(final.traces) == 1
    assert tool.calls == [{"name": "麻黄汤"}]

    kinds = [f"{payload.get('name')}:{payload.get('status')}" for kind, payload in events if kind == "tool"]
    assert kinds == ["search_formula:start", "search_formula:done"]

    last = final.messages[-1]
    assert isinstance(last, ToolMessage)
    payload = json.loads(last.content)
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == "f_1"

    # 第二轮拿到的 messages 里已经有 ToolMessage
    assert any(isinstance(m, ToolMessage) for m in model.calls[1])


def test_first_round_ai_message_is_kept_with_tool_calls(monkeypatch) -> None:
    """带 tool_calls 的 AIMessage 必须留在 messages 里，否则 OpenAI 协议会拒收 ToolMessage。"""
    _enable(monkeypatch)
    _patch_tool(monkeypatch, _FakeTool())
    monkeypatch.setattr(runner, "get_chat_model", lambda: _FakeModel([_tool_call(), AIMessage(content="好")]))

    final, _events = _run()

    ai_messages = [m for m in final.messages if isinstance(m, AIMessage)]
    assert len(ai_messages) == 1
    assert ai_messages[0].tool_calls[0]["name"] == "search_formula"


def test_trace_summary_has_no_question_text(monkeypatch) -> None:
    """落库摘要只记工具名/耗时/命中，不能把问题原文写进去。"""
    _enable(monkeypatch)
    _patch_tool(monkeypatch, _FakeTool())
    monkeypatch.setattr(
        runner,
        "get_chat_model",
        lambda: _FakeModel([_tool_call(args={"herb": "麻黄"}), AIMessage(content="好")]),
    )

    final, _events = _run()

    summary = final.traces[0].summary
    assert "ok=True" in summary and "hit=True" in summary and "count=1" in summary
    assert "麻黄" not in summary


# ==================== 上限与降级 ====================


def test_round_limit_stops_endless_tool_calls(monkeypatch) -> None:
    """模型每轮都要求调工具 → 必须在上限处停下，不能无限循环烧额度。"""
    _enable(monkeypatch, rounds=2)
    tool = _patch_tool(monkeypatch, _FakeTool())
    model = _FakeModel([_tool_call(call_id="c1"), _tool_call(call_id="c2"), _tool_call(call_id="c3")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    final, _events = _run()

    assert len(tool.calls) == 2, "轮次上限是 2，工具最多被调 2 次"
    assert len(model.calls) == 2, "上限 2 轮 = 最多 2 次模型调用，之后停止取证"
    assert final.used is True
    assert model.responses, "第 3 条脚本不该被消费掉（说明循环确实停了）"


def test_budget_exhausted_skips_tool_execution(monkeypatch) -> None:
    """预算耗尽后不再真正调工具，但要让模型知道「这次没查到」。"""
    _enable(monkeypatch, budget_ms=1)
    tool = _patch_tool(monkeypatch, _FakeTool())
    monkeypatch.setattr(runner, "get_chat_model", lambda: _FakeModel([_tool_call()]))

    final, _events = _run()

    assert tool.calls == [], "预算已耗尽，不该真的执行工具"
    # 要么整轮被跳过（traces 空），要么执行了但被预算拦下（ok=False）
    for trace in final.traces:
        assert trace.ok is False


def test_tool_timeout_retries_once(monkeypatch) -> None:
    """单工具超时重试 1 次，仍超时就转 ok=False（不让问答卡死）。"""
    _enable(monkeypatch, timeout=0.05)
    tool = _patch_tool(monkeypatch, _FakeTool(delay=0.5))
    monkeypatch.setattr(runner, "get_chat_model", lambda: _FakeModel([_tool_call(), AIMessage(content="好")]))

    final, _events = _run()

    assert len(tool.calls) == 2, "超时应该重试一次"
    assert final.traces[0].ok is False
    assert final.traces[0].error == "超时（>0.1s）" or "超时" in final.traces[0].error


def test_tool_exception_becomes_error_result(monkeypatch) -> None:
    """工具内部抛异常（理论上不该有，但不能信）→ 转成 ok=False 的可读结果。"""
    _enable(monkeypatch)
    _patch_tool(monkeypatch, _FakeTool(exc=RuntimeError("连接池炸了")))
    monkeypatch.setattr(runner, "get_chat_model", lambda: _FakeModel([_tool_call(), AIMessage(content="好")]))

    final, _events = _run()

    assert final.traces[0].ok is False
    assert "连接池炸了" in final.traces[0].error
    last = final.messages[-1]
    assert isinstance(last, ToolMessage)
    payload = json.loads(last.content)
    assert payload["ok"] is False
    assert "调用失败" in payload["hint"]


def test_unknown_tool_name_is_reported(monkeypatch) -> None:
    """模型编了一个不存在的工具名 → 如实告诉它，别让它以为查到了东西。"""
    _enable(monkeypatch)
    monkeypatch.setattr(
        runner, "get_chat_model", lambda: _FakeModel([_tool_call(name="search_ghost"), AIMessage(content="好")])
    )

    final, _events = _run()

    assert final.traces[0].ok is False
    assert "不存在的工具" in final.traces[0].hint


def test_decision_failure_stops_loop(monkeypatch) -> None:
    """决策轮模型挂了 → 停止取证，把控制权交回调用方（由它决定降级）。"""
    _enable(monkeypatch)
    monkeypatch.setattr(runner, "get_chat_model", lambda: _FakeModel([TimeoutError("模型超时")]))

    final, _events = _run()

    assert final.used is False
    assert final.traces == []


def test_emit_payload_has_no_full_args(monkeypatch) -> None:
    """SSE 里的参数要被截断：长问题不能整段塞进工具事件。"""
    _enable(monkeypatch)
    _patch_tool(monkeypatch, _FakeTool())
    long_query = "无" * 200
    monkeypatch.setattr(
        runner,
        "get_chat_model",
        lambda: _FakeModel([_tool_call(args={"query": long_query}), AIMessage(content="好")]),
    )

    _final, events = _run()

    start = next(payload for kind, payload in events if kind == "tool" and payload["status"] == "start")
    assert len(start["args"]["query"]) == 41, "超长参数应截断成 40 字 + 省略号"


# ==================== 清单类问题强制取证 ====================


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("库内哪些方剂含有麻黄这味药", True),
        ("有哪些方剂治太阳病", True),
        ("麻黄汤由哪些药组成", True),
        ("含有桂枝的方有哪些", True),
        ("桂枝和麻黄在哪些方里同时出现", True),
        ("有哪些医案用过小承气汤", True),
        ("麻黄汤的证治要点是什么", False),
        ("什么是太阳病", False),
        ("", False),
    ],
)
def test_needs_tool_evidence(question: str, expected: bool) -> None:
    """模式要窄：列举/统计类命中，解释类不命中（否则每次问答都多一轮 LLM 调用）。"""
    assert runner.needs_tool_evidence(question) is expected


def test_checklist_question_forces_required_on_first_round(monkeypatch) -> None:
    """清单类问题首轮 `tool_choice=required`，第二轮回到 auto。"""
    _enable(monkeypatch)
    _patch_tool(monkeypatch, _FakeTool())
    model = _FakeModel([_tool_call(), AIMessage(content="好")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    messages = [{"role": "user", "content": "【资料】\n[1] 麻黄汤\n\n【问题】\n库内哪些方剂含有麻黄这味药"}]
    _run(messages)

    assert model.choices == ["required", "auto"]


def test_plain_question_keeps_auto(monkeypatch) -> None:
    """普通问答不该被强制调工具（多一次 LLM 调用 = 多两秒等待）。"""
    _enable(monkeypatch)
    _patch_tool(monkeypatch, _FakeTool())
    model = _FakeModel([_tool_call(), AIMessage(content="好")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    messages = [{"role": "user", "content": "【资料】\n[1] 麻黄汤\n\n【问题】\n麻黄汤的证治要点是什么"}]
    _run(messages)

    assert model.choices == ["auto", "auto"]


def test_force_tools_can_be_disabled(monkeypatch) -> None:
    """`AGENT_FORCE_TOOLS=false` 时不强制（排查"是不是强制导致答偏"用）。"""
    _enable(monkeypatch)
    monkeypatch.setattr(get_settings(), "agent_force_tools", False)
    _patch_tool(monkeypatch, _FakeTool())
    model = _FakeModel([_tool_call(), AIMessage(content="好")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    messages = [{"role": "user", "content": "【问题】\n库内哪些方剂含有麻黄"}]
    _run(messages)

    assert model.choices == ["auto", "auto"]


def test_forced_binding_failure_falls_back_to_auto(monkeypatch) -> None:
    """强制绑定失败（老模型不支持 tool_choice）只降级为 auto，不影响整条问答。"""
    _enable(monkeypatch)
    _patch_tool(monkeypatch, _FakeTool())

    class _Picky(_FakeModel):
        def bind_tools(self, tools, **kwargs):
            if kwargs.get("tool_choice"):
                raise ValueError("tool_choice 不被支持")
            return super().bind_tools(tools, **kwargs)

    model = _Picky([_tool_call(), AIMessage(content="好")])
    monkeypatch.setattr(runner, "get_chat_model", lambda: model)

    messages = [{"role": "user", "content": "【问题】\n库内哪些方剂含有麻黄"}]
    _run(messages)

    assert model.choices == ["auto", "auto"]
