"""一期 4 个 Agent 工具的断言测试。

分两层（与 `test_formula_diff.py` 一致的分层思路）：
- **单元层**：PG 连接池 / Neo4j Driver 全部替身，不连库不联网，验证参数夹紧、参数绑定、
  `hit/ok/hint` 三态语义、去重与字段映射；
- **集成层**：连真实库，断言的是**库内可核对的事实**（桂枝汤五味药、麻黄汤含麻黄），
  环境没起时按 `helpers.pg_ready()` / `neo4j_ready()` 跳过而不是红一片。

红线段：所有工具都必须带 `notice`（或明确说明为何没有），且 `hit=false` 时 hint 非空——
只返回空数组会让模型自己补一句"一般来说"。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from helpers import make_unit, neo4j_ready, pg_ready

from app.tools import ALL_TOOLS, tool_names
from app.tools import catalog, graph, recall
from app.tools.common import clamp_int


# ==================== 替身 ====================


class _FakeCursor:
    def __init__(self, pool: "_FakePool") -> None:
        self._pool = pool

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def execute(self, sql: str, params: dict | None = None) -> None:
        self._pool.sql.append(sql)
        self._pool.params.append(params or {})
        if self._pool.raises is not None:
            raise self._pool.raises

    def fetchall(self) -> list[tuple]:
        return list(self._pool.rows)


class _FakeConn:
    def __init__(self, pool: "_FakePool") -> None:
        self._pool = pool

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def cursor(self) -> _FakeCursor:
        # 注意传 pool 而不是 conn：cursor 要往 pool 上记录 SQL
        return _FakeCursor(self._pool)


class _FakePool:
    def __init__(self, rows: list[tuple], raises: Exception | None = None) -> None:
        self.rows = rows
        self.raises = raises
        self.sql: list[str] = []
        self.params: list[dict] = []

    def connection(self, timeout: float | None = None) -> _FakeConn:  # noqa: ARG002
        return _FakeConn(self)


class _FakeSession:
    def __init__(self, driver: "_FakeDriver") -> None:
        self._driver = driver

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def run(self, cypher: str, **params: Any) -> list[dict]:
        self._driver.cyphers.append(cypher)
        self._driver.params.append(params)
        if self._driver.raises is not None:
            raise self._driver.raises
        return list(self._driver.rows)


class _FakeDriver:
    def __init__(self, rows: list[dict] | None = None, raises: Exception | None = None) -> None:
        self.rows = rows or []
        self.raises = raises
        self.cyphers: list[str] = []
        self.params: list[dict] = []

    def session(self) -> _FakeSession:
        return _FakeSession(self)


def _patch_pg(monkeypatch, rows: list[tuple] | None = None, raises: Exception | None = None) -> _FakePool:
    pool = _FakePool(rows or [], raises)
    monkeypatch.setattr(catalog, "get_pg_pool", lambda: pool)
    return pool


def _patch_neo4j(monkeypatch, rows: list[dict] | None = None, raises: Exception | None = None) -> _FakeDriver:
    driver = _FakeDriver(rows, raises)
    monkeypatch.setattr(graph, "get_neo4j_driver", lambda: driver)
    return driver


# ==================== 工具清单 ====================


def test_only_four_tools_in_phase_one() -> None:
    """一期只挂 4 个工具：`syndrome`/`dosage_rule` 表都是 0 行，挂上去只会诱发编造。"""
    assert tool_names() == ["search_formula", "search_case", "semantic_recall", "graph_neighbors"]
    assert len(ALL_TOOLS) == 4
    for item in ALL_TOOLS:
        assert item.description, f"{item.name} 缺少描述：模型靠它选工具"


# ==================== search_formula ====================


def test_search_formula_needs_at_least_one_condition(monkeypatch) -> None:
    pool = _patch_pg(monkeypatch)

    result = catalog.search_formula.invoke({})

    assert result["ok"] is False
    assert "至少提供" in result["hint"]
    assert pool.sql == [], "参数不全时不该查库"


def test_search_formula_maps_row_to_item(monkeypatch) -> None:
    # 列序与 catalog._FORMULA_SQL 一致：id/name/alias/efficacy/syndrome_text/page/herbs
    row = ("f_1", "麻黄汤", "麻黄汤方", "发汗解表", "无汗而喘", "12", "麻黄、桂枝、杏仁、甘草")
    _patch_pg(monkeypatch, [row])

    result = catalog.search_formula.invoke({"name": "麻黄汤"})

    assert result["ok"] is True and result["hit"] is True and result["count"] == 1
    item = result["items"][0]
    assert item["id"] == "f_1"
    assert item["herbs"] == ["麻黄", "桂枝", "杏仁", "甘草"]   # 按库内顺序，不打乱
    assert item["syndromeText"] == "无汗而喘"
    assert result["notice"], "涉及方剂内容必须带免责声明"


def test_search_formula_binds_params_instead_of_interpolating(monkeypatch) -> None:
    """注入面回归钉子：用户输入只能进 params，绝不能出现在 SQL 文本里。"""
    pool = _patch_pg(monkeypatch, [])
    payload = "'; DROP TABLE formula; --"

    catalog.search_formula.invoke({"name": payload})

    assert payload not in pool.sql[0]
    assert pool.params[0]["name"] == payload


def test_search_formula_miss_gives_actionable_hint(monkeypatch) -> None:
    _patch_pg(monkeypatch, [])

    result = catalog.search_formula.invoke({"herb": "不存在的药"})

    assert result["ok"] is True and result["hit"] is False and result["count"] == 0
    assert "库内没有" in result["hint"]
    assert result["notice"] == ""


def test_search_formula_db_failure_returns_error_not_raise(monkeypatch) -> None:
    """工具不许抛：抛出去模型拿不到可读原因，只会换个说法再编一遍。"""
    _patch_pg(monkeypatch, raises=RuntimeError("池未初始化"))

    result = catalog.search_formula.invoke({"name": "桂枝汤"})

    assert result["ok"] is False
    assert "RuntimeError" in result["hint"]


# ==================== search_case ====================


def test_search_case_needs_at_least_one_condition(monkeypatch) -> None:
    pool = _patch_pg(monkeypatch)

    result = catalog.search_case.invoke({"diagnosis": "  "})

    assert result["ok"] is False
    assert "至少提供" in result["hint"]
    assert pool.sql == []


def test_search_case_maps_row_to_item(monkeypatch) -> None:
    # 列序：id/title/unit_type/source_formula/syndrome_text/symptoms/signs/page
    row = ("cs_3", "伤寒论", "医案", "麻黄汤", "太阳伤寒", '["无汗"]', '["脉浮紧"]', "35")
    _patch_pg(monkeypatch, [row])

    result = catalog.search_case.invoke({"formula": "麻黄汤"})

    item = result["items"][0]
    assert item["id"] == "cs_3"
    assert item["sourceFormula"] == "麻黄汤"
    assert item["symptoms"] == '["无汗"]'
    assert result["hit"] is True


# ==================== graph_neighbors ====================


def test_graph_rejects_unknown_label(monkeypatch) -> None:
    """标签进 Cypher 前必须过白名单：图里只有 Formula / Herb。"""
    driver = _patch_neo4j(monkeypatch)

    result = graph.graph_neighbors.invoke({"entity": "太阳病", "label": "Syndrome"})

    assert result["ok"] is False
    assert "不支持" in result["hint"]
    assert driver.cyphers == [], "非法标签不该发到 Neo4j"


def test_graph_clamps_hops_and_maps_chinese_label(monkeypatch) -> None:
    driver = _patch_neo4j(monkeypatch, [{"label": "Herb", "name": "麻黄", "relTypes": ["COMPOSED_OF"]}])

    result = graph.graph_neighbors.invoke({"entity": "麻黄汤", "label": "药味", "hops": 99})

    assert result["hit"] is True
    assert ":Herb" in driver.cyphers[0]           # 中文别名映射成真实标签
    assert "*1..3" in driver.cyphers[0]          # 跳数夹到上限 3
    assert driver.params[0] == {"name": "麻黄汤", "limit": graph.MAX_NEIGHBORS}


def test_graph_dedupes_and_skips_unnamed_nodes(monkeypatch) -> None:
    _patch_neo4j(
        monkeypatch,
        [
            {"label": "Herb", "name": "麻黄", "relTypes": ["COMPOSED_OF"]},
            {"label": "Herb", "name": "麻黄", "relTypes": ["COMPOSED_OF"]},  # 重复
            {"label": "Herb", "name": "", "relTypes": []},                   # 无名节点
        ],
    )

    result = graph.graph_neighbors.invoke({"entity": "麻黄汤"})

    assert result["count"] == 1
    assert result["items"][0]["name"] == "麻黄"


def test_graph_miss_and_failure(monkeypatch) -> None:
    _patch_neo4j(monkeypatch, [])
    miss = graph.graph_neighbors.invoke({"entity": "根本没有这个方"})
    assert miss["ok"] is True and miss["hit"] is False and "未找到" in miss["hint"]

    _patch_neo4j(monkeypatch, raises=RuntimeError("Neo4j 未初始化"))
    err = graph.graph_neighbors.invoke({"entity": "麻黄汤"})
    assert err["ok"] is False and "RuntimeError" in err["hint"]


# ==================== semantic_recall ====================


def _invoke_recall(payload: dict) -> dict:
    """async 工具用 ainvoke 调用（与 Agent 循环里的调用方式一致）。"""
    return asyncio.run(recall.semantic_recall.ainvoke(payload))


def test_semantic_recall_clamps_top_k(monkeypatch) -> None:
    seen: dict = {}

    async def _fake_retrieve(question: str, top_k: int | None = None, ref_type: str | None = None):
        seen.update(question=question, top_k=top_k)
        return [make_unit(id="cu_14", ref_id="f_5", title="桂枝汤", score=0.6412)]

    monkeypatch.setattr(recall, "retrieve", _fake_retrieve)

    result = _invoke_recall({"query": "桂枝汤的组成", "top_k": 99})

    assert seen["top_k"] == recall.MAX_TOP_K
    assert result["hit"] is True
    item = result["items"][0]
    assert item["refId"] == "f_5"
    assert item["score"] == 0.6412
    assert item["snippet"]


def test_semantic_recall_empty_query_and_miss(monkeypatch) -> None:
    empty = _invoke_recall({"query": "   "})
    assert empty["ok"] is False and "不能为空" in empty["hint"]

    async def _fake_retrieve(*_args, **_kwargs):
        return []

    monkeypatch.setattr(recall, "retrieve", _fake_retrieve)
    miss = _invoke_recall({"query": "今天天气怎么样"})
    assert miss["ok"] is True and miss["hit"] is False
    assert "没有找到" in miss["hint"]
    assert miss["notice"] == ""


# ==================== 参数夹紧 ====================


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 5), ("abc", 5), ("7", 7), (0, 1), (-3, 1), (999, 10)],
)
def test_clamp_int(value, expected) -> None:
    """模型会传 None / 字符串 / 越界数字，统一夹紧而不是报错。"""
    assert clamp_int(value, default=5, minimum=1, maximum=10) == expected


# ==================== 集成层（连真实库，环境没起则跳过） ====================


def _skip_if_no_pg() -> None:
    reason = pg_ready()
    if reason:
        pytest.skip(reason)


def _skip_if_no_neo4j() -> None:
    reason = neo4j_ready()
    if reason:
        pytest.skip(reason)


def test_search_formula_real_pg_returns_known_composition() -> None:
    """库内事实：桂枝汤 = 桂枝/芍药/生姜/大枣/甘草（与 formula_diff 测试同一条钉子）。"""
    _skip_if_no_pg()

    result = catalog.search_formula.invoke({"name": "桂枝汤"})

    assert result["hit"] is True
    target = next(item for item in result["items"] if item["name"] == "桂枝汤")
    assert target["herbs"] == ["桂枝", "芍药", "生姜", "大枣", "甘草"]


def test_search_formula_real_pg_by_herb() -> None:
    """按药味查是**子串**匹配，所以每条命中必须至少有一味药名含「麻黄」。

    注意不能用 `"麻黄" in item["herbs"]`（精确成员判断）：库里存在 ETL 合并残留的药名，
    如 f_140 乌头汤里的「麻黄芍药黄芪」，它含麻黄但不是"一味叫麻黄的药"。
    """
    _skip_if_no_pg()

    result = catalog.search_formula.invoke({"herb": "麻黄"})

    assert result["hit"] is True
    assert all(any("麻黄" in herb for herb in item["herbs"]) for item in result["items"])


def test_search_formula_real_pg_keeps_dirty_herb_names() -> None:
    """脏药名必须**原样返回**，不许工具自己"清洗"掉。

    库内事实（`[实核 2026-10-28]`）：f_140 乌头汤的药味是「麻黄芍药黄芪」「甘草」「川乌」「以蜜」，
    前两条是 ETL 解析残留。数据归域1 修，工具这一层只负责如实呈现（红线二：不替人做判断）。
    """
    _skip_if_no_pg()

    result = catalog.search_formula.invoke({"name": "乌头汤", "herb": "麻黄"})

    assert result["hit"] is True
    herbs = {herb for item in result["items"] for herb in item["herbs"]}
    assert "麻黄芍药黄芪" in herbs


def test_search_case_real_pg_filters_stay_consistent() -> None:
    """命中时每条都必须真的含关键词；不命中也要给 hint（两种都是合法结果）。"""
    _skip_if_no_pg()

    result = catalog.search_case.invoke({"formula": "麻黄"})

    assert result["ok"] is True
    if result["hit"]:
        assert all("麻黄" in item["sourceFormula"] for item in result["items"])
    else:
        assert result["hint"]


def test_graph_neighbors_real_neo4j_one_hop_from_formula() -> None:
    """库内事实：麻黄汤与麻黄之间有 COMPOSED_OF，1 跳的邻居应当全是药味。"""
    _skip_if_no_neo4j()

    result = graph.graph_neighbors.invoke({"entity": "麻黄汤", "label": "方剂", "hops": 1})

    assert result["hit"] is True
    names = {item["name"] for item in result["items"]}
    assert "麻黄" in names
    assert all(item["label"] == "Herb" for item in result["items"])
