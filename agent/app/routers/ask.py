"""POST /api/agent/ask/sync —— 同步问答（RAG）。

流程：问题向量化 → pgvector 召回 Top-K → 拼提示词 → LLM 生成 → 带引用返回。

为什么先做同步版而不是 SSE 流式：
同步版不用处理长连接、断线重连、前端 EventSource，能先把「检索质量 + 提示词」调通；
链路稳定后再升级成 ask（SSE），改动只在"输出方式"，检索与提示词可原样复用。

降级策略（不抛 500，永远给前端一个能显示的答案）：
- 检索异常 / 无命中      → degraded=true，提示换个说法
- LLM 超时/失败/欠费      → degraded=true，直接列出检索到的资料摘要
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.llm import chat_stream, chat_with_messages
from app.rag import sse
from app.rag.context import build_messages, degraded_answer, extract_citations
from app.rag.retriever import retrieve
from app.schemas import AskData, AskRequest, AskUsage, R

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


@router.post("/ask/sync", response_model=R[AskData], summary="同步问答（向量检索 + 大模型）")
async def ask_sync(
    req: AskRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> R[AskData]:
    """一次问答（非流式）。只允许经网关访问，必须带网关注入的 X-User-Id。"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="缺少 X-User-Id：该端点只应经网关访问")
    question = req.question.strip()
    # 问题原文属健康敏感信息，只记长度 + 指纹，便于排查日志关联而不泄露内容
    logger.info(
        "问答请求：user=%s len=%d fp=%s（topK=%s refType=%s）",
        x_user_id,
        len(question),
        hashlib.sha1(question.encode("utf-8")).hexdigest()[:8],
        req.top_k,
        req.ref_type,
    )

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
            )
        )
    retrieve_ms = int((time.perf_counter() - t0) * 1000)

    if not units:
        logger.info("问答无命中：%s", question)
        return R.ok(
            AskData(
                answer=NO_HIT_ANSWER,
                citations=[],
                usage=AskUsage(retrieve_ms=retrieve_ms),
                degraded=True,
            )
        )

    # ---------- ② 生成 ----------
    citations = extract_citations(units)
    messages = build_messages(question, units)
    t1 = time.perf_counter()
    try:
        answer, usage = await chat_with_messages(messages)
    except Exception as exc:  # noqa: BLE001 —— LLM 挂了也不能让前端空白
        logger.exception("大模型调用失败，走降级")
        return R.ok(
            AskData(
                answer=degraded_answer(units),
                citations=citations,
                usage=AskUsage(retrieve_ms=retrieve_ms, llm_ms=int((time.perf_counter() - t1) * 1000)),
                degraded=True,
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
        "问答完成：检索 %dms / 生成 %dms，命中 %d 条，tokens=%s",
        retrieve_ms,
        llm_ms,
        len(citations),
        total_tokens or "未知",
    )

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
            ),
            degraded=False,
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
) -> AsyncIterator[str]:
    """SSE 事件流。顺序：tool(start) → tool(done) → citation* → token* → done。

    为什么把 citation 全部放在 token 之前：
    前端可以在第一个字出现前就把引用卡建好，正文里的 [1][2] 一出现就能对上号，
    不会出现"角标先到、卡片后到"的闪烁。代价是首字延迟多了几十毫秒（都是内存操作）。
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
        yield sse.token(f"检索服务异常（{type(exc).__name__}），请稍后重试。")
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

    # ---------- ③ 逐字生成 ----------
    messages = build_messages(question, units)
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

    # ---------- ④ 越界引用校对 ----------
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
        "流式问答完成：检索 %dms / 生成 %dms，命中 %d 条，字数 %d，tokens=%s%s",
        retrieve_ms,
        llm_ms,
        len(citations),
        sum(len(x) for x in buf),
        total_tokens or "未知",
        "（降级）" if degraded else "",
    )

    yield sse.done(
        conversation_id,
        degraded,
        usage={
            "retrieveMs": retrieve_ms,
            "llmMs": llm_ms,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
        },
        illegalCitations=illegal,
    )


@router.post("/ask", summary="流式问答（SSE，打字机输出）")
async def ask_stream(
    req: AskRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> StreamingResponse:
    """一次流式问答。与 `/ask/sync` 同一套检索与提示词，只换输出方式。

    ⚠️ 会话尚未落库：`agent_conversation` / `agent_message` 表已建但为空，
    且 `user_id` 外键指向 `app_user`，未经网关的真实用户 ID 插不进去。
    所以这里只**回显** conversationId（前端可拿它串多轮），M2 再做持久化。
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="缺少 X-User-Id：该端点只应经网关访问")
    if not _rate_ok(x_user_id):
        # 契约 §13.3 要求 429。注意 X-User-Id 是网关信任头、可被伪造，
        # 所以 8091 必须只允许网关访问，不能对外暴露。
        logger.warning("流式问答被限流：user=%s", x_user_id)
        raise HTTPException(status_code=429, detail="提问过于频繁，请稍后再试")

    question = req.question.strip()
    conversation_id = req.conversation_id or f"c_{uuid.uuid4().hex[:8]}"
    logger.info(
        "流式问答请求：user=%s len=%d fp=%s conv=%s（topK=%s refType=%s）",
        x_user_id,
        len(question),
        _fingerprint(question),
        conversation_id,
        req.top_k,
        req.ref_type,
    )

    return StreamingResponse(
        _ask_events(question, req, conversation_id, x_user_id),
        media_type="text/event-stream",
        headers=sse.STREAM_HEADERS,
    )
