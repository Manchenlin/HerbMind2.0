"""HerbMind Agent 服务入口（域3 智能域，:8091）。

当前阶段：已实现：
    GET  /api/agent/health        服务自身 + LLM 配置 + PG/Neo4j/Redis 探测
    POST /api/agent/ask/sync      同步问答（检索 + 工具取证 + 大模型，带引用与工具轨迹）
    POST /api/agent/ask           流式问答（SSE：retrieval → tool* → citation → token → done）
    POST /api/agent/formula/diff  方剂加减查证（纯规则，零大模型，不推断功效）
    GET  /api/agent/history       会话历史（读 agent_conversation / agent_message）

工具数据源（2026-10-31 起）：四个工具不再直连 PG/Neo4j，改走 svc-catalog / svc-search /
svc-graph 的 `/internal/**`，与 BFF 同一份检索口径。`AGENT_TOOLS_ENABLED=false` 可整体回退到单轮 RAG。

尚未实现（按 project_plan/09_API契约清单.md §10 逐个补，不要提前写进文档谎报）：
    POST /api/agent/coach          辨证教练（契约只有端点，没有字段细则）
    POST /api/agent/grade          结构化评分（同上）

启动（在 agent/ 目录下）：
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8091
经网关访问：http://localhost:8080/api/agent/health
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.clients import close_clients, init_clients
from app.config import get_settings
from app.db import close_resources, init_resources
from app.routers import ask, formula, health, history
from app.schemas import R

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("herbmind-agent")

settings = get_settings()

# Swagger UI 的静态资源目录（本地化，见下方 /docs 路由）
STATIC_DIR = Path(__file__).resolve().parent / "static"


async def _warmup_embedding() -> None:
    """后台预热 embedding 通道。

    实测首次调用 bge-m3 要 10~14 秒（TLS 握手 + 服务端模型冷启动），第二次只要 200~300ms。
    启动时先在后台打一发，用户第一次提问就不用干等。
    失败只记 warning：没网/没额度也不影响服务启动，等真用时再报错。
    """
    from app.llm import embed_query

    try:
        t0 = time.perf_counter()
        await embed_query("预热")
        logger.info("embedding 预热完成：%.0fms", (time.perf_counter() - t0) * 1000)
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding 预热失败（不影响正常使用）：%s", exc)


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
    # 工具要访问各 svc 的 /internal，HTTP 客户端也在这里建（单例连接池）
    init_clients(settings)
    warmup = asyncio.create_task(_warmup_embedding()) if settings.llm_configured else None
    try:
        yield
    finally:
        if warmup is not None:
            warmup.cancel()
        await close_clients()
        close_resources()
        logger.info("Agent 服务已关闭")


app = FastAPI(
    title="HerbMind Agent 服务",
    description=(
        "域3 智能域。已实现：GET /api/agent/health、POST /api/agent/ask/sync、"
        "POST /api/agent/ask（SSE 流式，带工具取证轨迹）、POST /api/agent/formula/diff（加减查证）、"
        "GET /api/agent/history（会话历史）；待实现：coach / grade"
    ),
    version=settings.app_version,
    lifespan=lifespan,
    # 关掉默认的 /docs /redoc：它们从 jsdelivr CDN 拉 swagger-ui / redoc 资源，
    # 国内网络会被 RST（控制台报 net::ERR_CONNECTION_RESET + SwaggerUIBundle is not defined），
    # 页面一片空白。/docs 由下方路由用本地静态资源重建。
    docs_url=None,
    redoc_url=None,
)

# 本地静态资源（swagger-ui 的 js/css/图标），放 agent/app/static/ 下随代码一起走
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/docs", include_in_schema=False)
async def swagger_ui_docs():
    """本地化的接口文档页：不依赖任何外网 CDN，断网/内网也能打开。"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon-32x32.png",
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
app.include_router(ask.router, prefix="/api/agent")
app.include_router(formula.router, prefix="/api/agent")
app.include_router(history.router, prefix="/api/agent")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志：每个请求一行「方法 路径 -> 状态码 耗时」，并回写 X-Request-Id 便于追踪。"""
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    # 存进 state：全局异常处理器据此给 500 响应补回 X-Request-Id
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        cost_ms = (time.perf_counter() - start) * 1000
        # 堆栈由全局异常处理器统一打印一次，这里只留摘要，避免同一异常刷两遍
        logger.warning(
            "%s %s -> 未处理异常 (%.1fms) req=%s",
            request.method,
            request.url.path,
            cost_ms,
            request_id,
        )
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


@app.exception_handler(StarletteHTTPException)
async def on_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """HTTPException（401 鉴权失败 / 404 等）也套 R 外壳，前端只写一套解析。

    FastAPI 默认对 HTTPException 返回 {"detail": "..."}，与业务错误的
    {code,msg,data} 不是一种格式，所以这里统一掉。
    """
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content=R.fail(exc.status_code, str(exc.detail)).model_dump(by_alias=True),
        headers={"X-Request-Id": request_id} if request_id else None,
    )


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
    request_id = getattr(request.state, "request_id", "")
    logger.exception("未捕获异常 %s req=%s", request.url.path, request_id)
    return JSONResponse(
        status_code=500,
        content=R.fail(500, f"服务内部错误：{type(exc).__name__}").model_dump(by_alias=True),
        # 异常路径不经过中间件的统一写头，这里补回，保证 500 也能对上日志
        headers={"X-Request-Id": request_id} if request_id else None,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=False,
    )
