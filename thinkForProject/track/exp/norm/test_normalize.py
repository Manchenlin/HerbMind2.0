# -*- coding: utf-8 -*-
"""T-03 反向验收集：至少 20 组"形似但非等价"必须不被合并，另加正例防止"关掉转换就全过"。

用例分三类：
  MUST_NOT_MERGE  形似但非等价 —— normalize 后必须不相等（误合并会输出错误出处）
  MUST_MERGE      同词异写     —— normalize 后必须相等（否则查不到，属漏检）
  ORDER           顺序敏感用例 —— 证明"词组白名单早于字级繁简"这一顺序不是装饰

只测负例是不够的：把转换全关掉，所有负例都会通过。正例是这条防线的另一半。

运行：pytest test_normalize.py -q  或  python test_normalize.py
"""

from __future__ import annotations

import normalize as N

# 形似但非等价：不得合并
MUST_NOT_MERGE: list[tuple[str, str, str]] = [
    ("乾薑", "乾隆", "一对多字盲转的经典反例"),
    ("白朮", "白木", "异体与形近字"),
    ("已", "己", "形近字，共用一画差"),
    ("己", "巳", "形近字"),
    ("桂枝汤", "桂枝", "方名与药名"),
    ("桂枝汤", "桂枝加桂汤", "同名不同方"),
    ("桂枝汤", "桂枝芍药知母汤", "共享前缀的不同方"),
    ("桂枝汤", "桂枝汤方", "方名与带后缀的称谓"),
    ("小柴胡汤", "柴胡桂枝汤", "共享药名的不同方"),
    ("麻黄汤", "麻黄附子细辛汤", "共享药名的不同方"),
    ("四逆汤", "四逆散", "剂型不同即不同方"),
    ("白虎汤", "白虎加人参汤", "加减方不是原方"),
    ("大承气汤", "小承气汤", "一字之差的两方"),
    ("小承气汤", "调胃承气汤", "同族不同方"),
    ("茯苓", "茯神", "同株不同药用部位"),
    ("川芎", "川穹", "错别字不得被归一修掉"),
    ("桂枝", "桂技", "错别字不得被归一修掉"),
    ("附子", "付子", "错别字不得被归一修掉"),
    ("太阳中风", "太阳伤寒", "证候相近但不同"),
    ("少阳病", "少阴病", "一字之差的两经病"),
    ("生地黄", "熟地黄", "炮制不同即不同药"),
    ("甘草", "炙甘草", "炮制不同即不同药"),
    ("人参", "党参", "不同药材，不可当别名"),
    ("半夏", "法夏", "简称属名称层，由词表解决而非归一"),
    ("黄连", "黄柏", "不同药材"),
    ("大枣", "大棗核", "药材与药材部位"),
]

# 同词异写：必须合并
MUST_MERGE: list[tuple[str, str, str]] = [
    ("桂枝湯", "桂枝汤", "繁简"),
    ("白朮", "白术", "异体（词组白名单）"),
    ("麻黃", "麻黄", "繁简"),
    ("人參", "人参", "繁简（词组白名单）"),
    ("當歸", "当归", "繁简"),
    ("黃連", "黄连", "繁简"),
    ("生薑", "生姜", "繁简"),
    ("黃耆", "黄芪", "异体正名"),
    ("黄耆", "黄芪", "异体正名的简体形态"),
    ("脈浮", "脉浮", "异体"),
    ("太陽中風", "太阳中风", "繁简"),
    ("溫病條辨", "温病条辨", "繁简，书名"),
    ("傷寒論", "伤寒论", "繁简，书名"),
    ("乾薑", "干姜", "一对多字在词组内应转"),
    ("桂枝汤。", "桂枝汤", "标点删除"),
    ("桂枝 汤", "桂枝汤", "空白删除"),
    ("（桂枝汤）", "桂枝汤", "全角括号"),
    ("ＡＢＣ", "abc", "全半角与大小写"),
    ("桂枝汤\u200b", "桂枝汤", "零宽字符"),
    ("小柴胡湯", "小柴胡汤", "方名繁简"),
]

# 顺序敏感：先字级繁简会毁掉白名单保护
ORDER_CASES: list[tuple[str, str, str]] = [
    ("乾隆", "乾隆", "白名单保护：不得被转成干隆"),
    ("乾隆年", "乾隆年", "同一保护的更长形态"),
    ("著作", "著作", "著读 zhù 不转着"),
    ("显著", "显著", "同上"),
    ("乾薑", "干姜", "同一字在词组内必须转"),
]


def _check_not_merge() -> list[str]:
    bad = []
    for a, b, why in MUST_NOT_MERGE:
        if N.normalize(a) == N.normalize(b):
            bad.append(f"[误合并] {a!r} 与 {b!r} 归一后相同（{N.normalize(a)!r}）：{why}")
    return bad


def _check_merge() -> list[str]:
    bad = []
    for a, b, why in MUST_MERGE:
        if N.normalize(a) != N.normalize(b):
            bad.append(f"[漏合并] {a!r}->{N.normalize(a)!r} 与 {b!r}->{N.normalize(b)!r}：{why}")
    return bad


def _check_order() -> list[str]:
    bad = []
    for a, expect, why in ORDER_CASES:
        got = N.normalize(a)
        if got != expect:
            bad.append(f"[顺序] {a!r} 期望 {expect!r}，实际 {got!r}：{why}")
    return bad


def _check_idempotent() -> list[str]:
    bad = []
    samples = [a for a, _, _ in MUST_MERGE] + [a for a, _, _ in MUST_NOT_MERGE]
    for s in samples:
        once = N.normalize(s)
        twice = N.normalize(once)
        if once != twice:
            bad.append(f"[幂等] {s!r}: {once!r} != {twice!r}")
    return bad


# pytest 入口
def test_not_merge() -> None:
    assert _check_not_merge() == []


def test_merge() -> None:
    assert _check_merge() == []


def test_order() -> None:
    assert _check_order() == []


def test_idempotent() -> None:
    assert _check_idempotent() == []


def main() -> None:
    groups = [
        ("形似非等价（不得合并）", _check_not_merge(), len(MUST_NOT_MERGE)),
        ("同词异写（必须合并）", _check_merge(), len(MUST_MERGE)),
        ("顺序敏感", _check_order(), len(ORDER_CASES)),
        ("幂等", _check_idempotent(), len(MUST_MERGE) + len(MUST_NOT_MERGE)),
    ]
    total_bad = 0
    print(f"rules_version={N.RULES_VERSION}")
    for name, bad, n in groups:
        total_bad += len(bad)
        print(f"\n{name}：{n - len(bad)}/{n} 通过")
        for line in bad:
            print("  " + line)
    print(f"\n合计失败 {total_bad} 条")
    raise SystemExit(1 if total_bad else 0)


if __name__ == "__main__":
    main()
