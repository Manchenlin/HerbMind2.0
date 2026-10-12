-- 00 · 扩展与中文分词配置（initdb 顺序执行：00 → 01 → 02）
-- 说明：默认镜像 pgvector/pgvector:pg17 已含 vector；pg_jieba 需额外安装。

CREATE EXTENSION IF NOT EXISTS vector;     -- 向量检索（1024 维）
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- 模糊匹配

-- 尝试安装 pg_jieba；失败则用 simple 兜底创建名为 jiebacfg 的检索配置，
-- 保证后续 DDL 与查询不报错（中文分词效果有限）。
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_jieba') THEN
    CREATE EXTENSION IF NOT EXISTS pg_jieba;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'jiebacfg') THEN
    CREATE TEXT SEARCH CONFIGURATION jiebacfg ( COPY = simple );
    RAISE NOTICE 'pg_jieba 未安装：已用 simple 兜底创建 jiebacfg（见 README「关于 pg_jieba」）';
  END IF;
END $$;
