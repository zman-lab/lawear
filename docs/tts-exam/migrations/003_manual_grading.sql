-- Lawear Exam Console — DB 마이그레이션 v3
-- Step 13: manual 채점 모드 도입.
--
-- 1) settings 테이블에 'grading_mode' row 추가
--    - 'manual' (디폴트) : Claude Code 외부 채점 (PUT /api/attempts/{id}/grade)
--    - 'auto'            : 17896 서버가 직접 Anthropic API 호출 (기존 Step 6/7)
--
-- 2) attempts.status CHECK 확장 → 'pending_grade' 추가
--    SQLite 는 CHECK 변경을 ALTER 로 못함 → 테이블 재생성 패턴
--    (cases / attempt_criteria FK 보존 + 인덱스 재생성).
--
-- 멱등성: db.py 의 user_version 가드로 한 번만 적용.

PRAGMA foreign_keys = OFF;  -- 테이블 재생성 동안 FK 일시 비활성 (재활성 후 PRAGMA ON)

-- ─── 1. settings.grading_mode INSERT (멱등) ─────────────────────────
INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES
  ('grading_mode', '"manual"', datetime('now'));

-- ─── 2. attempts CHECK 확장: 'pending_grade' 추가 ───────────────────
-- 신규 테이블 → 기존 데이터 복사 → 드롭 → 리네임.

CREATE TABLE attempts_new (
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

INSERT INTO attempts_new
SELECT id, case_id, answer_text, started_at, submitted_at, status,
       score_total, score_max, score_pct, grade, model, weights_json,
       eval_notes_json, diff_json, raw_response, error_code, is_stale,
       completed_at, error_message, elapsed_sec, is_mock
  FROM attempts;

DROP TABLE attempts;
ALTER TABLE attempts_new RENAME TO attempts;

-- 인덱스 재생성 (v1+v2 동일)
CREATE INDEX IF NOT EXISTS idx_attempts_case      ON attempts(case_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_submitted ON attempts(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_status    ON attempts(status);
CREATE INDEX IF NOT EXISTS idx_attempts_completed ON attempts(completed_at DESC);

PRAGMA foreign_keys = ON;

PRAGMA user_version = 3;
