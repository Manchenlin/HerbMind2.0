"""根目录 `test/` 的 pytest 引导。

被测代码分散在两个位置：

- `agent/`：本身是可 import 的包目录，插进 `sys.path` 后写 `from app.tools.common import ...`；
- `database/etl/`：目录名带连字符不能当包，且目录里没有 `__init__.py`（现有脚本就是
  `from db import pg` 这种同目录导入），所以直接把该目录插进 `sys.path`，测试里写
  `import docx_reader`。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for extra in (ROOT / "agent", ROOT / "database" / "etl"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
