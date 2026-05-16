-- Lawear Exam Console — DB 마이그레이션 v4
-- Step 20 (사용자 명시 2026-05-16): 채점 기준 v4 — articles 신설 (8기준).
--
-- v3 (7기준):  mnem 20 / color 15 / under 10 / outline 15 / sem 15 / rich 10 / miss 15
-- v4 (8기준):  mnem 16 / color 13 / under  8 / outline 10 / sem 12 / rich 20 / miss 11 / articles 10
--
-- 의미:
--   - Lv.4핏 (mnem+color+under+sem+miss = 60) — 기존 v3 5기준 합
--   - outline 10 (Lv.4핏에서 분리)
--   - articles 10 (신설 — 원본 언급 조문 매칭)
--   - rich 20 (사안의 경우 논리적 풍부함)
--   - 합계 100
--
-- 영향:
--   1. settings.weights row 갱신 (기존 v3 값 → v4 값).
--   2. attempt_criteria.CHECK 확장: criterion_key IN (..., 'articles') 추가.
--      SQLite 는 ALTER 로 CHECK 변경 불가 → 테이블 재생성 패턴 (003 패턴 차용).
--   3. attempts 테이블 무변경 (점수 컬럼 REAL 유지 — 소수점 2자리는 코드 로직).
--
-- 멱등성: db.py 의 user_version 가드로 한 번만 적용.

PRAGMA foreign_keys = OFF;  -- 테이블 재생성 동안 FK 일시 비활성

-- ─── 1. settings.weights row 갱신 (v3 → v4) ────────────────────────────
-- INSERT OR IGNORE 가 아니라 UPDATE — 기존 row 가 반드시 존재 (v1 INSERT 보장).
-- 사용자가 v3 가중치를 커스텀 조정했을 가능성도 있으나, 8 키 강제로
-- v4 디폴트로 일괄 갱신 (Step 20 사용자 명시).
UPDATE settings
   SET value_json = '{"mnem":16,"color":13,"under":8,"outline":10,"sem":12,"rich":20,"miss":11,"articles":10}',
       updated_at = datetime('now')
 WHERE key = 'weights';

-- ─── settings 에 weights row 가 어떤 이유로 없는 경우 보강 (멱등) ──────
INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES
  ('weights', '{"mnem":16,"color":13,"under":8,"outline":10,"sem":12,"rich":20,"miss":11,"articles":10}', datetime('now'));

-- ─── 2. attempt_criteria CHECK 확장: 'articles' 추가 ──────────────────
-- 003 패턴 차용: 신규 테이블 → 데이터 복사 → 드롭 → 리네임.

CREATE TABLE attempt_criteria_new (
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

INSERT INTO attempt_criteria_new
SELECT id, attempt_id, criterion_key, score, max_score, weight, comment
  FROM attempt_criteria;

DROP TABLE attempt_criteria;
ALTER TABLE attempt_criteria_new RENAME TO attempt_criteria;

CREATE INDEX IF NOT EXISTS idx_criteria_attempt ON attempt_criteria(attempt_id);

PRAGMA foreign_keys = ON;

PRAGMA user_version = 4;
