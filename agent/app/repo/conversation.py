"""会话 / 消息 / 工具轨迹的落库与读取（`agent_*` 三张表）。

表结构（`database/pg/03-domains.sql` §E，已建但本轮之前全空）：

    agent_conversation(id TEXT PK, user_id TEXT → app_user(id), title TEXT, created_at TIMESTAMPTZ)
    agent_message(id TEXT PK, conversation_id TEXT → agent_conversation(id), role, content, created_at)
    agent_tool_call(id BIGSERIAL, message_id TEXT → agent_message(id), tool_name, args_jsonb,
                    result_summary, latency_ms, created_at)

三条纪律：

1. **落库失败绝不影响问答返回**：所有写操作吞异常只 warning。用户问的是医学问题，
   不能因为一次 INSERT 超时就把整条回答变成 500（与现有「永不 500」策略一致）。
2. **不写 `app_user`**：`agent_conversation.user_id` 有外键指向它，但用户记录归域2 的登录链路。
   该用户还不存在时以 `user_id=NULL` 落库 —— Agent 无权替用户系统造账号。
3. **时间由 PG 的 `now()` 生成**，Python 侧不造时间，避免与其它模块的时区口径不一致。

为什么多轮记忆直接读 `agent_message` 而不用 LangGraph checkpointer：
本来就要为 history 落这张表，同一份数据两用；引入 checkpointer 会多一个依赖 + 一套 schema
（生产要 Postgres saver、测试要造假实现），收益不抵成本。这是对 08 §6 的有意偏差。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from typing import Any

from app.config import get_settings
from app.db import get_pg_pool

logger = logging.getLogger("herbmind-agent")

# 单条 SQL 的最长等待：落库属于"锦上添花"，不能拖慢回答
_DB_TIMEOUT = 3.0

# 会话标题取问题前若干字（问题原文可能很长，也存在健康敏感信息，不宜整段入库展示）
_TITLE_LEN = 30

# 匿名会话 ID 的归属指纹长度（sha1 前 8 位十六进制）。
# 8 位 = 32 bit，够区分 3~5 人规模，又不会把 user_id 直接写进 ID 泄露。
_SCOPE_LEN = 8

# 会话列表的硬上限：与 routers/history.py 的 MAX_LIMIT 保持一致。
# 路由层挡的是 HTTP 入参，这里挡的是"任何调用方"，避免上层改配置就把全表扫一遍。
_MAX_HISTORY_LIMIT = 50


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def anon_scope(user_id: str) -> str:
    """由 `X-User-Id` 派生匿名会话的归属指纹。

    为什么需要：`agent_conversation.user_id` 外键指向 `app_user`，而域2 登录链路还没产出用户记录，
    会话只能以 `user_id=NULL` 落库。若不加区分，`history` 的匿名兜底会返回**全库所有** NULL 会话
    —— 不同电脑、不同人互相能看到对方的会话标题（健康相关信息）。

    这里把指纹编进会话 ID（`c_<scope>_<uuid>`），列表时按前缀过滤，做到"同一个人自己的会话才能看到"，
    且**不动 DDL**（加列属跨域改动）。域2 登录上线后 `user_id` 是真实值，走 `user_id = %s` 分支，
    这个指纹自动失效。

    注意：这是**防误看**，不是鉴权。指纹只有 32 bit，可被枚举；真正的隔离靠网关 JWT + 域2 登录。
    """
    return hashlib.sha1((user_id or "").encode("utf-8")).hexdigest()[:_SCOPE_LEN]


def new_conversation_id(user_id: str) -> str:
    """生成会话 ID：`c_<user 指纹>_<随机 8 位>`。

    指纹在前是为了能用主键前缀匹配过滤（`repo.list_conversations`），
    随机部分保证同一用户多次提问不会撞 ID。
    """
    return f"c_{anon_scope(user_id)}_{uuid.uuid4().hex[:8]}"


async def _run(fn, *args: Any) -> Any:
    """在线程池里跑同步 psycopg 调用，带超时；任何异常都吞掉只告警。

    psycopg 是同步驱动，直接 await 会阻塞事件循环（一次问答要多写 2~3 行），
    所以统一 `asyncio.to_thread`。超时用 `wait_for` 兜住，避免 PG 卡住时整条问答一起卡。
    """
    try:
        return await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout=_DB_TIMEOUT)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("会话落库失败（已忽略，不影响回答）：%s", exc)
        return None


# ==================== 写 ====================


def _ensure_conversation_sync(conv_id: str, user_id: str, title: str) -> bool:
    with get_pg_pool().connection(timeout=_DB_TIMEOUT) as conn:
        with conn.cursor() as cur:
            # 用户记录归域2：不存在时只能以 NULL 落库（外键必须是真实用户）
            cur.execute("SELECT 1 FROM app_user WHERE id = %s", (user_id,))
            resolved = user_id if cur.fetchone() else None
            if resolved is None:
                logger.warning(
                    "app_user 里没有 %s，本会话以 user_id=NULL 落库（history 只能靠匿名兜底查到）",
                    user_id,
                )
            cur.execute(
                "INSERT INTO agent_conversation (id, user_id, title) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (conv_id, resolved, title),
            )
    return True


async def ensure_conversation(conv_id: str, user_id: str, title: str = "") -> bool:
    """确保会话存在（幂等）。

    Returns:
        True=已确保（含"本来就有"）；False=落库失败（调用方应继续回答，只是没有历史）。
    """
    if not conv_id:
        return False
    clean_title = (title or "").strip().replace("\n", " ")[:_TITLE_LEN]
    result = await _run(_ensure_conversation_sync, conv_id, user_id, clean_title)
    return bool(result)


def _append_message_sync(conv_id: str, role: str, content: str) -> str:
    message_id = _new_id("m")
    with get_pg_pool().connection(timeout=_DB_TIMEOUT) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO agent_message (id, conversation_id, role, content) VALUES (%s, %s, %s, %s)",
                (message_id, conv_id, role, content),
            )
    return message_id


async def append_message(conv_id: str, role: str, content: str) -> str | None:
    """追加一条消息，返回 message id（失败返回 None）。"""
    if not conv_id or not content:
        return None
    return await _run(_append_message_sync, conv_id, role, content)


def _record_tool_call_sync(
    message_id: str | None,
    tool_name: str,
    args: dict[str, Any],
    summary: str,
    latency_ms: int,
) -> bool:
    with get_pg_pool().connection(timeout=_DB_TIMEOUT) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO agent_tool_call (message_id, tool_name, args_jsonb, result_summary, latency_ms) "
                "VALUES (%s, %s, %s::jsonb, %s, %s)",
                (message_id, tool_name, json.dumps(args, ensure_ascii=False), summary, max(0, int(latency_ms))),
            )
    return True


async def record_tool_call(
    message_id: str | None,
    tool_name: str,
    args: dict[str, Any],
    summary: str,
    latency_ms: int,
) -> bool:
    """记录一次工具调用（`message_id` 可为 None：那一轮还没产生 assistant 消息）。"""
    result = await _run(_record_tool_call_sync, message_id, tool_name, args, summary, latency_ms)
    return bool(result)


# ==================== 读 ====================


def _recent_messages_sync(conv_id: str, limit: int) -> list[tuple[str, str]]:
    with get_pg_pool().connection(timeout=_DB_TIMEOUT) as conn:
        with conn.cursor() as cur:
            # 先取最近 N 条，再按时间正序还给调用方（模型需要"从旧到新"的对话顺序）
            cur.execute(
                "SELECT role, content FROM ("
                "  SELECT role, content, created_at, id FROM agent_message"
                "  WHERE conversation_id = %s AND role IN ('user', 'assistant')"
                "  ORDER BY created_at DESC, id DESC LIMIT %s"
                ") t ORDER BY created_at, id",
                (conv_id, limit),
            )
            return [(row[0], row[1] or "") for row in cur.fetchall()]


async def recent_messages(conv_id: str, limit: int | None = None) -> list[dict[str, str]]:
    """取最近几条对话消息作为多轮记忆（只含 user/assistant，不含 tool）。"""
    if not conv_id:
        return []
    n = limit or get_settings().memory_messages
    rows = await _run(_recent_messages_sync, conv_id, max(1, int(n)))
    if not rows:
        return []
    return [{"role": role, "content": content} for role, content in rows]


def _list_conversations_sync(user_id: str, limit: int, include_anonymous: bool) -> list[tuple]:
    with get_pg_pool().connection(timeout=_DB_TIMEOUT) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM app_user WHERE id = %s", (user_id,))
            known_user = cur.fetchone() is not None
            # 域2 登录链路还没产出 app_user 时，会话只能匿名落库（user_id=NULL）。
            # 此时退化成"看自己的匿名会话"（按 ID 里的用户指纹过滤），否则 history 永远是空列表。
            # ⚠️ 这是**临时口径**：真实用户上线后 known_user=True，自然只查自己的会话。
            # ⚠️ 不要去掉 LIKE 条件：那会让所有人看到同一批匿名会话（跨电脑/跨人泄露标题）。
            anonymous = include_anonymous and not known_user
            cur.execute(
                "SELECT c.id, coalesce(c.title, ''), c.created_at,"
                "       count(m.id) AS message_count, max(m.created_at) AS last_at"
                " FROM agent_conversation c"
                " LEFT JOIN agent_message m ON m.conversation_id = c.id"
                " WHERE c.user_id = %s OR (%s AND c.user_id IS NULL AND c.id LIKE %s)"
                " GROUP BY c.id, c.title, c.created_at"
                " ORDER BY c.created_at DESC"
                " LIMIT %s",
                (user_id, anonymous, f"c\\_{anon_scope(user_id)}\\_%", limit),
            )
            return list(cur.fetchall())


async def list_conversations(user_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    """列出该用户的会话（按创建时间倒序，带消息数与最后一条时间）。

    走已有索引 `idx_agent_conv_user(user_id, created_at DESC)`；
    消息数用一次聚合而不是 N+1。
    """
    # 与 routers/history.py 的 MAX_LIMIT 对齐：路由层已用 Query(le=50) 挡住越界，
    # 但 repo 是公共函数（脚本 / 将来的 BFF 直调都会用），配置写错或传大值时必须自己兜一次，
    # 否则聚合查询会按该值扫全表 agent_message
    n = min(int(limit or get_settings().history_limit), _MAX_HISTORY_LIMIT)
    rows = await _run(_list_conversations_sync, user_id, max(1, n), True)
    out: list[dict[str, Any]] = []
    for row in rows or []:
        conv_id, title, created_at, message_count, last_at = row
        out.append(
            {
                "id": conv_id,
                "title": title,
                "created_at": created_at.isoformat() if created_at else "",
                "message_count": int(message_count or 0),
                "last_at": last_at.isoformat() if last_at else "",
            }
        )
    return out
