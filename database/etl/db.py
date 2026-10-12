"""ETL 公共：PG / Neo4j 连接。

环境变量（可选）：
  PG_DSN     默认 postgresql://postgres:postgres@localhost:5432/herbmind
  NEO4J_URI  默认 bolt://localhost:7687
  NEO4J_USER / NEO4J_PASSWORD  默认 neo4j / herbmind123
"""
import os
from contextlib import contextmanager

import psycopg2

PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/herbmind")


@contextmanager
def pg():
    """事务型连接：正常提交、异常回滚。"""
    c = psycopg2.connect(PG_DSN)
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def execute(sql, params=None):
    with pg() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def query(sql, params=None):
    with pg() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def neo4j_driver():
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "herbmind123")
    return GraphDatabase.driver(uri, auth=(user, pwd))
