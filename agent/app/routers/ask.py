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

import logging
import re
import time

from fastapi import APIRouter

from app.llm import chat_with_messages
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
async def ask_sync(req: AskRequest) -> R[AskData]:
    """一次问答（非流式）。适合调试与不要求打字机效果的场景。"""
    question = req.question.strip()
    logger.info("问答请求：%s（topK=%s refType=%s）", question, req.top_k, req.ref_type)

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
