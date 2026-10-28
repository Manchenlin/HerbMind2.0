"""`GET /api/agent/health` 的断言测试。

健康检查的对外承诺：**依赖不通只报 degraded，绝不 500**（服务自身活着就要能回答）。
它也是契约里唯一的白名单端点 —— 不带 `X-User-Id` 必须能正常返回。

零外部依赖：三个探测函数与池统计全部替身替换。
"""

from __future__ import annotations

from helpers import fake_client

from app.routers import health as health_router
from app.schemas import DepStatus


def _patch_probes(monkeypatch, *, postgres=True, neo4j=True, redis=True) -> None:
    """按开关替换三个探测函数。"""
    monkeypatch.setattr(
        health_router,
        "probe_postgres",
        lambda: DepStatus(ok=postgres, detail="tables=41" if postgres else "OperationalError", latency_ms=3),
    )
    monkeypatch.setattr(
        health_router,
        "probe_neo4j",
        lambda: DepStatus(ok=neo4j, detail="Formula=245" if neo4j else "ServiceUnavailable", latency_ms=5),
    )
    monkeypatch.setattr(
        health_router,
        "probe_redis",
        lambda: DepStatus(ok=redis, detail="PONG" if redis else "ConnectionError", latency_ms=1),
    )
    monkeypatch.setattr(
        health_router,
        "pool_stats",
        lambda: {"poolSize": 1, "poolAvailable": 1, "requestsWaiting": 0},
    )


def test_health_is_whitelisted_and_ok(client, monkeypatch) -> None:
    """不带 X-User-Id 也能访问（白名单），全依赖正常 → status=ok、code=0。"""
    _patch_probes(monkeypatch)

    resp = client.get("/api/agent/health")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 0
    data = payload["data"]
    assert data["status"] == "ok"
    assert data["service"] == "herbmind-agent"
    # camelCase：llm.embeddingModel、deps.*.latencyMs、pgPool.*
    assert "embeddingModel" in data["llm"]
    assert data["deps"]["postgres"] == {"ok": True, "detail": "tables=41", "latencyMs": 3}
    assert data["pgPool"]["poolSize"] == 1


def test_health_reports_degraded_not_500(client, monkeypatch) -> None:
    """任一依赖不通 → status=degraded + msg 提示，HTTP 仍是 200（容器探针不能把服务判死）。"""
    _patch_probes(monkeypatch, neo4j=False)

    resp = client.get("/api/agent/health")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 0
    assert payload["data"]["status"] == "degraded"
    assert "部分依赖不可用" in payload["msg"]
    assert payload["data"]["deps"]["neo4j"]["ok"] is False
    assert payload["data"]["deps"]["postgres"]["ok"] is True


def test_health_does_not_require_user_header(client, monkeypatch) -> None:
    """请求头为空也必须 200（网关白名单依赖这条）。

    必须用真实 app：自建只挂 health 路由的最小应用里压根没有鉴权，断言恒真、抓不到回归。
    """
    _patch_probes(monkeypatch)

    resp = client.get("/api/agent/health", headers={})

    assert resp.status_code == 200


def test_pool_stats_absent_pool_returns_empty(monkeypatch) -> None:
    """池未初始化时 poolStats 返回空对象，而不是抛异常（health 不能因此 500）。"""
    from app import db

    monkeypatch.setattr(db, "_pg_pool", None)

    assert db.pool_stats() == {}
