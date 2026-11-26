\pset pager off

-- A 漏检样例：含"桂枝汤"子串，但分词检索不命中
SELECT '漏检样例' AS 项目;
SELECT u.id, left(u.body, 46) AS 片段, to_tsvector('chinese_zh', u.body) AS 该段词条
FROM units u
WHERE u.body LIKE '%桂枝汤%'
  AND NOT (u.tsv @@ to_tsquery('chinese_zh','桂枝汤'))
LIMIT 3;

-- B 单查询耗时
SELECT 'B1 分词检索 桂枝汤' AS 项目;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','桂枝汤');

SELECT 'B2 子串匹配 桂枝汤（无 trgm 索引）' AS 项目;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE body LIKE '%桂枝汤%';

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS units_trgm_idx ON units USING gin(body gin_trgm_ops);

SELECT 'B3 子串匹配 桂枝汤（有 trgm 索引）' AS 项目;
ANALYZE units;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE body LIKE '%桂枝汤%';

SELECT 'B4 归一后等值匹配（实体表的正确形态）' AS 项目;
CREATE TABLE IF NOT EXISTS formula_probe(norm_name text PRIMARY KEY, cnt int);
TRUNCATE formula_probe;
INSERT INTO formula_probe VALUES ('桂枝汤', 1), ('小柴胡汤', 1), ('清营汤', 1);
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT * FROM formula_probe WHERE norm_name = '桂枝汤';
