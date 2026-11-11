"""`database/etl/case_parser.py` 的单元测试。

切单元这件事最初按 `【问题】` 做锚点，实测推翻了：全书 228 个 `【问题】` 块分布在
**175 个小节**（`一、太阳伤寒类方证`）里，一个小节常含例一/例二/例三多份医案，
以及一组问题 + 讨论。所以单元 = 小节，而不是「一个问题块」。

三个最容易写错的地方：

1. **单元边界**：按小节标题 `一、` 切；小节标题在正文里会重复出现（排版重复），
   重复的那次不能算新单元，否则同一小节被切成两半。
2. **标签切分**：`【X】` 是固定标记，标记前段落按首词归类（现病史/查体/治法…）。
3. **合并剂量**：「麻黄、桂枝各 18g」是两味药各 18g，按逗号硬切会多出一味假药。
"""

from __future__ import annotations

from case_parser import guess_title, parse_herbs, split_sections, split_units


class TestSplitUnits:
    BLOCKS = [
        "一、太阳伤寒类方证",
        "现病史：无汗23年。",
        "治法：方拟麻黄汤加味治之。",
        "【问题】",
        "1.为什么？",
        "【问题解答】",
        "答：因为风寒束表。",
        "二、太阳中风类方证",
        "现病史：头痛三日。",
        "治法：方拟桂枝汤。",
        "【问题】",
        "1.为何？",
        "【问题解答】",
        "答：营卫不和。",
    ]

    def test_units_start_at_subsection_heading(self) -> None:
        units = split_units(self.BLOCKS)
        assert len(units) == 2
        assert units[0]["blocks"][0] == "一、太阳伤寒类方证"
        assert units[1]["blocks"][0] == "二、太阳中风类方证"

    def test_each_unit_keeps_its_own_case(self) -> None:
        units = split_units(self.BLOCKS)
        assert "桂枝汤" not in "".join(units[0]["blocks"])
        assert "麻黄汤" not in "".join(units[1]["blocks"])

    def test_blocks_cover_everything_once(self) -> None:
        units = split_units(self.BLOCKS)
        assert [b for u in units for b in u["blocks"]] == self.BLOCKS

    def test_duplicate_subsection_heading_does_not_split(self) -> None:
        """小节标题在正文里重复出现（排版重复），不能切成两个单元。"""
        blocks = ["一、太阳伤寒类方证", "正文正文正文。", "一、太阳伤寒类方证", "【问题】"]
        assert len(split_units(blocks)) == 1

    def test_no_subsection_heading_returns_single_unit(self) -> None:
        assert len(split_units(["现病史：无汗。", "【问题】"])) == 1

    def test_empty_input_returns_empty(self) -> None:
        assert split_units([]) == []


class TestGuessTitle:
    def test_formula_name_is_taken_from_treatment(self) -> None:
        blocks = ["一、太阳伤寒类方证", "现病史：无汗23年。", "治法：方拟麻黄汤加味治之。", "【问题】"]
        assert guess_title(blocks, 1) == "麻黄汤"

    def test_falls_back_to_case_number(self) -> None:
        assert guess_title(["现病史：无汗。", "【问题】"], 7) == "案例 7"


class TestSplitSections:
    def test_sections_split_by_marker_and_lead_word(self) -> None:
        unit = ["现病史：无汗。", "治法：方拟麻黄汤。", "【问题】", "1.为何？", "【论述】", "因为……"]
        secs = split_sections(unit)
        assert [s["kind"] for s in secs] == ["现病史", "治法", "问题", "论述"]

    def test_section_content_keeps_body_text(self) -> None:
        secs = split_sections(["现病史：无汗。", "辗转求治无效。"])
        assert secs[0]["content"] == "现病史：无汗。\n辗转求治无效。"

    def test_multiple_questions_stay_separate_sections(self) -> None:
        secs = split_sections(["【问题】", "1.甲？", "【问题解答】", "答甲。", "【问题】", "1.乙？"])
        assert [s["kind"] for s in secs] == ["问题", "问题解答", "问题"]

    def test_empty_unit_returns_empty(self) -> None:
        assert split_sections([]) == []


class TestParseHerbs:
    def test_combined_dose_is_not_split_into_extra_herb(self) -> None:
        herbs = parse_herbs("麻黄、桂枝各 18g，杏仁10g，甘草4g")
        assert herbs == [
            {"name": "麻黄", "dose": "18", "unit": "g"},
            {"name": "桂枝", "dose": "18", "unit": "g"},
            {"name": "杏仁", "dose": "10", "unit": "g"},
            {"name": "甘草", "dose": "4", "unit": "g"},
        ]

    def test_dose_is_kept_as_string(self) -> None:
        """剂量转成字符串，避免浮点误差（契约 §15 明确剂量是字符串）。"""
        assert parse_herbs("白术4.5g")[0]["dose"] == "4.5"

    def test_unit_ke_is_normalized_to_g(self) -> None:
        assert parse_herbs("甘草4克")[0]["unit"] == "g"

    def test_text_without_dose_returns_empty(self) -> None:
        assert parse_herbs("麻黄汤主之。") == []

    def test_duplicate_herb_keeps_first(self) -> None:
        herbs = parse_herbs("麻黄10g，麻黄6g")
        assert len(herbs) == 1
        assert herbs[0]["dose"] == "10"
