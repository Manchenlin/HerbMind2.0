"""模型工厂：ChatModel 与 Embeddings（硅基流动，OpenAI 兼容协议）。

为什么要"懒加载"：
- 模块 import 时就建客户端 → 没有 key 的机器连服务都起不来
- health 只需要知道"配没配"，不需要真的调模型（省钱、也不依赖网络）
所以这里全部用函数 + lru_cache，第一次真正用到时才创建。

⚠️ embedding 模型必须与库里 1024 维向量同源（BAAI/bge-m3），换模型要全量重算。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_chat_model():
    """返回 LangChain ChatModel（OpenAI 兼容）。"""
    from langchain_openai import ChatOpenAI

    s = get_settings()
    if not s.llm_configured:
        raise RuntimeError("LLM_API_KEY 未配置：请复制 agent/.env.example 为 .env 并填入 key")
    return ChatOpenAI(
        model=s.llm_model,
        api_key=s.llm_api_key,
        base_url=s.llm_api_base,
        temperature=s.llm_temperature,
        max_tokens=s.llm_max_tokens,
        timeout=25,          # 实测 1.4~8.6s，25s 足够；超时说明服务侧异常
        max_retries=1,       # 最坏 25×2 = 50s，仍在网关 60s 之内，不会白烧第二轮
        # 流式模式下 OpenAI 协议默认不回 usage，必须显式要，否则 /ask 的 token 统计永远为 0
        stream_usage=True,
    )


@lru_cache
def get_embeddings():
    """返回 LangChain Embeddings（BAAI/bge-m3，1024 维）。"""
    from langchain_openai import OpenAIEmbeddings

    s = get_settings()
    if not s.llm_configured:
        raise RuntimeError("LLM_API_KEY 未配置：bge-m3 也走同一个 key")
    return OpenAIEmbeddings(
        model=s.embedding_model,
        api_key=s.llm_api_key,
        base_url=s.llm_api_base,
        check_embedding_ctx_length=False,
    )


async def embed_query(text: str) -> list[float]:
    """把一句话转成 1024 维向量（同步 SDK 丢线程池，避免阻塞事件循环）。

    维度硬校验：换了模型但维度不同会立刻炸出来，而不是让检索静默返回垃圾结果。
    同维度但换模型（语义空间不同）无法靠代码发现，只能靠 .env 里的注释约束。
    """
    embeddings = get_embeddings()
    vector = await asyncio.to_thread(embeddings.embed_query, text)
    expected = get_settings().embedding_dim
    if len(vector) != expected:
        raise RuntimeError(
            f"embedding 维度不匹配：得到 {len(vector)} 维，期望 {expected} 维。"
            f"请确认 EMBEDDING_MODEL 未被改动（必须与建库时一致）。"
        )
    return vector


async def chat(prompt: str) -> str:
    """最简一问一答（后续问答走 Agent + 工具，这里只作为连通性示例）。"""
    model = get_chat_model()
    result = await model.ainvoke(prompt)
    return result.content if isinstance(result.content, str) else str(result.content)


async def chat_with_messages(messages: list[dict]) -> tuple[str, dict]:
    """按 messages 调模型，返回 (回答文本, token 用量)。

    messages 直接用 OpenAI 格式（role/content），方便将来平滑换成 Agent 调用。
    """
    model = get_chat_model()
    result = await model.ainvoke(messages)
    text = result.content if isinstance(result.content, str) else str(result.content)
    usage = getattr(result, "usage_metadata", None) or {}
    return text.strip(), dict(usage)


async def chat_stream(messages: list[dict]) -> AsyncIterator[tuple[str, object]]:
    """流式对话，产出 `("delta", 文本片段)` 与末尾一条 `("usage", {...})`。

    为什么用元组而不是直接 yield 字符串：
    调用方需要区分"正文片段"和"用量统计"——后者不能当正文拼进回答，
    但只有生成完才知道。用带标签的事件比在生成器外挂一个可变 dict 更清楚。

    注意：片段的粒度由上游决定（实测多数是 1~4 个汉字），
    不要假设"每次一个 token"，前端按收到的文本原样追加即可。
    """
    model = get_chat_model()
    last_usage: dict = {}
    async for chunk in model.astream(messages):
        usage = getattr(chunk, "usage_metadata", None)
        if usage:
            last_usage = dict(usage)
        content = chunk.content
        if isinstance(content, str):
            if content:
                yield ("delta", content)
        elif isinstance(content, list):
            # 部分兼容实现会把内容拆成分段数组（如 [{"type":"text","text":"..."}]）
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    piece = part.get("text") or ""
                    if piece:
                        yield ("delta", piece)
    if last_usage:
        yield ("usage", last_usage)
