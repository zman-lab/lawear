-- Lawear Exam Console — DB 마이그레이션 v2
-- Step 7 Attempts API 도입에 따른 attempts 컬럼 보강.
--
-- 추가 컬럼 4개 (멱등 — IF NOT EXISTS 의존 X, ADD COLUMN 은 SQLite 에서
-- 단일 실행만 가능하므로 db.py 의 user_version 가드로 멱등 보장):
--
--  1) completed_at    TEXT   — grading 종료 시각 (done/error 공통, ISO-8601)
--  2) error_message   TEXT   — 사용자 노출용 사유 (error_code 보완)
--  3) elapsed_sec     REAL   — Grader.grade() 실측 elapsed
--  4) is_mock         INTEGER NOT NULL DEFAULT 0  — mock 채점 여부 (Reports 필터/배지)
--
-- attempts.status CHECK 는 v1 그대로 ('grading','done','error') 유지.
-- (사양의 'completed'/'failed' 명칭은 클라이언트 표현용으로 매핑하되 DB enum 은 done/error)
--
-- 인덱스: completed_at DESC — Reports 최근 완료 정렬.

PRAGMA foreign_keys = ON;

-- ─── attempts 보강 컬럼 ─────────────────────────────────────────
ALTER TABLE attempts ADD COLUMN completed_at  TEXT;
ALTER TABLE attempts ADD COLUMN error_message TEXT;
ALTER TABLE attempts ADD COLUMN elapsed_sec   REAL;
ALTER TABLE attempts ADD COLUMN is_mock       INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_attempts_completed ON attempts(completed_at DESC);

-- ─── 잔존 grading row 마킹 (Q24 A — 서버 재시작 시) ────────────
-- 본 마이그레이션이 v1→v2 첫 적용 시점이라면 기존 grading row 가 있을 수 있음.
-- 마이그레이션 시점에서는 DB 락 X 상태이므로 안전.
UPDATE attempts
   SET status         = 'error',
       error_code     = COALESCE(error_code, 'server_restart'),
       error_message  = COALESCE(error_message, 'server restarted during grading (migration v2)'),
       completed_at   = COALESCE(completed_at, datetime('now'))
 WHERE status = 'grading';

PRAGMA user_version = 2;
