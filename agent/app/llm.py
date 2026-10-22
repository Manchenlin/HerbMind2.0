"""模型工厂：ChatModel 与 Embeddings（硅基流动，OpenAI 兼容协议）。

为什么要"懒加载"：
- 模块 import 时就建客户端 → 没有 key 的机器连服务都起不来
- health 只需要知道"配没配"，不需要真的调模型（省钱、也不依赖网络）
所以这里全部用函数 + lru_cache，第一次真正用到时才创建。

⚠️ embedding 模型必须与库里 1024 维向量同源（BAAI/bge-m3），换模型要全量重算。
"""

from __future__ import annotations

import asyncio
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
        timeout=60,          # 问答场景比纯补全慢，60 秒兜底
        max_retries=2,
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
    """把一句话转成 1024 维向量（同步 SDK 丢线程池，避免阻塞事件循环）。"""
    embeddings = get_embeddings()
    return await asyncio.to_thread(embeddings.embed_query, text)


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
