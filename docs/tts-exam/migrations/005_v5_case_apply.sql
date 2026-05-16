-- Lawear Exam Console — DB 마이그레이션 v5
-- Step 21 (사용자 명시 2026-05-17): 채점 기준 v5 — case_apply 0.5점 신설 + rich 20→15.
--
-- v4 (8기준): mnem 16 / color 13 / under 8 / outline 10 / sem 12 / rich 20 / miss 11 / articles 10
-- v5 (9기준): mnem 16 / color 13 / under 8 / outline 10 / sem 12 / rich 15 / miss 11 / articles 10 / case_apply 5
--
-- 의미:
--   - rich 20 → 15: 풍부함(원본 전체 대비) — 자세히 적을수록 가점, 의미 유지
--   - case_apply 5 (신설): 사안의 경우 — 수험생이 결론+근거의 법리/근거를 사안에 어떻게 적용했는지.
--     정확 매칭 X (강사 예시와 일치 불필요). 결론+근거를 활용해 사안에 논거 펼친 정도.
--   - 합계 100 (rich 5점 감소분 → case_apply 5점 신설로 흡수)
--
-- 영향:
--   1. settings.weights row 갱신 (v4 → v5).
--   2. attempt_criteria.CHECK 확장: criterion_key IN (..., 'case_apply') 추가.
--      SQLite 는 ALTER 로 CHECK 변경 불가 → 테이블 재생성 패턴 (003/004 패턴 차용).
--   3. attempts 테이블 무변경.
--
-- 멱등성: db.py 의 user_version 가드로 한 번만 적용.

PRAGMA foreign_keys = OFF;  -- 테이블 재생성 동안 FK 일시 비활성

-- ─── 1. settings.weights row 갱신 (v4 → v5) ────────────────────────────
-- v4 디폴트(rich:20)를 v5 디폴트(rich:15 + case_apply:5)로 일괄 갱신.
-- 사용자가 v4 가중치를 커스텀 조정했을 가능성도 있으나, 9 키 강제로
-- v5 디폴트로 일괄 갱신 (Step 21 사용자 명시).
UPDATE settings
   SET value_json = '{"mnem":16,"color":13,"under":8,"outline":10,"sem":12,"rich":15,"miss":11,"articles":10,"case_apply":5}',
       updated_at = datetime('now')
 WHERE key = 'weights';

-- ─── settings 에 weights row 가 어떤 이유로 없는 경우 보강 (멱등) ──────
INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES
  ('weights', '{"mnem":16,"color":13,"under":8,"outline":10,"sem":12,"rich":15,"miss":11,"articles":10,"case_apply":5}', datetime('now'));

-- ─── 2. attempt_criteria CHECK 확장: 'case_apply' 추가 ─────────────────
-- 004 패턴 차용: 신규 테이블 → 데이터 복사 → 드롭 → 리네임.

CREATE TABLE attempt_criteria_new (
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

INSERT INTO attempt_criteria_new
SELECT id, attempt_id, criterion_key, score, max_score, weight, comment
  FROM attempt_criteria;

DROP TABLE attempt_criteria;
ALTER TABLE attempt_criteria_new RENAME TO attempt_criteria;

CREATE INDEX IF NOT EXISTS idx_criteria_attempt ON attempt_criteria(attempt_id);

PRAGMA foreign_keys = ON;

PRAGMA user_version = 5;
