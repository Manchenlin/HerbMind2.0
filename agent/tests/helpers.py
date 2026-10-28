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
