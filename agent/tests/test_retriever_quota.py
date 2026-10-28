"""召回层（`app/rag/retriever.py`）的配额、阈值与取数格式测试。

为什么专门测配额：实测过"问方不给方"——Top5 全被医案占满，真正的方剂排在第 6 名开外。
所以 `retrieve()` 不指定 ref_type 时必须按 **方剂 60% + 医案 40%** 双路召回。
另外 `limit=1` 时不能硬塞一条医案（case_k 用 0 兜底而不是 1），这条容易在重构时写错。

零外部依赖：PG 连接池与 embedding 全部替身替换，不连库、不联网。
"""

from __future__ import annotations

import asyncio

import pytest

from app.rag import retriever as rv


class _FakeCursor:
    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn
        self._rows: list[tuple] = []

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def execute(self, _sql: str, params: dict) -> None:
        pool = self._conn.pool
        ref_type = params["ref_type"]
        pool.calls.append({"ref_type": ref_type, "limit": params["limit"], "vec": params["vec"]})
        self._rows = pool.rows_by_type.get(ref_type, [])[: params["limit"]]

    def fetchall(self) -> list[tuple]:
        return self._rows


class _FakeConn:
    def __init__(self, pool: "_FakePool") -> None:
        self.pool = pool

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)


class _FakePool:
    """够用的池替身：记录每次检索的 (ref_type, limit)，按类型返回预置行。"""

    def __init__(self, rows_by_type: dict[str, list[tuple]]) -> None:
        self.rows_by_type = rows_by_type
        self.calls: list[dict] = []

    def connection(self, timeout: float | None = None) -> _FakeConn:  # noqa: ARG002
        return _FakeConn(self)


def _rows(ref_type: str, scores: list[float]) -> list[tuple]:
    """按 (id, ref_type, ref_id, title, content, score) 的口径造行。"""
    return [
        (
            f"cu_{ref_type}_{i}",
            ref_type,
            f"{ref_type[0]}_{i}",
            f"{ref_type}标题{i}",
            f"{ref_type}正文{i}",
            score,
        )
        for i, score in enumerate(scores, 1)
    ]


def _patch(monkeypatch, rows_by_type, embed_calls: list[str] | None = None) -> _FakePool:
    pool = _FakePool(rows_by_type)
    monkeypatch.setattr(rv, "get_pg_pool", lambda: pool)

    async def _fake_embed(question: str) -> list[float]:
        if embed_calls is not None:
            embed_calls.append(question)
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(rv, "embed_query", _fake_embed)
    return pool


# ==================== 配额 ====================


def test_default_quota_is_60_percent_formula(monkeypatch) -> None:
    """top_k=5 且不限类型 → 方剂 3 条 + 医案 2 条，合并后按分数降序。"""
    embed_calls: list[str] = []
    pool = _patch(
        monkeypatch,
        {
            "formula": _rows("formula", [0.9, 0.7, 0.55]),
            "case": _rows("case", [0.85, 0.6]),
        },
        embed_calls,
    )

    units = asyncio.run(rv.retrieve("麻黄汤的组成", top_k=5, min_score=0.5))

    # 两路是并发跑的（asyncio.gather + to_thread），线程完成顺序不保证 → 只比"查了哪几路、各几条"
    assert {(c["ref_type"], c["limit"]) for c in pool.calls} == {("formula", 3), ("case", 2)}
    assert [u.score for u in units] == [0.9, 0.85, 0.7, 0.6, 0.55]
    # 两路共用同一个问题向量：只 embed 一次（否则白白多花 200~300ms）
    assert embed_calls == ["麻黄汤的组成"]


def test_limit_one_does_not_force_a_case_row(monkeypatch) -> None:
    """top_k=1 → 只查方剂 1 条，**不发**医案那一路（case_k 必须用 0 兜底）。"""
    pool = _patch(monkeypatch, {"formula": _rows("formula", [0.8]), "case": _rows("case", [0.9])})

    units = asyncio.run(rv.retrieve("桂枝汤", top_k=1, min_score=0.5))

    assert [c["ref_type"] for c in pool.calls] == ["formula"]
    assert pool.calls[0]["limit"] == 1
    assert len(units) == 1
    assert units[0].ref_type == "formula"


def test_explicit_ref_type_uses_single_path(monkeypatch) -> None:
    """指定 ref_type → 单路检索，limit 就是 top_k。"""
    pool = _patch(monkeypatch, {"case": _rows("case", [0.8, 0.75])})

    units = asyncio.run(rv.retrieve("小承气汤", top_k=2, ref_type="case", min_score=0.5))

    assert [(c["ref_type"], c["limit"]) for c in pool.calls] == [("case", 2)]
    assert [u.ref_type for u in units] == ["case", "case"]


# ==================== 阈值 ====================


def test_low_score_rows_are_dropped(monkeypatch) -> None:
    """低于相似度下限的一律丢弃：宁可少给，也不要塞不相关内容诱发幻觉。"""
    _patch(
        monkeypatch,
        {"formula": _rows("formula", [0.72, 0.31]), "case": _rows("case", [0.45])},
    )

    units = asyncio.run(rv.retrieve("麻黄汤", top_k=5, min_score=0.5))

    assert [u.score for u in units] == [0.72]


# ==================== 取数格式 ====================


def test_to_pgvector_literal() -> None:
    """向量以 pgvector 字面量字符串传参，由 PG 侧 cast，避免依赖 psycopg 适配器。"""
    assert rv._to_pgvector([0.5, -1.0, 0.0]) == "[0.5,-1,0]"


@pytest.mark.parametrize(
    ("ref_type", "title", "content", "expected"),
    [
        # case 的 title 只有书名（伤寒论/金匮要略/温病学），不能用 → 取正文第一行
        ("case", "伤寒论", "医案：小承气汤\n患者大便不通……", "小承气汤"),
        ("case", "伤寒论", "医案:桂枝汤\n恶风自汗……", "桂枝汤"),
        ("case", "伤寒论", "\n\n医案：麻黄汤\n无汗而喘", "麻黄汤"),
        # formula 的 title 就是方名，直接用
        ("formula", "麻黄汤", "组成：麻黄、桂枝", "麻黄汤"),
        # title 为空才退回 ref_id
        ("formula", "", "组成：未知", "f_9"),
    ],
)
def test_display_title(ref_type, title, content, expected) -> None:
    assert rv._display_title(ref_type, title, content, "f_9") == expected


def test_snippet_strips_newlines_and_truncates() -> None:
    """引用卡预览：换行压成空格，超长截断加省略号。"""
    unit = rv.RetrievedUnit(
        id="cu_1", ref_type="formula", ref_id="f_1", title="麻黄汤", content="第一行\n第二行", score=0.7
    )
    assert unit.snippet() == "第一行 第二行"

    long_unit = rv.RetrievedUnit(
        id="cu_2", ref_type="formula", ref_id="f_1", title="麻黄汤", content="药" * 200, score=0.7
    )
    snippet = long_unit.snippet()
    assert len(snippet) == rv.SNIPPET_LEN + 1  # 160 字 + 省略号
    assert snippet.endswith("…")
