"""把「一本书被拆成三本」还原成一本书，并补回整章丢失的第一章。

背景（2026-11-11 实核）
----------------------
源文件 `中医经典方证原文.docx` 其实是**一本书**《中医经典方证案例研究》：
每页页眉都印这个书名，正文是 4 章 38 节（第一章理论部分 + 伤寒论 / 温病学 / 金匮要略 各一章）。

但库里当初按「章标题里的《…》」建了 3 本独立的书：

    bk_1 伤寒论 / bk_2 温病学 / bk_3 金匮要略

于是书名错了、层级错了，而且**第一章整章没入库**（它没有《…》，被当成"无书名"跳过）。

本脚本两步，都可单独跑、都可重复跑
----------------------------------
    step merge     3 本合 1 本：书名改回《中医经典方证案例研究》，三个章节点挂到同一本书下
    step chapter1  从 docx 解析第一章 3 节，写 book_node + content_unit + 向量

⚠ 能力边界（必须知道）
--------------------
第一章正文落在 `content_unit(unit_type='theory', ref_type='node')`，**目前检索不到**：
agent 的 retriever 只走 `ref_type = 'formula' | 'case'` 两路，目录详情接口也只列方剂/医案/条文。
所以这一步的产出是「目录能看见第一章、正文已入库且带向量」，接入检索与详情展示要另改检索侧/前端。

用法（**必须在本目录 database/etl 下运行**）
    python merge_book_and_import_chapter1.py --dry-run      # 只打印计划，不写库、不调 API
    python merge_book_and_import_chapter1.py                # 两步都做
    python merge_book_and_import_chapter1.py --step merge
    python merge_book_and_import_chapter1.py --step chapter1 --docx "D:/.../中医经典方证原文.docx"

回滚
----
merge 会删掉 bk_2 / bk_3 两行 book。真要回滚，用导入快照重来
（`bash scripts/init-data.sh scripts/herbmind_data.sql --reset`），或从备份恢复。
所以**执行前先备份**：`docker exec herbmind-v2-pg pg_dump -U postgres -d herbmind > backup.sql`
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from db import pg, query
from docx_outline import parse_outline
from docx_reader import clean_blocks, read_docx_blocks

# 复用已有的 embedding 实现（同一把 key、同一个模型、同一套重试与维度校验）
from sync_content_unit import _to_pgvector, embed_batch, load_llm_conf

BOOK_ID = "bk_1"
BOOK_TITLE = "中医经典方证案例研究"
# 作者由组长确认（2026-11-11）：现代 陈宝国。原先 bk_1 上写的「张仲景 / 汉」是第二章那部
# 经典的作者，不是这本编纂书的作者，合并时必须覆盖掉。
BOOK_AUTHOR = "陈宝国"
BOOK_DYNASTY = "现代"
MERGE_BOOK_IDS = ("bk_1", "bk_2", "bk_3")

DEFAULT_DOCX = r"D:\HomeWork\_KeYanShiJian\中医经典方证原文.docx"

# 第一章的章节点；节标题按序号自动编号（第一节/第二节/第三节）
CHAPTER1_ID = "n_h0"
CHAPTER1_SEQ = 1
SECTION_IDS = ("n_s01", "n_s02", "n_s03")

_CHAPTER_HEAD = re.compile(r"^第[一二三四五六七八九十]+章")
_SPACES = re.compile(r"\s+")
_CN = "一二三四五六七八九十"


def _norm_title(text: str) -> str:
    """标题里的连续空白压成一个空格（docx 里常见「第一章  经典·证治·案例」）。"""
    return _SPACES.sub(" ", text.strip())


def collect_chapter1(docx: Path) -> dict:
    """解析 docx 第一章：返回 {title, sections: [{title, text}]}。"""
    if not docx.exists():
        raise SystemExit(f"找不到 docx：{docx}")
    blocks = clean_blocks(read_docx_blocks(str(docx)))
    outline = parse_outline(blocks)
    if not outline:
        raise SystemExit("docx 里没解析出任何章，检查文件是否换版了")

    chapter = outline[0]
    sections = chapter.get("sections") or []
    if not sections:
        raise SystemExit(f"第一章《{chapter['title']}》下面没解析出节")

    # 本章结束位置 = 下一章第一节的起点；最后一章则到文末
    if len(outline) > 1 and outline[1].get("sections"):
        chapter_end = outline[1]["sections"][0]["start_index"]
    else:
        chapter_end = len(blocks)

    starts = [s["start_index"] for s in sections]
    out_sections = []
    for idx, sec in enumerate(sections):
        begin = starts[idx]
        end = starts[idx + 1] if idx + 1 < len(starts) else chapter_end
        # 剔除范围内混进来的「第X章 …」标题行（第二章的标题就在本区间末尾）
        body = [
            b.strip()
            for b in blocks[begin:end]
            if b.strip() and not _CHAPTER_HEAD.match(b.strip())
        ]
        title = f"第{_CN[idx]}节 {_norm_title(sec['title'])}"
        out_sections.append({"title": title, "text": "\n".join(body)})

    return {"title": _norm_title(chapter["title"]), "sections": out_sections}


def plan_merge() -> list[str]:
    """打印/返回合并计划，顺便做前置校验。已合并过则直接返回空计划（幂等）。"""
    rows = query("SELECT id, title FROM book ORDER BY id")
    got = [r[0] for r in rows]
    if got == [BOOK_ID] and rows[0][1] == BOOK_TITLE:
        return ["已经是合并后的状态（book 表只有一本《中医经典方证案例研究》），跳过"]
    if tuple(got) != MERGE_BOOK_IDS:
        raise SystemExit(
            f"book 表不是预期的三本（实际 {got}）。"
            "若是其它数据集，本脚本不适用；请先人工确认 book 表内容。"
        )
    lines = [
        f"书名：{BOOK_ID} 改为《{BOOK_TITLE}》，作者改为 {BOOK_AUTHOR} / {BOOK_DYNASTY}"
        "（原值「张仲景 / 汉」是第二章那部经典的作者，不是这本书的）",
    ]
    for table in ("book_node", "content_unit", "relation", "classic"):
        n = query(f"SELECT count(*) FROM {table} WHERE book_id = ANY(%s)", (list(MERGE_BOOK_IDS),))[0][0]
        lines.append(f"{table}: 现有 {n} 行，全部归到 {BOOK_ID}")
    lines.append("删除 book 行：bk_2 / bk_3")
    lines.append("章节点 seq 固定为 2/3/4（第一章留 1，由 chapter1 步骤写入）")
    return lines


def do_merge() -> None:
    with pg() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE book SET title = %s, author = %s, dynasty = %s, edition = NULL WHERE id = %s",
            (BOOK_TITLE, BOOK_AUTHOR, BOOK_DYNASTY, BOOK_ID),
        )
        for table in ("book_node", "content_unit", "relation", "classic"):
            cur.execute(
                f"UPDATE {table} SET book_id = %s WHERE book_id = ANY(%s)",
                (BOOK_ID, list(MERGE_BOOK_IDS)),
            )
        cur.execute("DELETE FROM book WHERE id = ANY(%s)", (["bk_2", "bk_3"],))
        for node_id, seq in (("n_h1", 2), ("n_h2", 3), ("n_h3", 4)):
            cur.execute("UPDATE book_node SET seq = %s WHERE id = %s", (seq, node_id))
    print("✔ 合并完成：3 本 → 1 本")


def do_chapter1(docx: Path, dry_run: bool) -> None:
    chapter = collect_chapter1(docx)
    print(f"第一章：{chapter['title']}，节数 {len(chapter['sections'])}")
    for sec in chapter["sections"]:
        print(f"  · {sec['title']}  正文 {len(sec['text'])} 字")

    sections = chapter["sections"]
    if len(sections) > len(SECTION_IDS):
        raise SystemExit(f"第一章节数 {len(sections)} 超过预留 id 数 {len(SECTION_IDS)}，先改 SECTION_IDS")

    if dry_run:
        print("\n【演练】未写库、未调 embedding")
        return

    base, key, model, dim = load_llm_conf()
    print(f"模型：{model}（期望 {dim} 维）")
    vectors = embed_batch(base, key, model, [s["text"] for s in sections])
    if len(vectors) != len(sections):
        raise SystemExit(f"返回向量数不符：要 {len(sections)}，得 {len(vectors)}")
    for sec, vec in zip(sections, vectors):
        if len(vec) != dim:
            raise SystemExit(f"{sec['title']} 向量维度 {len(vec)} ≠ {dim}，拒绝写入")

    meta = json.dumps(
        {"source": Path(docx).name, "chapter": chapter["title"]}, ensure_ascii=False
    )
    with pg() as conn, conn.cursor() as cur:
        # 章节点（parent 为空，seq=1 排在第二/三/四章之前）
        cur.execute(
            """INSERT INTO book_node (id, book_id, parent_id, node_type, title, seq, path_text)
               VALUES (%s, %s, NULL, 'chapter', %s, %s, %s)
               ON CONFLICT (id) DO UPDATE
                 SET book_id = EXCLUDED.book_id, node_type = EXCLUDED.node_type,
                     title = EXCLUDED.title, seq = EXCLUDED.seq, path_text = EXCLUDED.path_text""",
            (CHAPTER1_ID, BOOK_ID, chapter["title"], CHAPTER1_SEQ, chapter["title"]),
        )
        for idx, (sec, vec) in enumerate(zip(sections, vectors)):
            node_id = SECTION_IDS[idx]
            cur.execute(
                """INSERT INTO book_node (id, book_id, parent_id, node_type, title, seq, path_text)
                   VALUES (%s, %s, %s, 'section', %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE
                     SET book_id = EXCLUDED.book_id, parent_id = EXCLUDED.parent_id,
                         node_type = EXCLUDED.node_type, title = EXCLUDED.title,
                         seq = EXCLUDED.seq, path_text = EXCLUDED.path_text""",
                (node_id, BOOK_ID, CHAPTER1_ID, sec["title"], idx + 1, f"{chapter['title']}/{sec['title']}"),
            )
            cur.execute(
                """INSERT INTO content_unit
                     (id, book_id, unit_type, ref_type, ref_id, title, content, embedding, meta_jsonb)
                   VALUES (%s, %s, 'theory', 'node', %s, %s, %s, %s::vector, %s::jsonb)
                   ON CONFLICT (id) DO UPDATE
                     SET book_id = EXCLUDED.book_id, unit_type = EXCLUDED.unit_type,
                         ref_type = EXCLUDED.ref_type, ref_id = EXCLUDED.ref_id,
                         title = EXCLUDED.title, content = EXCLUDED.content,
                         embedding = EXCLUDED.embedding, meta_jsonb = EXCLUDED.meta_jsonb""",
                (
                    f"cu_th{idx + 1}",
                    BOOK_ID,
                    node_id,
                    sec["title"],
                    sec["text"],
                    _to_pgvector(vec),
                    meta,
                ),
            )
    print("✔ 第一章写入完成（book_node 4 行 + content_unit 3 行，均带 1024 维向量）")


_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_int(text: str) -> int | None:
    """中文序号转数字：一→1、十→10、十一→11、二十一→21。"""
    if not text:
        return None
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = _CN_DIGITS.get(left, 1) if left else 1
        ones = _CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    return _CN_DIGITS.get(text)


def fix_seq(dry_run: bool) -> None:
    """按标题里的中文序号补 `seq`。

    为什么要修：旧数据所有节点的 seq 都是 0，`BookNodeService.tree()` 只按 seq 升序排，
    于是同一层级内实际顺序由数据库返回顺序决定 —— 实测第二章的「第一节 太阳病方证案例」
    被排到了最后，前端目录看起来是错的。这里只改 seq，不动任何标题/父子关系。
    """
    rows = query(
        "SELECT id, node_type, title, seq FROM book_node WHERE book_id = %s ORDER BY id",
        (BOOK_ID,),
    )
    updates: list[tuple[int, str, str]] = []
    for node_id, node_type, title, seq in rows:
        if node_type == "chapter":
            continue  # 章的 seq 已由 merge 固定为 1~4
        match = (
            re.match(r"^第([一二三四五六七八九十]+)节", title)
            if node_type == "section"
            else re.match(r"^([一二三四五六七八九十]+)、", title)
        )
        if not match:
            continue
        num = _cn_to_int(match.group(1))
        if num is None or num == seq:
            continue
        updates.append((num, node_id, title))

    print(f"需要修正 seq 的节点：{len(updates)} / {len(rows)}")
    for num, node_id, title in updates[:5]:
        print(f"  · {node_id} seq={num}  {title}")
    if len(updates) > 5:
        print(f"  … 其余 {len(updates) - 5} 个同理")
    if dry_run or not updates:
        if dry_run:
            print("【演练】未写库")
        return

    with pg() as conn, conn.cursor() as cur:
        for num, node_id, _title in updates:
            cur.execute("UPDATE book_node SET seq = %s WHERE id = %s", (num, node_id))
    print("✔ 排序修正完成")


def main() -> int:
    ap = argparse.ArgumentParser(description="合并书 + 补第一章")
    ap.add_argument("--step", choices=("all", "merge", "chapter1", "seq"), default="all")
    ap.add_argument("--docx", type=Path, default=Path(DEFAULT_DOCX), help="源 docx 路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写库、不调 API")
    args = ap.parse_args()

    if args.step in ("all", "merge"):
        print("== 合并三本书 ==\n  " + "\n  ".join(plan_merge()))
        if args.dry_run:
            print("\n【演练】未写库")
        else:
            do_merge()

    if args.step in ("all", "chapter1"):
        print("\n== 补第一章 ==")
        do_chapter1(args.docx, args.dry_run)

    if args.step in ("all", "seq"):
        print("\n== 修正节点排序 ==")
        fix_seq(args.dry_run)

    return 0



if __name__ == "__main__":
    sys.exit(main())
