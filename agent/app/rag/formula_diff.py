"""方剂加减**查证**（纯规则，零大模型）。

⚠️ 受 `project_plan/00_README_总览.md`「设计红线一」约束：
本模块**只做组成比对与原文引用，绝不推断功效**。给出的是"库里有没有这个组成"，
不是"这样加减有没有道理"。功效只允许原样摘录语料里的 `formula.efficacy` 字段。

做三件事：
1. **差集**：结果组成 = (基础方 − 去掉的药) + 加上的药
2. **精确匹配**：库里哪些方的组成与结果**逐味完全一致**
   —— 可能 0 个（如实说"未见完全对应的成方"），也可能多个（库里有同方重复收录，如 f_23/f_175 都是大承气汤）
3. **近似**：Jaccard 相似方 Top-N，**每条都标注"非同一方"**，避免被读成推荐

为什么不用 Neo4j：`COMPOSED_OF` 本身就是从 `formula_herb` 派生的，绕图多一跳；
而加减查证本质是集合运算，不是路径查询。数据源以 PG 为权威（红线四：能算的用规则）。

一个必须记住的数据限制
----------------------
本库**没有剂量**（`formula_herb.dose` 仅 69/1315 行有值，`role` 全空），
而《金匮要略》里小承气汤 / 厚朴三物汤 / 厚朴大黄汤**药味完全相同、仅剂量不同、主治迥异**。
所以：**"组成相同"不等于"是同一方"**。响应里必须带 `notice` 声明这一点，
且 `similarFormulas` 不能给"推荐"语义。
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from app.db import get_pg_pool

logger = logging.getLogger("herbmind-agent")

# 目录缓存：ETL 产物，进程内基本不变；重跑 ETL 后最多晚 5 分钟生效
CACHE_TTL = 300.0
_cache: dict[str, object] = {"at": 0.0, "data": None}

# 相似方最多给几条
SIMILAR_TOP_N = 3
# 低于这个 Jaccard 就不值得展示（0.5 以下基本是"两首不相干的方"）
SIMILAR_MIN = 0.5
# 原文条文段落截断长度
CLASSIC_TEXT_LIMIT = 600

# 药名里出现这些字符，基本就是 ETL 解析残留（实测库里有"不哎咀)上以水""矾石(烧)等分。""1、1."）
SUSPICIOUS_RE = re.compile(r"[()（）\[\]［］【】。，、,;；:：！？\s]|\d")

NOTICE = (
    "本结果仅比对**药味种类**，不比对剂量与君臣佐使配伍关系；"
    "「组成相同」不等于「是同一方」（如小承气汤/厚朴三物汤/厚朴大黄汤药味相同而剂量不同、主治迥异）。"
    "本系统不推断功效、不给处方建议，仅供学习参考。"
)

# 从 content_unit 正文里抠「经典条文」段落：从"经典条文："到"按语："之前
_CLASSIC_RE = re.compile(r"经典条文[：:]\s*(.*?)(?:\n\s*按语[：:]|$)", re.S)


@dataclass(slots=True)
class FormulaRecord:
    """一个方剂及其药味（按库内 seq 顺序）。"""

    id: str
    name: str
    alias: str
    efficacy: str
    syndrome_text: str
    page: str
    node_id: str
    herbs: list[str] = field(default_factory=list)
    classic_text: str = ""


def normalize(name: str) -> str:
    """药名归一：只做去空白与全角括号转半角。

    刻意**不做**"去括号内容"这类激进清洗 —— 库里 `芫花(熬)`、`麻黄(去节)` 的括号是炮制法，
    但也有 `不哎咀)上以水` 这种纯噪声，两者机器分不清，硬删只会制造新错误。
    可疑药名一律原样呈现并打 `warnings`，让人自己判断（红线二：不替人做判断）。
    """
    text = name.strip().replace("（", "(").replace("）", ")")
    return re.sub(r"[\s\u3000]+", "", text)


def is_suspicious(name: str) -> bool:
    """药名是否疑似 ETL 解析残留。"""
    return bool(SUSPICIOUS_RE.search(name)) or len(name) > 6


def _fetch_rows() -> tuple[list[tuple], dict[str, str]]:
    """一次取全量：方剂 × 药味 的展开行 + 方剂正文（用于条文段落）。"""
    with get_pg_pool().connection(timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT f.id, f.name, coalesce(f.alias,''), coalesce(f.efficacy,''),
                          coalesce(f.syndrome_text,''), coalesce(f.page,''), coalesce(f.node_id,''),
                          coalesce(fh.herb_name,''), coalesce(fh.seq, 0)
                   FROM formula f
                   LEFT JOIN formula_herb fh ON fh.formula_id = f.id
                   ORDER BY f.id, fh.seq"""
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT ref_id, content FROM content_unit WHERE ref_type = 'formula'"
            )
            contents = {r[0]: r[1] or "" for r in cur.fetchall()}
    return rows, contents


def _extract_classic_text(content: str) -> str:
    """从正文里截出「经典条文」段落（纯摘录，不做条文号解析）。"""
    match = _CLASSIC_RE.search(content)
    if not match:
        return ""
    text = " ".join(match.group(1).split())
    return text if len(text) <= CLASSIC_TEXT_LIMIT else text[:CLASSIC_TEXT_LIMIT] + "…"


def load_catalog(refresh: bool = False) -> dict[str, FormulaRecord]:
    """加载全部方剂到内存（带 TTL 缓存）。245 方 / 1315 行，一次约 10ms。"""
    now = time.monotonic()
    cached = _cache.get("data")
    if not refresh and cached is not None and now - float(_cache.get("at") or 0) < CACHE_TTL:
        return cached  # type: ignore[return-value]

    rows, contents = _fetch_rows()
    catalog: dict[str, FormulaRecord] = {}
    for fid, name, alias, efficacy, syndrome, page, node_id, herb, _seq in rows:
        rec = catalog.get(fid)
        if rec is None:
            rec = FormulaRecord(
                id=fid, name=name, alias=alias, efficacy=efficacy,
                syndrome_text=syndrome, page=page, node_id=node_id,
                classic_text=_extract_classic_text(contents.get(fid, "")),
            )
            catalog[fid] = rec
        if herb:
            rec.herbs.append(herb)

    _cache["data"] = catalog
    _cache["at"] = now
    logger.info("加减查证：目录已加载 %d 方 / %d 味", len(catalog),
                sum(len(r.herbs) for r in catalog.values()))
    return catalog


def _find_by_name(catalog: dict[str, FormulaRecord], query: str) -> list[FormulaRecord]:
    """按 id / 方名 / 别名找方剂。返回可能多个（库里有同方重复收录）。"""
    q = normalize(query)
    if not q:
        return []
    if q in catalog:
        return [catalog[q]]
    hits = [r for r in catalog.values() if normalize(r.name) == q]
    if not hits:
        hits = [r for r in catalog.values() if normalize(r.alias) == q]
    if not hits:
        # 兜底：包含关系（"桂枝加葛根汤" 里含 "桂枝"），只在不唯一时让人自己选
        hits = [r for r in catalog.values() if q in normalize(r.name)]
    return hits


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def diff(
    base: str,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    similar_top_n: int = SIMILAR_TOP_N,
) -> dict:
    """加减查证主入口（同步阻塞，调用方丢线程池）。

    Returns:
        结构化结果；**不含任何功效推断字段**，`efficacy` 一律是语料原文摘录。

    Raises:
        ValueError: 基础方找不到 / 找到多个无法确定 —— 由路由转 400
    """
    add = [normalize(x) for x in (add or []) if normalize(x)]
    remove = [normalize(x) for x in (remove or []) if normalize(x)]

    catalog = load_catalog()
    candidates = _find_by_name(catalog, base)
    if not candidates:
        raise ValueError(f"未找到方剂「{base}」")

    warnings: list[str] = []

    if len(candidates) > 1:
        # 库里有同方重复收录（如大承气汤 = f_23 + f_175，来自不同书/页）。
        # 若这些条目的组成完全一致，取第一条即可，不必烦用户；组成不同才要求指定 ID。
        herb_sigs = {frozenset(normalize(x) for x in c.herbs) for c in candidates}
        if len(herb_sigs) == 1:
            rec = candidates[0]
            ids = "、".join(c.id for c in candidates)
            warnings.append(
                f"库中「{rec.name}」有 {len(candidates)} 条重复收录（{ids}），组成一致，已取 {rec.id}。"
            )
        else:
            names = "、".join(f"{c.name}({c.id})" for c in candidates[:6])
            raise ValueError(
                f"「{base}」在库中对应多个方剂且组成不同：{names}。请改用方剂 ID 指定。"
            )
    else:
        rec = candidates[0]

    base_herbs = list(dict.fromkeys(rec.herbs))       # 去重保序
    base_set = set(base_herbs)

    # ---------- ① 差集 ----------
    removed = [h for h in remove if h in base_set]
    missing_in_base = [h for h in remove if h not in base_set]
    if missing_in_base:
        warnings.append(f"要减去的 {('、'.join(missing_in_base))} 不在基础方组成中，已忽略。")

    dup_add = [h for h in add if h in base_set]
    if dup_add:
        warnings.append(f"加上的 {('、'.join(dup_add))} 基础方里已有，未重复添加。")

    result_list = [h for h in base_herbs if h not in set(removed)]
    for h in add:
        if h not in base_set:
            result_list.append(h)
    result_set = set(result_list)

    # 加进来的药在库里是否作为药味出现过（拼错/没这味药能立刻发现）
    known_herbs = {normalize(x) for r in catalog.values() for x in r.herbs}
    unknown = [h for h in add if h not in known_herbs]
    if unknown:
        warnings.append(
            f"{('、'.join(unknown))} 在现有语料的所有方剂中均未出现，请核对药名是否正确。"
        )
    for h in add:
        if is_suspicious(h):
            warnings.append(f"药名「{h}」含括号/标点/数字，疑似原文解析残留，比对结果仅供参考。")

    # ---------- ② 精确匹配（逐味完全一致） ----------
    name_count: dict[str, int] = {}
    for r in catalog.values():
        name_count[normalize(r.name)] = name_count.get(normalize(r.name), 0) + 1

    matched = []
    for r in catalog.values():
        if r.id == rec.id:
            continue
        if set(normalize(x) for x in r.herbs) == result_set:
            matched.append({
                "id": r.id,
                "name": r.name,
                "alias": r.alias,
                "efficacy": r.efficacy,              # 语料原文，不是推断
                "syndromeText": r.syndrome_text,
                "page": r.page,
                "classicText": r.classic_text,
                # 库里同一个方名有重复收录时标出来，免得用户以为系统推荐了两个不同的方
                "duplicateName": name_count.get(normalize(r.name), 0) > 1,
            })
    matched.sort(key=lambda m: (m["duplicateName"], m["id"]))

    # ---------- ③ 近似（必须标注非同一方） ----------
    similar = []
    if similar_top_n > 0:
        pool = []
        for r in catalog.values():
            if r.id == rec.id or not r.herbs:
                continue
            score = _jaccard(result_set, set(normalize(x) for x in r.herbs))
            if score >= SIMILAR_MIN:
                pool.append((score, r))
        pool.sort(key=lambda t: (-t[0], t[1].id))
        for score, r in pool[:similar_top_n]:
            similar.append({
                "id": r.id,
                "name": r.name,
                "jaccard": round(score, 4),
                "note": "组成相近但**并非同一方**，仅供对照",
            })

    return {
        "base": {
            "id": rec.id,
            "name": rec.name,
            "alias": rec.alias,
            "herbs": base_herbs,
            "efficacy": rec.efficacy,
            "syndromeText": rec.syndrome_text,
            "page": rec.page,
            "classicText": rec.classic_text,
        },
        "removed": removed,
        "added": [h for h in add if h not in base_set],
        "resultHerbs": result_list,
        "matchedFormulas": matched,
        # 没命中时这条提示是**结论本身**，不是错误：库里确实没有
        "matchHint": (
            "" if matched
            else "现有语料中未见与此组成完全一致的成方。"
                 "这不代表该加减不合理，只表示库内无对应记载。"
        ),
        "similarFormulas": similar,
        "warnings": warnings,
        "doseCompared": False,      # 明确告诉前端：本次没有比对剂量（库内剂量缺失）
        "notice": NOTICE,
    }
