"""最小建图：PG(formula / formula_herb) → Neo4j(:Formula / :Herb + COMPOSED_OF)。

运行：python build_graph.py
"""
from db import neo4j_driver, query


def main():
    rows = query(
        """SELECT f.name, f.efficacy, f.page, h.herb_name, h.dose, h.unit, h.role
           FROM formula f LEFT JOIN formula_herb h ON h.formula_id = f.id
           ORDER BY f.id, h.seq"""
    )

    driver = neo4j_driver()
    try:
        with driver.session() as s:
            s.run("CREATE CONSTRAINT formula_name IF NOT EXISTS FOR (f:Formula) REQUIRE f.name IS UNIQUE")
            s.run("CREATE CONSTRAINT herb_name IF NOT EXISTS FOR (h:Herb) REQUIRE h.name IS UNIQUE")
            for name, efficacy, page, herb, dose, unit, role in rows:
                s.run(
                    "MERGE (f:Formula {name:$name}) SET f.efficacy=$efficacy, f.page=$page",
                    name=name, efficacy=efficacy, page=page,
                )
                if herb:
                    s.run(
                        """MATCH (f:Formula {name:$name})
                           MERGE (h:Herb {name:$herb})
                           MERGE (f)-[r:COMPOSED_OF]->(h)
                           SET r.dose=$dose, r.unit=$unit, r.role=$role""",
                        name=name, herb=herb, dose=float(dose) if dose is not None else None,
                        unit=unit, role=role,
                    )
            cnt = s.run("MATCH (f:Formula) RETURN count(f) AS c").single()["c"]
        print(f"build_graph: ok (Formula={cnt})")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
