-- 04 · 索引与性能（见 06 §6）
-- initdb 顺序：00 → 01 → 02 → 03 → 04（全部幂等）

-- 向量：HNSW（余弦）—— 检索主索引
CREATE INDEX IF NOT EXISTS idx_cu_hnsw
  ON content_unit USING hnsw (embedding vector_cosine_ops);

-- 全文：GIN（01 已建 idx_cu_tsv，这里兜底保证存在）
CREATE INDEX IF NOT EXISTS idx_cu_tsv
  ON content_unit USING gin (search_tsv);

-- 高频过滤
CREATE INDEX IF NOT EXISTS idx_cu_ref     ON content_unit(ref_type, ref_id);
CREATE INDEX IF NOT EXISTS idx_cu_unit    ON content_unit(unit_type);
CREATE INDEX IF NOT EXISTS idx_formula_name ON formula(name);
CREATE INDEX IF NOT EXISTS idx_formula_node ON formula(node_id);
CREATE INDEX IF NOT EXISTS idx_case_formula ON case_record(main_formula_id);
CREATE INDEX IF NOT EXISTS idx_quote_article ON classic_quote(article_no);

-- 模糊匹配（pg_trgm）：方剂名 / 药名
CREATE INDEX IF NOT EXISTS idx_formula_name_trgm ON formula USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_herb_name_trgm    ON formula_herb USING gin (herb_name gin_trgm_ops);
