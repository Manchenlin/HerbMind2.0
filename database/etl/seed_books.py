"""种子：灌入 book / classic / book_node（幂等）。

运行：python seed_books.py
"""
from db import execute

BOOKS = [
    ("fz", "中医经典方证案例研究", "fz", "陈宝国 主编", "现代", "已发布"),
    ("sh", "伤寒论", "fz", "张仲景", "汉", "整理中"),
]

CLASSICS = [
    ("c_fz", "fz", "中医经典方证案例研究", "方证", "现代"),
    ("c_sh", "sh", "伤寒论", "伤寒", "汉"),
]

# (id, book_id, classic_id, parent_id, node_type, title, seq)
NODES = [
    ("n_fz_ch2", "fz", "c_fz", None,       "chapter",  "第二章《伤寒论》方证案例研究", 2),
    ("n_fz_ch2_s1", "fz", "c_fz", "n_fz_ch2", "section", "第一节 太阳病", 1),
    ("n_fz_ch2_s1_c1", "fz", "c_fz", "n_fz_ch2_s1", "category", "一、太阳伤寒类方证", 1),
    ("n_sh_ch1", "sh", "c_sh", None,       "chapter",  "辨太阳病脉证并治（上）", 1),
    ("n_sh_ch1_s1", "sh", "c_sh", "n_sh_ch1", "section", "太阳病提纲", 1),
]


def main():
    for b in BOOKS:
        execute(
            """INSERT INTO book(id,title,book_type,author,dynasty,ingest_status)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
            b,
        )
    for c in CLASSICS:
        execute(
            """INSERT INTO classic(id,book_id,name,abbr,dynasty)
               VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
            c,
        )
    for n in NODES:
        execute(
            """INSERT INTO book_node(id,book_id,classic_id,parent_id,node_type,title,seq)
               VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
            n,
        )
    print("seed_books: ok (book=2, classic=2, book_node=5)")


if __name__ == "__main__":
    main()
