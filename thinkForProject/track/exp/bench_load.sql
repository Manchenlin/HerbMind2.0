\pset pager off
DROP TABLE IF EXISTS units;
CREATE TABLE units(id int PRIMARY KEY, body text);
COPY units FROM '/tmp/units.tsv' WITH (FORMAT text);
SELECT count(*) AS 行数, sum(length(body)) AS 总字数 FROM units;

ALTER TABLE units ADD COLUMN tsv tsvector;
\timing on
UPDATE units SET tsv = to_tsvector('chinese_zh', body);
\timing off

\timing on
CREATE INDEX units_tsv_idx ON units USING gin(tsv);
\timing off

SELECT pg_size_pretty(pg_total_relation_size('units')) AS 含索引大小,
       pg_size_pretty(pg_relation_size('units_tsv_idx')) AS tsvector索引;
