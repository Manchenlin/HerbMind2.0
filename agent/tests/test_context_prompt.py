"""提示词与引用抽取的断言测试（`app/rag/context.py`）。

这一册测的不是"代码逻辑"，而是**设计红线有没有真的写进提示词**（`CODEBUDDY.md` §五）：
不许用资料以外的知识、查不到就说查不到、不许编编号、涉及用药必须带"仅供学习参考"。
红线是项目最高优先级的约束，没有断言就等于没落实——改提示词时最容易悄悄丢一条。

零外部依赖：纯函数。
"""

from __future__ import annotations

from helpers import make_unit

from app.rag import context


# ==================== 红线：提示词必须含的硬约束 ====================


def test_system_prompt_keeps_red_line_constraints() -> None:
    """八条铁律里的关键约束逐条断言（删掉任何一条都算回归）。"""
    prompt = context.SYSTEM_PROMPT

    assert "不得使用资料以外的知识" in prompt          # 红线：只查证、不推断
    # "不要" 在提示词里出现十几次，用它当条件等于没断言 → 改成钉住具体句式
    assert "只有当资料确实不足以回答时" in prompt        # 红线：查不到才说查不到
    assert "资料中没有找到" in prompt                    # 红线的具体话术
    assert "不得出现超出该范围的编号" in prompt         # 防编造引用编号
    assert "仅供学习参考" in prompt                    # 免责声明
    assert "不要输出 JSON" in prompt                   # 出参格式稳定


def test_prompt_number_is_injected_and_has_no_placeholder_left() -> None:
    """`{n}` 必须被替换成真实资料条数，不能把占位符漏给模型。"""
    units = [make_unit(id="cu_1"), make_unit(id="cu_2")]

    messages = context.build_messages("麻黄汤的组成", units)
    system = messages[0]["content"]

    assert "{n}" not in system
    assert "共有 2 条" in system
    assert "1~2" in system


# ==================== 资料拼装 ====================


def test_build_materials_numbers_units_and_labels_type() -> None:
    """资料块按 1..n 编号，并标出「方剂 / 医案」，模型才知道自己在引什么。"""
    units = [
        make_unit(id="cu_1", ref_type="formula", title="麻黄汤", content="  组成：麻黄  "),
        make_unit(id="cu_2", ref_type="case", title="伤寒论", content="医案：小承气汤"),
    ]

    text = context.build_materials(units)

    assert text.startswith("[1]（方剂：麻黄汤）")
    assert "[2]（医案：伤寒论）" in text
    assert "组成：麻黄" in text and text.splitlines()[1] == "组成：麻黄"  # 首尾空白被去掉


def test_build_messages_shape() -> None:
    """messages 必须是 OpenAI 口径：system 在前、user 含【资料】与【问题】。"""
    messages = context.build_messages("  麻黄汤由哪些药组成  ", [make_unit()])

    assert [m["role"] for m in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert user.startswith("【资料】")
    assert "【问题】\n麻黄汤由哪些药组成" in user  # 问题去首尾空白


# ==================== 引用卡 ====================


def test_extract_citations_shapes() -> None:
    """引用卡：score 保留 4 位、snippet 去换行并截断、字段齐全。"""
    unit = make_unit(id="cu_14", ref_id="f_5", title="桂枝汤", content="药" * 300, score=0.6412345)

    citations = context.extract_citations([unit])

    assert len(citations) == 1
    card = citations[0]
    assert card.id == "cu_14"
    assert card.ref_id == "f_5"
    assert card.score == 0.6412
    assert card.snippet.endswith("…")
    assert len(card.snippet) == 161


def test_extract_citations_keeps_input_order() -> None:
    """引用编号必须与资料顺序一致：正文里的 [2] 就是第二条资料。"""
    units = [
        make_unit(id="cu_1", title="麻黄汤", score=0.9),
        make_unit(id="cu_2", title="桂枝汤", score=0.8),
    ]

    citations = context.extract_citations(units)

    assert [c.id for c in citations] == ["cu_1", "cu_2"]


# ==================== 降级文案 ====================


def test_degraded_answer_lists_materials_and_no_invented_content() -> None:
    """模型不可用时的降级文案：只摆检索到的资料摘要，不编造任何结论。"""
    units = [make_unit(id="cu_1", title="麻黄汤", content="组成：麻黄、桂枝、杏仁、甘草")]

    text = context.degraded_answer(units)

    assert "大模型服务暂时不可用" in text
    assert "[1] 方剂·麻黄汤：" in text
    assert "稍后重试" in text
    assert "功效" not in text and "主治" not in text  # 不替用户推断
