"""目录类工具：按方名/药味/证治查方剂，按病证/方名/症状查医案。

两个都只做**库内事实检索**（设计红线一：只查证 + 引用）：
返回的是 `formula` / `case_record` 里的原文摘录，不生成、不推断、不排序"哪个更好"。

为什么用 `position(lower(..) in lower(..))` 而不是 `ILIKE '%kw%'`：
1. ILIKE 的 `%` `_` 是通配符，模型传个 `%` 就会把全表捞出来；
2. 中文没有大小写问题，但要能匹配 `黄芪`/`黄耆` 这类不同写法只能靠数据侧，不在这里硬补；
3. position() 不涉及转义，参数化后没有注入面。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.db import get_pg_pool
from app.tools.common import NOTICE_FACT, clamp_int, error_result, miss_result, ok_result

logger = logging.getLogger("herbmind-agent")

# 单次返回上限：工具给模型看的，不是给前端翻页的，多了只会稀释上下文
MAX_ITEMS = 8

_FORMULA_SQL = """
SELECT f.id,
       f.name,
       coalesce(f.alias, '')          AS alias,
       coalesce(f.efficacy, '')       AS efficacy,
       coalesce(f.syndrome_text, '')  AS syndrome_text,
       coalesce(f.page, '')           AS page,
       coalesce(string_agg(fh.herb_name, '、' ORDER BY fh.seq), '') AS herbs
FROM formula f
LEFT JOIN formula_herb fh ON fh.formula_id = f.id
WHERE {where}
GROUP BY f.id
ORDER BY f.name
LIMIT %(limit)s
"""

_CASE_SQL = """
SELECT id,
       coalesce(title, '')             AS title,
       coalesce(unit_type, '')         AS unit_type,
       coalesce(source_formula, '')    AS source_formula,
       coalesce(syndrome_text, '')     AS syndrome_text,
       coalesce(symptoms_jsonb::text, '') AS symptoms,
       coalesce(signs_jsonb::text, '')    AS signs,
       coalesce(page, '')              AS page
FROM case_record
WHERE {where}
ORDER BY id
LIMIT %(limit)s
"""


def _contains(column: str, param: str) -> str:
    """大小写无关的子串匹配（参数化，无通配符）。"""
    return f"position(lower(%({param})s) in lower({column})) > 0"


@tool
def search_formula(name: str = "", herb: str = "", syndrome: str = "") -> dict[str, Any]:
    """按方名/别名、药味、证治原文关键词检索方剂（只读事实检索，不推断功效）。

    参数（至少给一个，多个条件之间是 AND）：
    - name：方名或别名，支持部分匹配，如「桂枝」能命中桂枝汤、桂枝加葛根汤；
    - herb：药味名，如「麻黄」，查含该药的方剂；
    - syndrome：证治/主治原文里的关键词，如「无汗而喘」「太阳病」。

    返回：方名、别名、药味（按库内顺序）、功效与证治的**原文摘录**、出处页。
    查不到时 hit=false + hint，请如实告知用户「库内未见记载」，不要凭印象补全。
    """
    name, herb, syndrome = name.strip(), herb.strip(), syndrome.strip()
    if not (name or herb or syndrome):
        return error_result("至少提供 name / herb / syndrome 之一：例如 name='桂枝汤' 或 herb='麻黄'。")

    clauses: list[str] = []
    params: dict[str, Any] = {"limit": MAX_ITEMS}
    if name:
        # 注意：Python 3.11 的 f-string 表达式里不能出现反斜杠，所以列名先落到变量里
        alias_col = "coalesce(f.alias, '')"
        clauses.append(f"({_contains('f.name', 'name')} OR {_contains(alias_col, 'name')})")
        params["name"] = name
    if herb:
        clauses.append(
            "EXISTS (SELECT 1 FROM formula_herb fh2 "
            f"WHERE fh2.formula_id = f.id AND {_contains('fh2.herb_name', 'herb')})"
        )
        params["herb"] = herb
    if syndrome:
        clauses.append(_contains("coalesce(f.syndrome_text, '')", "syndrome"))
        params["syndrome"] = syndrome

    try:
        with get_pg_pool().connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(_FORMULA_SQL.format(where=" AND ".join(clauses)), params)
                rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001 —— 工具不许抛，抛了模型只能瞎猜
        logger.exception("search_formula 查询失败")
        return error_result(f"方剂库暂时不可用（{type(exc).__name__}），请稍后重试或改用语义检索。")

    items = [
        {
            "id": row[0],
            "name": row[1],
            "alias": row[2],
            "herbs": [h for h in (row[6] or "").split("、") if h],
            "efficacy": row[3],
            "syndromeText": row[4],
            "page": row[5],
        }
        for row in rows
    ]
    if not items:
        return miss_result(
            f"库内没有符合（name={name or '-'}，herb={herb or '-'}，syndrome={syndrome or '-'}）的方剂。"
            "可以只用药味或证治关键词再试一次；仍无结果就如实告知用户未收录。"
        )
    return ok_result(items, notice=NOTICE_FACT)


@tool
def search_case(diagnosis: str = "", formula: str = "", symptom: str = "") -> dict[str, Any]:
    """检索医案（只读事实检索，不做辨证推断）。

    参数（至少给一个，多个条件之间是 AND）：
    - diagnosis：病证/治法关键词，匹配医案的证治原文，如「太阳病」「阳明腑实」；
    - formula：方名关键词，匹配医案记载的用方，如「小承气汤」；
    - symptom：症状关键词，匹配医案的症状字段，如「大便不通」。

    返回：医案标题（多为书名，不能当医案名用）、用方、证治原文、症状/体征原文、出处页。
    查不到时 hit=false + hint；不要用医案原文去反推"应当用某方"。
    """
    diagnosis, formula, symptom = diagnosis.strip(), formula.strip(), symptom.strip()
    if not (diagnosis or formula or symptom):
        return error_result(
            "至少提供 diagnosis / formula / symptom 之一：例如 formula='小承气汤' 或 symptom='大便不通'。"
        )

    clauses: list[str] = []
    params: dict[str, Any] = {"limit": MAX_ITEMS}
    if diagnosis:
        clauses.append(_contains("coalesce(syndrome_text, '')", "diagnosis"))
        params["diagnosis"] = diagnosis
    if formula:
        clauses.append(_contains("coalesce(source_formula, '')", "formula"))
        params["formula"] = formula
    if symptom:
        clauses.append(_contains("coalesce(symptoms_jsonb::text, '')", "symptom"))
        params["symptom"] = symptom

    try:
        with get_pg_pool().connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(_CASE_SQL.format(where=" AND ".join(clauses)), params)
                rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.exception("search_case 查询失败")
        return error_result(f"医案库暂时不可用（{type(exc).__name__}），请稍后重试或改用语义检索。")

    items = [
        {
            "id": row[0],
            "title": row[1],
            "unitType": row[2],
            "sourceFormula": row[3],
            "syndromeText": row[4],
            "symptoms": row[5],
            "signs": row[6],
            "page": row[7],
        }
        for row in rows
    ]
    if not items:
        return miss_result(
            f"库内没有符合（diagnosis={diagnosis or '-'}，formula={formula or '-'}，symptom={symptom or '-'}）的医案。"
            "可以换同义说法，或用 semantic_recall 做语义召回；仍无结果就如实告知未收录。"
        )
    return ok_result(items, notice=NOTICE_FACT)
