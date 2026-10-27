"""POST /api/agent/formula/diff —— 方剂加减**查证**。

⚠️ 受 `project_plan/00_README_总览.md`「设计红线一」约束：
本端点回答的是「库里有没有这个组成」，**不是**「这样加减有没有道理」。
响应里没有任何功效推断字段，`efficacy` / `syndromeText` / `classicText` 全部是语料原文摘录。

为什么单独开一个 router 而不是塞进 ask.py：
ask 是"问 → 检索 → 生成"，这里是"给定结构 → 集合运算 → 查表"，链路完全不同，
且这条链路**不碰大模型**（红线四），混在一起以后容易被人顺手加个 LLM 调用。
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException

from app.rag import formula_diff
from app.schemas import FormulaDiffData, FormulaDiffRequest, R

logger = logging.getLogger("herbmind-agent")

router = APIRouter(tags=["agent"])


@router.post(
    "/formula/diff",
    response_model=R[FormulaDiffData],
    summary="方剂加减查证（组成比对，不推断功效）",
)
async def formula_diff_endpoint(
    req: FormulaDiffRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> R[FormulaDiffData]:
    """给定基础方与加/减药味，查证库里是否有组成完全一致的成方。

    **不做的事**：不推断功效、不给加减建议、不生成新方（见设计红线一/三）。
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="缺少 X-User-Id：该端点只应经网关访问")

    logger.info(
        "加减查证：user=%s base=%s add=%d remove=%d",
        x_user_id,
        req.base_formula.strip()[:20],
        len(req.add),
        len(req.remove),
    )

    try:
        # 纯 SQL + 内存集合运算，同步阻塞，丢线程池避免卡事件循环
        data = await asyncio.to_thread(
            formula_diff.diff, req.base_formula, req.add, req.remove
        )
    except ValueError as exc:
        # 基础方找不到 / 重名无法确定 —— 属参数问题，400 比 500 更准确
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # PG 池未初始化等资源问题
        logger.exception("加减查证：资源不可用")
        raise HTTPException(status_code=503, detail=f"数据源暂不可用：{exc}") from exc

    logger.info(
        "加减查证完成：base=%s 结果 %d 味，命中 %d 个成方，近似 %d 个，告警 %d 条",
        data["base"]["name"],
        len(data["resultHerbs"]),
        len(data["matchedFormulas"]),
        len(data["similarFormulas"]),
        len(data["warnings"]),
    )
    return R.ok(FormulaDiffData(**data))
