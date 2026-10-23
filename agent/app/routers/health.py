"""GET /api/agent/health —— 健康检查（契约 §10 中唯一的白名单端点）。

返回：服务自身 + LLM 配置状态 + PG / Neo4j / Redis 探测结果。
探测并行执行，最坏 2 秒左右返回；任一依赖不通 → status=degraded（不是 500）。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.config import get_settings
from app.db import pool_stats
from app.probes import probe_neo4j, probe_postgres, probe_redis
from app.schemas import HealthData, R

router = APIRouter(tags=["agent"])


@router.get("/health", response_model=R[HealthData], summary="健康检查")
async def health() -> R[HealthData]:
    s = get_settings()

    # 三个探测都是阻塞 SDK，丢线程池并行跑（连接已复用，不再每次握手）
    pg, neo4j, redis_status = await asyncio.gather(
        asyncio.to_thread(probe_postgres),
        asyncio.to_thread(probe_neo4j),
        asyncio.to_thread(probe_redis),
    )
    deps = {"postgres": pg, "neo4j": neo4j, "redis": redis_status}
    all_ok = all(d.ok for d in deps.values())

    data = HealthData(
        status="ok" if all_ok else "degraded",
        service=s.app_name,
        version=s.app_version,
        llm={
            "provider": s.llm_api_base,
            "model": s.llm_model,
            "embeddingModel": s.embedding_model,
            "configured": s.llm_configured,
        },
        deps=deps,
        pg_pool=pool_stats(),
    )
    return R.ok(data, msg="success" if all_ok else "部分依赖不可用，详见 deps")
