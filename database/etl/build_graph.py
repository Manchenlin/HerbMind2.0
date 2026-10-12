"""建图：PG(formula / formula_herb) → Neo4j(:Formula / :Herb + COMPOSED_OF)。

要点：
  · 以 **formula.id** 为合并键（不能用 name —— 同名方剂会被吃掉）
  · **批量 UNWIND 写入**（2 条 Cypher 搞定，而不是每行一次往返 → 从分钟级降到秒级）

运行：python build_graph.py
"""
from db import neo4j_driver, query


def main():
    rows = query(
        """SELECT f.id, f.name, f.syndrome_text, f.page, h.herb_name, h.dose, h.unit, h.role
           FROM formula f LEFT JOIN formula_herb h ON h.formula_id = f.id
           ORDER BY f.id, h.seq"""
    )

    # 按 formula 聚合，便于批量写
    formulas, herbs = {}, []
    for fid, name, syndrome, page, herb, dose, unit, role in rows:
        formulas[fid] = {"id": fid, "name": name, "syndrome": syndrome,
                         "page": str(page) if page is not None else None}
        if herb:
            herbs.append({"id": fid, "herb": herb,
                          "dose": float(dose) if dose is not None else None,
                          "unit": unit, "role": role})

    driver = neo4j_driver()
    try:
        with driver.session() as s:
            # 清掉历史遗留的 name 唯一约束（同名方剂会冲突）
            s.run("DROP CONSTRAINT formula_name IF EXISTS")
            s.run("CREATE CONSTRAINT formula_id IF NOT EXISTS FOR (f:Formula) REQUIRE f.id IS UNIQUE")
            s.run("CREATE CONSTRAINT herb_name IF NOT EXISTS FOR (h:Herb) REQUIRE h.name IS UNIQUE")

            s.run(
                """UNWIND $rows AS row
                   MERGE (f:Formula {id: row.id})
                   SET f.name = row.name, f.syndrome = row.syndrome, f.page = row.page""",
                rows=list(formulas.values()),
            )
            s.run(
                """UNWIND $rows AS row
                   MATCH (f:Formula {id: row.id})
                   MERGE (h:Herb {name: row.herb})
                   MERGE (f)-[r:COMPOSED_OF]->(h)
                   SET r.dose = row.dose, r.unit = row.unit, r.role = row.role""",
                rows=herbs,
            )

            cnt = s.run("MATCH (f:Formula) RETURN count(f) AS c").single()["c"]
            hn = s.run("MATCH (h:Herb) RETURN count(h) AS c").single()["c"]
            rel = s.run("MATCH ()-[r:COMPOSED_OF]->() RETURN count(r) AS c").single()["c"]
        print(f"build_graph: ok (Formula={cnt}, Herb={hn}, COMPOSED_OF={rel})")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
