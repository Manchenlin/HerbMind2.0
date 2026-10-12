-- 01 · 表结构 v2（语料骨架 + 内容域 + 三域最小表）
-- 约定：ID 用 TEXT；时间用 TIMESTAMPTZ；生成列 search_tsv 禁止被 ORM 映射。

-- ============ A0 语料与骨架（插拔式） ============
CREATE TABLE IF NOT EXISTS book (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  book_type     TEXT NOT NULL CHECK (book_type IN ('fz','bencao','drug','case')),  -- 方证/本草/药品/医案
  author        TEXT,
  dynasty       TEXT,
  edition       TEXT,
  source_license TEXT,
  ingest_status TEXT NOT NULL DEFAULT 'draft',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 通用目录骨架（唯一目录表，自引用树）—— 替代原 book_chapter/section/category
CREATE TABLE IF NOT EXISTS book_node (
  id         TEXT PRIMARY KEY,
  book_id    TEXT NOT NULL REFERENCES book(id),
  classic_id TEXT,
  parent_id  TEXT REFERENCES book_node(id),
  node_type  TEXT NOT NULL CHECK (node_type IN ('chapter','section','category','unit')),
  title      TEXT NOT NULL,
  seq        INT NOT NULL DEFAULT 0,
  path_text  TEXT
);
CREATE INDEX IF NOT EXISTS idx_book_node_book   ON book_node(book_id);
CREATE INDEX IF NOT EXISTS idx_book_node_parent ON book_node(parent_id);

-- ============ A 内容域 ============
CREATE TABLE IF NOT EXISTS classic (
  id       TEXT PRIMARY KEY,
  book_id  TEXT REFERENCES book(id),
  name     TEXT,
  abbr     TEXT,
  dynasty  TEXT,
  path_text TEXT
);

CREATE TABLE IF NOT EXISTS formula (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  pinyin        TEXT,
  alias         TEXT,
  efficacy      TEXT,
  syndrome_text TEXT,
  source_text   TEXT,
  page          TEXT,
  node_id       TEXT REFERENCES book_node(id)     -- 原 category_id
);

CREATE TABLE IF NOT EXISTS formula_herb (
  id         BIGSERIAL PRIMARY KEY,
  formula_id TEXT REFERENCES formula(id),
  herb_name  TEXT NOT NULL,
  dose       NUMERIC,
  unit       TEXT,
  role       TEXT,                                 -- 君/臣/佐/使，可空
  seq        INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_formula_herb_formula ON formula_herb(formula_id);

CREATE TABLE IF NOT EXISTS case_record (
  id             TEXT PRIMARY KEY,
  title          TEXT,
  unit_type      TEXT,
  source_formula TEXT,
  main_formula_id TEXT REFERENCES formula(id),
  syndrome_text  TEXT,
  symptoms_jsonb JSONB,
  signs_jsonb    JSONB,
  page           TEXT
);

CREATE TABLE IF NOT EXISTS case_section (
  id      TEXT PRIMARY KEY,
  case_id TEXT REFERENCES case_record(id),
  kind    TEXT,   -- 提要/现病史/查体/辨证/治法/处方/效果/讨论/证治归纳/问题/问题解答
  content TEXT,
  seq     INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_case_section_case ON case_section(case_id);

CREATE TABLE IF NOT EXISTS classic_quote (
  id         TEXT PRIMARY KEY,
  article_no TEXT,
  classic_id TEXT REFERENCES classic(id),
  content    TEXT,
  plain_text TEXT,                                 -- AI 白话
  page       TEXT
);
CREATE INDEX IF NOT EXISTS idx_classic_quote_classic ON classic_quote(classic_id);

-- 统一内容单元（检索 / RAG 唯一入口；由 ETL 写入，search/agent 只读）
CREATE TABLE IF NOT EXISTS content_unit (
  id          TEXT PRIMARY KEY,
  book_id     TEXT REFERENCES book(id),
  unit_type   TEXT,            -- formula_full / case_full / quote / theory / section_abstract
  ref_type    TEXT,            -- formula / case_record / classic_quote / herb / drug
  ref_id      TEXT,
  title       TEXT,
  content     TEXT,
  embedding   vector(1024),
  search_tsv  tsvector GENERATED ALWAYS AS (to_tsvector('jiebacfg', coalesce(content,''))) STORED,
  meta_jsonb  JSONB,
  graph_synced BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_content_unit_book ON content_unit(book_id);
CREATE INDEX IF NOT EXISTS idx_content_unit_tsv  ON content_unit USING gin (search_tsv);
-- 向量索引（数据量大后再建亦可）：
-- CREATE INDEX ON content_unit USING hnsw (embedding vector_cosine_ops);

-- ============ B 用户域（域2，最小集） ============
CREATE TABLE IF NOT EXISTS app_user (
  id            TEXT PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT '游客',
  nickname      TEXT,
  avatar        TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ C 练习域（域2，最小集） ============
CREATE TABLE IF NOT EXISTS training_session (
  id          TEXT PRIMARY KEY,
  user_id     TEXT REFERENCES app_user(id),
  unit_ref    TEXT,
  mode        TEXT,          -- 先思后看 / 盲盒 / 背诵
  started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  duration_ms BIGINT
);

CREATE TABLE IF NOT EXISTS training_answer (
  id                    TEXT PRIMARY KEY,
  session_id            TEXT REFERENCES training_session(id),
  user_syndrome         TEXT,
  user_prescription_jsonb JSONB,
  user_treatment        TEXT,
  submitted_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS answer_score (
  id             TEXT PRIMARY KEY,
  answer_id      TEXT REFERENCES training_answer(id),
  syndrome_score NUMERIC,
  formula_score  NUMERIC,
  treatment_score NUMERIC,
  total          NUMERIC,
  hit_jsonb      JSONB,
  miss_jsonb     JSONB,
  extra_jsonb    JSONB
);
