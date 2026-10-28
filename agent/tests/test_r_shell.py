"""R 外壳与全局异常处理的断言测试。

钉住的契约（`CODEBUDDY.md` §四 / `project_plan/09` §12）：
- 所有响应（含 401 / 400 / 404 / 500）都必须是 `{code, msg, data}`，
  不允许出现 FastAPI 默认的裸 `{"detail": ...}` —— 否则前端要写两套解析。
- 每个响应都要回写 `X-Request-Id`，便于对着日志查一次请求。

零外部依赖：不连 PG / Neo4j / Redis / 大模型（health 的探测函数全部被替身替换）。
"""

from __future__ import annotations

import pytest

from helpers import fake_client

from app.schemas import DepStatus

R_SHELL_KEYS = {"code", "msg", "data"}


def _assert_r_shell(payload: dict) -> None:
    """断言响应体是 R 外壳，而不是裸 detail。"""
    assert set(payload) == R_SHELL_KEYS, f"不是 R 外壳：{payload}"
    assert "detail" not in payload


# ==================== 鉴权：缺 X-User-Id 一律 401 ====================


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/agent/ask/sync", {"question": "桂枝汤的组成"}),
        ("/api/agent/ask", {"question": "桂枝汤的组成"}),
    ],
)
def test_missing_user_id_returns_401_r_shell(client, path, body) -> None:
    """没带 X-User-Id → 401，且 body 是 R 外壳（不是 {"detail": ...}）。"""
    resp = client.post(path, json=body)

    assert resp.status_code == 401
    payload = resp.json()
    _assert_r_shell(payload)
    assert payload["code"] == 401
    assert payload["data"] is None
    assert "X-User-Id" in payload["msg"]


def test_user_id_header_lets_request_through(client, monkeypatch) -> None:
    """带了 X-User-Id 就应越过鉴权，进入业务逻辑（这里把检索替换成空结果以避开网络）。"""
    from app.routers import ask as ask_router

    async def _empty_retrieve(*_args, **_kwargs):
        return []

    monkeypatch.setattr(ask_router, "retrieve", _empty_retrieve)

    resp = client.post(
        "/api/agent/ask/sync",
        json={"question": "桂枝汤的组成"},
        headers={"X-User-Id": "u_test"},
    )

    assert resp.status_code == 200
    assert resp.json()["code"] == 0


# ==================== 参数校验：400 也套 R 外壳 ====================


@pytest.mark.parametrize(
    "body",
    [
        {"question": "短"},              # min_length=2，1 个汉字不合法
        {"question": "桂枝汤的组成", "topK": 99},   # le=10
        {"question": "桂枝汤的组成", "topK": 0},    # ge=1
        {"question": "桂枝汤的组成", "refType": "quote"},  # 只允许 formula / case
        {},                              # 缺 question
    ],
)
def test_validation_error_returns_400_r_shell(client, body) -> None:
    """参数校验失败 → 400 + R 外壳（FastAPI 默认是 422 + {"detail": [...]}）。"""
    resp = client.post(
        "/api/agent/ask/sync", json=body, headers={"X-User-Id": "u_test"}
    )

    assert resp.status_code == 400
    payload = resp.json()
    _assert_r_shell(payload)
    assert payload["code"] == 400


# ==================== 未知路由：404 也套 R 外壳 ====================


def test_unknown_route_returns_404_r_shell(client) -> None:
    resp = client.get("/api/agent/not-exist")

    assert resp.status_code == 404
    payload = resp.json()
    _assert_r_shell(payload)
    assert payload["code"] == 404


# ==================== 兜底：未捕获异常 → 500 也套 R 外壳 ====================


def test_unexpected_error_returns_500_r_shell(monkeypatch) -> None:
    """health 的探测函数抛出未捕获异常 → 走全局兜底，返回 R 外壳而非裸 500 HTML。

    注意 `raise_server_exceptions=False`：TestClient 默认会把异常重新抛给测试，
    那样就看不到响应体了（详见 helpers.py 顶部注释）。
    """
    from app.routers import health as health_router

    def _boom() -> DepStatus:
        raise RuntimeError("模拟探测崩溃")

    monkeypatch.setattr(health_router, "probe_postgres", _boom)
    client = fake_client(raise_server_exceptions=False)

    resp = client.get("/api/agent/health")

    assert resp.status_code == 500
    payload = resp.json()
    _assert_r_shell(payload)
    assert payload["code"] == 500
    assert "RuntimeError" in payload["msg"]


# ==================== X-Request-Id ====================


def test_request_id_is_echoed_on_success_and_error(client) -> None:
    """成功与失败都要回写 X-Request-Id：排障时要能用它把响应和日志对上。"""
    # 注意这条发的是「1 个汉字 → 违反 min_length=2」，拿到的是 400，不是 200
    validation_resp = client.post(
        "/api/agent/ask/sync", json={"question": "短"}, headers={"X-User-Id": "u_test"}
    )
    auth_resp = client.post("/api/agent/ask/sync", json={"question": "桂枝汤的组成"})

    assert validation_resp.status_code == 400
    assert auth_resp.status_code == 401
    for resp in (validation_resp, auth_resp):
        request_id = resp.headers.get("X-Request-Id")
        assert request_id, "响应缺少 X-Request-Id"
        assert len(request_id) == 8, f"请求 ID 应为 8 位短 ID，实际 {request_id}"
