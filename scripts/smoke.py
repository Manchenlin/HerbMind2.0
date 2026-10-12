"""端到端冒烟：PG 计数 + BFF 接口 + Neo4j 计数。

前置：中间件已起、种子已导入、svc-catalog / bff / gateway 已启动。
运行：python smoke.py     （任一失败即非零退出）
"""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database", "etl"))
from db import query, neo4j_driver  # noqa: E402

BFF = os.getenv("BFF_BASE", "http://localhost:8090")
FAIL = False


def check(label, cond, detail=""):
    global FAIL
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail else ""))
    if not cond:
        FAIL = True


def main():
    # 1) PG
    try:
        formula = query("SELECT count(*) FROM formula")[0][0]
        quotes = query("SELECT count(*) FROM classic_quote")[0][0]
        check("PG: formula=3", formula == 3, f"got {formula}")
        check("PG: classic_quote=5", quotes == 5, f"got {quotes}")
    except Exception as e:  # noqa: BLE001
        check("PG reachable", False, str(e))

    # 2) BFF（经网关或直连 BFF）
    try:
        r = requests.get(f"{BFF}/api/biz/library/tree", params={"bookId": "sh"}, timeout=5)
        body = r.json()
        check("BFF: code=0", body.get("code") == 0, f"body={json.dumps(body, ensure_ascii=False)[:120]}")
        check("BFF: data is list", isinstance(body.get("data"), list))
    except Exception as e:  # noqa: BLE001
        check("BFF reachable", False, str(e))

    # 3) Neo4j
    try:
        d = neo4j_driver()
        with d.session() as s:
            c = s.run("MATCH (f:Formula) RETURN count(f) AS c").single()["c"]
        d.close()
        check("Neo4j: Formula=3", c == 3, f"got {c}")
    except Exception as e:  # noqa: BLE001
        check("Neo4j reachable", False, str(e))

    print("\nSMOKE " + ("FAILED" if FAIL else "OK"))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
