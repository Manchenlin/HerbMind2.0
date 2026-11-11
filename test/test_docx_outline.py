"""`database/etl/docx_outline.py` 的单元测试。

两件事：
1. 纠正 OCR 错字 —— 同一章标题在书里有 `方证案例研究 / 万证杂例研究 / 徬寒论` 三种写法，
   还混进了批注 `…研究消失。`。不纠正就直接写进 `book_node.title`，前端目录树露错。
2. 解析章/节骨架并给出每节的起始块下标，供后面把案例单元挂到正确的节下。
"""

from __future__ import annotations

from docx_outline import fix_ocr, parse_outline


class TestFixOcr:
    def test_misspelled_classic_name(self) -> None:
        assert fix_ocr("第二章《徬寒论》方证案例研究") == "第二章《伤寒论》方证案例研究"

    def test_misspelled_heading_word(self) -> None:
        assert fix_ocr("第二章《伤寒论》万证杂例研究") == "第二章《伤寒论》方证案例研究"

    def test_editor_note_is_removed(self) -> None:
        assert fix_ocr("第四章《金匮要略》方证案例研究消失。") == "第四章《金匮要略》方证案例研究"

    def test_normal_text_is_untouched(self) -> None:
        assert fix_ocr("第一节   太阳病方证案例") == "第一节   太阳病方证案例"


class TestParseOutline:
    def test_table_of_contents_block_is_skipped(self) -> None:
        """目录页会把整章标题压进一个长段落，不能被当成章起点。"""
        toc = "目     录第一章    经典·证治·案例\t(\t(11))第二章《伤寒论》方证案例研究\t(\t(18))"
        blocks = [
            toc,
            "第一章  经典·证治·案例",
            "第一节   中医经典的作用",
            "第二章《伤寒论》方证案例研究",
            "第一节   太阳病方证案例",
        ]
        chapters = parse_outline(blocks)
        assert len(chapters) == 2
        assert chapters[0]["title"] == "第一章  经典·证治·案例"

    def test_chapter_maps_to_classic_book(self) -> None:
        blocks = [
            "第一章  经典·证治·案例",
            "第一节   中医经典的作用",
            "第二章《伤寒论》方证案例研究",
            "第一节   太阳病方证案例",
            "第三章《温病学》方证案例研究",
            "第一节   风温病证治",
        ]
        chapters = parse_outline(blocks)
        assert [c["book"] for c in chapters] == [None, "伤寒论", "温病学"]

    def test_section_start_index_points_into_blocks(self) -> None:
        blocks = [
            "第一章  经典·证治·案例",
            "第一节   中医经典的作用",
            "第二章《伤寒论》方证案例研究",
            "第一节   太阳病方证案例",
        ]
        chapters = parse_outline(blocks)
        assert chapters[1]["sections"][0]["start_index"] == 3

    def test_no_heading_returns_empty(self) -> None:
        assert parse_outline(["正文", "正文"]) == []

    def test_ocr_variant_chapters_are_merged(self) -> None:
        """错字章标题纠正后与正字版同名，必须合并成一章，节不能丢。"""
        blocks = [
            "第二章《伤寒论》方证案例研究",
            "第一节   太阳病方证案例",
            "第二章《徬寒论》方证案例研究",
            "第二节   阳明病方证案例",
        ]
        chapters = parse_outline(blocks)
        assert len(chapters) == 1
        assert [s["title"] for s in chapters[0]["sections"]] == ["太阳病方证案例", "阳明病方证案例"]

    def test_chapter_number_only_paragraph_merges(self) -> None:
        """书中「第一章」与「第一章  经典·证治·案例」是两个段落，属同一章。"""
        blocks = ["第一章  经典·证治·案例", "第一章", "第一节   中医经典的作用"]
        chapters = parse_outline(blocks)
        assert len(chapters) == 1
        assert len(chapters[0]["sections"]) == 1
