"""提示词拼装与引用抽取。

防幻觉的三条硬约束（写在 system 里，不是"建议"）：
1. 只能依据给定资料回答，不许用资料以外的知识
2. 资料不足必须明说"资料中没有"，禁止编造方名/药味/剂量/条文
3. 每个结论标 [n]，n 对应 citations 的序号，前端据此渲染引用卡

为什么这么严：中医问答里编造一味药、一个剂量，比答不上来危险得多。
"""

from __future__ import annotations

from app.rag.retriever import RetrievedUnit
from app.schemas import Citation

SYSTEM_PROMPT = """你是「本草心智」的中医知识助手，面向中医学习者，帮助他们理解方剂、医案与经典条文。

【回答铁律】
1. 只能依据【资料】中给出的内容回答，不得使用资料以外的知识，不得推测、不得脑补。
2. 资料不足以回答时，必须直接说"提供的资料中没有找到相关内容"，并说明缺少什么（例如缺少该方剂的组成、缺少某条原文）。禁止编造方名、药味、剂量、条文出处。
3. 每个结论后面用 [编号] 标注依据，编号对应【资料】里的序号，例如 [1][3]。没有依据的话不要写。
4. 引用原文时保持文言原貌，不要改写成白话；需要解释时另起一句用现代汉语说明。
5. 涉及用药时，末尾提示"具体用药请遵医嘱，本回答仅供学习参考"。
6. 输出用简洁的中文分段，不要使用 Markdown 标题层级，不要输出 JSON。
7. 如果决定回答"资料中没有找到相关内容"，就不要再标注任何 [编号]；编号只能用于支撑你实际说出的结论。
8. 【资料】共有 {n} 条，编号范围是 1~{n}，不得出现超出该范围的编号。"""


def build_materials(units: list[RetrievedUnit]) -> str:
    """把召回结果编号拼成【资料】块。"""
    blocks = []
    for idx, unit in enumerate(units, 1):
        head = f"[{idx}]（{unit.kind_label}：{unit.title or unit.id}）"
        blocks.append(f"{head}\n{unit.content.strip()}")
    return "\n\n".join(blocks)


def build_messages(question: str, units: list[RetrievedUnit]) -> list[dict]:
    """拼成 OpenAI 格式的 messages（将来换 Agent 调用也能直接复用）。"""
    user_content = f"【资料】\n{build_materials(units)}\n\n【问题】\n{question.strip()}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT.replace("{n}", str(len(units)))},
        {"role": "user", "content": user_content},
    ]


def extract_citations(units: list[RetrievedUnit]) -> list[Citation]:
    """把召回结果转成前端的引用卡数据。"""
    return [
        Citation(
            id=unit.id,
            ref_type=unit.ref_type,
            ref_id=unit.ref_id,
            title=unit.title,
            snippet=unit.snippet(),
            score=round(unit.score, 4),
        )
        for unit in units
    ]


def degraded_answer(units: list[RetrievedUnit]) -> str:
    """大模型不可用时的降级内容：不瞎编，直接把检索到的资料摘要摆出来。"""
    lines = ["大模型服务暂时不可用，先给你检索到的相关资料（未经整理）：", ""]
    for idx, unit in enumerate(units, 1):
        lines.append(f"[{idx}] {unit.kind_label}·{unit.title or unit.id}：{unit.snippet(120)}")
    lines.append("")
    lines.append("稍后重试可获得完整回答。")
    return "\n".join(lines)
