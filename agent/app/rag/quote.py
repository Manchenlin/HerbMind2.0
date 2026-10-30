r"""经典条文检索（补 `classic_quote` 的召回缺口）。

背景：`content_unit` 只有 535 条（方剂 245 + 医案 290），**568 条 `classic_quote` 没有向量**，
所以问「太阳病提纲是什么」时向量检索根本召不到原文。本模块直接查 `classic_quote` 补这一路。

⚠️ 关键实测坑（2026-10-28）：**PostgreSQL 的 `regexp_matches` 不支持非贪婪匹配**。
用 `'(\d+)\s*[.．、]\s*(.+?)\s*[(（](\d+)[)）]'` 拆条文，PG 会一路贪婪吃到文末最后一个编号，
结果一条 quote 只拆出 1 行、正文还是整段（`backend/svc-search` 的条文索引用的就是这条 SQL，
因此它返回的也是整段 + 末位条文号）。所以**拆条放在 Python 里做**：Python 的 `+?` 工作正常。

打分不走向量（条文没有向量）、也不用 pg_trgm（数据量小、避免每次查库）：
在内存里做**汉字 2-gram 覆盖率** —— `|query 片段 ∩ 条文片段| / |query 片段|`。
它可解释、无外部依赖，且对"用户直接抄原文提问"这种最常见场景非常准。
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from app.db import get_pg_pool
from app.rag.retriever import RetrievedUnit

logger = logging.getLogger("herbmind-agent")

# 目录缓存：ETL 产物，进程内基本不变（与 formula_diff 的 catalog 同策略）
CACHE_TTL = 300.0
_cache: dict[str, object] = {"at": 0.0, "data": None}

# 单条条文正文截断：再长就是整段混杂，截了避免稀释上下文
CHUNK_LIMIT = 400
# 相似度下限：低于它判无命中（宁可说"没找到"，也不塞不相关条文）
MIN_SCORE = 0.35
# 每次最多召回的条文数上限
MAX_TOP_K = 8

# 条文编号形如「1.太阳之为病……(1)」；正文可能有多条连排，需要逐条切开
_CHUNK_RE = re.compile(r"(\d{1,3})\s*[.．、]\s*(.+?)\s*[(（]\s*(\d{1,4})\s*[)）]", re.S)
# 2-gram 只保留汉字与字母数字，标点空白一律丢掉（"脉浮，头项" 与 "脉浮头项" 视为同一片段）
_NOT_WORD_RE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]")


@dataclass(slots=True)
class QuoteChunk:
    """一条拆好的经典条文。"""

    quote_id: str          # 原始 classic_quote.id（如 q_1）
    article_no: str        # 条文号（如 "35"），原文没编号时为空
    text: str              # 条文正文（已截断）
    classic_name: str      # 典籍名（伤寒论 / 金匮要略 / 温病学）
    seq: str               # 该 quote 内部的序号（如 "3"）

    @property
    def title(self) -> str:
        """给前端和提示词用的可读名称（始终带 quote_id，便于溯源到原文）。"""
        if self.article_no:
            return f"{self.classic_name}·第{self.article_no}条"
        if self.seq:
            return f"{self.classic_name}·{self.quote_id}#{self.seq}"
        return f"{self.classic_name}·{self.quote_id}"


def _ngrams(text: str, n: int = 2) -> set[str]:
    """汉字 n-gram 集合（去标点空白）。"""
    clean = _NOT_WORD_RE.sub("", text or "")
    if not clean:
        return set()
    if len(clean) <= n:
        return {clean}
    return {clean[i : i + n] for i in range(len(clean) - n + 1)}


def split_quote(content: str, quote_id: str, classic_name: str) -> list[QuoteChunk]:
    """把一条 `classic_quote` 正文拆成若干条文。

    用 Python 正则（非贪婪有效）。匹配不到任何「编号.正文(条文号)」结构时，
    整段作为一条返回 —— 库里有约一半条文没有括号编号（568 行里只有 48 行 article_no 非空），
    不能因为拆不开就丢掉。
    """
    chunks: list[QuoteChunk] = []
    for match in _CHUNK_RE.finditer(content or ""):
        text = match.group(2).strip()
        if not text:
            continue
        chunks.append(
            QuoteChunk(
                quote_id=quote_id,
                article_no=match.group(3).strip(),
                text=text[:CHUNK_LIMIT],
                classic_name=classic_name,
                seq=match.group(1).strip(),
            )
        )
    if not chunks:
        body = (content or "").strip()
        if body:
            chunks.append(
                QuoteChunk(
                    quote_id=quote_id, article_no="", text=body[:CHUNK_LIMIT],
                    classic_name=classic_name, seq="",
                )
            )
    return chunks


def load_quotes(refresh: bool = False) -> list[QuoteChunk]:
    """加载并拆分全部条文（带 TTL 缓存）。"""
    now = time.monotonic()
    cached = _cache.get("data")
    if not refresh and cached is not None and now - float(_cache.get("at") or 0) < CACHE_TTL:
        return cached  # type: ignore[return-value]

    with get_pg_pool().connection(timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT q.id, coalesce(q.content, ''), coalesce(c.name, '')
                   FROM classic_quote q
                   LEFT JOIN classic c ON c.id = q.classic_id
                   ORDER BY q.id"""
            )
            rows = cur.fetchall()

    chunks: list[QuoteChunk] = []
    for quote_id, content, classic_name in rows:
        chunks.extend(split_quote(content, quote_id, classic_name or "未标注典籍"))

    _cache["data"] = chunks
    _cache["at"] = now
    logger.info("条文索引已加载：%d 条原记录 → %d 条条文", len(rows), len(chunks))
    return chunks


def _score(query_grams: set[str], text: str) -> float:
    """2-gram 覆盖率：query 的片段有多少比例在条文里出现过。"""
    if not query_grams:
        return 0.0
    return len(query_grams & _ngrams(text)) / len(query_grams)


def retrieve_quotes(question: str, top_k: int = 5, min_score: float | None = None) -> list[RetrievedUnit]:
    """按 2-gram 覆盖率召回经典条文，返回与向量检索同构的 `RetrievedUnit`。

    Args:
        question: 用户问题原文（不需要预处理）
        top_k: 召回条数（1~8）
        min_score: 覆盖率下限，None 表示用 MIN_SCORE（0.35）

    Returns:
        按覆盖率降序的条文；`ref_type="quote"`、`ref_id` 是 `classic_quote.id`。
    """
    text = (question or "").strip()
    if not text:
        return []

    threshold = MIN_SCORE if min_score is None else min_score
    limit = max(1, min(int(top_k or 5), MAX_TOP_K))
    query_grams = _ngrams(text)
    if not query_grams:
        return []

    scored: list[tuple[float, QuoteChunk]] = []
    for chunk in load_quotes():
        score = _score(query_grams, chunk.text)
        if score >= threshold:
            scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:limit]

    logger.info(
        "条文检索『%s』阈值=%.2f → 命中 %d/%d 条，最高 %.3f",
        text[:20], threshold, len(top), len(scored), top[0][0] if top else 0.0,
    )
    return [
        RetrievedUnit(
            id=chunk.quote_id,
            ref_type="quote",
            ref_id=chunk.quote_id,
            title=chunk.title,
            content=chunk.text,
            score=round(score, 4),
        )
        for score, chunk in top
    ]
