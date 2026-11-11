"""根目录 `test/` 的 pytest 引导。

被测代码在 `agent/app/` 下（`agent` 自己就是一个可 import 的包目录），所以把 `agent/`
插进 `sys.path`，测试里就能写 `from app.tools.common import ...`，不必把测试塞回 `agent/tests/`。
"""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
