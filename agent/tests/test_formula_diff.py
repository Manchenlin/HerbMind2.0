"""加减查证的断言测试。

原则：**所有断言的事实都来自库内可逐味核对的数据，不凭印象写**（设计红线五）。
尤其是 `test_ma_huang_jia_ge_gen_is_not_ge_gen_tang` —— 它钉死的正是当初凭印象记错的那条。

跑法（用 conda 环境 herbmind 的 python，两种等价，均已实测通过）：
    # 1) pytest（herbmind 环境已装 pytest 9.1.1）
    python -m pytest agent/tests -q                        # 在仓库根目录
    python -m pytest tests/test_formula_diff.py -q         # 在 agent/ 目录

    # 2) 不依赖 pytest 的直跑（文件末尾自带汇总器）
    python tests/test_formula_diff.py                      # 在 agent/ 目录

两种方式都靠文件头部 `os.chdir(AGENT_DIR)` 定位 agent/.env，因此从哪个目录调用都可以。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 让 `from app...` 能导入，且让 config 的 env_file=".env" 找得到 agent/.env
AGENT_DIR = Path(__file__).resolve().parents[1]
os.chdir(AGENT_DIR)
sys.path.insert(0, str(AGENT_DIR))

from app.config import get_settings          # noqa: E402
from app.db import close_resources, init_resources  # noqa: E402
from app.rag import formula_diff             # noqa: E402


def setup_module(_module) -> None:
    init_resources(get_settings())


def teardown_module(_module) -> None:
    close_resources()


# ==================== 正向：能命中的加减 ====================


def test_zhi_ke_jia_ge_gen() -> None:
    """桂枝汤(5 味) + 葛根 = 桂枝加葛根汤(6 味)。"""
    r = formula_diff.diff("桂枝汤", add=["葛根"])

    assert r["base"]["herbs"] == ["桂枝", "芍药", "生姜", "大枣", "甘草"]
    assert set(r["resultHerbs"]) == {"葛根", "桂枝", "芍药", "生姜", "大枣", "甘草"}
    assert r["added"] == ["葛根"]
    assert r["removed"] == []
    assert "桂枝加葛根汤" in {m["name"] for m in r["matchedFormulas"]}
    assert r["matchHint"] == ""


def test_da_cheng_qi_jian_mang_xiao() -> None:
    """大承气汤 − 芒硝 = 小承气汤；顺带验证同名重复收录不报错。"""
    r = formula_diff.diff("大承气汤", remove=["芒硝"])

    assert set(r["resultHerbs"]) == {"大黄", "厚朴", "枳实"}
    assert r["removed"] == ["芒硝"]
    assert "小承气汤" in {m["name"] for m in r["matchedFormulas"]}
    # 库里 f_23 与 f_175 都叫大承气汤 → 应提示重复收录，而不是抛"对应多个方剂"
    assert any("重复收录" in w for w in r["warnings"])


def test_lookup_by_id() -> None:
    """支持用方剂 ID 指定。"""
    r = formula_diff.diff("f_5")
    assert r["base"]["name"] == "桂枝汤"
    assert r["base"]["id"] == "f_5"


# ==================== 核心反例 ====================


def test_ma_huang_jia_ge_gen_is_not_ge_gen_tang() -> None:
    """★ 麻黄汤 + 葛根 ≠ 葛根汤（当初凭印象记错的那条，钉死它）。

    麻黄汤 = 麻黄/桂枝/杏仁/甘草（4 味）
    葛根汤 = 葛根/麻黄/桂枝/芍药/生姜/大枣/甘草（7 味，**无杏仁**）
    麻黄汤加葛根只有 5 味且仍含杏仁，两者并不相同。
    """
    r = formula_diff.diff("麻黄汤", add=["葛根"])
    print(r)

    assert set(r["resultHerbs"]) == {"麻黄", "桂枝", "杏仁", "甘草", "葛根"}
    assert "葛根汤" not in {m["name"] for m in r["matchedFormulas"]}
    # 未命中必须给出说明，不能静默返回空列表让人以为系坏了
    assert r["matchHint"]

    # 近似方里可以出现葛根汤，但必须明确标注"并非同一方"
    similar = {s["name"]: s for s in r["similarFormulas"]}
    if "葛根汤" in similar:
        assert "并非同一方" in similar["葛根汤"]["note"]


def test_same_herbs_different_formula() -> None:
    """桂枝汤 与 桂枝加桂汤 药味完全相同（仅桂枝剂量不同）→ 必须如实返回多个命中。

    这是「组成相同 ≠ 同一方」的活证据，与《金匮要略》小承气汤/厚朴三物汤/厚朴大黄汤同理。
    系统不能武断只挑一个，也不能说"这是同一个方"。
    """
    r = formula_diff.diff("桂枝汤")

    assert r["doseCompared"] is False, "本库无剂量，必须明确声明没有比对剂量"
    assert "剂量" in r["notice"]
    # 药味相同的另一方应出现在命中列表里
    assert "桂枝加桂汤" in {m["name"] for m in r["matchedFormulas"]}


# ==================== 红线：不得输出功效推断 ====================


def test_no_efficacy_inference() -> None:
    """红线一：响应中不得出现任何功效推断字段；efficacy 只能是语料原文透传。"""
    r = formula_diff.diff("桂枝汤", add=["葛根"])

    forbidden = {
        "efficacyChange", "predictedEfficacy", "newEfficacy",
        "suggestion", "recommendation", "advice", "dosage",
    }
    assert not (forbidden & set(r.keys())), f"出现了禁止的推断字段：{forbidden & set(r.keys())}"

    for m in r["matchedFormulas"]:
        assert isinstance(m["efficacy"], str)   # 原样透传库里字段，可能为空串


def test_notice_present() -> None:
    """红线三：必须带免责声明。"""
    r = formula_diff.diff("桂枝汤")
    assert "不构成处方建议" in r["notice"] or "仅供学习参考" in r["notice"]


# ==================== 边界与告警 ====================


def test_remove_not_in_base_warns() -> None:
    r = formula_diff.diff("桂枝汤", remove=["附子"])
    assert r["removed"] == []
    assert any("不在基础方组成中" in w for w in r["warnings"])


def test_add_duplicate_warns() -> None:
    r = formula_diff.diff("桂枝汤", add=["桂枝"])
    assert r["added"] == []
    assert any("基础方里已有" in w for w in r["warnings"])


def test_add_unknown_herb_warns() -> None:
    r = formula_diff.diff("桂枝汤", add=["完全不存在的药"])
    assert any("均未出现" in w for w in r["warnings"])


def test_suspicious_herb_name_warns() -> None:
    """库里有 `不哎咀)上以水` 这类解析残留，用户传入时要提示。"""
    r = formula_diff.diff("桂枝汤", add=["矾石(烧)等分。"])
    assert any("疑似原文解析残留" in w for w in r["warnings"])


def test_unknown_formula_raises() -> None:
    try:
        formula_diff.diff("根本没有这个方")
    except ValueError as exc:
        assert "未找到" in str(exc)
    else:
        raise AssertionError("不存在的方剂应当抛 ValueError")


def test_empty_add_remove() -> None:
    """不加不减：结果应等于基础方本身。"""
    r = formula_diff.diff("麻黄汤")
    assert r["resultHerbs"] == r["base"]["herbs"]
    assert r["added"] == [] and r["removed"] == []


if __name__ == "__main__":
    # 不依赖 pytest 也能直跑：逐个执行并汇总
    import traceback

    init_resources(get_settings())
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
    close_resources()
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
