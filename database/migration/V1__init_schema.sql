-- ============================================================================
-- HerbMind 数据库初始化脚本 V1
-- 依据：thinkForProject/docs/06_数据库设计说明书.md（v0.4）
--       §3 表定义、§4.1 外键与 ON DELETE 策略、§5.2 索引 DDL、§7 初始化数据
-- 目标：PostgreSQL 16
--
-- 说明：
--   1. 本脚本可在空库上按顺序一次执行（psql -f V1__init_schema.sql）。
--   2. 共 30 张表、37 条索引；ID 为应用生成的 UUID 字符串（varchar(36)），
--      时间统一 timestamptz，JSON 列用 jsonb，数组列用 text[]。
--   3. 全库仅三处 ON DELETE CASCADE：question_unit → question、
--      五张学习记录表 / revoked_token → app_user；其余一律 RESTRICT。
--   4. 多态引用（favorite、note、review_item、conflict）不建外键，
--      由应用层写入前校验 + 每日对账兜底（见 §2.3、§4.4）。
-- ============================================================================

-- 扩展（§5.2）：pg_trgm 用于 content_unit.norm_text 的子串检索
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- ============================================================================
-- §3.1 书目与导入（7 张）
-- ============================================================================

-- 3.1.2 书目申请（先建，供 book.application_id 引用）
CREATE TABLE IF NOT EXISTS book_application (
    id            varchar(36)  NOT NULL,
    title         varchar(200) NOT NULL,
    author        varchar(100) NOT NULL,
    dynasty       varchar(50),
    edition       varchar(200) NOT NULL,
    catalog       text         NOT NULL,
    purpose       text         NOT NULL,
    status        varchar(8)   NOT NULL DEFAULT '待审'
                  CHECK (status IN ('待审', '通过', '驳回')),
    reject_reason text,
    reviewer      varchar(36),
    reviewed_at   timestamptz,
    check_status  varchar(8)   NOT NULL DEFAULT '待检'
                  CHECK (check_status IN ('待检', '通过', '拦截')),
    submitted_at  timestamptz  NOT NULL DEFAULT now(),
    created_at    timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_book_application PRIMARY KEY (id),
    CONSTRAINT ck_book_application_reject
        CHECK (status <> '驳回' OR (reject_reason IS NOT NULL AND btrim(reject_reason) <> '')),
    CONSTRAINT ck_book_application_review
        CHECK (status <> '通过' OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL))
);

-- 3.1.1 书目
CREATE TABLE IF NOT EXISTS book (
    id             varchar(36)  NOT NULL,
    application_id varchar(36),
    name           varchar(200) NOT NULL,
    author         varchar(100) NOT NULL,
    dynasty        varchar(50),
    edition        varchar(200) NOT NULL,
    status         varchar(16)  NOT NULL DEFAULT '待导入'
                   CHECK (status IN ('待导入', '已入库', '已停用')),
    created_at     timestamptz  NOT NULL DEFAULT now(),
    updated_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_book PRIMARY KEY (id),
    CONSTRAINT uq_book_application UNIQUE (application_id),
    CONSTRAINT fk_book_application FOREIGN KEY (application_id)
        REFERENCES book_application (id) ON DELETE RESTRICT
);

-- 3.1.3 导入任务
CREATE TABLE IF NOT EXISTS import_task (
    id                     varchar(36)   NOT NULL,
    book_id                varchar(36)   NOT NULL,
    status                 varchar(16)   NOT NULL DEFAULT '排队'
                           CHECK (status IN ('排队', '解析中', '切分中', '标注中', '质检中', '已完成', '失败')),
    stage                  varchar(8),
    started_at             timestamptz,
    finished_at            timestamptz,
    total_units            integer       NOT NULL DEFAULT 0,
    dedup_count            integer       NOT NULL DEFAULT 0,
    fragment_count         integer       NOT NULL DEFAULT 0,
    nature_prefill_rate    numeric(5,2),
    vocab_match_rate       numeric(5,2),
    collision_pending_count integer      NOT NULL DEFAULT 0,
    error_kind             varchar(32),
    idempotency_key        varchar(64)   NOT NULL,
    created_at             timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT pk_import_task PRIMARY KEY (id),
    CONSTRAINT fk_import_task_book FOREIGN KEY (book_id)
        REFERENCES book (id) ON DELETE RESTRICT,
    CONSTRAINT ck_import_task_counts
        CHECK (total_units >= 0 AND dedup_count >= 0
               AND fragment_count >= 0 AND collision_pending_count >= 0),
    CONSTRAINT ck_import_task_rates
        CHECK ((nature_prefill_rate IS NULL OR nature_prefill_rate BETWEEN 0 AND 100)
               AND (vocab_match_rate IS NULL OR vocab_match_rate BETWEEN 0 AND 100))
);

-- 3.1.6 篇章（自关联树；放在 content_unit 之前，先建 book 外键）
CREATE TABLE IF NOT EXISTS chapter (
    id         varchar(36)  NOT NULL,
    book_id    varchar(36)  NOT NULL,
    parent_id  varchar(36),
    name       varchar(200) NOT NULL,
    level      smallint     NOT NULL,
    seq        integer      NOT NULL,
    created_at timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_chapter PRIMARY KEY (id),
    CONSTRAINT fk_chapter_book FOREIGN KEY (book_id)
        REFERENCES book (id) ON DELETE RESTRICT,
    -- 删章禁止，只能停用整本书，故父章外键不做级联
    CONSTRAINT fk_chapter_parent FOREIGN KEY (parent_id)
        REFERENCES chapter (id) ON DELETE RESTRICT
);

-- 3.1.7 内容单元（全系统核心表）
CREATE TABLE IF NOT EXISTS content_unit (
    id                    varchar(36) NOT NULL,
    book_id               varchar(36) NOT NULL,
    chapter_id            varchar(36) NOT NULL,
    seq                   integer     NOT NULL,
    display_text          text        NOT NULL,
    norm_text             text        NOT NULL,
    norm_version          varchar(16) NOT NULL DEFAULT 'zh-norm-1.0',
    source_nature         varchar(8)  NOT NULL
                          CHECK (source_nature IN ('典籍原文', '注释', '教学论述', '医案', '其他（非正文）')),
    clause_no             varchar(32),
    quoted_from_book      varchar(200),
    quoted_from_chapter   varchar(200),
    quoted_from_clause    varchar(32),
    criteria_complete     boolean     NOT NULL DEFAULT false,
    criteria_missing_note text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_content_unit PRIMARY KEY (id),
    CONSTRAINT fk_content_unit_book FOREIGN KEY (book_id)
        REFERENCES book (id) ON DELETE RESTRICT,
    CONSTRAINT fk_content_unit_chapter FOREIGN KEY (chapter_id)
        REFERENCES chapter (id) ON DELETE RESTRICT,
    CONSTRAINT ck_content_unit_seq CHECK (seq >= 1),
    CONSTRAINT ck_content_unit_criteria
        CHECK (NOT criteria_complete OR criteria_missing_note IS NULL)
);

-- 3.1.4 修正留痕（只增不改）
CREATE TABLE IF NOT EXISTS correction (
    id          varchar(36) NOT NULL,
    unit_id     varchar(36) NOT NULL,
    field       varchar(32) NOT NULL
                CHECK (field IN ('display_text', 'source_nature', 'clause_no', 'seq',
                                 'chapter_id', 'quoted_from_book', 'quoted_from_chapter',
                                 'quoted_from_clause')),
    old_value   text,
    new_value   text,
    operator_id varchar(36) NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_correction PRIMARY KEY (id),
    CONSTRAINT fk_correction_unit FOREIGN KEY (unit_id)
        REFERENCES content_unit (id) ON DELETE RESTRICT
);

-- 3.1.5 碰撞清单（未确认的组不得入库）
CREATE TABLE IF NOT EXISTS norm_collision (
    id             varchar(36) NOT NULL,
    import_task_id varchar(36) NOT NULL,
    display_a      text        NOT NULL,
    display_b      text        NOT NULL,
    unit_a         varchar(36),
    unit_b         varchar(36),
    verdict        varchar(8)  NOT NULL DEFAULT '未确认'
                   CHECK (verdict IN ('未确认', '确认重复', '确认不同')),
    resolved_by    varchar(36),
    resolved_at    timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_norm_collision PRIMARY KEY (id),
    CONSTRAINT fk_norm_collision_task FOREIGN KEY (import_task_id)
        REFERENCES import_task (id) ON DELETE RESTRICT,
    CONSTRAINT fk_norm_collision_unit_a FOREIGN KEY (unit_a)
        REFERENCES content_unit (id) ON DELETE RESTRICT,
    CONSTRAINT fk_norm_collision_unit_b FOREIGN KEY (unit_b)
        REFERENCES content_unit (id) ON DELETE RESTRICT,
    CONSTRAINT ck_norm_collision_unresolved
        CHECK (verdict <> '未确认' OR (resolved_by IS NULL AND resolved_at IS NULL))
);


-- ============================================================================
-- §3.2 内容实体（8 张）
-- ============================================================================

-- 3.2.1 方剂
CREATE TABLE IF NOT EXISTS formula (
    id         varchar(36)  NOT NULL,
    book_id    varchar(36)  NOT NULL,
    name       varchar(200) NOT NULL,
    norm_name  varchar(200) NOT NULL,
    created_at timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_formula PRIMARY KEY (id),
    CONSTRAINT fk_formula_book FOREIGN KEY (book_id)
        REFERENCES book (id) ON DELETE RESTRICT
);

-- 3.2.2 方名别名
CREATE TABLE IF NOT EXISTS formula_alias (
    id         varchar(36)  NOT NULL,
    formula_id varchar(36)  NOT NULL,
    alias      varchar(200) NOT NULL,
    norm_alias varchar(200) NOT NULL,
    created_at timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_formula_alias PRIMARY KEY (id),
    CONSTRAINT fk_formula_alias_formula FOREIGN KEY (formula_id)
        REFERENCES formula (id) ON DELETE RESTRICT
);

-- 3.2.3 药味（跨书共享）
CREATE TABLE IF NOT EXISTS herb (
    id         varchar(36)  NOT NULL,
    name       varchar(100) NOT NULL,
    norm_name  varchar(100) NOT NULL,
    created_at timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_herb PRIMARY KEY (id)
);

-- 3.2.4 药味异名
CREATE TABLE IF NOT EXISTS herb_alias (
    id         varchar(36)  NOT NULL,
    herb_id    varchar(36)  NOT NULL,
    alias      varchar(100) NOT NULL,
    norm_alias varchar(100) NOT NULL,
    created_at timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_herb_alias PRIMARY KEY (id),
    CONSTRAINT fk_herb_alias_herb FOREIGN KEY (herb_id)
        REFERENCES herb (id) ON DELETE RESTRICT
);

-- 3.2.5 组成项
CREATE TABLE IF NOT EXISTS formula_herb (
    id          varchar(36) NOT NULL,
    formula_id  varchar(36) NOT NULL,
    herb_id     varchar(36) NOT NULL,
    dosage_text text,
    seq         smallint    NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_formula_herb PRIMARY KEY (id),
    CONSTRAINT fk_formula_herb_formula FOREIGN KEY (formula_id)
        REFERENCES formula (id) ON DELETE RESTRICT,
    CONSTRAINT fk_formula_herb_herb FOREIGN KEY (herb_id)
        REFERENCES herb (id) ON DELETE RESTRICT
);

-- 3.2.6 提及项
CREATE TABLE IF NOT EXISTS mention (
    id         varchar(36) NOT NULL,
    unit_id    varchar(36) NOT NULL,
    formula_id varchar(36) NOT NULL,
    is_primary boolean     NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_mention PRIMARY KEY (id),
    CONSTRAINT fk_mention_unit FOREIGN KEY (unit_id)
        REFERENCES content_unit (id) ON DELETE RESTRICT,
    CONSTRAINT fk_mention_formula FOREIGN KEY (formula_id)
        REFERENCES formula (id) ON DELETE RESTRICT
);

-- 3.2.7 医案（只存 unit_id，正文以 content_unit 为准）
CREATE TABLE IF NOT EXISTS case_record (
    id         varchar(36) NOT NULL,
    unit_id    varchar(36) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_case_record PRIMARY KEY (id),
    CONSTRAINT fk_case_record_unit FOREIGN KEY (unit_id)
        REFERENCES content_unit (id) ON DELETE RESTRICT
);

-- 3.2.8 医案所用方
CREATE TABLE IF NOT EXISTS case_formula (
    id         varchar(36) NOT NULL,
    case_id    varchar(36) NOT NULL,
    formula_id varchar(36) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_case_formula PRIMARY KEY (id),
    CONSTRAINT fk_case_formula_case FOREIGN KEY (case_id)
        REFERENCES case_record (id) ON DELETE RESTRICT,
    CONSTRAINT fk_case_formula_formula FOREIGN KEY (formula_id)
        REFERENCES formula (id) ON DELETE RESTRICT
);


-- ============================================================================
-- §3.3 练习（3 张）
-- ============================================================================

-- 3.3.3 题型白名单（唯一"枚举落表"的例外，须先于 question 建立）
CREATE TABLE IF NOT EXISTS question_type (
    code       varchar(8)  NOT NULL,
    name       varchar(32) NOT NULL,
    enabled    boolean     NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_question_type PRIMARY KEY (code)
);

-- 3.3.1 题目
CREATE TABLE IF NOT EXISTS question (
    id             varchar(36) NOT NULL,
    type           varchar(8)  NOT NULL,
    stem           text        NOT NULL,
    options        jsonb,
    answer_key     text        NOT NULL,
    answer_unique  boolean     NOT NULL DEFAULT true,
    fingerprint    varchar(64) NOT NULL,
    invalidated_at timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_question PRIMARY KEY (id),
    -- 题型取值交由白名单外键保证，不写取值 CHECK（BR-08）
    CONSTRAINT fk_question_type FOREIGN KEY (type)
        REFERENCES question_type (code) ON DELETE RESTRICT,
    CONSTRAINT ck_question_answer_unique CHECK (answer_unique)
);

-- 3.3.2 题目依据单元
CREATE TABLE IF NOT EXISTS question_unit (
    id          varchar(36) NOT NULL,
    question_id varchar(36) NOT NULL,
    unit_id     varchar(36) NOT NULL,
    ord         smallint    NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_question_unit PRIMARY KEY (id),
    -- 题目作废时依据随之删除（全库三处 CASCADE 之一）
    CONSTRAINT fk_question_unit_question FOREIGN KEY (question_id)
        REFERENCES question (id) ON DELETE CASCADE,
    CONSTRAINT fk_question_unit_unit FOREIGN KEY (unit_id)
        REFERENCES content_unit (id) ON DELETE RESTRICT
);


-- ============================================================================
-- §3.4 账号与学习记录（7 张）
-- ============================================================================

-- 3.4.1 用户
CREATE TABLE IF NOT EXISTS app_user (
    id            varchar(36) NOT NULL,
    openid        varchar(64) NOT NULL,
    role          varchar(8)  NOT NULL DEFAULT '学习者'
                  CHECK (role IN ('学习者', '管理员')),
    status        varchar(8)  NOT NULL DEFAULT '正常'
                  CHECK (status IN ('正常', '锁定')),
    failed_count  integer     NOT NULL DEFAULT 0,
    locked_until  timestamptz,
    password_hash varchar(100),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_app_user PRIMARY KEY (id),
    CONSTRAINT uq_app_user_openid UNIQUE (openid)
);

-- 3.4.2 令牌吊销清单
CREATE TABLE IF NOT EXISTS revoked_token (
    jti        varchar(64) NOT NULL,
    user_id    varchar(36) NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_revoked_token PRIMARY KEY (jti),
    CONSTRAINT fk_revoked_token_user FOREIGN KEY (user_id)
        REFERENCES app_user (id) ON DELETE CASCADE
);

-- 3.4.3 阅读进度（每用户一行）
CREATE TABLE IF NOT EXISTS reading_progress (
    id         varchar(36) NOT NULL,
    user_id    varchar(36) NOT NULL,
    book_id    varchar(36) NOT NULL,
    chapter_id varchar(36) NOT NULL,
    unit_id    varchar(36) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_reading_progress PRIMARY KEY (id),
    CONSTRAINT fk_reading_progress_user FOREIGN KEY (user_id)
        REFERENCES app_user (id) ON DELETE CASCADE,
    CONSTRAINT fk_reading_progress_book FOREIGN KEY (book_id)
        REFERENCES book (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reading_progress_chapter FOREIGN KEY (chapter_id)
        REFERENCES chapter (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reading_progress_unit FOREIGN KEY (unit_id)
        REFERENCES content_unit (id) ON DELETE RESTRICT
);

-- 3.4.4 收藏（多态引用，object_id 不建外键）
CREATE TABLE IF NOT EXISTS favorite (
    id          varchar(36) NOT NULL,
    user_id     varchar(36) NOT NULL,
    object_type varchar(16) NOT NULL
                CHECK (object_type IN ('content_unit', 'formula', 'case_record')),
    object_id   varchar(36) NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_favorite PRIMARY KEY (id),
    CONSTRAINT fk_favorite_user FOREIGN KEY (user_id)
        REFERENCES app_user (id) ON DELETE CASCADE
);

-- 3.4.5 笔记（多态引用）
CREATE TABLE IF NOT EXISTS note (
    id          varchar(36) NOT NULL,
    user_id     varchar(36) NOT NULL,
    object_type varchar(16) NOT NULL
                CHECK (object_type IN ('content_unit', 'formula', 'case_record')),
    object_id   varchar(36) NOT NULL,
    text        text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_note PRIMARY KEY (id),
    CONSTRAINT fk_note_user FOREIGN KEY (user_id)
        REFERENCES app_user (id) ON DELETE CASCADE
);

-- 3.4.6 作答
CREATE TABLE IF NOT EXISTS attempt (
    id          varchar(36) NOT NULL,
    user_id     varchar(36) NOT NULL,
    question_id varchar(36) NOT NULL,
    answer      text        NOT NULL,
    is_correct  boolean     NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_attempt PRIMARY KEY (id),
    CONSTRAINT fk_attempt_user FOREIGN KEY (user_id)
        REFERENCES app_user (id) ON DELETE CASCADE,
    -- 删作答不删题目（05 §11.13）
    CONSTRAINT fk_attempt_question FOREIGN KEY (question_id)
        REFERENCES question (id) ON DELETE RESTRICT
);

-- 3.4.7 复习条目（多态引用）
CREATE TABLE IF NOT EXISTS review_item (
    id             varchar(36) NOT NULL,
    user_id        varchar(36) NOT NULL,
    object_type    varchar(16) NOT NULL
                   CHECK (object_type IN ('content_unit', 'formula', 'case_record')),
    object_id      varchar(36) NOT NULL,
    interval_index smallint    NOT NULL DEFAULT 0
                   CHECK (interval_index BETWEEN 0 AND 5),
    due_at         timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_review_item PRIMARY KEY (id),
    CONSTRAINT fk_review_item_user FOREIGN KEY (user_id)
        REFERENCES app_user (id) ON DELETE CASCADE
);


-- ============================================================================
-- §3.5 治理与安全（5 张）
-- ============================================================================

-- 3.5.1 缺口
CREATE TABLE IF NOT EXISTS gap (
    id                varchar(36) NOT NULL,
    question_text     text        NOT NULL,
    book_id           varchar(36),
    check_status      varchar(8)  NOT NULL DEFAULT '待检'
                      CHECK (check_status IN ('待检', '通过', '拦截')),
    status            varchar(8)  NOT NULL DEFAULT '待处理'
                      CHECK (status IN ('待处理', '已补', '不可补')),
    queued_at         timestamptz NOT NULL DEFAULT now(),
    handler           varchar(36),
    handled_at        timestamptz,
    handle_result     text,
    client_request_id varchar(64) NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_gap PRIMARY KEY (id),
    CONSTRAINT fk_gap_book FOREIGN KEY (book_id)
        REFERENCES book (id) ON DELETE RESTRICT,
    CONSTRAINT ck_gap_handled
        CHECK (status = '待处理'
               OR (handler IS NOT NULL AND handled_at IS NOT NULL AND handle_result IS NOT NULL)),
    CONSTRAINT ck_gap_unfixable
        CHECK (status <> '不可补' OR btrim(handle_result) <> '')
);

-- 3.5.2 冲突（多态引用；values / sources 为保留字，必须加双引号）
CREATE TABLE IF NOT EXISTS conflict (
    id            varchar(36) NOT NULL,
    entity_type   varchar(16) NOT NULL
                  CHECK (entity_type IN ('formula', 'herb', 'content_unit')),
    entity_id     varchar(36) NOT NULL,
    field         varchar(32) NOT NULL,
    "values"      text[]      NOT NULL,
    "sources"     text[]      NOT NULL,
    status        varchar(16) NOT NULL DEFAULT '已检出'
                  CHECK (status IN ('已检出', '已确认差异', '已修正', '已驳回')),
    handler       varchar(36),
    handled_at    timestamptz,
    handle_result text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_conflict PRIMARY KEY (id),
    CONSTRAINT ck_conflict_parallel
        CHECK (cardinality("values") = cardinality("sources") AND cardinality("values") > 0),
    CONSTRAINT ck_conflict_handled
        CHECK (status = '已检出'
               OR (handler IS NOT NULL AND handled_at IS NOT NULL AND handle_result IS NOT NULL))
);

-- 3.5.3 检测记录（只存场景、结果、匿名标识与时间）
CREATE TABLE IF NOT EXISTS safety_check (
    id             varchar(36) NOT NULL,
    scene          varchar(32) NOT NULL,
    result         varchar(8)  NOT NULL
                   CHECK (result IN ('通过', '拦截')),
    target_anon_id varchar(64),
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_safety_check PRIMARY KEY (id)
);

-- 3.5.4 审计记录（只增不改，无 updated_at）
CREATE TABLE IF NOT EXISTS audit_log (
    id             varchar(36) NOT NULL,
    actor_id       varchar(36),
    action         varchar(32) NOT NULL,
    target_type    varchar(32) NOT NULL,
    target_id      varchar(36),
    result_summary text,
    detail         jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_audit_log PRIMARY KEY (id)
);

-- 3.5.5 数据缺陷
CREATE TABLE IF NOT EXISTS data_defect (
    id                        varchar(36) NOT NULL,
    kind                      varchar(16) NOT NULL
                              CHECK (kind IN ('出处不全', '跨表不一致', '归一碰撞未确认')),
    status                    varchar(8)  NOT NULL DEFAULT '待返工'
                              CHECK (status IN ('待返工', '已返工', '已关闭')),
    book_id                   varchar(36),
    unit_id                   varchar(36),
    batch_id                  varchar(36),
    detail                    text        NOT NULL,
    resolved_by_correction_id varchar(36),
    created_at                timestamptz NOT NULL DEFAULT now(),
    resolved_at               timestamptz,
    CONSTRAINT pk_data_defect PRIMARY KEY (id),
    CONSTRAINT fk_data_defect_book FOREIGN KEY (book_id)
        REFERENCES book (id) ON DELETE RESTRICT,
    CONSTRAINT fk_data_defect_unit FOREIGN KEY (unit_id)
        REFERENCES content_unit (id) ON DELETE RESTRICT,
    CONSTRAINT fk_data_defect_batch FOREIGN KEY (batch_id)
        REFERENCES import_task (id) ON DELETE RESTRICT,
    CONSTRAINT fk_data_defect_correction FOREIGN KEY (resolved_by_correction_id)
        REFERENCES correction (id) ON DELETE RESTRICT,
    CONSTRAINT ck_data_defect_locatable
        CHECK (unit_id IS NOT NULL OR batch_id IS NOT NULL),
    CONSTRAINT ck_data_defect_pending
        CHECK (status <> '待返工' OR resolved_at IS NULL),
    CONSTRAINT ck_data_defect_reworked
        CHECK (status <> '已返工' OR resolved_by_correction_id IS NOT NULL)
);


-- ============================================================================
-- §5.2 索引 DDL（共 37 条）
-- ============================================================================

-- 章节树（1）
CREATE UNIQUE INDEX IF NOT EXISTS uq_chapter_tree
  ON chapter (book_id, parent_id, seq) NULLS NOT DISTINCT;

-- 内容单元（2-4）
CREATE UNIQUE INDEX IF NOT EXISTS uq_content_unit_pos
  ON content_unit (book_id, chapter_id, seq);
CREATE INDEX IF NOT EXISTS gin_content_unit_norm
  ON content_unit USING gin (norm_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_content_unit_nature
  ON content_unit (book_id, source_nature);

-- 方剂与药味（5-11）
CREATE UNIQUE INDEX IF NOT EXISTS uq_formula_book_norm
  ON formula (book_id, norm_name);
CREATE INDEX IF NOT EXISTS ix_formula_alias_norm
  ON formula_alias (norm_alias);
CREATE UNIQUE INDEX IF NOT EXISTS uq_formula_alias
  ON formula_alias (formula_id, norm_alias);
CREATE UNIQUE INDEX IF NOT EXISTS uq_herb_norm
  ON herb (norm_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_herb_alias
  ON herb_alias (herb_id, norm_alias);
CREATE INDEX IF NOT EXISTS ix_herb_alias_norm
  ON herb_alias (norm_alias);
CREATE INDEX IF NOT EXISTS ix_formula_herb_herb
  ON formula_herb (herb_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_formula_herb
  ON formula_herb (formula_id, herb_id);

-- 提及、医案（12-15）
CREATE UNIQUE INDEX IF NOT EXISTS uq_mention
  ON mention (unit_id, formula_id);
CREATE INDEX IF NOT EXISTS ix_mention_formula
  ON mention (formula_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_case_record_unit
  ON case_record (unit_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_case_formula
  ON case_formula (case_id, formula_id);

-- 练习（16-17）
CREATE UNIQUE INDEX IF NOT EXISTS uq_question_unit
  ON question_unit (question_id, unit_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_question_unit_ord
  ON question_unit (question_id, ord);

-- 学习记录（18-22）
CREATE UNIQUE INDEX IF NOT EXISTS uq_review_item_obj
  ON review_item (user_id, object_type, object_id);
CREATE INDEX IF NOT EXISTS ix_review_item_due
  ON review_item (user_id, due_at);
CREATE INDEX IF NOT EXISTS ix_attempt_user_time
  ON attempt (user_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_favorite_obj
  ON favorite (user_id, object_type, object_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reading_progress_user
  ON reading_progress (user_id);

-- 导入与治理队列（23-30）
CREATE UNIQUE INDEX IF NOT EXISTS uq_import_task_idem
  ON import_task (idempotency_key);
CREATE INDEX IF NOT EXISTS ix_import_task_status
  ON import_task (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_import_task_active
  ON import_task (book_id)
  WHERE status IN ('排队', '解析中', '切分中', '标注中', '质检中');
CREATE INDEX IF NOT EXISTS ix_gap_status
  ON gap (status, created_at);
CREATE INDEX IF NOT EXISTS ix_gap_check
  ON gap (check_status);
CREATE INDEX IF NOT EXISTS ix_conflict_status
  ON conflict (status, created_at);
CREATE INDEX IF NOT EXISTS ix_book_app_check
  ON book_application (check_status);

-- 审计（31-32）
CREATE INDEX IF NOT EXISTS ix_audit_target
  ON audit_log (target_type, target_id);
CREATE INDEX IF NOT EXISTS ix_audit_at
  ON audit_log (created_at);

-- 队列与留痕（33-35）
CREATE INDEX IF NOT EXISTS ix_correction_unit
  ON correction (unit_id, created_at);
CREATE INDEX IF NOT EXISTS ix_norm_collision_batch
  ON norm_collision (import_task_id, verdict);
CREATE INDEX IF NOT EXISTS ix_data_defect_status
  ON data_defect (status, created_at);

-- 题目复用与去重（36-37）
CREATE UNIQUE INDEX IF NOT EXISTS uq_question_fingerprint
  ON question (fingerprint);
CREATE INDEX IF NOT EXISTS ix_question_unit_unit
  ON question_unit (unit_id);


-- ============================================================================
-- §7 初始化数据
-- ============================================================================

-- 7.1 题型白名单（停用只改 enabled，不删行）
INSERT INTO question_type (code, name, enabled) VALUES
  ('选择题',   '选择题',   true),
  ('组成匹配', '组成匹配', true),
  ('类方比较', '类方比较', true);

-- 7.2 复习间隔六档：不入库，作为应用配置 review.intervals_days = [1, 2, 4, 7, 15, 30]
--     对应 review_item.interval_index 0～5（答对 +1、答错 -1、封顶 5，FR-409）
-- 7.3 免责声明文案键：不入库，作为应用资源键
--     disclaimer.reading / disclaimer.exercise / disclaimer.answer（FR-207）
-- 7.4 保留期参数：不设初始化参数（保留期是需求承诺，不是运营配置，见 §6.4）
