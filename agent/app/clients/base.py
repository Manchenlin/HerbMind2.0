"""各 svc `/internal/**` 的统一 HTTP 客户端。

为什么要有这一层，而不是让每个工具自己 `httpx.get`：

- **连接池单例**：一次问答可能连调 3 个 svc，每次新建连接都要付握手成本；
- **错误口径只在这里解析**：svc 的 `/internal` **成功返回裸 DTO、失败返回 `R{code,msg}`**
  （4000 参数错 / 4040 实体不存在 / 5000 依赖不可用），这条约定只落在这一个文件里，
  工具层只认 `SvcError`，不必各自判断响应体长什么样；
- **超时统一**：connect=1s / read=5s，某个 svc 卡死时把损失限制在单次工具调用内。

`/internal/**` 不进网关、没有鉴权，只允许容器内网/本机访问；agent 是它的调用方之一。

生命周期与 `app/db.py` 同款：`main.py` 的 lifespan 里 `init_clients()` / `await close_clients()`。
但这里额外允许**惰性创建**：工具纪律是「一律不抛异常」，不能因为忘了 init 就把
"依赖不可用"变成一次未捕获异常（模型拿不到可读原因，只会换个说法再编一遍）。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("herbmind-agent")

# svc 名 → (配置字段名, 中文名)。新增 svc 时只改这张表 + config.py + .env.example
_SVC_META: dict[str, tuple[str, str]] = {
    "catalog": ("svc_catalog_url", "目录服务"),
    "search": ("svc_search_url", "检索服务"),
    "graph": ("svc_graph_url", "图谱服务"),
}

# 连接池上限：3~5 人的项目，20 条并发连接远超实际需要，同时给工具循环留足余量
_MAX_CONNECTIONS = 20

# `httpx.AsyncClient` 的连接池绑定**创建它的事件循环**。生产（uvicorn 单 loop）不会出问题，
# 但单测/脚本里 `asyncio.run()` 每次一个新 loop，复用旧 client 会炸在
# `RuntimeError: Event loop is closed`（已在 test_tools 集成层实测踩到）。
# 所以记下创建时的 loop，换 loop 就丢弃重建（旧的一致已随旧 loop 关闭，不能 aclose）。
_client: httpx.AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


class SvcError(Exception):
    """调用 svc 的 `/internal` 失败。

    Attributes:
        status: HTTP 状态码；**0 表示根本没连上**（连接被拒 / 超时 / 地址未配置）。
            工具层据此区分「查不到（404 → hit=false）」与「服务坏了（0/5xx → ok=false）」。
        msg:   给人看的原因，优先取 svc 返回的 `R.msg`。
        svc:   出错的 svc 名（catalog / search / graph），用于日志与提示文案。
    """

    def __init__(self, status: int, msg: str, svc: str = "") -> None:
        self.status = int(status)
        self.msg = msg
        self.svc = svc
        super().__init__(f"{svc or 'svc'}({status}): {msg}")

    @property
    def label(self) -> str:
        """中文服务名，用于拼给模型看的 hint。"""
        return _SVC_META.get(self.svc, ("", "服务"))[1]

    @property
    def unreachable(self) -> bool:
        """是否属于「服务侧不可用」（连不上 / 超时 / 5xx）。"""
        return self.status == 0 or self.status >= 500


def init_clients(s: Settings | None = None) -> None:
    """创建全局 HTTP 客户端（幂等：重复调用不会重建，避免漏关旧客户端）。"""
    global _client, _client_loop
    if _client is not None:
        return

    cfg = s or get_settings()
    try:
        _client_loop = asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的 loop（例如在同步代码里预热），交给第一次 get_client 时记录
        _client_loop = None
    _client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=cfg.svc_connect_timeout,
            read=cfg.svc_read_timeout,
            write=cfg.svc_read_timeout,
            pool=2.0,
        ),
        limits=httpx.Limits(
            max_connections=_MAX_CONNECTIONS,
            max_keepalive_connections=10,
        ),
        headers={"Accept": "application/json"},
    )
    logger.info(
        "svc HTTP 客户端已创建（connect=%.1fs read=%.1fs 上限 %d）：catalog=%s search=%s graph=%s",
        cfg.svc_connect_timeout,
        cfg.svc_read_timeout,
        _MAX_CONNECTIONS,
        cfg.svc_catalog_url,
        cfg.svc_search_url,
        cfg.svc_graph_url,
    )


async def close_clients() -> None:
    """关闭全局客户端（lifespan 退出时调用；异常只告警，不拦服务退出）。"""
    global _client, _client_loop
    if _client is None:
        return
    try:
        await _client.aclose()
        logger.info("svc HTTP 客户端已关闭")
    except Exception as exc:  # noqa: BLE001
        logger.warning("关闭 svc HTTP 客户端出错：%s", exc)
    _client = None
    _client_loop = None


def get_client() -> httpx.AsyncClient:
    """取全局客户端；未初始化或事件循环已换时惰性创建（见模块 docstring 的说明）。"""
    global _client, _client_loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if _client is not None and _client_loop is None:
        # 同步预热时没有 running loop，`_client_loop` 只记成了 None；现在有 loop 了，补绑定即可。
        # 不补的话会被下面的分支当成"换了循环"，把一个健康客户端连同连接池白白丢掉（泄漏 + 多一次建连）。
        _client_loop = loop
    elif _client is not None and _client_loop is not loop:
        # 换 loop 了（典型场景：单测每个用例一个 asyncio.run）：旧连接池绑在已关闭的 loop 上，
        # 复用会抛 "Event loop is closed"。不调用 aclose —— 旧 loop 已死，直接丢掉重建。
        logger.debug("事件循环已变化，重建 svc HTTP 客户端")
        _client = None

    if _client is None:
        init_clients()
    assert _client is not None  # init_clients 要么成功要么抛，这里只是给类型检查看
    return _client


def svc_base_url(svc: str) -> str:
    """取某个 svc 的 base url（去掉尾部斜杠）。"""
    field, _label = _SVC_META.get(svc, ("", ""))
    if not field:
        raise ValueError(f"未知的 svc：{svc}")
    return str(getattr(get_settings(), field, "") or "").rstrip("/")


async def get_json(svc: str, path: str, params: dict[str, Any] | None = None) -> Any:
    """GET 一个 `/internal` 接口，返回**裸 JSON**（2xx 时不拆 R 外壳）。"""
    return await _request(svc, "GET", path, params=params)


async def post_json(svc: str, path: str, body: Any | None = None) -> Any:
    """POST 一个 `/internal` 接口，返回**裸 JSON**。"""
    return await _request(svc, "POST", path, json=body)


async def _request(
    svc: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any | None = None,
) -> Any:
    """统一请求出口：成功返裸 JSON，失败一律抛 `SvcError`。"""
    field, label = _SVC_META.get(svc) or (None, None)
    if field is None:
        raise ValueError(f"未知的 svc：{svc}")

    base = svc_base_url(svc)
    if not base:
        raise SvcError(0, f"{label}地址未配置（{field.upper()}）", svc)

    # None 值的查询参数不要发出去：httpx 会把它们拼成 "herb=None" 这样的字符串
    clean = {k: v for k, v in (params or {}).items() if v is not None and v != ""}

    try:
        resp = await get_client().request(method, f"{base}{path}", params=clean, json=json)
    except httpx.TimeoutException:
        raise SvcError(0, f"{label}响应超时", svc) from None
    except httpx.HTTPError as exc:
        # 连接被拒 / DNS 失败 / 连接被重置：都是"服务不可达"，不该让模型以为是"查不到"
        raise SvcError(0, f"{label}不可达（{type(exc).__name__}）", svc) from None

    if 200 <= resp.status_code < 300:
        try:
            return resp.json()
        except ValueError:
            raise SvcError(resp.status_code, f"{label}返回的不是 JSON", svc) from None

    raise SvcError(resp.status_code, _error_msg(resp), svc)


def _error_msg(resp: httpx.Response) -> str:
    """从错误响应里取一句人话：先 `R.msg`，再 Spring 的 `detail`，最后退化成状态码。"""
    try:
        body = resp.json()
    except ValueError:
        text = (resp.text or "").strip()
        return text[:120] or f"HTTP {resp.status_code}"

    if isinstance(body, dict):
        for key in ("msg", "detail", "message"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return f"HTTP {resp.status_code}"
