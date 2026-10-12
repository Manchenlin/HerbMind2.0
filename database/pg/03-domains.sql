-- 03 · 其余域完整表（B 用户 / C 练习学习 / D 图谱规则 / E Agent / F 治理）+ 专属关系表
-- 见 06_数据库设计 §2。initdb 顺序：00 → 01 → 02 → 03（全部幂等）

-- ============ A 域补充：专属关系表（核心关系用专属表，跨域兜底才用 relation） ============
CREATE TABLE IF NOT EXISTS case_quote_rel (
  case_id  TEXT NOT NULL REFERENCES case_record(id),
  quote_id TEXT NOT NULL REFERENCES classic_quote(id),
  PRIMARY KEY (case_id, quote_id)
);
CREATE TABLE IF NOT EXISTS formula_quote_rel (
  formula_id TEXT NOT NULL REFERENCES formula(id),
  quote_id   TEXT NOT NULL REFERENCES classic_quote(id),
  PRIMARY KEY (formula_id, quote_id)
);

-- ============ B. 用户域（identity · 域2） ============
CREATE TABLE IF NOT EXISTS user_favorite (
  id          BIGSERIAL PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES app_user(id),
  target_type TEXT NOT NULL,          -- formula / case / quote
  target_id   TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS user_note (
  id          BIGSERIAL PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES app_user(id),
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  content     TEXT,
  anchor      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_note_user   ON user_note(user_id);
CREATE INDEX IF NOT EXISTS idx_user_note_target ON user_note(target_type, target_id);

CREATE TABLE IF NOT EXISTS discuss_topic (
  id          TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  title       TEXT,
  user_id     TEXT REFERENCES app_user(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_discuss_topic_target ON discuss_topic(target_type, target_id);

CREATE TABLE IF NOT EXISTS discuss_floor (
  id              TEXT PRIMARY KEY,
  topic_id        TEXT NOT NULL REFERENCES discuss_topic(id),
  user_id         TEXT REFERENCES app_user(id),
  content         TEXT,
  quote_floor_id  TEXT REFERENCES discuss_floor(id),
  is_pinned       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_discuss_floor_topic ON discuss_floor(topic_id);

CREATE TABLE IF NOT EXISTS note_reply (
  id         TEXT PRIMARY KEY,
  note_id    BIGINT NOT NULL REFERENCES user_note(id),
  user_id    TEXT REFERENCES app_user(id),
  content    TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ C. 练习与学习域（training · 域2） ============
-- training_session / training_answer / answer_score 已在 01 建好，这里补其余

CREATE TABLE IF NOT EXISTS training_record (          -- 兼容旧表（累计统计）
  id                  BIGSERIAL PRIMARY KEY,
  user_id             TEXT REFERENCES app_user(id),
  unit_ref            TEXT,
  submitted_syndrome  TEXT,
  is_correct          BOOLEAN,
  duration_ms         BIGINT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_training_record_user ON training_record(user_id);

CREATE TABLE IF NOT EXISTS wrong_book (
  user_id    TEXT NOT NULL REFERENCES app_user(id),
  unit_ref   TEXT NOT NULL,
  last_score NUMERIC,
  added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, unit_ref)
);

CREATE TABLE IF NOT EXISTS learning_event (
  id         BIGSERIAL PRIMARY KEY,
  user_id    TEXT REFERENCES app_user(id),
  event_type TEXT NOT NULL,          -- view / practice / recite / ask ...
  ref        TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_learning_event_user ON learning_event(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS learning_profile (
  user_id       TEXT PRIMARY KEY REFERENCES app_user(id),
  radar_jsonb   JSONB,               -- 三经典掌握度
  streak_days   INT NOT NULL DEFAULT 0,
  total_minutes INT NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS study_path (
  id         TEXT PRIMARY KEY,
  user_id    TEXT REFERENCES app_user(id),
  title      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS study_path_item (
  id        TEXT PRIMARY KEY,
  path_id   TEXT NOT NULL REFERENCES study_path(id),
  seq       INT NOT NULL DEFAULT 0,
  unit_ref  TEXT,
  reason    TEXT
);
CREATE INDEX IF NOT EXISTS idx_study_path_item_path ON study_path_item(path_id, seq);

CREATE TABLE IF NOT EXISTS recite_record (            -- 背诵 SRS
  user_id        TEXT NOT NULL REFERENCES app_user(id),
  quote_id       TEXT NOT NULL REFERENCES classic_quote(id),
  ease           NUMERIC NOT NULL DEFAULT 2.5,
  next_review_at TIMESTAMPTZ,
  last_result    TEXT,
  PRIMARY KEY (user_id, quote_id)
);

-- ============ D. 图谱/规则辅助域 ============
CREATE TABLE IF NOT EXISTS syndrome (
  id        TEXT PRIMARY KEY,
  name      TEXT NOT NULL,
  category  TEXT,                     -- 六经 / 卫气营血 / 三焦 …
  parent_id TEXT REFERENCES syndrome(id)
);

CREATE TABLE IF NOT EXISTS symptom (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT                           -- 症状
);

CREATE TABLE IF NOT EXISTS sign (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT                           -- 舌象 / 脉象 / 体征
);

CREATE TABLE IF NOT EXISTS formula_syndrome_rel (
  formula_id  TEXT NOT NULL REFERENCES formula(id),
  syndrome_id TEXT NOT NULL REFERENCES syndrome(id),
  PRIMARY KEY (formula_id, syndrome_id)
);

CREATE TABLE IF NOT EXISTS case_symptom_rel (
  case_id    TEXT NOT NULL REFERENCES case_record(id),
  symptom_id TEXT NOT NULL,
  kind       TEXT,                    -- symptom / sign
  PRIMARY KEY (case_id, symptom_id, kind)
);

CREATE TABLE IF NOT EXISTS dosage_rule (
  id         BIGSERIAL PRIMARY KEY,
  dynasty    TEXT,
  from_unit  TEXT NOT NULL,
  to_gram    NUMERIC,
  source     TEXT
);

-- ============ E. Agent 域（域3） ============
CREATE TABLE IF NOT EXISTS agent_conversation (
  id         TEXT PRIMARY KEY,
  user_id    TEXT REFERENCES app_user(id),
  title      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_conv_user ON agent_conversation(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_message (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES agent_conversation(id),
  role            TEXT NOT NULL,      -- user / assistant / tool
  content         TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_msg_conv ON agent_message(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS agent_tool_call (
  id             BIGSERIAL PRIMARY KEY,
  message_id     TEXT REFERENCES agent_message(id),
  tool_name      TEXT NOT NULL,
  args_jsonb     JSONB,
  result_summary TEXT,
  latency_ms     INT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ F. 治理域（域3） ============
CREATE TABLE IF NOT EXISTS verify_log (
  id          BIGSERIAL PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  action      TEXT,
  operator    TEXT,
  note        TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content_review (
  id         TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id  TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT '待复核',   -- 待复核 / 通过 / 驳回
  assignee   TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_content_review_status ON content_review(status);

CREATE TABLE IF NOT EXISTS issue (
  id          TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  issue_type  TEXT,
  descr       TEXT,
  status      TEXT NOT NULL DEFAULT '待处理',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_issue_status ON issue(status);

CREATE TABLE IF NOT EXISTS audit_log (
  id         BIGSERIAL PRIMARY KEY,
  actor      TEXT,
  action     TEXT,
  target     TEXT,
  detail     JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
