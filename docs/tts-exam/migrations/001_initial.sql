-- Lawear Exam Console — DB 마이그레이션 v1
-- dev-design archive #48 §4-2 DDL 1:1.
-- 5 테이블 + 인덱스 + UNIQUE + 초기 settings 3 row.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

-- ─── 1. cases ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cases (
  id            TEXT    PRIMARY KEY,
  subject       TEXT    NOT NULL,
  subject_kor   TEXT    NOT NULL,
  category      TEXT    NOT NULL,
  file          TEXT    NOT NULL,
  file_kor      TEXT,
  case_no       TEXT    NOT NULL,
  title         TEXT    NOT NULL,
  path          TEXT    NOT NULL,
  pdf_path      TEXT,
  points        INTEGER NOT NULL,
  user_case     TEXT,
  synced_at     TEXT    NOT NULL,
  content_hash  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_subject  ON cases(subject);
CREATE INDEX IF NOT EXISTS idx_cases_category ON cases(category);

-- ─── 2. attempts ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attempts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id         TEXT    NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  answer_text     TEXT    NOT NULL,
  started_at      TEXT,
  submitted_at    TEXT    NOT NULL,
  status          TEXT    NOT NULL DEFAULT 'grading'
                  CHECK (status IN ('grading','done','error')),
  score_total     REAL,
  score_max       REAL,
  score_pct       REAL,
  grade           TEXT
                  CHECK (grade IS NULL OR grade IN ('A','B','C','F','ERROR')),
  model           TEXT,
  weights_json    TEXT    NOT NULL,
  eval_notes_json TEXT,
  diff_json       TEXT,
  raw_response    TEXT,
  error_code      TEXT,
  is_stale        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_attempts_case      ON attempts(case_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_submitted ON attempts(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_status    ON attempts(status);

-- ─── 3. attempt_criteria ──────────────────────────────────────
-- Step 20 (v4, 2026-05-16): CHECK 확장 — 'articles' 추가 (8기준).
CREATE TABLE IF NOT EXISTS attempt_criteria (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id    INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  criterion_key TEXT    NOT NULL
                CHECK (criterion_key IN ('mnem','color','under','outline','sem','rich','miss','articles')),
  score         REAL    NOT NULL,
  max_score     REAL    NOT NULL,
  weight        REAL    NOT NULL,
  comment       TEXT,
  UNIQUE (attempt_id, criterion_key)
);
CREATE INDEX IF NOT EXISTS idx_criteria_attempt ON attempt_criteria(attempt_id);

-- ─── 4. bookmarks ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bookmarks (
  case_id       TEXT    PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
  bookmarked_at TEXT    NOT NULL
);

-- ─── 5. settings ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
  key         TEXT PRIMARY KEY,
  value_json  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- 초기 settings 3 row (멱등 — OR IGNORE)
-- Step 20 (v4, 2026-05-16): weights 8키 (articles 신설). 신규 DB 는 바로 v4 디폴트 적용.
-- 마이그 004 는 기존 v3 DB 의 weights row 를 v4 로 UPDATE.
INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES
  ('weights', '{"mnem":16,"color":13,"under":8,"outline":10,"sem":12,"rich":20,"miss":11,"articles":10}', datetime('now')),
  ('bias',    '{"err_weight":60,"stale_weight":40,"err_threshold":3,"stale_threshold":14}', datetime('now')),
  ('voice',   '{"lang":"ko-KR","silence_sec":3}', datetime('now'));
