"""端到端冒烟：PG 计数 + 向量 + BFF 接口 + Neo4j 计数。

前置：中间件已起、数据已导入（migrate_legacy.py）、svc-catalog / bff / gateway 已启动。
运行：python smoke.py     （任一失败即非零退出）
"""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database", "etl"))
from db import neo4j_driver, query  # noqa: E402

BFF = os.getenv("BFF_BASE", "http://localhost:8090")
FAIL = False

# 正式数据基线（来自 migrate_legacy）
EXPECT = {
    "formula": 245,
    "case_record": 290,
    "classic_quote": 568,
    "content_unit": 535,
    "formula_herb": 1006,
}


def check(label, cond, detail=""):
    global FAIL
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail else ""))
    if not cond:
        FAIL = True


def main():
    # 1) PG 行数
    try:
        for table, want in EXPECT.items():
            got = query(f"SELECT count(*) FROM {table}")[0][0]
            check(f"PG: {table}={want}", got == want, f"got {got}")
    except Exception as e:  # noqa: BLE001
        check("PG reachable", False, str(e))

    # 2) 向量（全部非空、1024 维）
    try:
        with_vec, dims = query(
            "SELECT count(*) FILTER (WHERE embedding IS NOT NULL), "
            "(SELECT vector_dims(embedding) FROM content_unit WHERE embedding IS NOT NULL LIMIT 1) "
            "FROM content_unit"
        )[0]
        check("PG: 向量 535 条", with_vec == 535, f"got {with_vec}")
        check("PG: 向量 1024 维", dims == 1024, f"got {dims}")
    except Exception as e:  # noqa: BLE001
        check("PG 向量可查", False, str(e))

    # 3) BFF（经网关或直连 BFF）
    try:
        r = requests.get(f"{BFF}/api/biz/library/tree", params={"bookId": "bk_1"}, timeout=5)
        body = r.json()
        check("BFF: code=0", body.get("code") == 0, f"body={json.dumps(body, ensure_ascii=False)[:100]}")
        check("BFF: data is list", isinstance(body.get("data"), list))
    except Exception as e:  # noqa: BLE001
        check("BFF reachable", False, str(e))

    # 4) Neo4j（方剂按 id 建，应为 245）
    try:
        d = neo4j_driver()
        with d.session() as s:
            c = s.run("MATCH (f:Formula) RETURN count(f) AS c").single()["c"]
            rel = s.run("MATCH ()-[r:COMPOSED_OF]->() RETURN count(r) AS c").single()["c"]
        d.close()
        check("Neo4j: Formula=245", c == 245, f"got {c}")
        check("Neo4j: COMPOSED_OF>900", rel > 900, f"got {rel}")
    except Exception as e:  # noqa: BLE001
        check("Neo4j reachable", False, str(e))

    print("\nSMOKE " + ("FAILED" if FAIL else "OK"))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
