"""依赖探测：health 用，只读、带超时、失败绝不抛异常。

设计要点：
- 每个探测函数返回 DepStatus，不 raise —— health 要能"报病"而不是"跟着病倒"
- 驱动缺失/连接不上都归为 ok=False + detail 人话原因
- 探测本身很轻：PG 查一次计数，Neo4j 只做 verify_connectivity，Redis 只 PING
"""

from __future__ import annotations

import time

from app.config import Settings
from app.schemas import DepStatus

# 探测超时（秒）：本机 Docker，2 秒足够；超时说明真有问题
TIMEOUT = 2.0


def _timed(fn) -> DepStatus:
    """统一计时 + 兜异常。"""
    start = time.perf_counter()
    try:
        detail = fn()
        return DepStatus(
            ok=True,
            detail=detail or "",
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 —— 探测层就是要吞掉一切异常
        return DepStatus(
            ok=False,
            detail=f"{type(exc).__name__}: {exc}"[:300],
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


def probe_postgres(s: Settings) -> DepStatus:
    """PG 探测：连通 + 表数 + content_unit 行数（顺带确认数据在不在）。"""

    def _run() -> str:
        import psycopg

        with psycopg.connect(s.pg_dsn, connect_timeout=int(TIMEOUT)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT (SELECT count(*) FROM information_schema.tables "
                    "        WHERE table_schema='public' AND table_type='BASE TABLE'),"
                    "       (SELECT count(*) FROM content_unit),"
                    "       (SELECT count(*) FROM content_unit WHERE embedding IS NOT NULL)"
                )
                tables, units, vectors = cur.fetchone()
        return f"tables={tables} content_unit={units} vectors={vectors}"

    return _timed(_run)


def probe_neo4j(s: Settings) -> DepStatus:
    """Neo4j 探测：握手成功 + 图规模（Formula/Herb/COMPOSED_OF）。"""

    def _run() -> str:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password)
        )
        try:
            driver.verify_connectivity()
            with driver.session() as session:
                rec = session.run(
                    "MATCH (f:Formula) WITH count(f) AS f "
                    "MATCH (h:Herb) WITH f, count(h) AS h "
                    "MATCH ()-[r:COMPOSED_OF]->() "
                    "RETURN f, h, count(r) AS r"
                ).single()
            if rec is None:
                return "connected（图为空）"
            return f"Formula={rec['f']} Herb={rec['h']} COMPOSED_OF={rec['r']}"
        finally:
            driver.close()

    return _timed(_run)


def probe_redis(s: Settings) -> DepStatus:
    """Redis 探测：只 PING。"""

    def _run() -> str:
        import redis

        client = redis.Redis.from_url(
            s.redis_url, socket_timeout=TIMEOUT, socket_connect_timeout=TIMEOUT
        )
        try:
            client.ping()
            return "PONG"
        finally:
            client.close()

    return _timed(_run)
