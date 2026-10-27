"""把 formula_herb 的药味回写进 content_unit 正文，并重算这些条的向量。

为什么需要这一步
----------------
`apply_supplement.py` 只修了 `formula_herb` 表和图库，但 **RAG 检索读的是
`content_unit.content`**。那 59 条正文里留下的字面量是 "组成：未找到"，
所以即使结构化数据已经补好，问"桂枝汤由哪些药组成"仍会答"资料未记载"。

本脚本做两件事：
  1. 用 formula_herb 的实际药味替换正文里的 "组成：xxx" 这一行
  2. **重算这些条目的 bge-m3 向量**（正文变了，旧向量与正文不一致；
     且新正文含药味信息，语义更贴"某方由什么组成"这类问题）

不重算行不行：能跑但检索会劣化 —— 向量描述的是"组成：未找到"那段文本，
问组成类问题时该条的相似度会偏低，可能被 0.5 阈值直接滤掉。

⚠️ 作用域只限「补录文件里的方剂」（白名单）
------------------------------------------
原有 186 个方剂的正文各有各的来源与写法，本脚本无权改写。实测若放开全库比对，
会命中 f_115「组成：用生糯米」、f_124「组成：1、1.」等 8 条 —— 它们的
`formula_herb` 本身就是脏数据，强行"对齐"等于拿脏值覆盖正文，还会把带剂量的
描述压成药名串。所以白名单外的正文一律不碰。

运行顺序（重跑全量迁移之后必须按此顺序补齐）
--------------------------------------------
    python migrate_legacy.py        # 全量迁移（会 TRUNCATE，补录数据被清空）
    python apply_supplement.py      # 重新补录 formula_herb
    python sync_content_unit.py     # 回写正文 + 重算向量   ← 本脚本
    python build_graph.py           # 同步 Neo4j

用法
----
  python sync_content_unit.py --dry-run    # 只看会改哪些，不调 API、不写库
  python sync_content_unit.py              # 正式执行
  python sync_content_unit.py --limit 3    # 只处理前 3 条（验证用，省钱）

幂等与安全：
  · 正文与 formula_herb 一致就跳过，不重复烧 embedding 额度；
  · 同样因为「不一致才写」，补录文件日后改了药味，重跑能把正文一起修正；
  · 向量全部取齐后才在**单个事务**里落库，中途 API 失败不会留下半截脏数据。
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from db import pg, query

ROOT = Path(__file__).resolve().parents[2]
AGENT_ENV = ROOT / "agent" / ".env"
DATA_DIR = Path(__file__).parent / "data"
SUPPLEMENT = DATA_DIR / "formula_herb_supplement.csv"

ZUCHENG_RE = re.compile(r"^组成：.*$", re.MULTILINE)

BATCH = 16          # 硅基流动单次 input 条数上限较宽，16 是稳妥值
RETRY = 2


def load_llm_conf() -> tuple[str, str, str, int]:
    """从 agent/.env 读模型配置（key 只在这一个文件里，不落日志）。"""
    if AGENT_ENV.exists():
        load_dotenv(AGENT_ENV)
    base = os.getenv("LLM_API_BASE", "https://api.siliconflow.cn/v1").rstrip("/")
    key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    dim = int(os.getenv("EMBEDDING_DIM", "1024"))
    if not key:
        raise SystemExit(f"未找到 LLM_API_KEY（应写在 {AGENT_ENV}）")
    return base, key, model, dim


def embed_batch(base: str, key: str, model: str, texts: list[str]) -> list[list[float]]:
    """批量取向量。失败重试 RETRY 次。"""
    url = f"{base}/embeddings"
    payload = {"model": model, "input": texts, "encoding_format": "float"}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    last: Exception | None = None
    for attempt in range(RETRY + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=90)
            resp.raise_for_status()
            data = resp.json()["data"]
            # 服务端不保证返回顺序，按 index 排回去
            data.sort(key=lambda d: d.get("index", 0))
            return [d["embedding"] for d in data]
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < RETRY:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"embedding 调用失败：{last}")


def fetch_herb_map() -> dict[str, str]:
    """formula_id → '麻黄、桂枝、杏仁、甘草'"""
    rows = query(
        """SELECT formula_id, string_agg(herb_name, '、' ORDER BY seq)
           FROM formula_herb GROUP BY formula_id"""
    )
    return {fid: herbs for fid, herbs in rows if herbs}


def load_supplement_ids(path: Path) -> set[str]:
    """读补录文件，拿到本脚本有权改写的方剂白名单。"""
    if not path.exists():
        raise SystemExit(f"补录文件不存在：{path}（先用 apply_supplement.py 生成/应用补录）")
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return {(row.get("formula_id") or "").strip() for row in csv.DictReader(fh)} - {""}


def fetch_targets(ids: set[str]) -> list[tuple[str, str, str]]:
    """(content_unit.id, ref_id, content)，**只在补录白名单内**，且不做占位符过滤。

    两个约束缺一不可：

    1. 不能再用 `content LIKE '%组成：未找到%'` 当待办判据 —— 正文回写过一次后占位符就没了，
       此后若补录文件改了某方的药味，这条永远匹配不到，正文与 formula_herb 永久失配且无告警。
       改成取白名单全量、在 rewrite() 之后逐条比对（不相等才写）。

    2. 必须限定在白名单内 —— 不加限制会去改写原有 186 个方剂的正文：
       实测会命中 f_115「组成：用生糯米」、f_124「组成：1、1.」等 8 条，
       它们的 formula_herb 本身就是脏数据，强行"对齐"等于用脏值覆盖正文，
       而且会把带剂量的描述压成药名串。补录脚本没有权限动别人的正文。
    """
    if not ids:
        return []
    return query(
        """SELECT id, ref_id, content FROM content_unit
           WHERE ref_type = 'formula' AND ref_id = ANY(%s)
           ORDER BY ref_id""",
        (list(ids),),
    )


def rewrite(content: str, herbs: str) -> str:
    """把 "组成：xxx" 这一行换成实际药味；没有这一行就插在首行之后。"""
    line = f"组成：{herbs}"
    if ZUCHENG_RE.search(content):
        return ZUCHENG_RE.sub(line, content, count=1)
    head, _, tail = content.partition("\n")
    return f"{head}\n{line}\n{tail}"


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"


def main() -> int:
    ap = argparse.ArgumentParser(description="回写正文组成并重算向量")
    ap.add_argument("--file", type=Path, default=SUPPLEMENT,
                    help="补录 CSV（同时作为可改写方剂的白名单），应与 apply_supplement 用同一个")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不调 API、不写库")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（验证用）")
    args = ap.parse_args()

    ids = load_supplement_ids(args.file)
    herb_map = fetch_herb_map()
    targets = fetch_targets(ids)
    if args.limit:
        targets = targets[: args.limit]

    print(f"补录白名单：{len(ids)} 个方剂；对应正文：{len(targets)} 条")
    if not targets:
        print("没有需要回写的正文（可能已经同步过，或补录尚未执行）")
        return 0

    plan: list[tuple[str, str, str]] = []
    skipped = 0
    for cu_id, ref_id, content in targets:
        herbs = herb_map.get(ref_id)
        if not herbs:
            skipped += 1          # 该方剂仍无药味（正文占位符保持原样）
            continue
        new_content = rewrite(content, herbs)
        if new_content == content:
            skipped += 1
            continue
        plan.append((cu_id, ref_id, new_content))

    print(f"其中可回写：{len(plan)} 条，跳过 {skipped} 条（无药味或正文已同步）")
    if not plan:
        return 0

    if args.dry_run:
        for cu_id, ref_id, new_content in plan[:5]:
            line = ZUCHENG_RE.search(new_content)
            print(f"  · {ref_id} → {line.group(0) if line else '(无组成行)'}")
        if len(plan) > 5:
            print(f"  … 其余 {len(plan) - 5} 条同理")
        print("\n【演练】未调用 embedding、未写库")
        return 0

    base, key, model, dim = load_llm_conf()
    print(f"模型：{model}（期望 {dim} 维）")

    # 先把所有向量取齐，再一次性事务入库。
    # 逐批提交的写法一旦中途 API 抖动，会出现"前 N 条正文已改、后 M 条原样"，
    # 而占位符已被替换掉、重跑再也匹配不到前 N 条 → 永久不一致且不报错。
    embedded: list[tuple[str, str, list[float]]] = []
    for i in range(0, len(plan), BATCH):
        chunk = plan[i : i + BATCH]
        vectors = embed_batch(base, key, model, [c[2] for c in chunk])
        if len(vectors) != len(chunk):
            raise SystemExit(f"返回向量数不符：要 {len(chunk)} 条，得 {len(vectors)} 条")
        for (cu_id, ref_id, new_content), vec in zip(chunk, vectors):
            if len(vec) != dim:
                raise SystemExit(f"{ref_id} 向量维度 {len(vec)} ≠ {dim}，拒绝写入")
            embedded.append((cu_id, new_content, vec))
        print(f"  已取向量 {len(embedded)}/{len(plan)}（尚未写库）")

    with pg() as conn, conn.cursor() as cur:
        for cu_id, new_content, vec in embedded:
            cur.execute(
                "UPDATE content_unit SET content = %s, embedding = %s::vector WHERE id = %s",
                (new_content, _to_pgvector(vec), cu_id),
            )
        conn.commit()
    done = len(embedded)

    if args.limit:
        # --limit 是拿来做验证的，此时全库必然还有大量未处理项，
        # 报一个"还剩 N 条"只会让人误以为出错了，直接跳过全库校验。
        print(f"\n完成：回写 {done} 条并重算向量（--limit {args.limit} 局部处理，未做全库校验）")
        return 0

    # 全库校验：重算一遍"应该长什么样"，与实际存量比。有药味却未对齐的才是真问题，
    # 那几个无药味的章节标题（f_63/f_69/f_70/f_121/f_125）天然不算在内。
    remaining = sum(
        1
        for _cu_id, ref_id, content in fetch_targets(ids)
        if (herbs := herb_map.get(ref_id)) and rewrite(content, herbs) != content
    )
    print(f"\n完成：回写 {done} 条并重算向量；全库仍未对齐的 {remaining} 条（应为 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
