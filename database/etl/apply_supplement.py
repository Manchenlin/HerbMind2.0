"""补录 formula_herb（方案 A：独立补录层，幂等）。

背景
----
旧库 ETL 只认正文里的 "组成：" 标签。有 59 个方剂在原始书稿里就没有该段落，
content_unit 里留下的是 59 条 "组成：未找到"，因此无法靠重跑 ETL 修出来，
只能从外部补录（标准方书）。

为什么必须独立成一个文件而不是直接改库
--------------------------------------
`migrate_legacy.py` 第 52 行是 `TRUNCATE ... formula_herb ... CASCADE`，
任何人重跑一次全量迁移，手工写进库的补录数据就没了。
所以补录数据落成 data/formula_herb_supplement.csv，本脚本在迁移**之后**执行。

用法
----
  python apply_supplement.py --check      # 只体检：CSV 是否合法、能覆盖多少缺口
  python apply_supplement.py --dry-run    # 演练：打印将要执行的操作，不写库
  python apply_supplement.py              # 正式写入
  python apply_supplement.py --rollback data/_apply_log_XXXXXXXX.json   # 回滚某次写入

约定
----
· CSV 列：formula_id, herb_name, seq, source
· 只补 **药味名与顺序**，dose / unit / role 一律留 NULL
  —— 各家教材的剂量换算互不相同，补空比补错安全；剂量另行人工补。
· 幂等：按 formula_id 分组，先 DELETE 该方全部行再 INSERT。
  没出现在 CSV 里的方剂一律不碰；现有内容与 CSV 完全一致的也跳过（不删不插）。
· 安全阀：现有数据与 CSV **不一致**时默认拒绝覆盖，加 --force-overwrite 才动。
  ⚠️ 判据刻意不用"dose/role 是否为空"来区分数据来源 —— migrate_legacy.py 没有写 role 列，
  且剂量解析失败就写 NULL，实测 1315 行里只有 69 行有剂量，靠空值判断会把真实 ETL
  数据误当成上次补录写入的行，然后静默覆盖掉。
· 退出码：0=成功，1=补录文件本身有问题，2=需要人工决策（有冲突）。
· 每次正式写入都会在 data/ 下留一份 _apply_log_<时间戳>.json，
  内含写入前该方剂的原行，可用于 --rollback。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from db import pg

DATA_DIR = Path(__file__).parent / "data"
SUPPLEMENT = DATA_DIR / "formula_herb_supplement.csv"

REQUIRED_COLS = ("formula_id", "herb_name", "seq", "source")


def load_csv(path: Path) -> tuple[dict[str, list[dict]], list[str]]:
    """读补录表，返回 ({formula_id: [行...]}, 错误信息列表)。"""
    if not path.exists():
        return {}, [f"补录文件不存在：{path}"]

    errors: list[str] = []
    grouped: dict[str, list[dict]] = {}

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLS if c not in (reader.fieldnames or [])]
        if missing:
            return {}, [f"CSV 缺列：{missing}（应为 {REQUIRED_COLS}）"]

        for lineno, raw in enumerate(reader, start=2):
            fid = (raw.get("formula_id") or "").strip()
            herb = (raw.get("herb_name") or "").strip()
            seq_raw = (raw.get("seq") or "").strip()
            src = (raw.get("source") or "").strip()

            if not fid or not herb:
                errors.append(f"第 {lineno} 行：formula_id/herb_name 为空")
                continue
            try:
                seq = int(seq_raw)
            except ValueError:
                errors.append(f"第 {lineno} 行：seq 不是整数（{seq_raw!r}）")
                continue
            if not src:
                # 出处是审核依据，缺了就无法追溯，直接拦
                errors.append(f"第 {lineno} 行：source（出处）为空，无法追溯")
                continue

            grouped.setdefault(fid, []).append({"herb_name": herb, "seq": seq, "source": src})

    # seq 重复说明顺序写错了，早拦比入库后再查便宜
    for fid, rows in grouped.items():
        seqs = [r["seq"] for r in rows]
        if len(seqs) != len(set(seqs)):
            errors.append(f"{fid}：seq 有重复 {sorted(seqs)}")

    return grouped, errors


def collect_state(cur, grouped: dict[str, list[dict]]) -> tuple[dict, list[str]]:
    """校验 formula_id 存在性、抓取补录前的原行。"""
    problems: list[str] = []
    before: dict[str, list[dict]] = {}

    cur.execute("SELECT id, name FROM formula WHERE id = ANY(%s)", (list(grouped),))
    existing = {r[0]: r[1] for r in cur.fetchall()}
    for fid in grouped:
        if fid not in existing:
            problems.append(f"{fid}：formula 表中不存在该 id")
        else:
            # 先铺好空列表：没有药味的方剂不会出现在下面的查询结果里，
            # 不做这一层初始化，"可补齐多少方剂" 会被少算成 0
            before[fid] = []

    cur.execute(
        """SELECT formula_id, herb_name, dose, unit, role, seq
           FROM formula_herb WHERE formula_id = ANY(%s) ORDER BY formula_id, seq""",
        (list(grouped),),
    )
    for fid, herb, dose, unit, role, seq in cur.fetchall():
        before.setdefault(fid, []).append(
            {"herb_name": herb,
             "dose": float(dose) if dose is not None else None,
             "unit": unit, "role": role, "seq": seq}
        )
    return before, problems


def report_gap(cur) -> int:
    cur.execute(
        """SELECT count(*) FROM formula f
           WHERE NOT EXISTS (SELECT 1 FROM formula_herb fh WHERE fh.formula_id = f.id)"""
    )
    return cur.fetchone()[0]


def do_apply(grouped: dict[str, list[dict]], before: dict, dry_run: bool) -> int:
    """按 formula_id 先 DELETE 再 INSERT。传进来的 grouped 应当是"确实要写"的那部分。"""
    with pg() as conn, conn.cursor() as cur:
        if not dry_run:
            for fid, rows in grouped.items():
                cur.execute("DELETE FROM formula_herb WHERE formula_id = %s", (fid,))
                for r in rows:
                    cur.execute(
                        """INSERT INTO formula_herb(formula_id, herb_name, dose, unit, role, seq)
                           VALUES (%s, %s, NULL, NULL, NULL, %s)""",
                        (fid, r["herb_name"], r["seq"]),
                    )
            conn.commit()

        # 报告（dry-run 时库没变，仍按"补录后"预期算）
        cur.execute("SELECT count(*) FROM formula WHERE id = ANY(%s)", (list(grouped),))
        f_cnt = cur.fetchone()[0] if grouped else 0
        gap = report_gap(cur) if not dry_run else None

    added = sum(len(v) for v in grouped.values())
    overwritten = sum(1 for fid in grouped if before.get(fid))
    tag = "【演练】" if dry_run else "【已写入】"
    print(f"\n{tag} 覆盖方剂 {f_cnt} 个，写入药味 {added} 条")
    print(f"        其中覆盖了库中已有数据的方剂：{overwritten} 个")
    if gap is not None:
        print(f"        补录后仍无药味的方剂：{gap} 个（原有 59 个）")
    return added


def save_log(grouped: dict, before: dict) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"_apply_log_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(
        json.dumps({"applied_at": datetime.now().isoformat(timespec="seconds"),
                    "formula_ids": sorted(grouped),
                    "inserted": grouped,
                    "before": before},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def do_rollback(log_path: Path) -> None:
    log = json.loads(log_path.read_text(encoding="utf-8"))
    fids = log["formula_ids"]
    before = log.get("before") or {}
    with pg() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM formula_herb WHERE formula_id = ANY(%s)", (fids,))
        n = 0
        for fid, rows in before.items():
            for r in rows:
                cur.execute(
                    """INSERT INTO formula_herb(formula_id, herb_name, dose, unit, role, seq)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (fid, r["herb_name"], r["dose"], r["unit"], r["role"], r["seq"]),
                )
                n += 1
        conn.commit()
    print(f"已回滚 {len(fids)} 个方剂，恢复补录前原行 {n} 条")


def main() -> int:
    ap = argparse.ArgumentParser(description="补录 formula_herb（幂等）")
    ap.add_argument("--file", type=Path, default=SUPPLEMENT, help="补录 CSV 路径")
    ap.add_argument("--check", action="store_true", help="只校验与体检，不写库")
    ap.add_argument("--dry-run", action="store_true", help="演练，不写库")
    ap.add_argument("--force-overwrite", action="store_true",
                    help="允许覆盖库里已有药味的方剂（默认拒绝）")
    ap.add_argument("--rollback", type=Path, help="按 apply 日志回滚")
    args = ap.parse_args()

    if args.rollback:
        do_rollback(args.rollback)
        return 0

    grouped, errors = load_csv(args.file)
    if errors:
        print("补录文件有问题，已中止：")
        for e in errors:
            print("  ·", e)
        return 1

    print(f"补录文件：{args.file}")
    print(f"涉及方剂：{len(grouped)} 个，药味 {sum(len(v) for v in grouped.values())} 条")

    with pg() as conn, conn.cursor() as cur:
        before, problems = collect_state(cur, grouped)
        gap_before = report_gap(cur)

    if problems:
        print("校验未通过，已中止：")
        for p in problems:
            print("  ·", p)
        return 1

    # 只有当前为空、且 csv 里有它的方剂才算"新补齐"，已补过的不再计入缺口变化
    fresh = [fid for fid in grouped if not before.get(fid)]
    print(f"当前全库无药味方剂：{gap_before} 个")
    print(f"本次新补齐：{len(fresh)} 个 → 补后剩 {gap_before - len(fresh)} 个"
          f"（另有 {len(grouped) - len(fresh)} 个早已补录）")

    # 判据改为「现有内容是否与本次要写的完全一致」，不再猜数据来源。
    # 为什么不能靠 dose/role 是否为空来区分"ETL 原始数据"和"上次补录写入的行"：
    # migrate_legacy.py 的 INSERT 根本没有 role 列（全库 role 非空 = 0 行），
    # 且剂量为"适量"/"—"/空 时 dose 也写 NULL —— 实测 1315 行里只有 69 行有剂量。
    # 用空值判断会把 1246 行真实 ETL 数据误当成"纯补录行"，然后静默 DELETE+INSERT 覆盖。
    def _same_as_plan(fid: str) -> bool:
        old = before.get(fid) or []
        new = grouped[fid]
        if len(old) != len(new):
            return False

        def key(r: dict) -> tuple[str, int]:
            return (r["herb_name"], r["seq"])

        return sorted(map(key, old)) == sorted(map(key, new))

    # 完全一致 → 幂等重跑，连 DELETE 都不做
    rerun = {k: v for k, v in before.items() if v and _same_as_plan(k)}
    # 有数据但内容不同 → 一律视为真实数据，必须人工放行
    conflict = {k: v for k, v in before.items() if v and not _same_as_plan(k)}
    if rerun:
        print(f"其中 {len(rerun)} 个方剂已与补录文件一致，无需改动")

    if conflict and not args.force_overwrite:
        print("\n以下方剂库里已有数据且与补录文件不一致，默认不覆盖：")
        for fid, rows in conflict.items():
            print(f"  · {fid}：现有 {len(rows)} 条，补录 {len(grouped[fid])} 条")
        print("  如确认要用补录文件替换它们，加 --force-overwrite")
        # 用 2 而不是 1：调用方要能与"补录文件本身有问题"（返回 1）区分开
        return 2

    if args.check:
        print("\n体检通过（--check 模式，未写库）")
        return 0

    # 只写"内容确实不一致"的那部分：已一致的跳过，避免无意义的 DELETE+INSERT
    to_write = {k: v for k, v in grouped.items() if k not in rerun}
    if not to_write:
        print("\n所有方剂都已与补录文件一致，无需写入")
        return 0

    do_apply(to_write, before, dry_run=args.dry_run)

    if not args.dry_run:
        log = save_log(to_write, before)
        print(f"        回滚日志：{log}")
        print("\n下一步：python sync_content_unit.py → build_graph.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
