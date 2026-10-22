"""外部资源生命周期管理：PG 连接池 / Neo4j Driver / Redis 客户端。

设计要点：
- **全局单例**，在 main.py 的 lifespan 里 init_resources() / close_resources()
- PG 用 psycopg_pool：省掉每次请求 20~25ms 的握手 + 认证开销
- Neo4j 只建一个 Driver：它内部自带连接池，每次新建 Driver 要 150ms+
- Redis 只建一个 client：内部同样自带连接池
- 取用统一走 get_xxx()，未初始化时给出人话异常（说明忘了在 lifespan 里 init）

⚠️ 用 PG 池必须写成 with get_pg_pool().connection()：
   - 正常退出自动 commit 并归还连接
   - 抛异常自动 rollback 并归还
   手动 getconn/putconn 一旦漏掉 rollback，脏连接会污染下一个请求。
"""

from __future__ import annotations

import logging

from app.config import Settings

logger = logging.getLogger("herbmind-agent")

# 模块级单例（进程内唯一；uvicorn 多 worker 时每个进程各一份，属正常）
_pg_pool = None
_neo4j_driver = None
_redis_client = None


def init_resources(s: Settings) -> None:
    """启动时建池。PG 连不上只报错不崩——让 health 去报病，别把服务拦死。"""
    global _pg_pool, _neo4j_driver, _redis_client

    # ---------- PostgreSQL 连接池 ----------
    try:
        from psycopg_pool import ConnectionPool

        _pg_pool = ConnectionPool(
            conninfo=s.pg_dsn,
            min_size=1,          # 启动就备 1 条，第一个请求不用等握手
            max_size=5,          # 3~5 人用的项目，5 条足够；配合 PG max_connections=100
            timeout=3,           # 池满后最多等 3 秒，宁可报错也不无限挂起
            max_idle=300,        # 空闲 5 分钟回收，防止被中间设备掐断后留在池里
            open=False,
            name="herbmind-agent-pg",
        )
        try:
            _pg_pool.open(wait=True, timeout=5)
            logger.info("PG 连接池已启动：min=1 max=5（%s）", _mask(s.pg_dsn))
        except Exception as exc:  # noqa: BLE001
            # 池对象保留：PG 稍后恢复时 psycopg_pool 会自动补连接。
            # 一旦置 None，本进程余生都用不了库（必须重启容器才能恢复）。
            logger.warning("PG 暂时不可达（池已保留，恢复后自动重连）：%s", exc)
    except Exception as exc:  # noqa: BLE001 —— 建池本身失败（配置错/驱动缺失）
        _pg_pool = None
        logger.error("PG 连接池创建失败（health 会显示 postgres 不可用）：%s", exc)

    # ---------- Neo4j Driver（内部自带池，全局一个就够） ----------
    try:
        from neo4j import GraphDatabase

        _neo4j_driver = GraphDatabase.driver(
            s.neo4j_uri,
            auth=(s.neo4j_user, s.neo4j_password),
            max_connection_pool_size=10,
            connection_timeout=3,
        )
        # 注意：这里刻意不 verify_connectivity()，否则 Neo4j 没启动会连带服务起不来
        logger.info("Neo4j Driver 已创建（%s）", s.neo4j_uri)
    except Exception as exc:  # noqa: BLE001
        _neo4j_driver = None
        logger.error("Neo4j Driver 创建失败：%s", exc)

    # ---------- Redis 客户端（内部自带池） ----------
    try:
        import redis

        _redis_client = redis.Redis.from_url(
            s.redis_url,
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=True,
        )
        logger.info("Redis 客户端已创建（%s）", s.redis_url)
    except Exception as exc:  # noqa: BLE001
        _redis_client = None
        logger.error("Redis 客户端创建失败：%s", exc)


def close_resources() -> None:
    """关闭时释放所有资源（顺序无所谓，各自兜异常）。"""
    global _pg_pool, _neo4j_driver, _redis_client

    if _pg_pool is not None:
        try:
            _pg_pool.close()
            logger.info("PG 连接池已关闭")
        except Exception as exc:  # noqa: BLE001
            logger.warning("关闭 PG 连接池出错：%s", exc)
        _pg_pool = None

    if _neo4j_driver is not None:
        try:
            _neo4j_driver.close()
            logger.info("Neo4j Driver 已关闭")
        except Exception as exc:  # noqa: BLE001
            logger.warning("关闭 Neo4j Driver 出错：%s", exc)
        _neo4j_driver = None

    if _redis_client is not None:
        try:
            _redis_client.close()
            logger.info("Redis 客户端已关闭")
        except Exception as exc:  # noqa: BLE001
            logger.warning("关闭 Redis 客户端出错：%s", exc)
        _redis_client = None


def get_pg_pool():
    """取 PG 连接池。用法：with get_pg_pool().connection() as conn: ..."""
    if _pg_pool is None:
        raise RuntimeError("PG 连接池未初始化（应用需经 lifespan 启动，且 PG 需可达）")
    return _pg_pool


def get_neo4j_driver():
    """取 Neo4j Driver 单例。"""
    if _neo4j_driver is None:
        raise RuntimeError("Neo4j Driver 未初始化（应用需经 lifespan 启动）")
    return _neo4j_driver


def get_redis_client():
    """取 Redis 客户端单例。"""
    if _redis_client is None:
        raise RuntimeError("Redis 客户端未初始化（应用需经 lifespan 启动）")
    return _redis_client


def pool_stats() -> dict:
    """连接池统计（排查并发问题用，health 里可选返回）。"""
    if _pg_pool is None:
        return {}
    st = _pg_pool.get_stats()
    return {
        "poolSize": st.get("pool_size"),
        "poolAvailable": st.get("pool_available"),
        "requestsWaiting": st.get("requests_waiting"),
    }


def _mask(dsn: str) -> str:
    """把 DSN 里的密码打码，避免日志泄露。"""
    import re

    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", dsn)
