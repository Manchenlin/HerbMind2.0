"""GET /api/agent/history —— 当前用户的会话列表。

数据源：`agent_conversation` + `agent_message` 两张表（见 `app/repo/conversation.py`）。
鉴权：只信网关注入的 `X-User-Id`，缺失直接 401（8091 不允许对外暴露）。

为什么 `limit` 默认传 0：真正的默认值在 `HISTORY_LIMIT` 配置里，
两处各写一个默认值迟早会打架（和 `AskRequest.topK` 交给 retrieve() 读配置是同一个道理）。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from app.repo.conversation import list_conversations
from app.schemas import ConversationBrief, HistoryData, R

router = APIRouter(tags=["agent"])

# 上限保护：会话列表是给人看的，50 条之后没人会翻
MAX_LIMIT = 50


@router.get("/history", response_model=R[HistoryData], summary="会话历史列表")
async def history(
    limit: int = Query(
        default=0,
        ge=0,
        le=MAX_LIMIT,
        description=f"返回条数；不传用配置 HISTORY_LIMIT（上限 {MAX_LIMIT}）",
    ),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> R[HistoryData]:
    """列出当前用户的会话（按创建时间倒序）。

    失败口径：查询出错不 500，返回空列表 + `msg` 说明（历史是辅助功能，
    不能因为它把整个页面打红）；鉴权缺失才是 401。
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="缺少 X-User-Id：该端点只应经网关访问")

    rows = await list_conversations(x_user_id, limit or None)
    items = [ConversationBrief(**row) for row in rows]
    msg = "success" if rows else "暂无会话记录"
    return R.ok(HistoryData(conversations=items, total=len(items)), msg=msg)
