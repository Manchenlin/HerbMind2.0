"""Agent 域纯函数单元测试（不连库、不调模型）。

覆盖两处「规则必须由代码算、不能让模型算」的地方（设计红线四）：

1. `app/tools/graph.py`：标签白名单与关系类型推导 —— 传错标签要在本地就拦住，
   推导不出关系时**返回空**而不是补一个 `COMPOSED_OF`；
2. `app/tools/score.py`：参考答案切条目、二字词口径、模型回填的逐字对齐 —— 这三步
   一旦放松（比如改成"包含即命中"），分数会虚高，等于承认"只答对一半也算对"。
"""

from __future__ import annotations

import pytest

from app.tools.graph import _rel_types, resolve_label
from app.tools.score import _bigrams, _match_items, _norm, _score_of, _segments


class TestResolveLabel:
    """标签白名单：只认 Formula / Herb 及其中文别名。"""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Formula", "Formula"),
            ("formula", "Formula"),
            ("  方剂  ", "Formula"),
            ("方", "Formula"),
            ("方子", "Formula"),
            ("Herb", "Herb"),
            ("herb", "Herb"),
            ("药", "Herb"),
            ("药味", "Herb"),
            ("中药", "Herb"),
            ("本草", "Herb"),
        ],
    )
    def test_known_aliases(self, raw: str, expected: str) -> None:
        assert resolve_label(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "Syndrome", "证候", "症状", "Book", "formulas"])
    def test_unknown_labels_return_none(self, raw: str) -> None:
        """未实体化的类型必须返回 None，让调用方报"不支持"，而不是透传给 svc。"""
        assert resolve_label(raw) is None

    def test_none_and_missing_are_treated_as_unknown(self) -> None:
        assert resolve_label(None) is None  # type: ignore[arg-type]


class TestRelTypes:
    """从边表里推邻居与中心的关系类型。"""

    CENTER = "f_1"

    def test_edge_touching_center_is_reported(self) -> None:
        edges = [{"source": "f_1", "target": "h_麻黄", "rel": "COMPOSED_OF"}]
        assert _rel_types(edges, "h_麻黄", self.CENTER) == ["COMPOSED_OF"]

    def test_direction_does_not_matter(self) -> None:
        """边写成 center→药 还是 药→center 都应认出来。"""
        assert _rel_types([{"source": "h_桂枝", "target": "f_1", "rel": "COMPOSED_OF"}], "h_桂枝", "f_1") == [
            "COMPOSED_OF"
        ]

    def test_edges_not_touching_center_are_ignored(self) -> None:
        """两个邻居之间的边不能算到中心头上。"""
        edges = [{"source": "h_麻黄", "target": "h_桂枝", "rel": "COMPOSED_OF"}]
        assert _rel_types(edges, "h_麻黄", self.CENTER) == []

    def test_missing_rel_yields_empty_not_a_guess(self) -> None:
        """图里没有关系就返回空列表，不编一个 COMPOSED_OF。"""
        assert _rel_types([{"source": "f_1", "target": "h_麻黄"}], "h_麻黄", self.CENTER) == []

    def test_duplicate_rels_are_deduped(self) -> None:
        edges = [
            {"source": "f_1", "target": "h_麻黄", "rel": "COMPOSED_OF"},
            {"source": "h_麻黄", "target": "f_1", "rel": "COMPOSED_OF"},
        ]
        assert _rel_types(edges, "h_麻黄", self.CENTER) == ["COMPOSED_OF"]

    def test_no_edges_returns_empty(self) -> None:
        assert _rel_types([], "h_麻黄", self.CENTER) == []


class TestSegments:
    """参考答案切条目：顿号/逗号/分号/句号都切，1 字碎屑丢掉。"""

    REF = "恶风寒、发热，头身疼痛；舌淡红，苔薄白。脉浮紧"

    def test_splits_on_chinese_punctuation(self) -> None:
        assert _segments(self.REF) == [
            "恶风寒",
            "发热",
            "头身疼痛",
            "舌淡红",
            "苔薄白",
            "脉浮紧",
        ]

    def test_single_char_fragment_is_dropped(self) -> None:
        """「脉」这种单字没有信息量，切出来会污染 miss 列表。"""
        assert _segments("恶风，脉，发热") == ["恶风", "发热"]

    def test_empty_input_returns_empty_list(self) -> None:
        assert _segments("") == []
        assert _segments("，，。；") == []

    def test_does_not_split_inside_a_segment(self) -> None:
        """不能把「脉浮缓」拆成「脉浮」+「脉缓」—— 这是改用代码切条目的全部理由。"""
        assert _segments("脉浮缓") == ["脉浮缓"]


class TestBigrams:
    def test_punctuation_and_spaces_are_stripped(self) -> None:
        assert _bigrams("恶风，发热。") == _bigrams("恶风发热")

    def test_produces_overlapping_pairs(self) -> None:
        assert _bigrams("恶风寒") == {"恶风", "风寒"}

    def test_single_char_has_no_bigram(self) -> None:
        assert _bigrams("脉") == set()
        assert _bigrams("") == set()


class TestMatchItems:
    """模型回填的命中清单必须逐字对齐候选条目（防幻觉）。"""

    ITEMS = ["恶风寒", "发热", "脉浮缓"]

    def test_exact_item_is_kept(self) -> None:
        assert _match_items(["恶风寒"], self.ITEMS) == ["恶风寒"]

    def test_item_with_stray_punctuation_is_aligned(self) -> None:
        assert _match_items(["脉 浮 缓。"], self.ITEMS) == ["脉浮缓"]

    def test_item_outside_candidates_is_dropped(self) -> None:
        """模型编出来的条目不能进 hit。"""
        assert _match_items(["怕冷", "恶风寒"], self.ITEMS) == ["恶风寒"]

    def test_duplicates_count_once_and_keep_order(self) -> None:
        assert _match_items(["发热", "恶风寒", "发热"], self.ITEMS) == ["发热", "恶风寒"]

    def test_partial_answer_is_not_promoted(self) -> None:
        """「脉浮」只是「脉浮缓」的一半，包含匹配会把它救回来 —— 这里必须丢弃。"""
        assert _match_items(["脉浮"], self.ITEMS) == []

    def test_blank_inputs_are_ignored(self) -> None:
        assert _match_items(["", "  "], self.ITEMS) == []
        assert _match_items([], self.ITEMS) == []


class TestNorm:
    def test_strips_punctuation_and_spaces(self) -> None:
        assert _norm(" 脉 浮 缓。") == "脉浮缓"

    def test_none_safe(self) -> None:
        assert _norm(None) == ""  # type: ignore[arg-type]


class TestScoreOf:
    @pytest.mark.parametrize(
        ("hit", "miss", "expected"),
        [
            ([], [], 0),  # 没有标准答案就不给分
            (["a"], [], 100),
            ([], ["a"], 0),
            (["a"], ["b"], 50),
            (["a", "b"], ["c"], 67),
        ],
    )
    def test_ratio_is_hit_over_total(self, hit: list[str], miss: list[str], expected: int) -> None:
        assert _score_of(hit, miss) == expected
