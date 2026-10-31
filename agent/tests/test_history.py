"""会话落库与 `GET /api/agent/history` 的测试。

用假 PG 池断言 **SQL 文本与参数**，不连库：
- 聚合查询必须是**一条 SQL**（`count(m.id)` + `max(m.created_at)`），不能 N+1；
- `app_user` 不存在时必须把 `user_id` 降级成 NULL（外键指向它，Agent 无权造账号）；
- 落库失败只能告警，不能把异常抛给问答链路。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from app.repo import conversation as repo
from app.routers import history as history_router

HEADERS = {"X-User-Id": "u_test"}


# ==================== 假 PG 池 ====================


class _FakeCursor:
    def __init__(self, pool: "_FakePool") -> None:
        self._pool = pool
        self._batch: Any = None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def execute(self, sql: str, params: tuple | None = None) -> None:
        # 归一化空白，便于断言 SQL 里出现的关键片段
        self._pool.sql.append(" ".join(sql.split()))
        self._pool.params.append(params)
        if self._pool.raises is not None:
            raise self._pool.raises
        self._batch = self._pool.script.pop(0) if self._pool.script else None

    def fetchone(self):
        return self._batch

    def fetchall(self) -> list:
        return list(self._batch or [])


class _FakeConn:
    def __init__(self, pool: "_FakePool") -> None:
        self._pool = pool

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._pool)


class _FakePool:
    def __init__(self, script: list[Any] | None = None, raises: Exception | None = None) -> None:
        self.script = list(script or [])
        self.raises = raises
        self.sql: list[str] = []
        self.params: list[Any] = []

    def connection(self, timeout: float | None = None) -> _FakeConn:  # noqa: ARG002
        return _FakeConn(self)


def _patch_pool(monkeypatch, pool: _FakePool) -> _FakePool:
    monkeypatch.setattr(repo, "get_pg_pool", lambda: pool)
    return pool


def _now() -> datetime:
    return datetime(2026, 10, 31, 9, 30, tzinfo=timezone.utc)


# ==================== list_conversations ====================


def test_list_conversations_uses_single_aggregate_query(monkeypatch) -> None:
    pool = _patch_pool(
        monkeypatch,
        _FakePool([(1,), [("c_1", "麻黄汤的组成", _now(), 4, _now())]]),
    )

    rows = asyncio.run(repo.list_conversations("u_1", 20))

    assert rows == [
        {
            "id": "c_1",
            "title": "麻黄汤的组成",
            "created_at": _now().isoformat(),
            "message_count": 4,
            "last_at": _now().isoformat(),
        }
    ]
    sql = pool.sql[1]
    assert "LEFT JOIN agent_message" in sql
    assert "count(m.id)" in sql and "max(m.created_at)" in sql
    assert "ORDER BY c.created_at DESC" in sql
    assert "LIMIT" in sql
    # 已知用户 → 不启用匿名兜底（第三个参数是 LIKE 模式，此时不生效）
    assert pool.params[1] == ("u_1", False, f"c\\_{repo.anon_scope('u_1')}\\_%", 20)


def test_list_conversations_falls_back_to_anonymous_when_user_unknown(monkeypatch) -> None:
    """域2 登录链路还没产出 app_user 时，会话只能匿名落库，history 必须还能查到。"""
    pool = _patch_pool(monkeypatch, _FakePool([None, []]))

    asyncio.run(repo.list_conversations("u_ghost", 20))

    assert pool.params[1] == ("u_ghost", True, f"c\\_{repo.anon_scope('u_ghost')}\\_%", 20)
    assert "c.user_id IS NULL" in pool.sql[1]
    assert "c.id LIKE %s" in pool.sql[1], "匿名兜底必须按会话 ID 的用户指纹过滤，不能全库返回"


def test_anonymous_conversations_are_scoped_per_user() -> None:
    """核心断言：两个不同的未知用户，拿到的 LIKE 前缀必须不同（否则会互相看到会话标题）。"""
    scope_a = repo.anon_scope("u_alice")
    scope_b = repo.anon_scope("u_bob")

    assert scope_a != scope_b
    assert len(scope_a) == 8 and len(scope_b) == 8
    assert repo.anon_scope("u_alice") == scope_a, "同一个 user 每次必须得到同一指纹"


def test_new_conversation_id_carries_user_scope() -> None:
    """新会话 ID 形状：`c_<指纹>_<8 位随机>`，指纹在前以便主键前缀过滤。"""
    conv_id = repo.new_conversation_id("u_alice")
    scope = repo.anon_scope("u_alice")

    assert conv_id.startswith(f"c_{scope}_")
    tail = conv_id.rsplit("_", 1)[-1]
    assert len(tail) == 8 and all(ch in "0123456789abcdef" for ch in tail)
    # 同一用户的两次新会话不能撞 ID
    assert conv_id != repo.new_conversation_id("u_alice")


def test_list_conversations_swallows_db_failure(monkeypatch) -> None:
    """查询炸了 → 返回空列表而不是抛异常（history 是辅助功能）。"""
    _patch_pool(monkeypatch, _FakePool(raises=RuntimeError("池未初始化")))

    assert asyncio.run(repo.list_conversations("u_1", 20)) == []


# ==================== ensure_conversation ====================


def test_ensure_conversation_nulls_user_when_app_user_missing(monkeypatch) -> None:
    pool = _patch_pool(monkeypatch, _FakePool([None]))

    ok = asyncio.run(repo.ensure_conversation("c_1", "u_ghost", "麻黄汤的组成"))

    assert ok is True
    assert "SELECT 1 FROM app_user" in pool.sql[0]
    insert_sql, insert_params = pool.sql[1], pool.params[1]
    assert "INSERT INTO agent_conversation" in insert_sql
    assert "ON CONFLICT (id) DO NOTHING" in insert_sql
    assert insert_params == ("c_1", None, "麻黄汤的组成")


def test_ensure_conversation_keeps_user_when_app_user_exists(monkeypatch) -> None:
    pool = _patch_pool(monkeypatch, _FakePool([(1,)]))

    asyncio.run(repo.ensure_conversation("c_2", "u_1", "桂枝汤"))

    assert pool.params[1] == ("c_2", "u_1", "桂枝汤")


def test_ensure_conversation_truncates_title(monkeypatch) -> None:
    pool = _patch_pool(monkeypatch, _FakePool([(1,)]))

    asyncio.run(repo.ensure_conversation("c_3", "u_1", "问" * 100 + "\n第二行"))

    title = pool.params[1][2]
    assert len(title) == 30
    assert "\n" not in title


def test_ensure_conversation_failure_returns_false(monkeypatch) -> None:
    _patch_pool(monkeypatch, _FakePool(raises=RuntimeError("池未初始化")))

    assert asyncio.run(repo.ensure_conversation("c_4", "u_1", "标题")) is False


# ==================== append_message / record_tool_call ====================


def test_append_message_returns_generated_id(monkeypatch) -> None:
    pool = _patch_pool(monkeypatch, _FakePool())

    message_id = asyncio.run(repo.append_message("c_1", "user", "麻黄汤的组成"))

    assert message_id and message_id.startswith("m_")
    assert "INSERT INTO agent_message" in pool.sql[0]
    assert pool.params[0] == (message_id, "c_1", "user", "麻黄汤的组成")


def test_record_tool_call_casts_jsonb(monkeypatch) -> None:
    pool = _patch_pool(monkeypatch, _FakePool())

    asyncio.run(repo.record_tool_call("m_1", "search_formula", {"name": "麻黄汤"}, "ok=True", 12))

    sql, params = pool.sql[0], pool.params[0]
    assert "INSERT INTO agent_tool_call" in sql
    assert "%s::jsonb" in sql, "args_jsonb 是 JSONB 列，必须显式 cast"
    assert params[0] == "m_1"
    assert params[1] == "search_formula"
    assert '"name": "麻黄汤"' in params[2] or '"name":"麻黄汤"' in params[2]
    assert params[4] == 12


def test_empty_conversation_id_writes_nothing(monkeypatch) -> None:
    pool = _patch_pool(monkeypatch, _FakePool())

    assert asyncio.run(repo.append_message("", "user", "内容")) is None
    assert asyncio.run(repo.ensure_conversation("", "u_1", "标题")) is False
    assert pool.sql == []


# ==================== recent_messages ====================


def test_recent_messages_returns_chronological_dicts(monkeypatch) -> None:
    pool = _patch_pool(monkeypatch, _FakePool([[("user", "问"), ("assistant", "答")]]))

    rows = asyncio.run(repo.recent_messages("c_1", 6))

    assert rows == [{"role": "user", "content": "问"}, {"role": "assistant", "content": "答"}]
    sql = pool.sql[0]
    assert "ORDER BY created_at DESC, id DESC" in sql, "先取最近的，再反转"
    assert "role IN ('user', 'assistant')" in sql, "tool 消息不进多轮记忆"
    assert pool.params[0] == ("c_1", 6)


# ==================== 路由 ====================


def test_history_requires_user_id(client) -> None:
    resp = client.get("/api/agent/history")

    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 401
    assert "X-User-Id" in body["msg"]


def test_history_empty_list(client, monkeypatch) -> None:
    async def _empty(_user_id, _limit=None):
        return []

    monkeypatch.setattr(history_router, "list_conversations", _empty)

    resp = client.get("/api/agent/history", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"] == {"conversations": [], "total": 0}
    assert body["msg"] == "暂无会话记录"


def test_history_maps_fields_to_camel_case(client, monkeypatch) -> None:
    async def _rows(_user_id, _limit=None):
        return [
            {
                "id": "c_1",
                "title": "麻黄汤的组成",
                "created_at": "2026-10-31T09:30:00+00:00",
                "message_count": 4,
                "last_at": "2026-10-31T09:31:00+00:00",
            }
        ]

    monkeypatch.setattr(history_router, "list_conversations", _rows)

    data = client.get("/api/agent/history", headers=HEADERS).json()["data"]

    assert data["total"] == 1
    conv = data["conversations"][0]
    assert set(conv) == {"id", "title", "createdAt", "messageCount", "lastAt"}
    assert conv["messageCount"] == 4


def test_history_limit_upper_bound(client, monkeypatch) -> None:
    """limit 超过 50 直接判参数错误，不能让它去扫全表。"""

    async def _rows(_user_id, _limit=None):  # pragma: no cover - 不该被调用
        return []

    monkeypatch.setattr(history_router, "list_conversations", _rows)

    resp = client.get("/api/agent/history", params={"limit": 999}, headers=HEADERS)

    assert resp.status_code == 400
    assert resp.json()["code"] == 400


def test_history_zero_limit_uses_config(client, monkeypatch) -> None:
    """limit=0（不传）交给配置，路由不许自己写死默认值。"""
    seen: dict = {}

    async def _rows(_user_id, limit=None):
        seen["limit"] = limit
        return []

    monkeypatch.setattr(history_router, "list_conversations", _rows)

    client.get("/api/agent/history", headers=HEADERS)

    assert seen["limit"] is None


def test_list_conversations_caps_limit_at_repo_level(monkeypatch) -> None:
    """回归钉子：上限不能只放在路由的 `Query(le=50)` 上。

    `list_conversations` 是公共函数（脚本、将来 BFF 直调都会用），
    传个大值或把 HISTORY_LIMIT 配错，聚合查询就会按该值扫全表 `agent_message`。
    """
    pool = _patch_pool(monkeypatch, _FakePool([(1,), []]))

    asyncio.run(repo.list_conversations("u_1", 9999))

    assert pool.params[1][-1] == 50, "SQL 的 LIMIT 参数必须被夹到 50"
