"""工具返回值外壳与参数夹紧。

统一成 `{"ok", "hit", "count", "items", "hint", "notice"}` 六字段，理由：

- `ok=False`：工具**没跑成功**（库不可用、参数非法）。hint 说清原因，让模型换个方式或如实告诉用户；
- `hit=False`：工具跑成功了，但**库里确实没有**对应记录。hint 说明缺什么；
- 两者都必须带 hint —— 只返回空数组会让模型自己脑补一句"一般来说"，这正是设计红线二要禁的；
- `notice` 是红线免责声明，凡返回方剂/用药相关内容都非空。

工具**一律不抛异常**：抛出去会被上层当成"工具故障"，模型拿不到可读原因，
反而更容易编。异常统一转成 ok=False + hint。
"""

from __future__ import annotations

from typing import Any

# 红线段：不允许推断功效、不给剂量与处方建议
NOTICE_FACT = "以下内容为库内语料原文摘录，未做任何推断；本系统不推断功效、不给处方建议，仅供学习参考。"


def _envelope(
    *,
    ok: bool,
    items: list[dict[str, Any]] | None = None,
    hint: str = "",
    notice: str = "",
) -> dict[str, Any]:
    rows = items or []
    return {
        "ok": ok,
        "hit": ok and bool(rows),
        "count": len(rows),
        "items": rows,
        "hint": hint,
        "notice": notice,
    }


def ok_result(items: list[dict[str, Any]], notice: str = NOTICE_FACT) -> dict[str, Any]:
    """有命中。"""
    return _envelope(ok=True, items=items, notice=notice if items else "")


def miss_result(hint: str, notice: str = "") -> dict[str, Any]:
    """执行成功但无命中：hint 必须具体（缺什么 / 可以换成查什么）。"""
    return _envelope(ok=True, items=[], hint=hint, notice=notice)


def error_result(hint: str) -> dict[str, Any]:
    """工具自身失败（含参数非法、依赖不可用）。"""
    return _envelope(ok=False, items=[], hint=hint)


def clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    """把模型给的数字夹到合法区间。

    模型会传 0、负数、100、甚至字符串（"5"）。这里统一兜住：
    夹紧而不是报错 —— 报错只会让模型重试一次同样的错值，白烧一轮 token。
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(number, maximum))
