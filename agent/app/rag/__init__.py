"""RAG 层：检索（retriever）+ 提示词与引用（context）。

一期只做「向量检索 → 拼上下文 → 生成」，即 naive RAG。
二期再加 pg_jieba 全文混合召回、Neo4j 邻居扩展、bge-reranker 重排。
"""
