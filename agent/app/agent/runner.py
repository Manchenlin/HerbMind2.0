"""工具调用循环（手写，不用 `langchain.agents.create_agent`）。

为什么要手写：
- 需要**精确控制 SSE 事件时序**（tool start/done 必须早于 citation 与 token）；
- 需要**轮次与耗时双重上限**（模型可能反复调同一个工具，网关 60s 兜不住）；
- 需要**失败降级**：工具全挂时仍然能生成答案，而不是整条问答 500；
- 上面三件事都要能单测，`create_agent` 把这些都藏在内部，测不到也改不动。

循环形态：

    for round in 1..max_rounds:
        ai = await model.bind_tools(TOOLS).ainvoke(messages)
        if not ai.tool_calls: break            # 模型认为资料够了
        for call in ai.tool_calls:
            emit tool(start) → 执行（超时+重试1次）→ emit tool(done)
            messages += ToolMessage(结果)
    最终由调用方用 astream 逐字生成（不在本模块里做，保证 SSE 时机由路由掌握）

**多轮记忆不用 LangGraph checkpointer**：`agent_message` 表本来就为落库而存在，
历史消息从表里读即可，等于同一份数据两用。引入 checkpointer 会多一个依赖 + 一套 schema
（生产用 Postgres/SQLite saver，测试还要造假实现），收益不抵成本。这是对 08 §6 的有意偏差。

工具**可以被 `AGENT_TOOLS_ENABLED=false` 整体关掉**：出问题时限流/回退不需要改代码。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import ToolMessage

from app.config import get_settings
from app.llm import get_chat_model
from app.tools import ALL_TOOLS
from app.tools.common import error_result

logger = logging.getLogger("herbmind-agent")

# 单轮「要不要调工具」的决策超时。比工具本身宽松（要出完整 tool_call 的参数），
# 但必须小于网关 60s，否则最坏情况下前端等到超时。
_DECISION_TIMEOUT = 20.0

# 工具名 → 工具对象。名字与 ALL_TOOLS 一致，模型返回的 name 直接查表
_TOOL_MAP = {t.name: t for t in ALL_TOOLS}

# 「必须遍历库内完整清单」的问法。命中这些模式时，光靠 RAG 的 5 条片段作答一定不全，
# 所以首轮用 `tool_choice="required"` 强制模型取证。
#
# 为什么需要这条规则（2026-10-31 实测）：Qwen2.5-7B 在「只能依据【资料】回答」的强约束下，
# 面对"哪些方剂含有麻黄"会直接拿召回的两三条凑答案，一次工具都不调。单纯在提示词里
# 写"必须先调工具"无效（试过 3 版措辞），`tool_choice="required"` 才稳定生效。
#
# 模式刻意写得窄：只覆盖"列举/统计/核对清单"的问法，普通问答（解释条文、归纳证治）不受影响。
_NEEDS_EVIDENCE = re.compile(
    r"哪些方剂|有哪些方剂|哪几首方|几首方|哪些方[子]?(?:含|有|用|治)"
    r"|含.{0,6}(?:这味药|哪味药|什么药)|含有.{0,4}的方"
    r"|同时出现|共有.{0,6}药|都有哪些药|由哪些药组成|包含哪些药|组成是(?:什么|啥)"
    r"|哪些医案|有几则医案|用过.{0,6}方"
)


def _question_of(messages: list[Any]) -> str:
    """从最后一条 user 消息里取出【问题】段（`build_messages` 拼的格式）。"""
    for message in reversed(messages):
        content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
        if isinstance(content, str) and "【问题】" in content:
            return content.split("【问题】", 1)[1].strip()
    return ""


def needs_tool_evidence(question: str) -> bool:
    """问题是否属于「必须遍历库内完整清单」的类型。"""
    return bool(question) and _NEEDS_EVIDENCE.search(question) is not None


@dataclass(slots=True)
class ToolTrace:
    """一次工具调用的轨迹（用于 SSE、同步返回、落库三处）。"""

    name: str
    args: dict[str, Any]
    ok: bool
    hit: bool
    count: int
    ms: int
    error: str = ""
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        """给 API 用的精简结构（不含 hint 全文，避免把提示词塞进响应）。"""
        out: dict[str, Any] = {
            "name": self.name,
            "args": self.args,
            "ok": self.ok,
            "hit": self.hit,
            "count": self.count,
            "ms": self.ms,
        }
        if self.error:
            out["error"] = self.error
        return out

    @property
    def summary(self) -> str:
        """落库 `agent_tool_call.result_summary` 用的一行摘要（不含问题原文）。"""
        parts = [f"ok={self.ok}", f"hit={self.hit}", f"count={self.count}"]
        if self.hint:
            parts.append(f"hint={self.hint[:160]}")
        if self.error:
            parts.append(f"error={self.error[:120]}")
        return " ".join(parts)


@dataclass(slots=True)
class _LoopResult:
    """循环终态：扩展后的 messages + 轨迹 + 是否真的调用过工具。"""

    messages: list[Any]
    traces: list[ToolTrace] = field(default_factory=list)
    used: bool = False


def _safe_args(args: Any) -> dict[str, Any]:
    """把模型给的参数收敛成可安全放进 SSE 的小对象。

    问题原文属健康敏感信息，日志里一律不记（沿用 `fp` 指纹机制）；
    SSE 是回给用户自己的，可以带参数，但截断到 40 字，避免工具卡撑爆。
    """
    out: dict[str, Any] = {}
    for key, value in (args or {}).items() if isinstance(args, dict) else []:
        if isinstance(value, str):
            out[str(key)] = value if len(value) <= 40 else value[:40] + "…"
        elif isinstance(value, (int, float, bool)) or value is None:
            out[str(key)] = value
        else:
            out[str(key)] = str(value)[:40]
    return out


def _text_of(message: Any) -> str:
    """取消息正文（兼容字符串与分段数组两种 content）。"""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


async def _invoke_tool(tool: Any, args: dict[str, Any]) -> Any:
    """调用工具。统一走 ainvoke —— 四个工具都是 async（数据源是 HTTP）。"""
    return await tool.ainvoke(args)


async def _execute(
    name: str,
    args: dict[str, Any],
    *,
    deadline: float,
) -> tuple[ToolTrace, dict[str, Any]]:
    """执行单个工具：限时 + 失败重试 1 次 + 永不抛异常。

    Args:
        deadline: `time.monotonic()` 表示的本次问答工具阶段截止时刻。
            留给单个工具的时间从不超过剩余预算，所以总耗时有硬上界。

    Returns:
        (轨迹, 六字段工具结果)。结果会被塞进 `ToolMessage` 交给模型。
    """
    started = time.perf_counter()
    tool = _TOOL_MAP.get(name)
    safe_args = _safe_args(args)

    if tool is None:
        # 模型编了一个不存在的工具名：如实告诉它，别让它以为查到了东西
        result = error_result(f"不存在的工具「{name}」，可用工具：{', '.join(sorted(_TOOL_MAP))}")
        return (
            ToolTrace(
                name=name,
                args=safe_args,
                ok=False,
                hit=False,
                count=0,
                ms=0,
                error="unknown tool",
                hint=result["hint"],
            ),
            result,
        )

    settings = get_settings()
    remaining = deadline - time.monotonic()
    if remaining <= 0.2:
        result = error_result(
            f"本次问答的工具调用预算（{settings.agent_tool_budget_ms}ms）已用完，"
            f"未能执行 {name}。请基于已有资料作答，并说明这部分没有查到。"
        )
        return (
            ToolTrace(
                name=name,
                args=safe_args,
                ok=False,
                hit=False,
                count=0,
                ms=0,
                error="budget exhausted",
                hint=result["hint"],
            ),
            result,
        )

    timeout = max(0.5, min(settings.agent_tool_timeout, remaining))
    result: dict[str, Any] | None = None
    error = ""

    for attempt in (1, 2):
        try:
            raw = await asyncio.wait_for(_invoke_tool(tool, args), timeout=timeout)
            result = raw if isinstance(raw, dict) else {"ok": True, "hit": bool(raw), "count": 0, "items": raw, "hint": "", "notice": ""}
            error = ""
            break
        except asyncio.CancelledError:
            # 客户端断开：让取消继续向上传播，不要被"工具不许抛"吞掉
            raise
        except asyncio.TimeoutError:
            error = f"超时（>{timeout:.1f}s）"
        except Exception as exc:  # noqa: BLE001 —— 工具层异常一律转成可读结果
            error = f"{type(exc).__name__}: {exc}"

        if attempt == 1:
            remaining = deadline - time.monotonic()
            if remaining <= 0.2:
                break
            # 重试也不能超预算
            timeout = max(0.5, min(settings.agent_tool_timeout, remaining))

    if result is None:
        logger.warning("工具 %s 执行失败：%s", name, error)
        result = error_result(
            f"工具 {name} 调用失败（{error}）。这条路径没有查到内容，"
            "请如实说明，不要用印象补全；也可以换用其它工具再试。"
        )

    ms = int((time.perf_counter() - started) * 1000)
    # 日志只记工具名 / 耗时 / 命中数，不记参数（问题原文属健康敏感信息）
    logger.info("工具调用：%s %dms ok=%s hit=%s count=%s", name, ms, result.get("ok"), result.get("hit"), result.get("count"))
    return (
        ToolTrace(
            name=name,
            args=safe_args,
            ok=bool(result.get("ok")),
            hit=bool(result.get("hit")),
            count=int(result.get("count") or 0),
            ms=ms,
            error=error,
            hint=str(result.get("hint") or ""),
        ),
        result,
    )


async def stream_tool_loop(messages: list[Any]) -> AsyncIterator[tuple[str, Any]]:
    """跑工具调用循环，边跑边产出事件。

    产出的事件（`(kind, payload)`）：
    - `("tool", {...})`  工具轨迹，直接转成 SSE 的 `tool` 事件；
    - `("finish", _LoopResult)` 循环结束，带扩展后的 messages / 轨迹 / 是否用过工具。

    调用方拿到 `finish` 后用最终 messages 走 astream 逐字生成。
    """
    settings = get_settings()
    current: list[Any] = list(messages)
    traces: list[ToolTrace] = []
    used = False

    if not settings.agent_tools_enabled or not ALL_TOOLS:
        logger.info("工具调用已关闭（AGENT_TOOLS_ENABLED=false），按单轮 RAG 走")
        yield ("finish", _LoopResult(messages=current))
        return

    try:
        base_model = get_chat_model()
        model = base_model.bind_tools(ALL_TOOLS)
    except Exception as exc:  # noqa: BLE001 —— 没有 key / 模型不支持 bind_tools
        logger.warning("绑定工具失败，退回单轮 RAG：%s", exc)
        yield ("finish", _LoopResult(messages=current))
        return

    # 清单类问题首轮强制取证（见 _NEEDS_EVIDENCE 的注释）。绑定失败就退回普通 auto，
    # 不能因为一次"强制"失败把整条问答拖死。
    forced_model = None
    if settings.agent_force_tools and needs_tool_evidence(_question_of(current)):
        try:
            forced_model = base_model.bind_tools(ALL_TOOLS, tool_choice="required")
            logger.info("命中清单类问法，首轮强制取证（tool_choice=required）")
        except Exception as exc:  # noqa: BLE001
            logger.warning("强制工具取证绑定失败，改用 auto：%s", exc)

    deadline = time.monotonic() + settings.agent_tool_budget_ms / 1000.0

    for round_index in range(1, settings.agent_max_tool_rounds + 1):
        if time.monotonic() >= deadline:
            logger.info("工具预算耗尽，第 %d 轮不再取证", round_index)
            break
        active = forced_model if (round_index == 1 and forced_model is not None) else model
        try:
            ai = await asyncio.wait_for(active.ainvoke(current), timeout=_DECISION_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 —— 决策轮失败就当"模型不需要工具"
            logger.warning("第 %d 轮工具决策失败，停止取证：%s", round_index, exc)
            break

        calls = list(getattr(ai, "tool_calls", None) or [])
        if not calls:
            # 模型认为资料够了。注意这一轮的正文**不采用**：最终回答由调用方重新
            # astream 生成，保证 SSE 一定是流式的（计划里明确的取舍）。
            break

        used = True
        current.append(ai)

        for call in calls:
            name = str(call.get("name") or "")
            args = call.get("args") or {}
            call_id = str(call.get("id") or name)
            yield ("tool", {"name": name, "status": "start", "args": _safe_args(args), "round": round_index})

            trace, result = await _execute(name, args, deadline=deadline)
            traces.append(trace)
            yield (
                "tool",
                {
                    "name": name,
                    "status": "done",
                    "ms": trace.ms,
                    "ok": trace.ok,
                    "hits": trace.count,
                    "count": trace.count,
                    "hit": trace.hit,
                    "round": round_index,
                },
            )
            # ToolMessage.content 必须是字符串：模型看不到 Python 对象
            current.append(
                ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call_id)
            )

    yield ("finish", _LoopResult(messages=current, traces=traces, used=used))


async def run_tool_loop(messages: list[Any]) -> tuple[list[Any], list[ToolTrace], bool]:
    """同步端点用的包装：跑完整个循环，返回 (messages, 轨迹, 是否用过工具)。"""
    final = _LoopResult(messages=list(messages))
    async for kind, payload in stream_tool_loop(messages):
        if kind == "finish":
            final = payload
    return final.messages, final.traces, final.used
