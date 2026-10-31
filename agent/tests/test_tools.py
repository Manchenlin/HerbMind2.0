"""一期 4 个 Agent 工具的断言测试。

分两层：

- **单元层**：`app.clients.*` 的调用全部替身，不发 HTTP、不连库，验证参数夹紧、
  请求参数拼装、`hit/ok/hint` 三态语义、`exact` 确定性校验、字段映射与去重；
- **集成层**：真打各 svc 的 `/internal`，断言的是**库内可核对的事实**
  （桂枝汤五味药、麻黄汤与麻黄相连）。svc 没起时按 `helpers.svc_*_ready()` 跳过而不是红一片。

⚠️ 2026-10-31 迁移后工具**不再直连 PG/Neo4j**：原来 patch 的是 `catalog.get_pg_pool` /
`graph.get_neo4j_driver`，现在 patch 的是 `xxx.search_client` / `xxx.graph_client`。
如果只换实现不换测试，旧的 patch 会打在没人用的符号上，用例会"假通过"。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from helpers import svc_graph_ready, svc_search_ready

from app.clients import SvcError
from app.tools import ALL_TOOLS, tool_names
from app.tools import catalog, graph, recall
from app.tools.common import clamp_int


# ==================== 替身 ====================


class _FakeSearch:
    """替身：`app.clients.search` 的两个函数（svc-search 客户端）。"""

    def __init__(self, payload: dict | None = None, raises: Exception | None = None) -> None:
        self.payload = payload or {}
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    async def search(self, **kwargs: Any) -> dict:
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return self.payload

    async def recall(self, **kwargs: Any) -> dict:
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return self.payload


class _FakeGraph:
    """替身：`app.clients.graph` 的 neighbors（svc-graph 客户端）。"""

    def __init__(self, payload: dict | None = None, raises: Exception | None = None) -> None:
        self.payload = payload or {}
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    async def neighbors(self, **kwargs: Any) -> dict:
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return self.payload


def _hit(
    *,
    ref_type: str = "formula",
    ref_id: str = "f_1",
    title: str = "麻黄汤",
    snippet: str = "组成：麻黄、桂枝、杏仁、甘草",
    herbs: list[str] | None = None,
    score: float = 0.93,
) -> dict:
    """一条 SearchHitVO（字段与 svc-search 实际返回一致）。"""
    return {
        "id": f"cu_{ref_id}",
        "refType": ref_type,
        "refId": ref_id,
        "title": title,
        "snippet": snippet,
        "score": score,
        "page": "12",
        "bookId": "bk_1",
        "bookTitle": "伤寒论",
        "classic": None,
        "chapter": None,
        "section": None,
        "herbs": herbs if herbs is not None else ["麻黄", "桂枝", "杏仁", "甘草"],
        "matchedBy": ["fulltext", "fuzzy"],
        "meta": {},
    }


def _payload(hits: list[dict]) -> dict:
    return {
        "list": hits,
        "total": len(hits),
        "page": 1,
        "size": 8,
        "mode": "hybrid",
        "tookMs": 3,
        "facets": {},
    }


def _invoke(tool, payload: dict) -> dict:
    """async 工具统一用 ainvoke 调用（与 Agent 循环里的调用方式一致）。"""
    return asyncio.run(tool.ainvoke(payload))


def _patch_search(monkeypatch, module, fake: _FakeSearch) -> _FakeSearch:
    monkeypatch.setattr(module, "search_client", fake)
    return fake


# ==================== 工具清单 ====================


def test_only_four_tools_in_phase_one() -> None:
    """一期只挂 4 个工具：`syndrome`/`dosage_rule` 表都是 0 行，挂上去只会诱发编造。"""
    assert tool_names() == ["search_formula", "search_case", "semantic_recall", "graph_neighbors"]
    assert len(ALL_TOOLS) == 4
    for item in ALL_TOOLS:
        assert item.description, f"{item.name} 缺少描述：模型靠它选工具"


# ==================== search_formula ====================


def test_search_formula_needs_at_least_one_condition(monkeypatch) -> None:
    fake = _patch_search(monkeypatch, catalog, _FakeSearch())

    result = _invoke(catalog.search_formula, {})

    assert result["ok"] is False
    assert "至少提供" in result["hint"]
    assert fake.calls == [], "参数不全时不该发 HTTP 请求"


def test_search_formula_maps_hit_to_item(monkeypatch) -> None:
    _patch_search(monkeypatch, catalog, _FakeSearch(_payload([_hit()])))

    result = _invoke(catalog.search_formula, {"name": "麻黄汤"})

    assert result["ok"] is True and result["hit"] is True and result["count"] == 1
    item = result["items"][0]
    assert item["id"] == "f_1"                 # 用 refId（业务 ID），不是 content_unit.id
    assert item["title"] == "麻黄汤"
    assert item["herbs"] == ["麻黄", "桂枝", "杏仁", "甘草"]   # 按库内顺序，不打乱
    assert item["exact"] is True, "关键词「麻黄汤」出现在标题里，应判为确证"
    assert item["matchedTerms"] == ["麻黄汤"]
    assert item["matchedBy"] == ["fulltext", "fuzzy"]        # 召回腿由服务端给
    assert result["notice"], "涉及方剂内容必须带免责声明"


def test_search_formula_uses_herb_as_q_when_only_herb(monkeypatch) -> None:
    """回归钉子：svc-search 在 q 为空时不跑任何召回腿，只给药味必须把药味当 q 传。

    否则会拿到空列表并被误判成「库内没有麻黄这味药」。
    """
    fake = _patch_search(monkeypatch, catalog, _FakeSearch(_payload([])))

    _invoke(catalog.search_formula, {"herb": "麻黄"})

    call = fake.calls[0]
    assert call["herb"] == "麻黄"
    assert call["q"] == "麻黄", "只给药味时 q 不能是空串"
    assert call["ref_type"] == "formula"


def test_search_formula_marks_semantic_only_hits_as_not_exact(monkeypatch) -> None:
    """语义相近但关键词没出现 → exact=false + hint 说明「不得当作确证」（红线二）。"""
    # 标题/摘录里都没有「太阳病」
    _patch_search(
        monkeypatch,
        catalog,
        _FakeSearch(_payload([_hit(snippet="组成：麻黄、桂枝、杏仁、甘草")])),
    )

    result = _invoke(catalog.search_formula, {"syndrome": "太阳病"})

    assert result["hit"] is True
    assert result["items"][0]["exact"] is False
    assert result["items"][0]["matchedTerms"] == []
    assert "exact=false" in result["hint"]
    assert "确证" in result["hint"]


def test_search_formula_miss_gives_actionable_hint(monkeypatch) -> None:
    _patch_search(monkeypatch, catalog, _FakeSearch(_payload([])))

    result = _invoke(catalog.search_formula, {"herb": "不存在的药"})

    assert result["ok"] is True and result["hit"] is False and result["count"] == 0
    assert "库内没有" in result["hint"]
    assert result["notice"] == ""


def test_search_formula_unreachable_returns_error_not_raise(monkeypatch) -> None:
    """工具不许抛：抛出去模型拿不到可读原因，只会换个说法再编一遍。"""
    _patch_search(monkeypatch, catalog, _FakeSearch(raises=SvcError(0, "检索服务不可达", "search")))

    result = _invoke(catalog.search_formula, {"name": "桂枝汤"})

    assert result["ok"] is False
    assert "不可用" in result["hint"]
    assert "不要凭印象" in result["hint"]


def test_search_formula_business_error_is_not_reported_as_unreachable(monkeypatch) -> None:
    """4000（参数错）与「服务不可达」要给不同提示，否则用户会去重启服务。"""
    _patch_search(monkeypatch, catalog, _FakeSearch(raises=SvcError(400, "type 不合法", "search")))

    result = _invoke(catalog.search_formula, {"name": "桂枝汤"})

    assert result["ok"] is False
    assert "调整关键词" in result["hint"]


def test_search_formula_ignores_non_formula_hits(monkeypatch) -> None:
    """即使服务端多给了医案/条文，工具也只返回方剂（type 过滤兜底）。"""
    _patch_search(
        monkeypatch,
        catalog,
        _FakeSearch(_payload([_hit(), _hit(ref_type="case", ref_id="cs_3", title="伤寒论")])),
    )

    result = _invoke(catalog.search_formula, {"name": "麻黄汤"})

    assert result["count"] == 1
    assert result["items"][0]["title"] == "麻黄汤"


# ==================== search_case ====================


def test_search_case_needs_at_least_one_condition(monkeypatch) -> None:
    fake = _patch_search(monkeypatch, catalog, _FakeSearch())

    result = _invoke(catalog.search_case, {"diagnosis": "  "})

    assert result["ok"] is False
    assert "至少提供" in result["hint"]
    assert fake.calls == []


def test_search_case_maps_hit_to_item(monkeypatch) -> None:
    _patch_search(
        monkeypatch,
        catalog,
        _FakeSearch(
            _payload(
                [
                    _hit(
                        ref_type="case",
                        ref_id="cs_3",
                        title="小承气汤",
                        snippet="医案：小承气汤 阳明腑实，大便不通",
                        herbs=[],
                    )
                ]
            )
        ),
    )

    result = _invoke(catalog.search_case, {"formula": "小承气汤"})

    item = result["items"][0]
    assert item["id"] == "cs_3"
    assert item["title"] == "小承气汤"
    assert item["exact"] is True
    assert result["hit"] is True
    assert result["notice"]


def test_search_case_joins_all_conditions_into_q(monkeypatch) -> None:
    fake = _patch_search(monkeypatch, catalog, _FakeSearch(_payload([])))

    _invoke(catalog.search_case, {"diagnosis": "阳明腑实", "formula": "小承气汤"})

    assert fake.calls[0]["q"] == "阳明腑实 小承气汤"
    assert fake.calls[0]["ref_type"] == "case"


# ==================== graph_neighbors ====================


def _neighbors_payload() -> dict:
    return {
        "center": {"id": "f_1", "label": "Formula", "name": "麻黄汤", "props": {}},
        "nodes": [
            {"id": "h_麻黄", "label": "Herb", "name": "麻黄", "props": {}},
            {"id": "h_桂枝", "label": "Herb", "name": "桂枝", "props": {}},
            {"id": "h_x", "label": "Herb", "name": "", "props": {}},          # 无名节点，应跳过
        ],
        "edges": [
            {"source": "f_1", "target": "h_麻黄", "rel": "COMPOSED_OF", "props": {}},
            {"source": "f_1", "target": "h_桂枝", "rel": "COMPOSED_OF", "props": {}},
            {"source": "h_麻黄", "target": "h_桂枝", "rel": "COMPOSED_OF", "props": {}},  # 不含 center
        ],
        "truncated": False,
    }


def test_graph_rejects_unknown_label_locally(monkeypatch) -> None:
    """标签白名单在工具层：非法值不发 HTTP，也不把服务端的 4000 混成故障。"""
    fake = _FakeGraph(_neighbors_payload())
    monkeypatch.setattr(graph, "graph_client", fake)

    result = _invoke(graph.graph_neighbors, {"entity": "太阳病", "label": "Syndrome"})

    assert result["ok"] is False
    assert "不支持" in result["hint"]
    assert fake.calls == [], "非法标签不该发到 svc-graph"


def test_graph_maps_chinese_label_and_clamps_hops(monkeypatch) -> None:
    fake = _FakeGraph(_neighbors_payload())
    monkeypatch.setattr(graph, "graph_client", fake)

    result = _invoke(graph.graph_neighbors, {"entity": "麻黄汤", "label": "药味", "hops": 99})

    call = fake.calls[0]
    assert call["label"] == "Herb"                 # 中文别名映射成真实标签
    assert call["hops"] == graph.MAX_HOPS          # 跳数夹到上限 3
    assert call["limit"] == graph.MAX_NEIGHBORS
    assert call["entity"] == "麻黄汤"
    assert result["hit"] is True


def test_graph_derives_rel_types_from_center_edges_only(monkeypatch) -> None:
    """relTypes 只取「一端是 center」的边；其它边不能算成这个邻居的关系。"""
    monkeypatch.setattr(graph, "graph_client", _FakeGraph(_neighbors_payload()))

    result = _invoke(graph.graph_neighbors, {"entity": "麻黄汤"})

    # 无名节点被跳过，只剩两条
    assert result["count"] == 2
    names = {item["name"]: item for item in result["items"]}
    assert set(names) == {"麻黄", "桂枝"}
    assert names["麻黄"]["relTypes"] == ["COMPOSED_OF"]
    assert names["麻黄"]["label"] == "Herb"


def test_graph_not_found_is_hit_false_not_error(monkeypatch) -> None:
    """4040（实体不存在）是「查不到」，不是「服务坏了」——这是两者最容易被搞混的地方。"""
    monkeypatch.setattr(
        graph, "graph_client", _FakeGraph(raises=SvcError(404, "实体不存在：某不存在方", "graph"))
    )

    result = _invoke(graph.graph_neighbors, {"entity": "某不存在方"})

    assert result["ok"] is True and result["hit"] is False
    assert "未找到" in result["hint"]
    assert "不要凭印象" in result["hint"]


def test_graph_unreachable_is_error(monkeypatch) -> None:
    monkeypatch.setattr(graph, "graph_client", _FakeGraph(raises=SvcError(0, "图谱服务不可达", "graph")))

    result = _invoke(graph.graph_neighbors, {"entity": "麻黄汤"})

    assert result["ok"] is False
    assert "search_formula" in result["hint"], "图谱挂了要给出可用替代路径"


def test_graph_truncated_gives_hint(monkeypatch) -> None:
    payload = _neighbors_payload()
    payload["truncated"] = True
    monkeypatch.setattr(graph, "graph_client", _FakeGraph(payload))

    result = _invoke(graph.graph_neighbors, {"entity": "麻黄汤"})

    assert "截断" in result["hint"]


# ==================== semantic_recall ====================


def test_semantic_recall_clamps_top_k_and_maps_hit(monkeypatch) -> None:
    fake = _patch_search(
        monkeypatch,
        recall,
        _FakeSearch(_payload([_hit(ref_type="formula", ref_id="f_5", title="桂枝汤", score=0.64)])),
    )

    result = _invoke(recall.semantic_recall, {"query": "桂枝汤的组成", "top_k": 99})

    assert fake.calls[0]["size"] == recall.MAX_TOP_K
    assert fake.calls[0]["q"] == "桂枝汤的组成"
    assert result["hit"] is True
    item = result["items"][0]
    assert item["refId"] == "f_5"
    assert item["score"] == 0.64
    assert item["snippet"]
    assert item["refType"] == "formula"


def test_semantic_recall_drops_low_score_hits(monkeypatch) -> None:
    """阈值 0.5：低于它的命中要被丢掉，否则「无命中」语义就没了。"""
    _patch_search(
        monkeypatch,
        recall,
        _FakeSearch(_payload([_hit(score=0.31), _hit(ref_id="f_2", score=0.72)])),
    )

    result = _invoke(recall.semantic_recall, {"query": "无汗而喘"})

    assert result["count"] == 1
    assert result["items"][0]["refId"] == "f_2"


def test_semantic_recall_empty_query_and_miss(monkeypatch) -> None:
    empty = _invoke(recall.semantic_recall, {"query": "   "})
    assert empty["ok"] is False and "不能为空" in empty["hint"]

    _patch_search(monkeypatch, recall, _FakeSearch(_payload([])))
    miss = _invoke(recall.semantic_recall, {"query": "今天天气怎么样"})
    assert miss["ok"] is True and miss["hit"] is False
    assert "没有找到" in miss["hint"]
    assert miss["notice"] == ""


def test_semantic_recall_unreachable_is_error(monkeypatch) -> None:
    _patch_search(monkeypatch, recall, _FakeSearch(raises=SvcError(0, "检索服务不可达", "search")))

    result = _invoke(recall.semantic_recall, {"query": "无汗而喘"})

    assert result["ok"] is False
    assert "不可用" in result["hint"]


# ==================== 参数夹紧 ====================


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 5), ("abc", 5), ("7", 7), (0, 1), (-3, 1), (999, 10)],
)
def test_clamp_int(value, expected) -> None:
    """模型会传 None / 字符串 / 越界数字，统一夹紧而不是报错。"""
    assert clamp_int(value, default=5, minimum=1, maximum=10) == expected


# ==================== 集成层（真打各 svc 的 /internal，环境没起则跳过） ====================


def _skip_if_no_search() -> None:
    reason = svc_search_ready()
    if reason:
        pytest.skip(reason)


def _skip_if_no_graph() -> None:
    reason = svc_graph_ready()
    if reason:
        pytest.skip(reason)


def test_search_formula_real_svc_returns_known_composition() -> None:
    """库内事实：桂枝汤 = 桂枝/芍药/生姜/大枣/甘草（与 formula_diff 测试同一条钉子）。"""
    _skip_if_no_search()

    result = _invoke(catalog.search_formula, {"name": "桂枝汤"})

    assert result["hit"] is True
    target = next(item for item in result["items"] if item["title"] == "桂枝汤")
    assert target["herbs"] == ["桂枝", "芍药", "生姜", "大枣", "甘草"]
    assert target["exact"] is True


def test_search_formula_real_svc_by_herb_has_exact_hit() -> None:
    """按药味查：混合召回可能带回语义相近的条目，但至少要有一条关键词真命中。"""
    _skip_if_no_search()

    result = _invoke(catalog.search_formula, {"herb": "麻黄"})

    assert result["hit"] is True
    assert any(item["exact"] for item in result["items"]), "按药味查至少要有一条真命中"
    exact_item = next(item for item in result["items"] if item["exact"])
    assert any("麻黄" in herb for herb in exact_item["herbs"])


def test_search_case_real_svc_returns_something_or_hint() -> None:
    """命中时每条都要有标题与摘录；不命中也要给 hint（两种都是合法结果）。"""
    _skip_if_no_search()

    result = _invoke(catalog.search_case, {"formula": "麻黄"})

    assert result["ok"] is True
    if result["hit"]:
        assert all(item["title"] or item["snippet"] for item in result["items"])
    else:
        assert result["hint"]


def test_graph_neighbors_real_svc_one_hop_from_formula() -> None:
    """库内事实：麻黄汤与麻黄之间有 COMPOSED_OF，1 跳的邻居应当全是药味。"""
    _skip_if_no_graph()

    result = _invoke(graph.graph_neighbors, {"entity": "麻黄汤", "label": "方剂", "hops": 1})

    assert result["hit"] is True
    names = {item["name"] for item in result["items"]}
    assert "麻黄" in names
    assert all(item["label"] == "Herb" for item in result["items"])


# ==================== _decorate：未命中关键词必须全部进提示 ====================


def test_decorate_collects_unmatched_terms_across_items() -> None:
    """回归钉子：未命中词要**跨条目累加**，不能只保留最后一条的差集。

    旧写法 `unmatched = [...]` 是赋值覆盖：两条结果各自只命中一个词时，
    前一条的未命中词会被后一条整体覆盖，`hint` 漏词 → 模型把近似结果说成确证（红线二）。
    """
    items = [
        {"title": "麻黄汤", "herbs": ["麻黄"], "snippet": "无汗而喘"},
        {"title": "桂枝汤", "herbs": ["桂枝"], "snippet": "头痛发热"},
    ]

    decorated, unmatched = catalog._decorate(items, ["麻黄", "桂枝", "太阳病"])

    assert [item["exact"] for item in decorated] == [False, False]
    assert [item["matchedTerms"] for item in decorated] == [["麻黄"], ["桂枝"]]
    # 两个词各自只在一条里命中，都必须出现在提示里，且保持原关键词顺序
    assert unmatched == ["麻黄", "桂枝", "太阳病"]


def test_decorate_returns_empty_unmatched_when_all_terms_hit() -> None:
    """全部命中时不能产出提示：每轮都说"可能不精确"只会变成噪声。"""
    items = [{"title": "麻黄汤", "herbs": ["麻黄", "桂枝"], "snippet": ""}]

    decorated, unmatched = catalog._decorate(items, ["麻黄", "桂枝"])

    assert decorated[0]["exact"] is True
    assert unmatched == []
