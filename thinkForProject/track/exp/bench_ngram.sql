\pset pager off
DROP TABLE IF EXISTS units;
CREATE TABLE units(id int PRIMARY KEY, body text);
COPY units FROM '/tmp/units.tsv' WITH (FORMAT text);
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX units_trgm_idx ON units USING gin(body gin_trgm_ops);
ANALYZE units;

SELECT '索引体积（8980 段 / 416367 字）' AS 项目;
SELECT pg_size_pretty(pg_relation_size('units')) AS 表,
       pg_size_pretty(pg_relation_size('units_trgm_idx')) AS trgm索引;

SELECT '1 字查询 芪' AS 项目;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE body LIKE '%芪%';

SELECT '2 字查询 桂枝' AS 项目;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE body LIKE '%桂枝%';

SELECT '3 字查询 桂枝汤' AS 项目;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE body LIKE '%桂枝汤%';

SELECT '4 字查询 桂枝汤加' AS 项目;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE body LIKE '%桂枝汤加%';

SELECT '5 字查询 桂枝汤主之' AS 项目;
EXPLAIN (ANALYZE, TIMING OFF, COSTS OFF) SELECT count(*) FROM units WHERE body LIKE '%桂枝汤主之%';
