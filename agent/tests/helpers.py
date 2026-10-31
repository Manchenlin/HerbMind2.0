"""测试公共工具：路径定位 / 假数据 / SSE 报文解析 / TestClient 工厂。

分层原则（关系到"跑测试前要不要先起 Docker"）：
- 本目录下**除 `test_formula_diff.py` 外**，一律不连 PG / Neo4j / Redis / 大模型：
  检索与 LLM 全部用 monkeypatch 替换 → 不装中间件也能全绿。
- 只有 `test_formula_diff.py` 是直连真实库的集成测试（库里有 245 方，断言要逐味核对）。

TestClient 的两个坑（实测 starlette 1.9.0 / httpx 0.28.1）：
1. **不要用 `with TestClient(app)`**：那会跑 lifespan → 建 PG 连接池 + 后台预热 embedding（真网络调用）。
   直接 `TestClient(app)` 发请求时 lifespan 不执行，正好符合"零外部依赖"。
2. 注册了全局 `Exception` 兜底处理器后，`raise_server_exceptions=True`（默认）会把异常重新抛给测试，
   拿不到 500 响应 → 要验兜底处理器必须 `fake_client(raise_server_exceptions=False)`。
"""

from __future__ import annotations

import atexit
import json
import os
import sys
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

# config.py 的 env_file=".env" 是相对 cwd 的，必须切到 agent/ 才读得到真实配置；
# 而 main.py / llm.py 在模块级就 get_settings()，所以这一步只能在导入期做。
# 代价是 chdir 对全进程生效 → 记下原 cwd 并在进程退出时还原，
# 避免之后任何走相对路径的代码（子进程、日志文件）被静默带偏。
_ORIGINAL_CWD = os.getcwd()
os.chdir(AGENT_DIR)
atexit.register(os.chdir, _ORIGINAL_CWD)

from fastapi.testclient import TestClient  # noqa: E402

from app.rag.retriever import RetrievedUnit  # noqa: E402


def make_unit(
    id: str = "cu_1",
    ref_type: str = "formula",
    ref_id: str | None = None,
    title: str = "麻黄汤",
    content: str = "组成：麻黄、桂枝、杏仁、甘草",
    score: float = 0.72,
) -> RetrievedUnit:
    """造一条召回结果（字段与真实检索返回一致）。

    ref_id 不传时按类型给默认值：写死 f_1 会造出「case + f_1」这种库里不存在的组合，
    下游对 refId 的断言就失去意义了。
    """
    return RetrievedUnit(
        id=id,
        ref_type=ref_type,
        ref_id=ref_id or ("f_1" if ref_type == "formula" else "cs_3"),
        title=title,
        content=content,
        score=score,
    )


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """把 SSE 响应体拆成 [{"event": 事件名, "data": 已解析的 JSON}]。

    顺便验证了协议本身：每个 data 必须是单行 JSON，否则 json.loads 会抛。
    """
    events: list[dict[str, Any]] = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        name: str | None = None
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data_lines.append(line[len("data: ") :])
        events.append(
            {"event": name, "data": json.loads("\n".join(data_lines)) if data_lines else None}
        )
    return events


def event_names(events: list[dict[str, Any]]) -> list[str]:
    """只取事件名序列，便于断言顺序。"""
    return [str(e["event"]) for e in events]


def fake_client(**kwargs: Any) -> TestClient:
    """建一个不跑 lifespan 的 TestClient（不碰任何外部服务）。"""
    from app.main import app

    return TestClient(app, **kwargs)


# 集成测试的环境守卫：探一次、结果缓存住。
# 缓存是必须的 —— 每次调用 init_resources() 都会新建一个连接池并覆盖全局单例，
# 旧池不会被关掉，多探几次就会在进程里留下一堆没人用的池。
_PG_STATE: dict[str, str | None] = {"checked": "no", "reason": None}


def _ensure_resources() -> None:
    """确保外部资源已初始化。

    只在"没有池 / 池已关闭"时才 init：`test_formula_diff` 的 teardown 会 close_resources()，
    后续模块再查库时池是关着的，必须重建；但重复 init 又会漏池，所以要判断。
    """
    from app import db
    from app.config import get_settings

    pool = db._pg_pool
    if pool is None or getattr(pool, "closed", False):
        db.init_resources(get_settings())


def pg_ready() -> str | None:
    """PG 是否可用且有数据：返回 None=可用，否则返回人类可读的不可用原因。"""
    if _PG_STATE["checked"] == "yes":
        return _PG_STATE["reason"]

    from app.db import get_pg_pool

    reason: str | None = None
    try:
        _ensure_resources()
        with get_pg_pool().connection(timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM formula")
                formulas = cur.fetchone()[0]
        # 只连通不够：快照没导时同样会一片红，且报错信息毫无指向性
        if formulas < 200:
            reason = f"PG 可连但数据缺失（formula 仅 {formulas} 行，应有 245 行）：请先导入快照"
    except Exception as exc:  # noqa: BLE001
        reason = (
            f"PG 不可用（{type(exc).__name__}: {exc}）："
            "请先 bash scripts/start-infra.sh 并导入快照"
        )

    _PG_STATE["checked"] = "yes"
    _PG_STATE["reason"] = reason
    return reason


def neo4j_ready() -> str | None:
    """Neo4j 是否可用：返回 None=可用，否则返回原因。"""
    from app.db import get_neo4j_driver

    try:
        _ensure_resources()
        with get_neo4j_driver().session() as session:
            session.run("RETURN 1").consume()
        return None
    except Exception as exc:  # noqa: BLE001
        return f"Neo4j 不可用（{type(exc).__name__}: {exc}）：请先 bash scripts/start-infra.sh"


# ==================== svc 守卫（工具迁移后的集成测试入口） ====================
# 工具已不再直连 PG/Neo4j，而是打 svc 的 /internal，所以集成测试要探 svc 而不是库。
# 同样缓存探测结果：每个模块都探一次会白等好几个超时。
_SVC_STATE: dict[str, str | None] = {}


def _svc_probe(name: str, url: str, params: dict[str, Any] | None = None) -> str | None:
    """探一个 svc 的 /internal 接口：返回 None=可用，否则返回原因。"""
    if name in _SVC_STATE:
        return _SVC_STATE[name]

    import httpx

    reason: str | None = None
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(url, params=params or {})
        if resp.status_code >= 400:
            reason = f"{name} 返回 {resp.status_code}：确认 svc 已启动且数据库已导快照"
    except Exception as exc:  # noqa: BLE001
        reason = (
            f"{name} 不可达（{type(exc).__name__}: {exc}）："
            "请先起后端 svc（mvn spring-boot:run）再跑集成测试"
        )

    _SVC_STATE[name] = reason
    return reason


def svc_search_ready() -> str | None:
    """svc-search 是否可用（工具 search_* / semantic_recall 的数据源）。"""
    from app.clients.base import svc_base_url

    return _svc_probe(
        "svc-search",
        f"{svc_base_url('search')}/internal/search",
        {"q": "麻黄汤", "type": "formula", "size": 1},
    )


def svc_graph_ready() -> str | None:
    """svc-graph 是否可用（工具 graph_neighbors 的数据源）。"""
    from app.clients.base import svc_base_url

    return _svc_probe(
        "svc-graph",
        f"{svc_base_url('graph')}/internal/graph/neighbors",
        {"entity": "麻黄汤", "label": "Formula", "hops": 1},
    )
