"""依赖探测：health 用，只读、带超时、失败绝不抛异常。

设计要点：
- 每个探测函数返回 DepStatus，不 raise —— health 要能"报病"而不是"跟着病倒"
- 连接一律复用 db.py 里的池/单例（不再每次新建，省掉 20~150ms 握手）
- 探测本身很轻：PG 查一次计数，Neo4j 查一次规模，Redis 只 PING
"""

from __future__ import annotations

import time

from app.db import get_neo4j_driver, get_pg_pool, get_redis_client
from app.schemas import DepStatus

# 探测超时（秒）：本机 Docker，2~3 秒足够；超时说明真有问题
TIMEOUT = 3.0


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


def probe_postgres() -> DepStatus:
    """PG 探测：从池里借连接查表数 + content_unit 行数（顺带确认数据在不在）。"""

    def _run() -> str:
        pool = get_pg_pool()
        # with 上下文：正常结束自动 commit 并归还，异常自动 rollback 并归还
        with pool.connection(timeout=TIMEOUT) as conn:
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


def probe_neo4j() -> DepStatus:
    """Neo4j 探测：复用全局 Driver，查图规模（Formula/Herb/COMPOSED_OF）。"""

    def _run() -> str:
        driver = get_neo4j_driver()
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

    return _timed(_run)


def probe_redis() -> DepStatus:
    """Redis 探测：复用全局客户端，只 PING。"""

    def _run() -> str:
        client = get_redis_client()
        client.ping()
        return "PONG"

    return _timed(_run)
