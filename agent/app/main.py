"""HerbMind Agent 服务入口（域3 智能域，:8091）。

当前阶段：**骨架**。已实现：
    GET /api/agent/health   服务自身 + LLM 配置 + PG/Neo4j/Redis 探测

尚未实现（按 project_plan/09_API契约清单.md §10 逐个补，不要提前写进文档谎报）：
    POST /api/agent/ask            SSE 流式问答
    POST /api/agent/ask/sync       同步问答
    GET  /api/agent/history        会话历史
    POST /api/agent/coach          辨证教练
    POST /api/agent/formula/diff   加减推演
    POST /api/agent/grade          结构化评分（供 BFF 编排调用）

启动（在 agent/ 目录下）：
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8091
经网关访问：http://localhost:8080/api/agent/health
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import close_resources, init_resources
from app.routers import health
from app.schemas import R

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("herbmind-agent")

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动/关闭钩子（替代 FastAPI 已废弃的 @app.on_event）。

    在这里建/关外部资源：PG 连接池、Neo4j Driver、Redis 客户端。
    PG 连不上只记 error 不崩服务 —— 由 health 报告依赖状态。
    """
    logger.info(
        "Agent 服务启动：env_port=%s model=%s embedding=%s key_configured=%s",
        settings.app_port,
        settings.llm_model,
        settings.embedding_model,
        settings.llm_configured,
    )
    init_resources(settings)
    try:
        yield
    finally:
        close_resources()
        logger.info("Agent 服务已关闭")


app = FastAPI(
    title="HerbMind Agent 服务",
    description="域3 智能域：问答 / 辨证教练 / 评分 / 图谱（当前仅骨架 + health）",
    version=settings.app_version,
    lifespan=lifespan,
)

# 前端本地开发直连时用得上；正式环境经网关 8080，不需要前端直连 8091
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 所有业务路由统一挂在 /api/agent 下（与网关路由规则一致）
app.include_router(health.router, prefix="/api/agent")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志：每个请求一行「方法 路径 -> 状态码 耗时」，并回写 X-Request-Id 便于追踪。"""
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        cost_ms = (time.perf_counter() - start) * 1000
        logger.exception("%s %s -> 500 (%.1fms) req=%s", request.method, request.url.path, cost_ms, request_id)
        raise
    cost_ms = (time.perf_counter() - start) * 1000
    # 健康检查太频繁时可降为 debug，先保留 info 便于本地观察
    logger.info(
        "%s %s -> %s (%.1fms) req=%s",
        request.method,
        request.url.path,
        response.status_code,
        cost_ms,
        request_id,
    )
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """参数校验失败也套 R 外壳，前端不用区分两种错误格式。"""
    logger.warning("参数校验失败 %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=400,
        content=R.fail(400, "参数校验失败").model_dump(by_alias=True),
    )


@app.exception_handler(Exception)
async def on_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """兜底：任何未捕获异常都转成 R 外壳，避免前端拿到裸 500 HTML。"""
    logger.exception("未捕获异常 %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=R.fail(500, f"服务内部错误：{type(exc).__name__}").model_dump(by_alias=True),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=False,
    )
