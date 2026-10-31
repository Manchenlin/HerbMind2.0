"""pytest 公共夹具：TestClient + 限流计数器重置。

为什么需要 conftest：`os.chdir(agent/)` 与 `sys.path` 必须**在任何 `app.*` 导入之前**完成，
否则 `config.py` 的 `.env` 读不到、`from app...` 也导入不了。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 先让 tests/ 可被导入，再 import helpers（helpers 内部会补 AGENT_DIR 到 sys.path 并 chdir）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from helpers import fake_client  # noqa: E402

from app.routers import ask as ask_router  # noqa: E402


@pytest.fixture
def client():
    """不跑 lifespan 的 TestClient：零外部依赖。"""
    return fake_client()


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """限流计数是模块级全局字典，用例之间必须清空。

    否则跑满 20 次的用例会把后续用例顶成 429（且失败原因看起来毫无关联）。
    """
    ask_router._rate_hits.clear()
    yield
    ask_router._rate_hits.clear()


@pytest.fixture(autouse=True)
def disable_agent_tools(monkeypatch):
    """默认关闭工具调用循环。

    原因：`app/agent/runner.py` 会真的 `get_chat_model().bind_tools()` 再发一次决策请求。
    本机 `.env` 里有真实 key，问答用例若不关就会真联网、真烧额度，还会因模型波动偶发超时
    （表现为"测试时快时慢"，很难定位）。

    测工具链路的用例（`test_agent_loop.py` / `test_ask_memory.py`）在自己内部显式打开，
    并替换 `get_chat_model` 为假模型。
    """
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "agent_tools_enabled", False)
    yield
