"""提示词拼装与引用抽取。

防幻觉的三条硬约束（写在 system 里，不是"建议"）：
1. 只能依据给定资料回答，不许用资料以外的知识
2. 资料不足必须明说"资料中没有"，禁止编造方名/药味/剂量/条文
3. 每个结论标 [n]，n 对应 citations 的序号，前端据此渲染引用卡

为什么这么严：中医问答里编造一味药、一个剂量，比答不上来危险得多。
"""

from __future__ import annotations

from app.config import get_settings
from app.rag.retriever import RetrievedUnit
from app.schemas import Citation

SYSTEM_PROMPT = """你是「本草心智」的中医知识助手，面向中医学习者，帮助他们理解方剂、医案与经典条文。

【回答铁律】
1. 只能依据【资料】中给出的内容回答，不得使用资料以外的知识，不得推测、不得脑补。
2. 只有当资料确实不足以回答时，才用一句话说明资料不足并指出缺什么（例如缺少该方剂组成）。此时**不要**标注任何 [编号]。资料充足时，不要出现"资料中没有找到"之类的话。
3. 每个结论后面用 [编号] 标注依据，编号对应【资料】里的序号，例如 [1][3]。没有依据的话不要写。
4. 引用原文时保持文言原貌，不要改写成白话；需要解释时另起一句用现代汉语说明。
5. 涉及用药时，末尾提示"具体用药请遵医嘱，本回答仅供学习参考"。
6. 输出用简洁的中文分段，不要使用 Markdown 标题层级，不要输出 JSON。
7. 【资料】共有 {n} 条，编号范围是 1~{n}，不得出现超出该范围的编号。
8. 直接输出回答正文。不要复述以上规则，不要在结尾重复输出模板句，不要输出【资料】原文块。"""

# 工具开启时才拼进 system（`AGENT_TOOLS_ENABLED=false` 时不出现，避免模型"想去调一个不存在的工具"）。
# 为什么必须有这一段：实测（2026-10-31，Qwen2.5-7B）不给工具指引时模型只会照【资料】作答、
# 一次工具都不调（`run_tool_loop` 的 used 恒为 False），等于工具白接。
# 给了指引后模型能正确产出 `tool_calls`（如 `search_formula(herb="麻黄")`）。
TOOL_NOTE = """

【工具使用（对铁律 1 的补充，硬性）】
铁律 1 里的「资料」**也包括你通过工具取回的库内结果**。凡是需要列举/统计/核对库内**完整清单**的问题，
直接凭【资料】里的三五条片段作答即视为违反铁律 1（因为那样必然不完整）；**必须先调用工具**取回结果再回答：
- 「哪些方剂含有某味药」「含某药的方有哪些」→ 用 search_formula(herb=...)
- 「某方由哪些药组成」而【资料】没给全 → 用 search_formula(name=...)
- 「某病证有哪些医案」「有没有用过某方」→ 用 search_case(...)
- 「某药用在哪些方」「两方共有/不同的药味」→ 用 graph_neighbors(...)
- 「换个说法找相近记载」「没查到关键词时」→ 用 semantic_recall(...)

其余问题（解释条文含义、归纳某方的证治要点）直接用【资料】回答即可，不必调工具。

- 工具返回 `exact=false` 只表示「语义相近」，不得表述为「库内确有记载」。
- 工具返回 `ok=false` 表示那次查询失败：如实说明这部分没有查到，不得用印象补全。
- 工具结果同样是库内事实，但**不要给它编号**；正文角标仍只标【资料】的 1~{n}。
"""


def build_materials(units: list[RetrievedUnit]) -> str:
    """把召回结果编号拼成【资料】块。"""
    blocks = []
    for idx, unit in enumerate(units, 1):
        head = f"[{idx}]（{unit.kind_label}：{unit.title or unit.id}）"
        blocks.append(f"{head}\n{unit.content.strip()}")
    return "\n\n".join(blocks)


HISTORY_NOTE = """

【历史对话使用规则】
下方【历史对话】是本会话之前几轮的内容，只用来理解上下文（比如"它的组成"里的"它"指谁）。
它不是【资料】，不得作为回答依据，也不得引用其中的 [编号]；与【资料】冲突时以【资料】为准。
"""


def build_messages(
    question: str,
    units: list[RetrievedUnit],
    history: list[dict[str, str]] | None = None,
) -> list[dict]:
    """拼成 OpenAI 格式的 messages。

    Args:
        history: 多轮记忆，形如 `[{"role":"user","content":"..."}, ...]`（时间正序）。
            只取 user/assistant 两类，由 `repo.conversation.recent_messages` 保证。

    为什么历史单独成段而不是拼进【资料】：历史里的回答是上一轮的模型输出，
    把它当"资料"引用等于让模型引用自己（红线二：只能依据库内原文）。
    """
    user_content = f"【资料】\n{build_materials(units)}\n\n【问题】\n{question.strip()}"
    system = SYSTEM_PROMPT.replace("{n}", str(len(units)))
    # 工具开启时才告诉模型"可以调工具"；关掉开关后提示词回到改造前的样子
    if get_settings().agent_tools_enabled:
        system += TOOL_NOTE.replace("{n}", str(len(units)))

    valid_history = [
        item
        for item in (history or [])
        if item.get("role") in ("user", "assistant") and (item.get("content") or "").strip()
    ]
    if valid_history:
        system += HISTORY_NOTE

    messages: list[dict] = [{"role": "system", "content": system}]
    if valid_history:
        messages.extend(
            {"role": item["role"], "content": str(item["content"]).strip()} for item in valid_history
        )
    messages.append({"role": "user", "content": user_content})
    return messages


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
