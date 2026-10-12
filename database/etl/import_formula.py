"""方证与条文种子（幂等）：3 方 + 剂量明细 + 5 条文。

运行：python import_formula.py
"""
from db import execute

# (id, name, node_id, efficacy, syndrome_text, page)
FORMULAS = [
    ("f_mh", "麻黄汤", "n_fz_ch2_s1_c1", "发汗解表，宣肺平喘", "外感风寒表实证：无汗而喘、脉浮紧", "19-21"),
    ("f_gz", "桂枝汤", "n_fz_ch2_s1_c1", "解肌发表，调和营卫", "外感风寒表虚证：汗出恶风、脉浮缓", "22-24"),
    ("f_gg", "葛根汤", "n_fz_ch2_s1_c1", "发汗解表，升津舒筋", "太阳伤寒兼项背强几几", "24-26"),
]

# (formula_id, herb_name, dose, unit, role, seq)
HERBS = [
    ("f_mh", "麻黄", 9, "g", "君", 1), ("f_mh", "桂枝", 6, "g", "臣", 2),
    ("f_mh", "杏仁", 9, "g", "佐", 3), ("f_mh", "甘草", 3, "g", "使", 4),
    ("f_gz", "桂枝", 9, "g", "君", 1), ("f_gz", "白芍", 9, "g", "臣", 2),
    ("f_gz", "生姜", 9, "g", "佐", 3), ("f_gz", "大枣", 4, "枚", "佐", 4),
    ("f_gz", "甘草", 6, "g", "使", 5),
    ("f_gg", "葛根", 12, "g", "君", 1), ("f_gg", "麻黄", 9, "g", "臣", 2),
    ("f_gg", "桂枝", 6, "g", "臣", 3), ("f_gg", "白芍", 6, "g", "佐", 4),
    ("f_gg", "生姜", 9, "g", "佐", 5), ("f_gg", "大枣", 4, "枚", "佐", 6),
    ("f_gg", "甘草", 6, "g", "使", 7),
]

# (id, article_no, classic_id, content, page)
QUOTES = [
    ("q_1", "1", "c_sh", "太阳之为病，脉浮，头项强痛而恶寒。", "3"),
    ("q_2", "2", "c_sh", "太阳病，发热，汗出，恶风，脉缓者，名为中风。", "3"),
    ("q_3", "3", "c_sh", "太阳病，或已发热，或未发热，必恶寒，体痛，呕逆，脉阴阳俱紧者，名为伤寒。", "3"),
    ("q_35", "35", "c_sh", "太阳病，头痛发热，身疼腰痛，骨节疼痛，恶风，无汗而喘者，麻黄汤主之。", "19"),
    ("q_96", "96", "c_sh", "伤寒五六日中风，往来寒热，胸胁苦满，嘿嘿不欲饮食，心烦喜呕……小柴胡汤主之。", "48"),
]


def main():
    for f in FORMULAS:
        execute(
            """INSERT INTO formula(id,name,node_id,efficacy,syndrome_text,page)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
            f,
        )
    for h in HERBS:
        execute(
            """INSERT INTO formula_herb(formula_id,herb_name,dose,unit,role,seq)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            h,
        )
    for q in QUOTES:
        execute(
            """INSERT INTO classic_quote(id,article_no,classic_id,content,page)
               VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
            q,
        )
    print("import_formula: ok (formula=3, formula_herb=16, classic_quote=5)")


if __name__ == "__main__":
    main()
