"""经典条文检索（`app/rag/quote.py`）的断言测试。

为什么要单独测：
1. `classic_quote` 568 条**没有向量**，向量检索永远召不到，这条链路是唯一入口；
2. 拆条必须放在 Python 里做 —— PostgreSQL 的 `regexp_matches` 实测不支持非贪婪，
   在 SQL 里拆会把整段吐成一条（`svc-search` 的条文索引就是这么写的，它返回的是整段）；
3. 打分是自研的 2-gram 覆盖率，阈值与排序都得钉住，否则很容易退化成"什么都命中"。

零外部依赖层用替身（`load_quotes`），集成层连真实库并按 `helpers.pg_ready()` 跳过。
"""

from __future__ import annotations

import pytest

from helpers import pg_ready

from app.rag import quote

# 库内真实结构（q_1 的原文就是多条连排，实测 2026-10-28）
_MULTI = (
    "1.太阳之为病，脉浮，头项强痛而恶寒。(1) "
    "2.太阳病，或已发热，或未发热，必恶寒，体痛，呕逆，脉阴阳俱紧者，名为伤寒。(3) "
    "3.太阳病，头痛发热，身疼腰痛……无汗而喘者，麻黄汤主之。(35)"
)


# ==================== 拆条 ====================


def test_split_multi_chunk_content() -> None:
    """多条连排的正文要拆成多条，条文号各不相同。"""
    chunks = quote.split_quote(_MULTI, "q_1", "伤寒论")

    assert [c.article_no for c in chunks] == ["1", "3", "35"]
    assert chunks[0].text == "太阳之为病，脉浮，头项强痛而恶寒。"
    assert chunks[2].seq == "3"
    assert all(c.classic_name == "伤寒论" for c in chunks)


def test_split_falls_back_to_whole_text_without_numbering() -> None:
    """没有「编号.正文(条文号)」结构的条文不能被丢掉（库里约一半是这样）。"""
    chunks = quote.split_quote("热郁于里，经气郁阻不利，故身体灼热而骨节烦疼", "q_100", "温病学")

    assert len(chunks) == 1
    assert chunks[0].article_no == ""
    assert chunks[0].title == "温病学·q_100"  # 没有条文号时退回 quote_id 便于溯源


def test_split_truncates_overlong_chunk() -> None:
    chunks = quote.split_quote("1." + "药" * 900 + "(99)", "q_x", "伤寒论")

    assert len(chunks) == 1
    assert len(chunks[0].text) == quote.CHUNK_LIMIT


# ==================== 打分与召回 ====================


def _fake_quotes() -> list[quote.QuoteChunk]:
    return [
        quote.QuoteChunk("q_1", "1", "太阳之为病，脉浮，头项强痛而恶寒。", "伤寒论", "1"),
        quote.QuoteChunk("q_1", "35", "太阳病，头痛发热，无汗而喘者，麻黄汤主之。", "伤寒论", "3"),
        quote.QuoteChunk("q_100", "", "热郁于里，经气郁阻不利。", "温病学", ""),
    ]


def test_ngrams_ignores_punctuation() -> None:
    """「脉浮，头项」与「脉浮头项」必须算出同一组片段，否则用户抄原文也匹配不上。"""
    assert quote._ngrams("脉浮，头项") == quote._ngrams("脉浮头项")


def test_retrieve_orders_by_coverage_and_applies_threshold(monkeypatch) -> None:
    monkeypatch.setattr(quote, "load_quotes", _fake_quotes)

    units = quote.retrieve_quotes("太阳之为病脉浮头项强痛而恶寒")

    assert units, "这条查询必须能召回第 1 条"
    assert units[0].ref_type == "quote"
    assert units[0].ref_id == "q_1"
    assert "头项强痛" in units[0].content
    assert units[0].title == "伤寒论·第1条"
    # 覆盖率低的（温病学那条）必须被阈值挡掉
    assert all(unit.title != "温病学·q_100" for unit in units)


def test_retrieve_returns_empty_for_unrelated_question(monkeypatch) -> None:
    monkeypatch.setattr(quote, "load_quotes", _fake_quotes)

    assert quote.retrieve_quotes("今天北京天气怎么样") == []


def test_retrieve_clamps_top_k_and_handles_empty_question(monkeypatch) -> None:
    monkeypatch.setattr(quote, "load_quotes", _fake_quotes)

    assert quote.retrieve_quotes("   ") == []
    assert len(quote.retrieve_quotes("太阳病", top_k=99)) <= quote.MAX_TOP_K


def test_quote_units_feed_prompt_with_correct_label(monkeypatch) -> None:
    """引用卡与提示词都要能认 ref_type=quote（否则会显示成 "quote" 原文）。"""
    from app.rag.context import build_materials, extract_citations

    monkeypatch.setattr(quote, "load_quotes", _fake_quotes)
    units = quote.retrieve_quotes("太阳之为病脉浮")

    assert units[0].kind_label == "条文"
    assert "（条文：" in build_materials(units)
    assert extract_citations(units)[0].ref_type == "quote"


# ==================== 集成层（真实库） ====================


def test_real_db_recalls_song_article_one() -> None:
    """库内事实：`q_1` 的第一条就是「太阳之为病，脉浮，头项强痛而恶寒。(1)」。"""
    reason = pg_ready()
    if reason:
        pytest.skip(reason)

    units = quote.retrieve_quotes("太阳之为病脉浮头项强痛而恶寒", top_k=3)

    assert units, "条文检索没有命中，说明拆条或打分退化了"
    top = units[0]
    assert top.ref_type == "quote"
    assert "头项强痛" in top.content
    assert top.score >= quote.MIN_SCORE


def test_real_db_load_splits_more_than_raw_rows() -> None:
    """568 行原始记录必须拆出**多于** 568 条（否则说明拆条又退回"整段一条"）。"""
    reason = pg_ready()
    if reason:
        pytest.skip(reason)

    chunks = quote.load_quotes(refresh=True)

    assert len(chunks) > 568
    assert sum(1 for c in chunks if c.article_no) > 48  # 原始只有 48 行有 article_no
