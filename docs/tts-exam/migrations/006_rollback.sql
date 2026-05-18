-- Lawear Exam Console — DB 마이그레이션 v6 ROLLBACK (v6 → v5)
-- 사용 시점: v6 적용 후 문제 발견 시 다운그레이드
-- 실행 방법: sqlite3 exam.db < migrations/006_rollback.sql
--
-- 주의:
--   - data 손실 인정 — answer_subq / subq_elapsed / hints_used JSON 값 보존 X
--   - legacy answer_text는 보존 (NOT NULL이므로 v5 스키마 호환)
--   - attempt_criteria.subq_key 동일 (attempt_id, criterion_key) row 다중 시 MIN(id) 하나만 보존

PRAGMA foreign_keys = OFF;

-- ─── 1. attempts 재생성 (v6 신규 3 컬럼 제거) ────────────────────────
-- SQLite ALTER DROP COLUMN 미지원 → 재생성

CREATE TABLE attempts_v5_restore (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id         TEXT    NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  answer_text     TEXT    NOT NULL,
  started_at      TEXT,
  submitted_at    TEXT    NOT NULL,
  status          TEXT    NOT NULL DEFAULT 'grading'
                  CHECK (status IN ('grading','done','error','pending_grade')),
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
  is_stale        INTEGER NOT NULL DEFAULT 0,
  completed_at    TEXT,
  error_message   TEXT,
  elapsed_sec     REAL,
  is_mock         INTEGER NOT NULL DEFAULT 0
);

INSERT INTO attempts_v5_restore (id, case_id, answer_text, started_at, submitted_at, status,
                                  score_total, score_max, score_pct, grade, model, weights_json,
                                  eval_notes_json, diff_json, raw_response, error_code, is_stale,
                                  completed_at, error_message, elapsed_sec, is_mock)
SELECT id, case_id, answer_text, started_at, submitted_at, status,
       score_total, score_max, score_pct, grade, model, weights_json,
       eval_notes_json, diff_json, raw_response, error_code, is_stale,
       completed_at, error_message, elapsed_sec, is_mock
  FROM attempts;

DROP TABLE attempts;
ALTER TABLE attempts_v5_restore RENAME TO attempts;

CREATE INDEX IF NOT EXISTS idx_attempts_case      ON attempts(case_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_submitted ON attempts(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_status    ON attempts(status);
CREATE INDEX IF NOT EXISTS idx_attempts_completed ON attempts(completed_at DESC);

-- ─── 2. attempt_criteria 재생성 (subq_key 제거 + 원래 UNIQUE) ──────
-- 동일 (attempt_id, criterion_key) row 다중 시 MIN(id) 하나만 보존 (다중 카드 → 단일 모드)

CREATE TABLE attempt_criteria_v5_restore (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id    INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  criterion_key TEXT    NOT NULL
                CHECK (criterion_key IN ('mnem','color','under','outline','sem','rich','miss','articles','case_apply')),
  score         REAL    NOT NULL,
  max_score     REAL    NOT NULL,
  weight        REAL    NOT NULL,
  comment       TEXT,
  UNIQUE (attempt_id, criterion_key)
);

INSERT INTO attempt_criteria_v5_restore (id, attempt_id, criterion_key, score, max_score, weight, comment)
SELECT MIN(id), attempt_id, criterion_key, MAX(score), MAX(max_score), MAX(weight), MAX(comment)
  FROM attempt_criteria
 GROUP BY attempt_id, criterion_key;

DROP TABLE attempt_criteria;
ALTER TABLE attempt_criteria_v5_restore RENAME TO attempt_criteria;

CREATE INDEX IF NOT EXISTS idx_criteria_attempt ON attempt_criteria(attempt_id);

PRAGMA foreign_keys = ON;

PRAGMA user_version = 5;
