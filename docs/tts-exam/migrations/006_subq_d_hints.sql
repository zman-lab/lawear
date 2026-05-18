-- Lawear Exam Console — DB 마이그레이션 v6
-- Step 24-1: 다중설문 D안 + 시간 추적 + 힌트 5단계 (lawear-a519, 2026-05-18)
--
-- 변경:
--   1. attempts 컬럼 3개 추가 (NULL 허용, legacy answer_text fallback 호환):
--      - answer_subq TEXT     — JSON {subq_key: 답안 텍스트}
--      - subq_elapsed TEXT    — JSON {subq_key: 초 단위 정수}
--      - hints_used TEXT      — JSON {subq_key: [step_n, ...]}
--   2. attempt_criteria 컬럼 1개 추가 + UNIQUE 재구성 + 인덱스:
--      - subq_key TEXT NULL   — NULL=legacy 단일 / non-NULL=다중 카드
--      - UNIQUE(attempt_id, criterion_key) → UNIQUE(attempt_id, COALESCE(subq_key, ''), criterion_key)
--      - SQLite UNIQUE 변경 불가 → 003/005 패턴 차용 (재생성)
--      - CREATE INDEX idx_criteria_subq (다중 카드 조회 성능)
--
-- 영향:
--   - legacy attempts #2/#3/#5 호환 — answer_subq NULL → answer_text 단일 모드 fallback
--   - 단일 모고01_02 (1 .md) — answer_subq NULL fallback (1:1)
--   - 다중 7건 모고 — answer_subq dict {subq_key: text} + 카드별 채점
--   - 가나 하위 (예민 민법 모고02) — subq_key="설문 1 가", "설문 1 나" 별도 row
--
-- 멱등성: db.py user_version 가드로 한 번만 적용.
-- ROLLBACK: 006_rollback.sql 별도 제공 (data 손실 인정 — answer_subq/elapsed/hints JSON 값 보존 X, legacy answer_text는 보존).

PRAGMA foreign_keys = OFF;  -- 테이블 재생성 동안 FK 일시 비활성

-- ─── 1. attempts ALTER ADD COLUMN × 3 (NULL 허용) ──────────────────────
-- SQLite ALTER ADD COLUMN 지원 (NULL 허용 + DEFAULT NULL — CHECK 변경 X라 OK)

ALTER TABLE attempts ADD COLUMN answer_subq TEXT;    -- JSON 직렬화, NULL 허용
ALTER TABLE attempts ADD COLUMN subq_elapsed TEXT;   -- JSON 초 정수, NULL 허용
ALTER TABLE attempts ADD COLUMN hints_used TEXT;     -- JSON list[step_n], NULL 허용

-- ─── 2. attempt_criteria 재생성 (subq_key 추가 + UNIQUE 변경) ──────────
-- 005 패턴 차용. SQLite는 UNIQUE 변경 불가라 재생성.

-- NOTE: SQLite UNIQUE constraint는 expression(COALESCE 등) 금지 → CREATE UNIQUE INDEX 패턴 사용

CREATE TABLE attempt_criteria_new (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id    INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  subq_key      TEXT,  -- NULL = legacy 단일 / non-NULL = 다중 카드 (예: "설문 1", "설문 1 가")
  criterion_key TEXT    NOT NULL
                CHECK (criterion_key IN ('mnem','color','under','outline','sem','rich','miss','articles','case_apply')),
  score         REAL    NOT NULL,
  max_score     REAL    NOT NULL,
  weight        REAL    NOT NULL,
  comment       TEXT
);

INSERT INTO attempt_criteria_new (id, attempt_id, subq_key, criterion_key, score, max_score, weight, comment)
SELECT id, attempt_id, NULL, criterion_key, score, max_score, weight, comment
  FROM attempt_criteria;

DROP TABLE attempt_criteria;
ALTER TABLE attempt_criteria_new RENAME TO attempt_criteria;

-- 인덱스 재생성 (005 패턴 + UNIQUE INDEX with COALESCE + idx_criteria_subq 신규)
CREATE INDEX IF NOT EXISTS idx_criteria_attempt ON attempt_criteria(attempt_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_criteria_unique ON attempt_criteria(attempt_id, COALESCE(subq_key, ''), criterion_key);
CREATE INDEX IF NOT EXISTS idx_criteria_subq ON attempt_criteria(attempt_id, subq_key);

PRAGMA foreign_keys = ON;

PRAGMA user_version = 6;
