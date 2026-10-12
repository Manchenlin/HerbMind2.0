-- 02 · 通用关系表（兜底跨域/小众关系）
-- 见 06_数据库设计 §7：核心关系用专属表（formula_herb、content_unit…），
-- 跨域或小众关系用本表兜底，避免"一张表装天下"的 EAV 陷阱。
-- initdb 顺序：00 → 01 → 02（幂等）

CREATE TABLE IF NOT EXISTS relation (
  id        BIGSERIAL PRIMARY KEY,
  from_type TEXT NOT NULL,          -- case / formula / quote / herb ...
  from_id   TEXT NOT NULL,
  rel_type  TEXT NOT NULL,          -- cites / related / derived_from ...
  to_type   TEXT NOT NULL,
  to_id     TEXT NOT NULL,
  props     JSONB,
  book_id   TEXT REFERENCES book(id),
  UNIQUE (from_type, from_id, rel_type, to_type, to_id)
);
CREATE INDEX IF NOT EXISTS idx_relation_from ON relation(from_type, from_id);
CREATE INDEX IF NOT EXISTS idx_relation_to   ON relation(to_type, to_id);
