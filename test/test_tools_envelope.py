"""`agent/app/tools/common.py` 工具返回值外壳的单元测试。

为什么要单独测这层：六个字段（`ok/hit/count/items/hint/notice`）是**模型读得懂的唯一约定**，
`ok=False`（没查成）与 `hit=False`（查了没有）语义完全不同（09 契约 §13.3）。
写错一个字段，模型就会把"服务挂了"说成"库里没有"，或反之。
"""

from __future__ import annotations

from app.tools.common import NOTICE_FACT, error_result, miss_result, ok_result

FIELDS = {"ok", "hit", "count", "items", "hint", "notice"}


class TestEnvelopeShape:
    """三种出口的字段集合与取值必须稳定。"""

    def test_all_results_share_exactly_six_fields(self) -> None:
        for payload in (
            ok_result([{"id": "f_1"}]),
            miss_result("库里没有"),
            error_result("服务不可用"),
        ):
            assert set(payload) == FIELDS

    def test_ok_result_counts_items_and_marks_hit(self) -> None:
        payload = ok_result([{"id": "f_1"}, {"id": "f_2"}])
        assert payload["ok"] is True
        assert payload["hit"] is True
        assert payload["count"] == 2
        assert len(payload["items"]) == 2

    def test_ok_result_with_no_items_is_not_a_hit(self) -> None:
        """有 ok 不等于有命中：空列表必须 hit=False，且不该挂免责声明。"""
        payload = ok_result([])
        assert payload["ok"] is True
        assert payload["hit"] is False
        assert payload["count"] == 0
        assert payload["notice"] == ""

    def test_fact_notice_is_attached_whenever_items_exist(self) -> None:
        """返回了方剂/用药内容就必须带免责声明（设计红线三）。"""
        assert ok_result([{"id": "f_1"}])["notice"] == NOTICE_FACT

    def test_miss_result_is_success_but_empty(self) -> None:
        payload = miss_result("图谱里没有「不存在的方」，请换名称再查")
        assert payload["ok"] is True
        assert payload["hit"] is False
        assert payload["count"] == 0
        assert "不存在的方" in payload["hint"]

    def test_error_result_is_not_ok_and_carries_reason(self) -> None:
        payload = error_result("图谱服务不可用")
        assert payload["ok"] is False
        assert payload["hit"] is False
        assert payload["items"] == []
        assert payload["hint"] == "图谱服务不可用"

    def test_hint_survives_on_ok_result(self) -> None:
        """ok 结果里的 hint 是给模型的附加提醒（如 truncated），不能被丢掉。"""
        payload = ok_result([{"id": "f_1"}], hint="仅显示前 50 个邻居")
        assert payload["hint"] == "仅显示前 50 个邻居"
