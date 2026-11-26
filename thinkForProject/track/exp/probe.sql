\pset pager off
SELECT '分词效果' AS 项目;
SELECT to_tsvector('chinese_zh', '桂枝汤主之，太阳中风，阳浮而阴弱，啬啬恶寒，淅淅恶风，翕翕发热，鼻鸣干呕者，桂枝汤主之') AS 词条;

SELECT '2 长句' AS 项目;
SELECT to_tsvector('chinese_zh', '《温病条辨·上·30》脉虚夜寐不安，烦渴舌赤，时有谵语，目常开不闭，或喜闭不开，暑入手厥阴也，清营汤主之') AS 词条;

SELECT '3 查询词' AS 项目;
SELECT to_tsquery('chinese_zh', '桂枝汤') AS 查询;

SELECT '4 匹配测试' AS 项目;
SELECT to_tsvector('chinese_zh', '太阳中风，阳浮而阴弱，桂枝汤主之') @@ to_tsquery('chinese_zh', '桂枝汤') AS 命中;
SELECT to_tsvector('chinese_zh', '太阳中风，阳浮而阴弱，桂枝汤主之') @@ to_tsquery('chinese_zh', '桂枝芍药知母汤') AS 不应命中;
