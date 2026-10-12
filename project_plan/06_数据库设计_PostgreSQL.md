# 06 · 数据库设计（PostgreSQL）

> 主库：PostgreSQL 17，扩展 `pgvector`（向量 1024 维）+ `pg_jieba`（中文全文）+ `pg_trgm`（模糊匹配）。
> 承接现有 535 条结构化数据；在原 17 表基础**增强 + 扩充**。
> **支持插拔式多语料**（见 [14 插拔式书籍扩展方案](14_插拔式书籍扩展方案.md)）：顶层加 `book`/`book_node`，检索层统一为 `content_unit`。

> **✅ 实施状态（2026-10-12）**：**已建成并可复现**。
> 建库脚本 `HerbMind/database/pg/`：`00-extensions` → `01-schema`（语料骨架 + 内容域 + 最小三域）→ `02-relation`（通用关系兜底）→ `03-domains`（用户/练习/图谱规则/Agent/治理 + 专属关系表）→ `04-indexes`（HNSW 向量 + GIN 全文/trgm）。
> 实测：全新库顺序执行 **41 张表 / 73 个索引（含 1 个 HNSW）**，`errors=0`；真实数据 **245 方 / 290 案 / 568 条文 / 535 向量（1024 维）** 已入库。
> 与设计的差异：§2 A 域的 `case_quote_rel`/`formula_quote_rel` **保留为专属表**，另建通用 `relation` 兜底（§7 策略）；`study_path`/`study_path_item`、`symptom`/`sign` 等按 §2 逐字落地。

## 1. 设计原则

- **内容与用户分离**：书籍内容（catalog 域）与用户行为（identity/training 域）分表，互不耦合。
- **语料可插拔**：书籍以 `book`（语料）为顶层，`book_node` 为通用目录骨架；新增一本书 = 注册 + 跑导入，**不改表**。
- **文本 + 向量共存**：长文本落表，同时生成 `embedding`（pgvector）与 `search_tsv`（pg_jieba 全文）列。
- **图谱派生**：Neo4j 节点/关系由本库关系表 ETL 派生，不双写；用 `graph_synced` 标记。
- **可追溯**：内容变更留 `verify_log` / `audit_log`。

## 2. 表清单

### A0. 语料与骨架（新增 · 插拔式）

| 表 | 用途 | 关键字段 |
|---|---|---|
| `book` | 语料注册（一本书 = 一条；可含多部经典） | id, title, book_type(方证/本草/药品/医案), author, dynasty, edition, source_license, ingest_status |
| `book_node` | 通用目录骨架（**唯一目录表**，自引用树） | id, book_id, classic_id, parent_id, node_type(chapter/section/category/unit), title, seq, path_text |

> **选项 A（真收敛，已采纳）**：原 `book_chapter / book_section / book_category` **三表删除**，全部并入 `book_node` 一棵自引用树；层级为 `book → classic → book_node（章/节/类/单元，parent_id 递归）→ 内容`。任意语料通用。

### A. 内容域（catalog）

| 表 | 用途 | 关键字段 |
|---|---|---|
| `classic` | 经典著作（伤寒论/温病学/金匮要略） | id, book_id, name, abbr, dynasty, path_text |
| ~~`book_chapter` / `book_section` / `book_category`~~ | **已删除** → 并入 `book_node`（选项 A 真收敛） | — |
| `formula` | 方剂 | id, name, pinyin, alias, efficacy, syndrome_text, source_text, page, node_id(→book_node 叶子) |
| `formula_herb` | 方-药 | id, formula_id, herb_name, dose, unit, role(君臣佐使可空), seq |
| `case_record` | 案例 | id, title, unit_type, source_formula, main_formula_id, syndrome_text, symptoms_jsonb, signs_jsonb, page |
| `case_section` | 案例栏目 | id, case_id, kind(提要/现病史/查体/辨证/治法/处方/效果/讨论/证治归纳/问题/问题解答), content, seq |
| `classic_quote` | 经典条文 | id, article_no, classic_id, content, plain_text(AI 白话), page |
| `case_quote_rel` | 案-条文引用 | case_id, quote_id |
| `formula_quote_rel` | 方-条文引用 | formula_id, quote_id |
| `content_unit` | **统一内容单元**（原 `rag_chunk` 升级；所有书 / 所有类型的知识块统一入口，检索 / RAG 只面向此表） | id, book_id, unit_type, ref_type, ref_id, title, content, embedding vector(1024), search_tsv, meta_jsonb, graph_synced |

> `chunk_type` 取值：`formula_full / case_full / quote / theory / section_abstract`。

> **多语料特化表（按 `book.book_type` 选用，后续语料）**：本草类 `herb` + `herb_source`（性味/归经/功效/主治/炮制/禁忌）；药品类 `drug`（成分/规格/适应症/用法/不良反应/批准文号）；医案类复用 `case_record`。详见 [14](14_插拔式书籍扩展方案.md)。

### B. 用户域（identity）

| 表 | 用途 |
|---|---|
| `app_user` | 用户（id, username, password_hash, role, nickname, avatar, created_at） |
| `user_favorite` | 收藏（user_id, target_type, target_id, created_at） |
| `user_note` | 笔记（user_id, target_type, target_id, content, anchor, created_at） |
| `discuss_topic` | 讨论主题（按方证聚合） |
| `discuss_floor` | 讨论楼层（topic_id, user_id, content, quote_floor_id, is_pinned） |
| `note_reply` | 笔记回复 |

### C. 练习与学习域（training）

| 表 | 用途 | 关键字段 |
|---|---|---|
| `training_session` | 练习会话 | id, user_id, unit_ref, mode(先思后看/盲盒/背诵), started_at, duration_ms |
| `training_answer` | 答题 | id, session_id, user_syndrome, user_prescription_jsonb, user_treatment, submitted_at |
| `answer_score` | 评分明细 | id, answer_id, syndrome_score, formula_score, treatment_score, total, hit_jsonb, miss_jsonb, extra_jsonb |
| `training_record` | 兼容旧表（累计统计） | user_id, unit_ref, submitted_syndrome, is_correct, duration_ms |
| `wrong_book` | 错题本 | user_id, unit_ref, last_score, added_at |
| `learning_event` | 学习行为流 | user_id, event_type, ref, created_at |
| `learning_profile` | 学习画像 | user_id, radar_jsonb(三经典掌握度), streak_days, total_minutes |
| `study_path` / `study_path_item` | 学习路径与节点 | path, items(seq, unit_ref, reason) |
| `recite_record` | 背诵 SRS | user_id, quote_id, ease, next_review_at, last_result |

### D. 图谱/规则辅助域

| 表 | 用途 |
|---|---|
| `syndrome` | 证候字典（name, category(六经/卫气营血…), parent_id） |
| `symptom` / `sign` | 症状 / 舌脉体征字典 |
| `formula_syndrome_rel` | 方-证 关系 |
| `case_symptom_rel` | 案-症 关系 |
| `dosage_rule` | 剂量换算规则（dynasty, from_unit, to_gram, source） |

### E. Agent 域

| 表 | 用途 |
|---|---|
| `agent_conversation` | 会话（user_id, title, created_at） |
| `agent_message` | 消息（conversation_id, role, content, created_at） |
| `agent_tool_call` | 工具调用留痕（message_id, tool_name, args_jsonb, result_summary, latency_ms） |

### F. 治理域

| 表 | 用途 |
|---|---|
| `verify_log` | 校验记录（target_type, target_id, action, operator, note, created_at） |
| `content_review` | 复核工单（target, status(待复核/通过/驳回), assignee） |
| `issue` | OCR 疑点/问题清单（target_type, target_id, issue_type, desc, status） |
| `audit_log` | 全局操作审计 |

## 3. 关键关系（ER 摘要）

```
book 1─* classic 1─* book_node（章/节/类/单元，自引用树）
book_node（叶子/单元）1─* formula / case_record / classic_quote
formula 1─* formula_herb
formula *─* classic_quote   (formula_quote_rel)
case_record 1─* case_section
case_record *─* classic_quote (case_quote_rel)
formula *─* syndrome (formula_syndrome_rel)
app_user 1─* user_favorite / user_note / training_session / learning_event
training_session 1─* training_answer 1─1 answer_score
content_unit —— (book_id, ref_type, ref_id) 指向 formula / case_record / classic_quote / herb / drug …（多态，跨书跨类型）
```

## 4. 向量与全文检索

```sql
-- 向量召回（bge-m3, 1024 维, 余弦）
SELECT id, content, 1 - (embedding <=> %s::vector) AS score
FROM content_unit
WHERE (%s IS NULL OR meta_jsonb @> %s::jsonb)
ORDER BY embedding <=> %s::vector
LIMIT 20;

-- 中文全文（pg_jieba）
SELECT id, content, ts_rank(search_tsv, plainto_tsquery('jiebacfg', %s)) AS rank
FROM content_unit
WHERE search_tsv @@ plainto_tsquery('jiebacfg', %s)
ORDER BY rank DESC
LIMIT 20;
```

混合召回：向量 Top-K ⊕ 全文 Top-K → 去重 + RRF/加权重排 → 送 Agent。

## 5. 与现有 17 表的对应

| 现有表 | 处理 |
|---|---|
| classic | **保留** + 补 `book_id`、`path_text` |
| book_chapter / book_section / book_category | **删除**，并入 `book_node`（选项 A 真收敛） |
| formula / formula_herb | **保留** + 补 `efficacy`(现缺失)、`syndrome_text`、`pinyin`、`role` |
| case_record / case_section | **保留** + 补 `syndrome_text`、`symptoms_jsonb`、`signs_jsonb`、`unit_type` |
| classic_quote / case_quote_rel | **保留** + 补 `plain_text`、`formula_quote_rel` |
| app_user / user_favorite / user_note | **保留** |
| training_record | **保留兼容**；新增 `training_session/answer/score` 承载完整评分 |
| case_discuss | **拆分**为 `discuss_topic/discuss_floor` |
| rag_chunk | **升级为 `content_unit`** + 补 `book_id`、`unit_type`、`ref_type`、`search_tsv`、`graph_synced` |
| verify_log | **保留** + 新增 `content_review/issue/audit_log` |
| — | **新增顶层**：`book`（语料）、`book_node`（唯一目录表）；原 chapter/section/category **三表删除并入** `book_node` |
| — | **新增**：syndrome/symptom/sign、formula_syndrome_rel、case_symptom_rel、wrong_book、learning_event/profile、study_path、recite_record、dosage_rule、agent_*、herb/drug（后续语料特化） |

## 6. 索引与性能

- 向量列建 HNSW 索引：`USING hnsw (embedding vector_cosine_ops)`。
- 全文列建 GIN 索引：`USING gin (search_tsv)`。
- 高频过滤列（book_id、classic_id、node_id、target_type、user_id）建 B-Tree。
- 大文本（case_section.content）与向量分表/分区存储，避免全表扫描。

## 7. 插拔式扩展（多语料）

四层「骨架共用 + 类型特化」（详见 [14](14_插拔式书籍扩展方案.md)）：

```
① content_unit        统一内容单元（向量+全文）—— 检索 / RAG 唯一入口
② 特化实体            方证 formula / 本草 herb / 药品 drug / 医案 case（按 book_type 选用）
③ book_node           通用目录骨架（章 / 节 / 类 / 单元）
④ book                语料注册（书名 / 类型 / 版权 / 状态）
```

**关系泛化**：核心关系用专属表（`formula_herb`、`case_quote_rel` …，类型安全）；跨域 / 小众关系用通用表兜底 `relation(from_type, from_id, rel_type, to_type, to_id, props jsonb, book_id)`。**不追求"一张表装天下"（避开 EAV 陷阱）。**

**归属与同步**：`content_unit` 由 **ETL 写入**（`database/etl/`），`svc-search` / Agent **只读**；内容表（catalog 域）为**唯一事实源**。内容变更**不实时同步**索引与图谱——由 ETL **定时 / 手动**重建，`graph_synced` 标记进度（v1 不引入消息队列，见 [05 §4.3](05_系统技术架构.md)）。
