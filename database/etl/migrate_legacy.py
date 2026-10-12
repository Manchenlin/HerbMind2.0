"""旧库 → 新库 迁移（M1 正式数据导入）。

旧库（herbmind-pg:latest / PostgreSQL 16，库 herbmind）表：
  classic / formula / formula_herb / case_record / classic_quote
  rag_chunk（含 1024 维向量）/ book_chapter / book_section / book_category / case_quote_rel
新库（v2 DDL）：book / classic / book_node / formula / formula_herb / case_record /
  case_section / classic_quote / content_unit / relation

要点：
  · 新库 ID 为 TEXT，用前缀区分来源域（bk_/c_/n_h|n_s|n_g/f_/cs_/sec_/q_/cu_）
  · **向量原样搬运**（不重算 embedding，省云额度）
  · 幂等：先清空目标内容表，再全量导入

用法：
  python migrate_legacy.py
环境变量：OLD_DSN（默认 5433）、PG_DSN（新库，默认 5432）
"""
import os
import sys

import psycopg2
from psycopg2.extras import execute_values

OLD_DSN = os.getenv("OLD_DSN", "postgresql://herbmind:herbmind123@localhost:5433/herbmind")
NEW_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/herbmind")

# 需先清空的目标表（本库仅为阶段0 打样数据，清空安全）
TARGETS = [
    "relation", "content_unit", "case_section", "case_record",
    "classic_quote", "formula_herb", "formula", "book_node", "classic", "book",
]


def old():
    return psycopg2.connect(OLD_DSN)


def new():
    return psycopg2.connect(NEW_DSN)


def q(cur, sql, args=None):
    cur.execute(sql, args)
    return cur.fetchall()


def main():
    o, n = old(), new()
    oc, nc = o.cursor(), n.cursor()

    print("== 清空新库目标表 ==")
    nc.execute("TRUNCATE " + ", ".join(TARGETS) + " CASCADE")

    # ---------- 1) book（每个经典 = 一本书） ----------
    rows = q(oc, "SELECT id, name, author, dynasty FROM classic")
    execute_values(nc, """INSERT INTO book(id,title,book_type,author,dynasty,ingest_status)
                          VALUES %s""",
                   [(f"bk_{i}", name, "fz", author, dynasty, "已发布") for i, name, author, dynasty in rows])
    print(f"book: {len(rows)}")

    # ---------- 2) classic ----------
    rows = q(oc, "SELECT id, name, abbr, dynasty FROM classic")
    execute_values(nc, "INSERT INTO classic(id,book_id,name,abbr,dynasty) VALUES %s",
                   [(f"c_{i}", f"bk_{i}", name, abbr, dynasty) for i, name, abbr, dynasty in rows])
    print(f"classic: {len(rows)}")

    # ---------- 3) book_node（旧三表 → 单树） ----------
    chapters = q(oc, "SELECT id, classic_id, title, seq FROM book_chapter")
    sections = q(oc, "SELECT s.id, s.chapter_id, s.title, s.seq, c.classic_id "
                     "FROM book_section s JOIN book_chapter c ON c.id = s.chapter_id")
    cats = q(oc, "SELECT g.id, g.section_id, g.title, g.seq, c.classic_id "
                 "FROM book_category g JOIN book_section s ON s.id = g.section_id "
                 "JOIN book_chapter c ON c.id = s.chapter_id")
    nodes = []
    for i, cid, title, seq in chapters:
        nodes.append((f"n_h{i}", f"bk_{cid}", f"c_{cid}", None, "chapter", title, seq or 0))
    for i, chid, title, seq, cid in sections:
        nodes.append((f"n_s{i}", f"bk_{cid}", f"c_{cid}", f"n_h{chid}", "section", title, seq or 0))
    for i, seid, title, seq, cid in cats:
        nodes.append((f"n_g{i}", f"bk_{cid}", f"c_{cid}", f"n_s{seid}", "category", title, seq or 0))
    execute_values(nc, """INSERT INTO book_node(id,book_id,classic_id,parent_id,node_type,title,seq)
                          VALUES %s""", nodes)
    print(f"book_node: {len(nodes)}")

    # ---------- 4) formula（node_id 由 rag_chunk.meta 的 category 反查） ----------
    meta = {}
    for st, sid, m in q(oc, "SELECT source_type, source_id, meta_jsonb FROM rag_chunk"):
        meta[(st, sid)] = m or {}
    cat_by_title = {title: nid for nid, title in q(nc, "SELECT id, title FROM book_node WHERE node_type='category'")}

    rows = q(oc, "SELECT id, name, alias, efficacy, page FROM formula")
    payload = []
    for i, name, alias, syndrome, page in rows:
        m = meta.get(("formula", i), {})
        node_id = cat_by_title.get(m.get("category"))
        payload.append((f"f_{i}", name, alias, syndrome, str(page) if page else None, node_id))
    execute_values(nc, """INSERT INTO formula(id,name,alias,syndrome_text,page,node_id)
                          VALUES %s""", payload)
    print(f"formula: {len(payload)}")

    # ---------- 5) formula_herb（dose text → numeric，role 空，seq 按原顺序） ----------
    rows = q(oc, "SELECT formula_id, herb_name, dose, unit, id FROM formula_herb ORDER BY formula_id, id")
    seq = {}
    payload = []
    for fid, herb, dose, unit, _ in rows:
        seq[fid] = seq.get(fid, 0) + 1
        try:
            d = float(dose) if dose not in (None, "", "—") else None
        except (TypeError, ValueError):
            d = None
        payload.append((f"f_{fid}", herb, d, unit, seq[fid]))
    execute_values(nc, """INSERT INTO formula_herb(formula_id,herb_name,dose,unit,seq)
                          VALUES %s""", payload)
    print(f"formula_herb: {len(payload)}")

    # ---------- 6) case_record（syndrome 取自 rag_chunk.meta） ----------
    rows = q(oc, "SELECT id, title, main_formula_id, page, meta_jsonb FROM case_record")
    payload = []
    for i, title, mfid, page, m in rows:
        syn = (m or {}).get("syndrome") or meta.get(("case", i), {}).get("syndrome")
        payload.append((f"cs_{i}", title, "case", f"f_{mfid}" if mfid else None, syn, str(page) if page else None))
    execute_values(nc, """INSERT INTO case_record(id,title,unit_type,main_formula_id,syndrome_text,page)
                          VALUES %s""", payload)
    print(f"case_record: {len(payload)}")

    # ---------- 7) case_section（case_text → 案例原文；analysis_raw → 按语） ----------
    rows = q(oc, "SELECT id, case_text, analysis_raw FROM case_record")
    payload = []
    for i, ct, ar in rows:
        if ct:
            payload.append((f"sec_{i}_1", f"cs_{i}", "案例原文", ct, 1))
        if ar:
            payload.append((f"sec_{i}_2", f"cs_{i}", "按语", ar, 2))
    execute_values(nc, """INSERT INTO case_section(id,case_id,kind,content,seq) VALUES %s""", payload)
    print(f"case_section: {len(payload)}")

    # ---------- 8) classic_quote ----------
    rows = q(oc, "SELECT id, article_no, classic_id, content, page FROM classic_quote")
    execute_values(nc, """INSERT INTO classic_quote(id,article_no,classic_id,content,page)
                          VALUES %s""",
                   [(f"q_{i}", ano, f"c_{cid}", content, str(page) if page else None)
                    for i, ano, cid, content, page in rows])
    print(f"classic_quote: {len(rows)}")

    # ---------- 9) content_unit（向量原样搬运） ----------
    book_by_title = {title: bid for bid, title in q(nc, "SELECT id, title FROM book")}
    rows = q(oc, """SELECT id, source_type, source_id, chunk_type, content, meta_jsonb, embedding::text
                    FROM rag_chunk ORDER BY id""")
    payload = []
    for i, st, sid, ctype, content, m, vec in rows:
        m = m or {}
        title = m.get("formula") or m.get("classic") or st
        ref_id = f"f_{sid}" if st == "formula" else f"cs_{sid}"
        payload.append((f"cu_{i}", book_by_title.get(m.get("classic")), ctype, st, ref_id,
                        title, content, vec, psycopg2.extras.Json(m)))
    execute_values(nc, """INSERT INTO content_unit(id,book_id,unit_type,ref_type,ref_id,title,content,embedding,meta_jsonb)
                          VALUES %s""", payload)
    print(f"content_unit: {len(payload)}")

    # ---------- 10) relation（旧 case_quote_rel） ----------
    rows = q(oc, "SELECT case_id, quote_id FROM case_quote_rel")
    execute_values(nc, """INSERT INTO relation(from_type,from_id,rel_type,to_type,to_id)
                          VALUES %s ON CONFLICT DO NOTHING""",
                   [("case", f"cs_{c}", "cites", "quote", f"q_{qid}") for c, qid in rows])
    print(f"relation: {len(rows)}")

    o.close()
    n.commit()
    n.close()
    print("\nmigrate_legacy: ok")


if __name__ == "__main__":
    sys.exit(main())
