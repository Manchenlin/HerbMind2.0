"""`database/etl/docx_reader.py` 的单元测试。

这本书是从 PDF/扫描件转来的 docx：每页页眉重复书名与章标题、页码单独成段。
不先 wash 掉，8710 个块里会混进上千条伪段落，后面 case_record 的正文直接脏。

判断标准（实测）：`中医经典方证案例研究`（页眉书名）与纯页码每页都出现，属噪音；
章标题**首次**出现是正文结构，必须保留给 outline 解析，只在重复出现时剔除。
"""

from __future__ import annotations

from docx_reader import clean_blocks, is_noise


class TestIsNoise:
    def test_page_number_is_noise(self) -> None:
        assert is_noise("128") is True
        assert is_noise("  45  ") is True

    def test_running_header_book_title_is_noise(self) -> None:
        assert is_noise("中医经典方证案例研究") is True

    def test_chapter_heading_is_kept(self) -> None:
        """章标题首次出现是结构信息，不能当噪音丢掉。"""
        assert is_noise("第一章  经典·证治·案例") is False
        assert is_noise("第二章《伤寒论》方证案例研究") is False

    def test_body_paragraph_is_kept(self) -> None:
        assert is_noise("现病史：全身皮肤无汗出23年。") is False

    def test_marker_paragraph_is_kept(self) -> None:
        assert is_noise("【问题】") is False


class TestCleanBlocks:
    def test_second_occurrence_of_heading_is_dropped(self) -> None:
        """页眉会把同一个章标题重复上千次，只留第一次。"""
        raw = ["第二章《伤寒论》方证案例研究", "第二章《伤寒论》方证案例研究", "【问题】"]
        assert clean_blocks(raw) == ["第二章《伤寒论》方证案例研究", "【问题】"]

    def test_noise_lines_are_dropped(self) -> None:
        raw = ["中医经典方证案例研究", "现病史：无汗。", "128"]
        assert clean_blocks(raw) == ["现病史：无汗。"]

    def test_repeated_body_text_is_not_deduped(self) -> None:
        """正文里重复出现的短句不是页眉，不能被当成重复标题删掉。"""
        raw = ["脉浮紧。", "脉浮紧。"]
        assert clean_blocks(raw) == ["脉浮紧。", "脉浮紧。"]

    def test_empty_text_is_dropped(self) -> None:
        assert clean_blocks(["", "  ", "正文"]) == ["正文"]
