"""`syndrome_score`（证候比对评分）的断言测试。

分三层：
- **职责层**：参考答案条目由代码切分、遗漏由集合差推出、分数由代码算；
  模型只回一份"命中的条目"清单，且清单外的说法一律丢弃（防幻觉）；
- **降级层**：模型不可用、报错、或"判全错但字面有重合"时退回条目级字面比对，
  口径与语义路径一致（同为「参考答案条目被覆盖的比例」）；
- **外壳层**：工具返回 `ok/hit/count/items/hint/notice` 六字段。

⚠️ 本机 `.env` 里有真实 key，`get_settings().llm_configured` 为 True。
所以每个用例都必须替换 `score.get_chat_model`，否则会真联网、真烧额度。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.tools import score as score_mod
from app.tools.score import SyndromeScore, score_syndrome, syndrome_score

REF = "恶风，发热，汗出，头痛，脉浮缓"
ITEMS = ["恶风", "发热", "汗出", "头痛", "脉浮缓"]


# ==================== 替身 ====================


class _FakeSettings:
    def __init__(self, configured: bool = True) -> None:
        self.llm_configured = configured


class _FakeScorer:
    """替身：`with_structured_output()` 返回的 Runnable。"""

    def __init__(self, result: Any = None, raises: Exception | None = None) -> None:
        self.result = result
        self.raises = raises
        self.calls: list[Any] = []

    async def ainvoke(self, messages: Any) -> Any:
        self.calls.append(messages)
        if self.raises is not None:
            raise self.raises
        return self.result


class _FakeModel:
    """替身：ChatModel（只实现本工具用到的方法）。"""

    def __init__(self, scorer: _FakeScorer) -> None:
        self.scorer = scorer
        self.copies: list[dict[str, Any]] = []

    def model_copy(self, update: dict[str, Any] | None = None) -> "_FakeModel":
        self.copies.append(dict(update or {}))
        return self

    def with_structured_output(self, schema: Any, method: str | None = None) -> _FakeScorer:
        return self.scorer


def _patch(
    monkeypatch,
    *,
    matched: list[str] | None = None,
    raises: Exception | None = None,
    configured: bool = True,
) -> tuple[_FakeModel, _FakeScorer]:
    result = SyndromeScore(matched=matched or []) if raises is None else None
    scorer = _FakeScorer(result, raises)
    model = _FakeModel(scorer)
    monkeypatch.setattr(score_mod, "get_settings", lambda: _FakeSettings(configured))
    monkeypatch.setattr(score_mod, "get_chat_model", lambda: model)
    return model, scorer


def _score(user: str, ref: str = REF) -> dict:
    return asyncio.run(score_syndrome(user, ref))


# ==================== 入参校验 ====================


def test_empty_user_answer_refuses_to_score(monkeypatch) -> None:
    """学生没写东西不能给分，也不能触发模型调用。"""
    _, scorer = _patch(monkeypatch, matched=["恶风"])

    result = _score("   ")

    assert result["ok"] is False
    assert result["score"] == 0
    assert "作答为空" in result["hint"]
    assert scorer.calls == []


def test_empty_reference_refuses_to_score(monkeypatch) -> None:
    """没有参考答案就是没有标准，不给分。"""
    _, scorer = _patch(monkeypatch, matched=["恶风"])

    result = _score("恶风，发热", "")

    assert result["ok"] is False
    assert result["score"] == 0
    assert "参考答案为空" in result["hint"]
    assert scorer.calls == []


def test_reference_without_segments_refuses_to_score(monkeypatch) -> None:
    """参考答案切不出条目（只有标点/单字）时不能假装能评分。"""
    _, scorer = _patch(monkeypatch, matched=[])

    result = _score("恶风", "，。；")

    assert result["ok"] is False
    assert "无法切分" in result["hint"]
    assert scorer.calls == []


# ==================== 条目切分与组装（代码职责） ====================


def test_full_match_scores_100_without_extra(monkeypatch) -> None:
    """全部条目答到：100 分，且学生原话不会被当成多余项。"""
    _patch(monkeypatch, matched=list(ITEMS))

    result = _score("恶风，发热，汗出，头痛，脉浮缓")

    assert result["ok"] is True
    assert result["degraded"] is False
    assert result["hit"] == ITEMS
    assert result["miss"] == []
    assert result["score"] == 100
    assert result["extra"] == []


def test_miss_is_derived_by_set_difference(monkeypatch) -> None:
    """遗漏项不由模型给，由「候选条目 − 命中」推出，保证不会漏项。"""
    _patch(monkeypatch, matched=["恶风", "发热"])

    result = _score("恶风发热，脉浮紧，无汗而喘")

    assert result["hit"] == ["恶风", "发热"]
    assert result["miss"] == ["汗出", "头痛", "脉浮缓"]
    assert result["score"] == 40


def test_extra_lists_unrelated_student_segments(monkeypatch) -> None:
    """学生多说的、与任何命中条目都无关的片段才进 extra；不扣分。"""
    _patch(monkeypatch, matched=list(ITEMS))

    result = _score("恶风，发热，汗出，头痛，脉浮缓，太阳病")

    assert result["extra"] == ["太阳病"]
    assert result["score"] == 100


def test_empty_match_and_no_overlap_scores_zero(monkeypatch) -> None:
    """模型判全错且字面也确实无重合 → 0 分，不降级。"""
    _patch(monkeypatch, matched=[])

    result = _score("脉浮紧，无汗而喘", "恶风，发热，汗出")

    assert result["score"] == 0
    assert result["degraded"] is False
    assert result["miss"] == ["恶风", "发热", "汗出"]


# ==================== 防幻觉 ====================


def test_item_outside_candidate_list_is_dropped(monkeypatch) -> None:
    """模型回了候选清单外的说法（如把「脉浮缓」写成「脉浮」）一律丢弃。

    宁可少算一条命中（保守扣分），也不能让碎片混进 hit 把分数抬高。
    """
    _patch(monkeypatch, matched=["脉浮"])

    result = _score("脉浮紧，无汗而喘", "恶风，发热，汗出")

    assert result["hit"] == []
    assert result["score"] == 0
    assert result["degraded"] is False


def test_item_with_stray_punctuation_is_aligned(monkeypatch) -> None:
    """模型抄条目时多了标点/空格，去标点后逐字相等仍可对齐。"""
    _patch(monkeypatch, matched=["恶风，", " 发热 "])

    result = _score("恶风发热，汗出")

    assert result["hit"] == ["恶风", "发热"]
    assert result["score"] == 40


def test_duplicate_matched_entries_count_once(monkeypatch) -> None:
    _patch(monkeypatch, matched=["恶风", "恶风", "发热"])

    result = _score("恶风发热")

    assert result["hit"] == ["恶风", "发热"]
    assert result["score"] == 40


# ==================== 模型调用约定 ====================


def test_scoring_runs_at_temperature_zero(monkeypatch) -> None:
    """评分类调用必须 temperature=0（08 文档 §12）。"""
    model, _ = _patch(monkeypatch, matched=["恶风"])

    _score("恶风")

    assert model.copies and model.copies[0].get("temperature") == 0.0


def test_prompt_carries_numbered_items_and_student_text(monkeypatch) -> None:
    """条目必须编号下发，学生原文原样进提示词。"""
    _, scorer = _patch(monkeypatch, matched=["恶风"])

    _score("我辨为恶风", "恶风，发热")

    joined = str(scorer.calls[0])
    assert "1. 恶风" in joined
    assert "2. 发热" in joined
    assert "我辨为恶风" in joined


# ==================== 降级 ====================


def test_llm_failure_falls_back_to_literal_compare(monkeypatch) -> None:
    """模型超时/报错时退回字面比对，并在 hint 里说清口径。"""
    _patch(monkeypatch, raises=TimeoutError("超时"))

    result = _score("怕风，发热，出汗")

    assert result["ok"] is True
    assert result["degraded"] is True
    assert "语义比对失败" in result["hint"]
    # 字面口径只认得出「发热」，近义的「怕风/出汗」不算命中
    assert result["hit"] == ["发热"]
    assert result["score"] == 20


def test_missing_key_falls_back_without_calling_model(monkeypatch) -> None:
    """没配 key 时不报错、不联网，直接字面比对。"""
    model, scorer = _patch(monkeypatch, configured=False)

    result = _score("恶风，发热")

    assert result["degraded"] is True
    assert result["score"] == 40
    assert scorer.calls == []
    assert model.copies == []


def test_contradiction_between_model_and_literal_falls_back(monkeypatch) -> None:
    """模型说一条都没答到，但字面明明有重合 → 判定模型失效，降级而不是给 0 分。"""
    _patch(monkeypatch, matched=[])

    result = _score("恶风，发热")

    assert result["degraded"] is True
    assert "矛盾" in result["hint"]
    assert result["score"] > 0


def test_literal_fallback_splits_by_punctuation(monkeypatch) -> None:
    """条目按顿号/逗号/分号切分，单个「脉」字这类碎屑不参与计分。"""
    _patch(monkeypatch, configured=False)

    result = _score("舌淡红，苔薄白；脉浮紧", "舌淡红，苔薄白；脉浮紧")

    assert result["degraded"] is True
    assert result["score"] == 100
    assert result["miss"] == []


# ==================== 工具外壳 ====================


def test_tool_envelope_shape(monkeypatch) -> None:
    """工具的返回值必须符合 `ok/hit/count/items/hint/notice` 六字段约定。"""
    _patch(monkeypatch, matched=["恶风", "发热"])

    result = asyncio.run(
        syndrome_score.ainvoke({"user_syndrome": "恶风发热", "ref_syndrome": REF})
    )

    assert result["ok"] is True
    assert result["hit"] is True
    assert result["count"] == 1
    item = result["items"][0]
    assert item["score"] == 40
    assert item["degraded"] is False
    assert "学习参考" in result["notice"]
    assert "不扣分" in result["hint"]


def test_tool_returns_error_envelope_on_empty_input(monkeypatch) -> None:
    """入参非法走 ok=False（工具失败），不是 hit=false（库内没有）。"""
    _patch(monkeypatch, matched=[])

    result = asyncio.run(syndrome_score.ainvoke({"user_syndrome": "", "ref_syndrome": REF}))

    assert result["ok"] is False
    assert result["hit"] is False
    assert result["hint"]


def test_tool_is_registered_with_description() -> None:
    """模型靠描述选工具，描述不能空，且要写明何时不用它。"""
    assert syndrome_score.name == "syndrome_score"
    assert syndrome_score.description
    assert "参考答案" in syndrome_score.description
    assert "不要用" in syndrome_score.description


@pytest.mark.parametrize(
    ("hit", "miss", "expected"),
    [
        (["a"], [], 100),
        ([], ["a"], 0),
        (["a"], ["b"], 50),
        (["a", "b"], ["c"], 67),
        ([], [], 0),
    ],
)
def test_score_ratio(hit: list[str], miss: list[str], expected: int) -> None:
    """覆盖率口径单测：|hit| / (|hit| + |miss|)，两边都空时按 0 分。"""
    assert score_mod._score_of(hit, miss) == expected
