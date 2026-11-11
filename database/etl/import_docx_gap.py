"""把 docx 里没进 content_unit 的正文补录成「节级补充单元」（R2）。

背景
----
旧库 `rag_chunk` 的切分以 `【问题】` 为锚点，锚点之外的节首概述、病机论述、
医案辨证按语在切分时被丢掉。docx 清洗后 7,939 段正文，库里只有 538 个单元，
逐段比对后有 630 段真叙述（约 3.8 万字）从未入库。

做法（方案 A：不动存量）
------------------------
另起一类单元挂到节节点上，**一条存量数据都不改**：

    unit_type = 'section_abstract'
    ref_type  = 'node'
    ref_id    = 所属节节点 id（节节点缺失时挂到父章）
    id        = cu_gap_<节点id>_<序号>   ← 执行前先删自己的前缀，天然幂等

排除项（不算正文缺失）：目录点线页、章/节标题行、`【原文回顾】` 这类纯标记行。

排序
----
`meta_jsonb->>'page'` 取「该段之前最近一个已入库段落的页码」，让补充单元落在原书对应位置；
同一页内由后端 `BookMapper.unitsOfNode` 让补充单元排在原文单元之前。

用法
----
    python import_docx_gap.py --check      # 只报告缺口与计划（默认），不写库、不调 API
    python import_docx_gap.py --dry-run    # 额外打印计划中的单元样例
    python import_docx_gap.py --apply      # 正式写库 + 补向量（会调用 embedding API）

写库只 DELETE `id LIKE 'cu_gap_%'`，不 TRUNCATE、不碰其余 538 条。
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx_outline import fix_ocr  # noqa: E402
from docx_reader import TABLE_PLACEHOLDER, clean_blocks, read_docx_blocks  # noqa: E402
from sync_content_unit import _to_pgvector, embed_batch, load_llm_conf  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

DOCX = Path(r"D:\HomeWork\_KeYanShiJian\中医经典方证原文.docx")
PG_DSN = "postgresql://postgres:postgres@localhost:5432/herbmind"

_CH = re.compile(r"^第[一二三四五六七八九十]+章")
_SEC = re.compile(r"^第[一二三四五六七八九十]+节")
_MARK_ONLY = re.compile(r"^【[^】]{1,8}】$")  # 整段只有一个标记，如【原文回顾】
_HEADING_MAX = 40  # 标题段长度上限；超过这个长度的是目录页被压成的长段落
UNIT_MAX_CHARS = 1200  # 单个补充单元的字数上限
GAP_PREFIX = "cu_gap_"
EMBED_BATCH = 16


def norm(s: str) -> str:
    return re.sub(r"[\s\u3000]+", "", s or "")


# ================================================================ docx 侧


def is_toc_block(b: str) -> bool:
    """目录页：几百字的点线 + 「(数字」页码。"""
    t = norm(b)
    if t in {"目录", "目次"}:
        return True
    return len(t) > 200 and (t.count("…") >= 3 or len(re.findall(r"\(\d{1,3}", t)) >= 3)


def toc_pages(docx: Path) -> dict[str, str]:
    """从目录表格解析「标题 → 页码」，返回 norm(标题) → '19'。"""
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    out: dict[str, str] = {}
    if body is None:
        return out
    for child in body:
        if child.tag != W + "tbl":
            continue
        for tr in child.findall(W + "tr"):
            cells = [
                "".join(n.text or "" for n in tc.iter(W + "t")).strip()
                for tc in tr.findall(W + "tc")
            ]
            if len(cells) < 3:
                continue
            title = norm(cells[0])
            m = re.search(r"(\d{1,4})", cells[-1])
            if title and m and "…" in cells[1]:
                out.setdefault(title, m.group(1))
    return out


def parse_marks(blocks: list[str]) -> list[dict]:
    """抽出章/节标题的位置：`[{index, kind, title}]`，顺序与正文一致。"""
    marks: list[dict] = []
    for i, b in enumerate(blocks):
        t = fix_ocr(b.strip())
        if len(t) > _HEADING_MAX:
            continue
        if _CH.match(t):
            # 正文里重复出现的「第一章」这种极简行没有书名，无法定位，跳过
            if len(norm(t)) <= 3:
                continue
            marks.append({"index": i, "kind": "chapter", "title": t})
        elif _SEC.match(t):
            marks.append({"index": i, "kind": "section", "title": t})
    return marks


def _cell_text(tc) -> str:
    return "".join(n.text or "" for n in tc.iter(W + "t")).strip()


def extract_real_tables(docx: Path) -> list[dict]:
    """抽出真正的表格（78 个里只有 2 个），带所属节和前面的锚段。"""
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    if body is None:
        return []
    chapter = sec = ""
    anchors: list[str] = []
    out: list[dict] = []
    for child in body:
        if child.tag == W + "p":
            t = "".join(n.text or "" for n in child.iter(W + "t")).strip()
            if not t:
                continue
            ft = fix_ocr(t)
            if len(ft) <= _HEADING_MAX and _CH.match(ft):
                # 每页页眉都印章标题；同章重复出现时不能把当前节重置掉，
                # 否则节内表格会被判成「只属于章」
                if ft != chapter:
                    chapter, sec = ft, ""
            elif len(ft) <= _HEADING_MAX and _SEC.match(ft):
                sec = ft
            anchors.append(ft)
            if len(anchors) > 6:
                anchors.pop(0)
        elif child.tag == W + "tbl":
            rows = [[_cell_text(tc) for tc in tr.findall(W + "tc")] for tr in child.findall(W + "tr")]
            flat = "".join("".join(r) for r in rows)
            if "…" in flat and len(flat) > 200:  # 目录点线页
                continue
            if len(rows) < 2:  # 单行且不是目录的，不具备表格信息量
                continue
            out.append({"rows": rows, "chapter": chapter, "section": sec, "anchors": list(anchors)})
    return out


def table_to_text(rows: list[list[str]]) -> tuple[str, str]:
    """把表格转成「一行一条」的可读文本，返回 (标题, 正文)。"""
    head = [c.replace(" ", "") for c in rows[0]]
    if len(head) >= 4:  # 行式：首行表头，首列是方名
        lines = []
        for r in rows[1:]:
            cells = [f"{head[i]}：{r[i]}" for i in range(1, min(len(head), len(r))) if r[i].strip()]
            if r and r[0].strip():
                lines.append(f"{r[0].strip()}——" + "；".join(cells))
        return f"方证比较（{'、'.join(r[0].strip() for r in rows[1:])}）", "\n".join(lines)

    left = head[1] if len(head) > 1 else ""
    right = head[2] if len(head) > 2 else ""
    lines = [f"比较项：{left} / {right}"]
    for r in rows[1:]:
        dim = r[0].strip() if r else ""
        a = r[1].strip() if len(r) > 1 else ""
        b = r[2].strip() if len(r) > 2 else ""
        if a and b:
            lines.append(f"{dim}：{left}——{a}；{right}——{b}")
        elif a or b:
            lines.append(f"{dim}：{a or b}")
    return f"方证比较（{left} / {right}）", "\n".join(lines)


def build_table_units(
    docx: Path, by_title: dict[str, tuple[str, str]], sec_groups: dict[str, dict]
) -> list[dict]:
    """把真表格生成补录单元（unit_type='table'）。"""
    units: list[dict] = []
    for t in extract_real_tables(docx):
        nid, _how = match_node(t["section"], "section", by_title, None)
        if not nid:
            print(f"  [跳过表格] 无法定位节点：{t['section'] or t['chapter']}")
            continue
        title, content = table_to_text(t["rows"])
        if not content.strip():
            continue
        sec_key = norm(t["section"])
        page = lesson_first_page(sec_groups, sec_key)
        g_sec = sec_groups.get(sec_key)
        if g_sec is not None:  # 用表格前面最近的锚段定位页码
            for a in reversed(t["anchors"]):
                pos = g_sec["text"].find(norm(a))
                if pos >= 0:
                    page = page_from_pos(pos, g_sec) or page
                    break
        units.append(
            {
                "id": f"{GAP_PREFIX}{nid}_t{len(units) + 1:02d}",
                "node_id": nid,
                "title": title,
                "page": page,
                "content": content,
                "chars": len(norm(content)),
                "paras": len(t["rows"]),
                "chapter": t["chapter"],
                "section": t["section"],
                "seq": 900 + len(units),
                "unit_type": "table",
            }
        )
    return units


# ================================================================ 库侧


def pg():
    return psycopg2.connect(PG_DSN)


def load_nodes(cur) -> tuple[dict[str, tuple[str, str]], str]:
    """返回 (norm标题 → (节点id, 节点标题), 默认 book_id)。"""
    cur.execute("SELECT id, title, book_id FROM book_node ORDER BY id")
    by_title: dict[str, tuple[str, str]] = {}
    book_id = ""
    for nid, title, bid in cur.fetchall():
        if not nid.startswith("n_"):  # 章 n_h / 节 n_s / 类 n_g，其余前缀不是目录节点
            continue
        by_title.setdefault(norm(title), (nid, title))
        book_id = book_id or (bid or "")
    return by_title, book_id


def load_corpus(cur) -> str:
    """全库正文串，只用于「节级语料缺失」时的兜底判断。

    排除自己写的 `cu_gap_*`：否则重跑时补录内容会被当成「已入库」，
    计划变成空表，幂等就废了。
    """
    cur.execute("SELECT content FROM content_unit WHERE id NOT LIKE %s ORDER BY id", (f"{GAP_PREFIX}%",))
    return "".join(norm(r[0] or "") for r in cur.fetchall())


def load_section_texts(cur) -> dict[str, dict]:
    """按节把已有单元正文拼成独立串，供「节内定位页码」用。

    为什么必须按节隔离：全库正文是按 id 拼的、不是按原书页序，同一句话在别的章节
    也出现过时会把位置反查到别的节（实测把第二章的概述定位到了第 304 页）。
    节内拼接后，前一个已入库段落的页码就是本节的真实位置。
    """
    cur.execute(
        """SELECT coalesce(meta_jsonb->>'section',''), coalesce(meta_jsonb->>'page',''), content
           FROM content_unit
           WHERE coalesce(meta_jsonb->>'section','') <> '' AND id NOT LIKE %s
           ORDER BY id""",
        (f"{GAP_PREFIX}%",),
    )
    groups: dict[str, dict] = {}
    for sec, page, content in cur.fetchall():
        g = groups.setdefault(norm(sec), {"text": "", "offsets": [], "pages": []})
        g["offsets"].append(len(g["text"]))
        g["pages"].append(page or "")
        g["text"] += norm(content)
    return groups


def lesson_first_page(groups: dict[str, dict], sec_key: str) -> str:
    """节首页码：该节已有单元里页码最小的那个，用于节内定位失败时兜底。"""
    g = groups.get(sec_key)
    if not g:
        return ""
    best: tuple[int, str] | None = None
    for page in g["pages"]:
        m = re.search(r"(\d{1,4})", page or "")
        if m and (best is None or int(m.group(1)) < best[0]):
            best = (int(m.group(1)), page)
    return best[1] if best else ""


def page_from_pos(pos: int, g: dict) -> str:
    lo, hi = 0, len(g["offsets"]) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if g["offsets"][mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return g["pages"][lo]


def match_node(
    title: str,
    kind: str,
    by_title: dict[str, tuple[str, str]],
    chapter_id: str | None,
) -> tuple[str | None, str]:
    """标题 → 节点 id。精确优先，其次模糊（OCR 变体），失败退回当前章。"""
    key = norm(title)
    hit = by_title.get(key)
    if hit:
        return hit[0], "精确"
    best = difflib.get_close_matches(key, list(by_title), n=1, cutoff=0.72)
    if best:
        ratio = difflib.SequenceMatcher(None, key, best[0]).ratio()
        return by_title[best[0]][0], f"模糊{ratio:.2f}"
    if kind == "section" and chapter_id:
        return chapter_id, "退回父章"
    return None, "未匹配"


# ================================================================ 计划


def build_plan(docx: Path) -> tuple[list[dict], dict]:
    blocks = clean_blocks(read_docx_blocks(docx))
    marks = parse_marks(blocks)
    pages_by_title = toc_pages(docx)

    with pg() as conn, conn.cursor() as cur:
        by_title, book_id = load_nodes(cur)
        corpus = load_corpus(cur)
        sec_groups = load_section_texts(cur)

    # 段落 → (节点id, 节点标题, 节标题)
    owner: list[tuple[str | None, str, str]] = []
    chapter_id: str | None = None
    chapter_title = ""
    section_id: str | None = None
    section_title = ""
    mi = 0
    for i in range(len(blocks)):
        while mi < len(marks) and marks[mi]["index"] == i:
            m = marks[mi]
            nid, _how = match_node(m["title"], m["kind"], by_title, chapter_id)
            if m["kind"] == "chapter":
                chapter_id, chapter_title = nid, m["title"]
                section_id, section_title = None, ""
            else:
                section_id, section_title = nid, m["title"]
            mi += 1
        node = section_id or chapter_id
        owner.append((node, section_title or chapter_title, chapter_title))

    # 按节点归集缺口段落（保持原书顺序）
    groups: dict[str, dict] = {}
    order: list[str] = []
    skipped = {"toc": 0, "mark": 0, "heading": 0, "no_node": 0, "table": 0, "noise": 0}
    gap_paras = 0
    gap_chars = 0
    last_sec = None
    last_page = ""

    for i, b in enumerate(blocks):
        node_id, node_title, chap_title = owner[i]
        text = fix_ocr(b.strip())
        nb = norm(b)

        # 换节就重置「当前位置页码」，避免上一节的页码串到本节
        if norm(node_title) != last_sec:
            last_sec, last_page = norm(node_title), ""

        # 是否已入库：优先在本节语料里找（顺带拿到本节内的真实页码）
        g_sec = sec_groups.get(last_sec)
        if g_sec is not None:
            pos = g_sec["text"].find(nb)
            if pos >= 0:
                last_page = page_from_pos(pos, g_sec) or last_page
                continue
        elif nb in corpus:  # 该节没有节级单元（如第一章理论节），退回全库判断
            continue

        if b == TABLE_PLACEHOLDER:  # 表格单独处理，不进正文补录
            skipped["table"] += 1
            continue
        if is_toc_block(b):
            skipped["toc"] += 1
            continue
        if _MARK_ONLY.match(text):
            skipped["mark"] += 1
            continue
        if len(text) <= _HEADING_MAX and (_CH.match(text) or _SEC.match(text)):
            skipped["heading"] += 1
            continue
        # 页眉残留与 OCR 变体标题：短且带「案例研究」的都不是正文
        # （实测「甲乙经典方证案例研究」「第二早《伤寒论》力证案例研究」）
        if "案例研究" in text and len(norm(text)) <= 25:
            skipped["noise"] += 1
            continue
        if not node_id:
            skipped["no_node"] += 1
            continue

        gap_paras += 1
        gap_chars += len(norm(text))
        if node_id not in groups:
            groups[node_id] = {"nodeTitle": node_title, "chapter": chap_title, "items": []}
            order.append(node_id)
        groups[node_id]["items"].append({"text": text, "chars": len(nb), "page": last_page})

    # 每个节点内按字数合并成单元
    plan: list[dict] = []
    for node_id in order:
        g = groups[node_id]
        seq = 0
        cur_chunk: list[dict] = []
        size = 0

        def flush(chunk: list[dict]) -> None:
            nonlocal seq
            if not chunk:
                return
            seq += 1
            # 页优先用「本单元首段之前最近一个已入库段落」的页码（节内定位，不会串节）；
            # 该节一个已入库段落都没有时，退到节首页码 / 目录表格里的页码
            sec_key = norm(g["nodeTitle"])
            page = chunk[0]["page"] or lesson_first_page(sec_groups, sec_key)
            if not page:
                num = pages_by_title.get(sec_key)
                page = f"第{num}页" if num else ""
            plan.append(
                {
                    "id": f"{GAP_PREFIX}{node_id}_{seq:03d}",
                    "node_id": node_id,
                    "title": g["nodeTitle"],
                    "page": page,
                    "content": "\n".join(x["text"] for x in chunk),
                    "chars": sum(x["chars"] for x in chunk),
                    "paras": len(chunk),
                    "chapter": g["chapter"],
                    "section": g["nodeTitle"],
                    "seq": seq,
                }
            )

        for item in g["items"]:
            if cur_chunk and size + item["chars"] > UNIT_MAX_CHARS:
                flush(cur_chunk)
                cur_chunk, size = [], 0
            cur_chunk.append(item)
            size += item["chars"]
        flush(cur_chunk)

    # 真表格（78 个里 2 个）一并补录
    plan.extend(build_table_units(docx, by_title, sec_groups))

    # 未匹配到节点的标题（报告用）
    unmatched = []
    for m in marks:
        nid, how = match_node(m["title"], m["kind"], by_title, None)
        if nid is None:
            unmatched.append(m["title"])

    stats = {
        "blocks": len(blocks),
        "marks": len(marks),
        "gap_paras": gap_paras,
        "gap_chars": gap_chars,
        "units": len(plan),
        "unit_chars": sum(p["chars"] for p in plan),
        "by_node": len(groups),
        "skipped": skipped,
        "unmatched_marks": unmatched,
        "book_id": book_id,
    }
    return plan, stats


# ================================================================ 写库


def apply_plan(plan: list[dict], book_id: str) -> None:
    base, key, model, dim = load_llm_conf()
    print(f"embedding：{model}（{dim} 维）@ {base}")

    vectors: list[list[float]] = []
    for i in range(0, len(plan), EMBED_BATCH):
        batch = plan[i : i + EMBED_BATCH]
        vectors.extend(embed_batch(base, key, model, [p["content"] for p in batch]))
        print(f"  已取向量 {len(vectors)}/{len(plan)}")
        time.sleep(0.3)

    rows = []
    for p, vec in zip(plan, vectors):
        if len(vec) != dim:
            raise SystemExit(f"向量维度不符：{p['id']} 得到 {len(vec)}，应为 {dim}")
        meta = {
            "chapter": p["chapter"],
            "section": p["section"],
            "page": p["page"],
            "gap": True,
            "gapSeq": p["seq"],
            "source": "docx_gap",
        }
        rows.append(
            (
                p["id"],
                book_id,
                p.get("unit_type", "section_abstract"),
                "node",
                p["node_id"],
                p["title"],
                p["content"],
                _to_pgvector(vec),
                Json(meta),
            )
        )

    with pg() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM content_unit WHERE id LIKE %s", (f"{GAP_PREFIX}%",))
        deleted = cur.rowcount
        execute_values(
            cur,
            """INSERT INTO content_unit
               (id, book_id, unit_type, ref_type, ref_id, title, content, embedding, meta_jsonb)
               VALUES %s""",
            rows,
            template="(%s,%s,%s,%s,%s,%s,%s,%s::vector,%s)",
        )
        conn.commit()
    print(f"已删除旧补录行 {deleted} 条，写入 {len(rows)} 条")


# ================================================================ 入口


def main() -> int:
    ap = argparse.ArgumentParser(description="docx 缺口正文补录（只增不改存量）")
    ap.add_argument("--docx", default=str(DOCX), help="源 docx 路径")
    ap.add_argument("--dry-run", action="store_true", help="打印计划样例，不写库")
    ap.add_argument("--apply", action="store_true", help="正式写库并补向量")
    ap.add_argument("--check", action="store_true", help="只报告缺口（默认行为）")
    args = ap.parse_args()

    docx = Path(args.docx)
    if not docx.exists():
        raise SystemExit(f"源 docx 不存在：{docx}")

    plan, stats = build_plan(docx)
    print("=== 缺口统计 ===")
    print(f"清洗后段落 {stats['blocks']}，章/节标题 {stats['marks']} 个")
    print(f"未入库的正文段落 {stats['gap_paras']} 段、{stats['gap_chars']} 字")
    sk = stats["skipped"]
    print(f"排除项：目录页 {sk['toc']}、纯标记行 {sk['mark']}、标题行 {sk['heading']}、"
          f"表格占位 {sk['table']}、页眉噪声 {sk['noise']}、无归属节点 {sk['no_node']}")
    print(f"计划生成 {stats['units']} 个补充单元（{stats['unit_chars']} 字），涉及 {stats['by_node']} 个节点")
    if stats["unmatched_marks"]:
        print(f"未匹配到节点的标题 {len(stats['unmatched_marks'])} 个：{stats['unmatched_marks'][:5]}")

    print("\n=== 按节点分布（前 10）===")
    per: dict[str, list[int]] = {}
    for p in plan:
        per.setdefault(p["title"], [0, 0])
        per[p["title"]][0] += 1
        per[p["title"]][1] += p["chars"]
    for title, (n, c) in sorted(per.items(), key=lambda kv: -kv[1][1])[:10]:
        print(f"  {c:>6} 字 / {n:>2} 单元  {title}")

    no_page = sorted({p["title"] for p in plan if not p["page"]})
    print(f"\n取不到页码的单元 {sum(1 for p in plan if not p['page'])} 个"
          f"（会排到该节末尾）：{no_page[:6]}")

    tbls = [p for p in plan if p.get("unit_type") == "table"]
    print(f"\n=== 真表格单元 {len(tbls)} 个 ===")
    for p in tbls:
        print(f"[{p['id']}] page={p['page'] or '(空)'} {p['title']}")
        print("  " + p["content"].replace("\n", "\n  "))

    if args.dry_run or args.apply:
        print("\n=== 单元样例（前 3）===")
        for p in plan[:3]:
            print(f"\n[{p['id']}] page={p['page'] or '(空)'} {p['chars']} 字 / {p['paras']} 段")
            print("  " + p["content"][:220].replace("\n", "\n  "))

    if not args.apply:
        print("\n（未写库。确认无误后加 --apply 执行）")
        return 0

    apply_plan(plan, stats["book_id"])
    print("\n下一步：python build_graph.py（把新单元同步进 Neo4j）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
