\pset pager off
\timing on

-- 1 方名：分词检索 vs 子串匹配的命中数
SELECT '桂枝汤' AS 查询词,
       (SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','桂枝汤')) AS 分词命中,
       (SELECT count(*) FROM units WHERE body LIKE '%桂枝汤%') AS 子串命中
UNION ALL
SELECT '小柴胡汤',
       (SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','小柴胡汤')),
       (SELECT count(*) FROM units WHERE body LIKE '%小柴胡汤%')
UNION ALL
SELECT '清营汤',
       (SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','清营汤')),
       (SELECT count(*) FROM units WHERE body LIKE '%清营汤%')
UNION ALL
SELECT '桂枝',
       (SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','桂枝')),
       (SELECT count(*) FROM units WHERE body LIKE '%桂枝%');

-- 2 症状词：检验"词被切碎后短语匹配"的假阳性
SELECT '恶寒' AS 查询词,
       (SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','恶寒')) AS 分词命中,
       (SELECT count(*) FROM units WHERE body LIKE '%恶寒%') AS 子串命中
UNION ALL
SELECT '太阳中风',
       (SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','太阳中风')),
       (SELECT count(*) FROM units WHERE body LIKE '%太阳中风%')
UNION ALL
SELECT '脉浮',
       (SELECT count(*) FROM units WHERE tsv @@ to_tsquery('chinese_zh','脉浮')),
       (SELECT count(*) FROM units WHERE body LIKE '%脉浮%');

-- 3 分词命中的假阳性样例：出现在分词结果里但不含该子串的段落
SELECT id, left(body, 40) AS 片段
FROM units
WHERE tsv @@ to_tsquery('chinese_zh','恶寒') AND body NOT LIKE '%恶寒%'
LIMIT 5;
