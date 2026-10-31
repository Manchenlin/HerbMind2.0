"""`app/clients` 的协议层测试（httpx.MockTransport，不联网）。

这一层只负责三件事，测试也只钉这三件：
1. **2xx 返回裸 DTO**（svc 的 `/internal` 成功时不包 `R`，不要再拆一层）；
2. **非 2xx 抛 `SvcError`**，并把 `R.msg` 取出来当原因（工具层据此拼提示）；
3. **连不上/超时抛 `SvcError(0)`**，与「服务端返回 4040 查不到」严格分开。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from app.clients import base, catalog, graph, search


def _run(handler, coro_fn):
    """在 mock transport 上跑一次调用，结束后恢复全局客户端。

    必须同时设置 `_client_loop`：`get_client()` 会比对"client 是在哪个 loop 里建的"，
    只塞 `_client` 不塞 loop 会被判成"换了事件循环"，从而丢弃替身去打真实 localhost。
    """

    async def _inner():
        loop = asyncio.get_running_loop()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            base._client = client
            base._client_loop = loop
            try:
                return await coro_fn()
            finally:
                base._client = None
                base._client_loop = None

    return asyncio.run(_inner())


def _json_response(status: int, payload: Any) -> httpx.Response:
    return httpx.Response(status, json=payload)


# ==================== 2xx：裸 DTO ====================


def test_2xx_returns_bare_dto() -> None:
    """成功响应是裸 DTO，不许再去拆 `R.data`。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return _json_response(200, {"list": [{"id": "cu_1"}], "total": 1})

    data = _run(handler, lambda: search.search(q="麻黄汤", ref_type="formula", size=8))

    assert data["total"] == 1
    assert data["list"][0]["id"] == "cu_1"
    assert "/internal/search" in seen["url"]
    assert "type=formula" in seen["url"]


def test_empty_params_are_not_sent() -> None:
    """None / 空串的查询参数不能发出去，否则会拼成 `herb=None` 被服务端当成药名。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return _json_response(200, {})

    _run(handler, lambda: search.search(q="桂枝汤", ref_type=None, herb=None, size=5))

    assert "herb=" not in seen["url"]
    assert "type=" not in seen["url"]


def test_post_json_sends_body() -> None:
    """recall 是 POST，参数进 body 而不是 query。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = request.content.decode()
        return _json_response(200, {"list": [], "total": 0})

    data = _run(handler, lambda: search.recall(q="无汗而喘", size=5))

    assert data["total"] == 0
    assert seen["method"] == "POST"
    assert "无汗而喘" in seen["body"]


# ==================== 非 2xx：SvcError + R.msg ====================


def test_4040_becomes_svc_error_with_msg() -> None:
    """svc 的 4040 走 HTTP 404 + R{code,msg}：工具层要靠 msg 说明「图谱里没有这个实体」。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(404, {"code": 4040, "msg": "实体不存在：麻黄汤", "data": None})

    with pytest.raises(base.SvcError) as info:
        _run(handler, lambda: graph.neighbors(entity="麻黄汤"))

    err = info.value
    assert err.status == 404
    assert err.msg == "实体不存在：麻黄汤"
    assert err.svc == "graph"
    assert err.unreachable is False, "4040 是查不到，不是服务不可用"


def test_5000_marks_unreachable() -> None:
    """5000 是服务侧故障，工具要给「稍后重试」而不是「查不到」。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(500, {"code": 5000, "msg": "Neo4j 不可用", "data": None})

    with pytest.raises(base.SvcError) as info:
        _run(handler, lambda: graph.neighbors(entity="麻黄汤"))

    assert info.value.status == 500
    assert info.value.unreachable is True


def test_non_json_error_body_falls_back_to_status() -> None:
    """网关/中间件可能返回 HTML 错误页，不能因此炸在 json() 上。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    with pytest.raises(base.SvcError) as info:
        _run(handler, lambda: catalog.formula("f_1"))

    assert info.value.status == 502
    assert "Bad Gateway" in info.value.msg


# ==================== 连不上 / 超时 ====================


def test_connect_error_becomes_status_zero() -> None:
    """连接被拒 = 服务不可达（status=0），与 404 的语义必须分开。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(base.SvcError) as info:
        _run(handler, lambda: search.search(q="麻黄汤"))

    assert info.value.status == 0
    assert info.value.unreachable is True
    assert "不可达" in info.value.msg


def test_timeout_becomes_status_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(base.SvcError) as info:
        _run(handler, lambda: search.recall(q="麻黄汤"))

    assert info.value.status == 0
    assert "超时" in info.value.msg


# ==================== 其它 ====================


def test_unknown_svc_is_programming_error() -> None:
    """svc 名写错属于代码 bug，应立刻抛 ValueError，而不是当成「服务不可达」吞掉。"""
    with pytest.raises(ValueError):
        asyncio.run(base.get_json("nope", "/internal/x"))


def test_svc_base_url_strips_trailing_slash() -> None:
    """配置里带尾斜杠时不能拼出 `//internal`（部分容器会 404）。"""
    from app.config import get_settings

    settings = get_settings()
    original = settings.svc_search_url
    settings.svc_search_url = "http://localhost:8083/"
    try:
        assert base.svc_base_url("search") == "http://localhost:8083"
    finally:
        settings.svc_search_url = original


def test_client_is_rebuilt_when_event_loop_changes(monkeypatch) -> None:
    """回归钉子：`httpx.AsyncClient` 的连接池绑定创建它的 loop。

    单测/脚本里 `asyncio.run()` 每个用例一个新 loop，复用旧 client 会抛
    `RuntimeError: Event loop is closed`（test_tools 集成层实测踩到）。
    这里连着跑两个 loop，必须**重建**客户端并成功发出第二次请求。
    """
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _json_response(200, {"total": 0})

    def _fake_init(_settings=None) -> None:
        base._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        base._client_loop = asyncio.get_running_loop()

    monkeypatch.setattr(base, "init_clients", _fake_init)

    async def _call() -> dict:
        return await base.get_json("search", "/internal/search")

    asyncio.run(_call())
    asyncio.run(_call())

    assert len(calls) == 2, "第二个 loop 必须重建客户端，而不是复用已死的连接池"
    base._client = None
    base._client_loop = None


def test_prewarmed_client_is_reused_not_dropped() -> None:
    """回归钉子：同步预热（当时没有 running loop）后首次进 loop，应补绑定而不是丢弃重建。

    丢弃等于把一个健康的连接池连同 socket 一起泄漏，还白付一次建连成本。
    """
    dummy = object()
    base._client = dummy       # 模拟 init_clients() 在没有 loop 的同步代码里创建
    base._client_loop = None   # 当时没有 running loop，所以没记 loop

    async def _call():
        return base.get_client()

    got = asyncio.run(_call())

    assert got is dummy, "预热出来的客户端不该被当成「换了循环」丢掉"
    base._client = None
    base._client_loop = None
