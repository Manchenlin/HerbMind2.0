"""问答端点：POST /api/agent/ask/sync（同步）与 POST /api/agent/ask（SSE 流式）。

两条链路**共用同一套**检索、工具调用循环与提示词，只有输出方式不同：

    问题 → ① 读多轮记忆（带 conversationId 时）
         → ② pgvector 召回 Top-K（RAG 主链，口径已校准，本轮不动）
         → ③ 工具调用循环（模型自主取证，最多 N 轮，SSE 推 tool 事件）
         → ④ 生成回答（带 [n] 引用角标）
         → ⑤ 后台落库（会话 / 消息 / 工具轨迹，失败不影响回答）

降级策略（不抛 500，永远给前端一个能显示的答案）：
- 检索异常 / 无命中      → degraded=true，提示换个说法
- 工具全挂 / 超预算      → 模型拿 error_result 继续生成（工具是增强，不是前置条件）
- LLM 超时/失败/欠费      → degraded=true，直接列出检索到的资料摘要
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import logging
import re
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.agent.runner import ToolTrace, run_tool_loop, stream_tool_loop
from app.llm import chat_stream, chat_with_messages
from app.rag import sse
from app.rag.context import build_messages, degraded_answer, extract_citations
from app.rag.retriever import retrieve
from app.repo.conversation import (
    append_message,
    ensure_conversation,
    new_conversation_id,
    recent_messages,
    record_tool_call,
)
from app.schemas import AskData, AskRequest, AskUsage, R, ToolCallBrief

logger = logging.getLogger("herbmind-agent")

router = APIRouter(tags=["agent"])

NO_HIT_ANSWER = (
    "提供的资料中没有找到相关内容。\n"
    "可以换个说法，或补充症状、方名、病名后再问。\n"
    "（当前知识库仅含 245 首方剂与 290 则医案的内容摘要，经典条文暂未纳入检索。）"
)

_CITE_TAG = re.compile(r"\[(\d{1,2})\]")


def clamp_citation_tags(text: str, max_index: int) -> tuple[str, list[int]]:
    """剔除越界引用角标。

    实测踩到过：资料只有 5 条，模型回答了 [1][6]。这种"编造编号"比答错更难发现，
    所以这里做硬校验——越界的一律删掉并记日志（日志里出现就说明提示词还需加强）。
    """
    illegal: list[int] = []

    def _repl(match: re.Match) -> str:
        num = int(match.group(1))
        if 1 <= num <= max_index:
            return match.group(0)
        illegal.append(num)
        return ""

    cleaned = _CITE_TAG.sub(_repl, text)
    if illegal:
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned, illegal


# ==================== 会话落库（后台执行，失败不影响回答） ====================


async def _persist_ask(
    conversation_id: str,
    user_id: str,
    question: str,
    answer: str,
    traces: list[ToolTrace],
) -> None:
    """把一次问答写进 `agent_*` 三表。

    刻意放在响应之后执行（BackgroundTasks）：写库是"锦上添花"，
    不能让它占用户等待回答的时间。每个 repo 函数自己吞异常只告警。
    """
    if not conversation_id:
        return
    if not await ensure_conversation(conversation_id, user_id, question):
        # 会话都没建起来，再写消息一定撞外键，直接放弃（只留 warning）
        return
    await append_message(conversation_id, "user", question)
    assistant_id = await append_message(conversation_id, "assistant", answer)
    if assistant_id is None:
        # 只告警不放弃：agent_tool_call.message_id 允许 NULL，
        # 丢掉轨迹等于丢掉"这轮为什么这样回答"的唯一依据
        logger.warning(
            "assistant 消息落库失败，工具轨迹将以 message_id=NULL 写入：conv=%s", conversation_id
        )
    for trace in traces:
        await record_tool_call(
            assistant_id, trace.name, trace.args, trace.summary, trace.ms
        )


def _trace_briefs(traces: list[ToolTrace]) -> list[ToolCallBrief]:
    return [ToolCallBrief(**trace.to_dict()) for trace in traces]


# ==================== 同步问答 ====================


@router.post("/ask/sync", response_model=R[AskData], summary="同步问答（检索 + 工具取证 + 大模型）")
async def ask_sync(
    req: AskRequest,
    background: BackgroundTasks,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> R[AskData]:
    """一次问答（非流式）。只允许经网关访问，必须带网关注入的 X-User-Id。"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="缺少 X-User-Id：该端点只应经网关访问")
    if not _rate_ok(x_user_id):
        # 与 /ask 共用同一套窗口计数：两条链路成本相同（一次问答实测 promptTokens≈5300），
        # 防护不该只做一半
        logger.warning("同步问答被限流：user=%s", x_user_id)
        raise HTTPException(status_code=429, detail="提问过于频繁，请稍后再试")
    question = req.question.strip()
    # 新会话 ID 带 user 指纹：登录上线前会话只能匿名落库，靠 ID 前缀区分"谁的和谁"，
    # 否则 history 会把全库匿名会话都返回同一个人（见 repo.anon_scope 的注释）
    conversation_id = req.conversation_id or new_conversation_id(x_user_id)
    # 问题原文属健康敏感信息，只记长度 + 指纹，便于排查日志关联而不泄露内容
    logger.info(
        "问答请求：user=%s len=%d fp=%s conv=%s（topK=%s refType=%s）",
        x_user_id,
        len(question),
        hashlib.sha1(question.encode("utf-8")).hexdigest()[:8],
        conversation_id,
        req.top_k,
        req.ref_type,
    )

    history = await recent_messages(req.conversation_id) if req.conversation_id else []

    # ---------- ① 检索 ----------
    t0 = time.perf_counter()
    try:
        units = await retrieve(question, top_k=req.top_k, ref_type=req.ref_type)
    except Exception as exc:  # noqa: BLE001 —— 检索失败也要给前端可显示的答复
        logger.exception("检索失败")
        return R.ok(
            AskData(
                answer=f"检索服务异常（{type(exc).__name__}），请稍后重试。",
                citations=[],
                usage=AskUsage(retrieve_ms=int((time.perf_counter() - t0) * 1000)),
                degraded=True,
                conversation_id=conversation_id,
            )
        )
    retrieve_ms = int((time.perf_counter() - t0) * 1000)

    if not units:
        logger.info("问答无命中：fp=%s", hashlib.sha1(question.encode("utf-8")).hexdigest()[:8])
        background.add_task(_persist_ask, conversation_id, x_user_id, question, NO_HIT_ANSWER, [])
        return R.ok(
            AskData(
                answer=NO_HIT_ANSWER,
                citations=[],
                usage=AskUsage(retrieve_ms=retrieve_ms),
                degraded=True,
                conversation_id=conversation_id,
            )
        )

    # ---------- ② 工具取证 ----------
    citations = extract_citations(units)
    messages = build_messages(question, units, history)
    t_tools = time.perf_counter()
    messages, traces, _used = await run_tool_loop(messages)
    tools_ms = int((time.perf_counter() - t_tools) * 1000)
    if traces:
        logger.info(
            "工具取证：%d 次调用 %dms（%s）",
            len(traces),
            tools_ms,
            ", ".join(f"{t.name}:{'OK' if t.ok else 'FAIL'}/{t.count}" for t in traces),
        )

    # ---------- ③ 生成 ----------
    t1 = time.perf_counter()
    try:
        answer, usage = await chat_with_messages(messages)
    except Exception as exc:  # noqa: BLE001 —— LLM 挂了也不能让前端空白
        logger.exception("大模型调用失败，走降级")
        fallback = degraded_answer(units)
        background.add_task(_persist_ask, conversation_id, x_user_id, question, fallback, traces)
        return R.ok(
            AskData(
                answer=fallback,
                citations=citations,
                usage=AskUsage(
                    retrieve_ms=retrieve_ms,
                    llm_ms=int((time.perf_counter() - t1) * 1000),
                    tools_ms=tools_ms,
                ),
                degraded=True,
                tool_calls=_trace_briefs(traces),
                conversation_id=conversation_id,
            )
        )
    llm_ms = int((time.perf_counter() - t1) * 1000)
    answer, illegal_tags = clamp_citation_tags(answer, len(citations))
    if illegal_tags:
        logger.warning(
            "模型输出了越界引用编号 %s（资料只有 %d 条），已自动剔除——若频繁出现需加强提示词",
            illegal_tags,
            len(citations),
        )

    prompt_tokens = int(usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

    logger.info(
        "问答完成：检索 %dms / 工具 %dms（%d 次）/ 生成 %dms，命中 %d 条，tokens=%s",
        retrieve_ms,
        tools_ms,
        len(traces),
        llm_ms,
        len(citations),
        total_tokens or "未知",
    )

    background.add_task(_persist_ask, conversation_id, x_user_id, question, answer, traces)

    return R.ok(
        AskData(
            answer=answer,
            citations=citations,
            usage=AskUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                retrieve_ms=retrieve_ms,
                llm_ms=llm_ms,
                tools_ms=tools_ms,
            ),
            degraded=False,
            tool_calls=_trace_briefs(traces),
            conversation_id=conversation_id,
        )
    )


# ==================== 流式问答（SSE） ====================

# 流式路径的特殊性：响应头在开始输出那一刻就发出去了（HTTP 200），
# 此后**没有任何机会再改状态码**。所以检索失败、模型失败一律降级成"正文里说明"，
# 不能用 raise HTTPException —— 那会导致浏览器收到一个已经开始的流 + 一个无法解析的错误。


def _fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


# 契约 §13.3 要求 429 限流。一次流式问答实测 promptTokens≈5168，
# 前端一个循环就能把额度打光，必须先挡住。
_RATE_WINDOW = 60.0          # 统计窗口（秒）
_RATE_MAX = 20               # 单窗口内最多提问次数
_rate_hits: dict[str, collections.deque[float]] = {}


def _rate_ok(user_id: str, limit: int = _RATE_MAX, window: float = _RATE_WINDOW) -> bool:
    """滑动窗口限流（单进程内存版）。

    多副本部署时计数是按实例各算各的，只能挡住"单点疯狂刷"；
    要全局精确限流得放 Redis（本机已有 herbmind-v2-redis，M2 再接）。
    """
    now = time.monotonic()
    hits = _rate_hits.setdefault(user_id, collections.deque())
    while hits and now - hits[0] > window:
        hits.popleft()
    if len(hits) >= limit:
        return False
    hits.append(now)
    return True


async def _ask_events(
    question: str,
    req: AskRequest,
    conversation_id: str,
    user_id: str,
    holder: dict,
) -> AsyncIterator[str]:
    """SSE 事件流。顺序：retrieval(start) → retrieval(done) → tool(start/done)*
    → citation* → token* → done。

    为什么 citation 全部放在 token 之前：
    前端可以在第一个字出现前就把引用卡建好，正文里的 [1][2] 一出现就能对上号，
    不会出现"角标先到、卡片后到"的闪烁。代价是首字延迟多了几十毫秒（都是内存操作）。

    工具取证发生在 citation 之后、token 之前：引用卡来自 RAG 检索（此时已确定），
    工具只是模型额外取证，不能反过来推迟引用卡。
    """
    t0 = time.perf_counter()
    yield sse.tool("retrieval", "start")

    # ---------- ① 检索 ----------
    try:
        units = await retrieve(question, top_k=req.top_k, ref_type=req.ref_type)
    except asyncio.CancelledError:
        logger.info("客户端在检索阶段断开：user=%s fp=%s", user_id, _fingerprint(question))
        raise
    except Exception as exc:  # noqa: BLE001 —— 检索失败也要给前端可显示的答复
        logger.exception("流式问答：检索失败")
        text = f"检索服务异常（{type(exc).__name__}），请稍后重试。"
        yield sse.token(text)
        yield sse.done(conversation_id, True, usage={"retrieveMs": int((time.perf_counter() - t0) * 1000)})
        return
    retrieve_ms = int((time.perf_counter() - t0) * 1000)
    yield sse.tool("retrieval", "done", hits=len(units))

    if not units:
        logger.info("流式问答无命中：fp=%s", _fingerprint(question))
        yield sse.token(NO_HIT_ANSWER)
        yield sse.done(conversation_id, True, usage={"retrieveMs": retrieve_ms})
        return

    # ---------- ② 引用卡（先于正文） ----------
    citations = extract_citations(units)
    for idx, cite in enumerate(citations, 1):
        yield sse.citation(idx, cite.model_dump(by_alias=True))

    # ---------- ③ 工具取证（模型自主决定要不要调、调几次） ----------
    history = await recent_messages(req.conversation_id) if req.conversation_id else []
    messages = build_messages(question, units, history)
    traces: list[ToolTrace] = []
    t_tools = time.perf_counter()
    async for kind, payload in stream_tool_loop(messages):
        if kind == "tool":
            extra = {k: v for k, v in payload.items() if k not in ("name", "status")}
            yield sse.tool(str(payload.get("name") or ""), str(payload.get("status") or ""), **extra)
        elif kind == "finish":
            messages = payload.messages
            traces = payload.traces
    tools_ms = int((time.perf_counter() - t_tools) * 1000)

    # ---------- ④ 逐字生成 ----------
    t1 = time.perf_counter()
    buf: list[str] = []
    usage_raw: dict = {}
    degraded = False

    try:
        async for kind, payload in chat_stream(messages):
            if kind == "delta":
                text = str(payload)
                buf.append(text)
                yield sse.token(text)
            elif kind == "usage":
                usage_raw = payload  # type: ignore[assignment]
    except asyncio.CancelledError:
        # 用户关页面/切走：别把已生成的部分丢掉，日志里留痕便于观察中断率
        logger.info(
            "客户端在生成阶段断开：user=%s fp=%s 已生成 %d 字",
            user_id,
            _fingerprint(question),
            sum(len(x) for x in buf),
        )
        raise
    except Exception:  # noqa: BLE001
        logger.exception("流式问答：大模型调用失败，转降级")
        degraded = True
        # 已经吐了半截就不能再推降级全文（会和上文重复），只补一句说明
        tail = degraded_answer(units) if not buf else "\n\n（生成中断，请稍后重试）"
        buf.append(tail)
        yield sse.token(tail)
    llm_ms = int((time.perf_counter() - t1) * 1000)

    # ---------- ⑤ 越界引用校对 ----------
    # token 已经发出去了，剔除动作做不了，只能把越界编号回传给前端自己擦
    _, illegal = clamp_citation_tags("".join(buf), len(citations))
    if illegal:
        logger.warning(
            "模型输出了越界引用编号 %s（资料只有 %d 条），已回传给前端剔除——若频繁出现需加强提示词",
            illegal,
            len(citations),
        )

    prompt_tokens = int(usage_raw.get("input_tokens") or 0)
    completion_tokens = int(usage_raw.get("output_tokens") or 0)
    total_tokens = int(usage_raw.get("total_tokens") or (prompt_tokens + completion_tokens))

    logger.info(
        "流式问答完成：检索 %dms / 工具 %dms（%d 次）/ 生成 %dms，命中 %d 条，字数 %d，tokens=%s%s",
        retrieve_ms,
        tools_ms,
        len(traces),
        llm_ms,
        len(citations),
        sum(len(x) for x in buf),
        total_tokens or "未知",
        "（降级）" if degraded else "",
    )

    # 落库放到流结束之后执行（BackgroundTask），不占用生成时间。
    # 生成器没法"返回"数据给调用方，所以把结果写进本次请求私有的 holder。
    holder["answer"] = "".join(buf)
    holder["traces"] = list(traces)

    yield sse.done(
        conversation_id,
        degraded,
        usage={
            "retrieveMs": retrieve_ms,
            "toolsMs": tools_ms,
            "llmMs": llm_ms,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
        },
        illegalCitations=illegal,
    )


async def _persist_from_holder(
    conversation_id: str,
    user_id: str,
    question: str,
    holder: dict,
) -> None:
    """流结束后从 holder 取最终答案与轨迹落库（见 `_ask_events` 末尾）。"""
    await _persist_ask(
        conversation_id,
        user_id,
        question,
        str(holder.get("answer") or ""),
        list(holder.get("traces") or []),
    )


@router.post("/ask", summary="流式问答（SSE，打字机输出）")
async def ask_stream(
    req: AskRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> StreamingResponse:
    """一次流式问答。与 `/ask/sync` 同一套检索、工具与提示词，只换输出方式。

    会话落库：请求开始时生成/沿用 conversationId，流结束后后台写入
    `agent_conversation` / `agent_message` / `agent_tool_call`。
    带同一个 conversationId 再次提问即接上多轮记忆。
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="缺少 X-User-Id：该端点只应经网关访问")
    if not _rate_ok(x_user_id):
        # 契约 §13.3 要求 429。注意 X-User-Id 是网关信任头、可被伪造，
        # 所以 8091 必须只允许网关访问，不能对外暴露。
        logger.warning("流式问答被限流：user=%s", x_user_id)
        raise HTTPException(status_code=429, detail="提问过于频繁，请稍后再试")

    question = req.question.strip()
    # 新会话 ID 带 user 指纹：登录上线前会话只能匿名落库，靠 ID 前缀区分"谁的和谁"，
    # 否则 history 会把全库匿名会话都返回同一个人（见 repo.anon_scope 的注释）
    conversation_id = req.conversation_id or new_conversation_id(x_user_id)
    logger.info(
        "流式问答请求：user=%s len=%d fp=%s conv=%s（topK=%s refType=%s）",
        x_user_id,
        len(question),
        _fingerprint(question),
        conversation_id,
        req.top_k,
        req.ref_type,
    )

    # 每个请求一个私有 holder：生成器把最终答案与工具轨迹写进来，流结束后落库。
    # 不用模块级变量存，避免并发请求互相覆盖。
    holder: dict = {"answer": "", "traces": []}
    return StreamingResponse(
        _ask_events(question, req, conversation_id, x_user_id, holder),
        media_type="text/event-stream",
        headers=sse.STREAM_HEADERS,
        background=BackgroundTask(
            _persist_from_holder, conversation_id, x_user_id, question, holder
        ),
    )
