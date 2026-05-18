-- Lawear Exam Console — DB 마이그레이션 v7
-- Phase 4 (lawear-e571, 2026-05-19): 9키 가중치 v6 재조정 + weights_version 표시
--
-- 변경 의도:
--   v5 (학습 보조 37 + 답안 본질 63 = 100) → v6 (학습 보조 23 + 답안 본질 77 = 100)
--   학습 보조 키 (mnem/color/under) 하향, 답안 본질 키 (articles/sem/miss/case_apply/outline) 상향.
--
-- v6 가중치 (settings.weights 갱신):
--   - mnem    16 → 10  (학습 보조 하향)
--   - color   13 →  8  (학습 보조 하향)
--   - under    8 →  5  (학습 보조 하향)
--   - outline 10 → 14  (목차 본문 가치 상향)
--   - sem     12 → 15  (의미 일치 상향)
--   - miss    11 → 13  (누락 차감 강화 — Phase 2 missing_critical 반영)
--   - articles 10 → 15 (조문 매칭 — 자체 채점 articles 4→2 엄격화 반영)
--   - case_apply 5 → 7 (사안 적용 상향)
--   - rich    15 → 13  (본질 키 우선이라 약간 낮춤)
--   합 = 10+8+5+14+15+13+13+15+7 = 100
--
-- weights_version 키 신설 (logical 버전 표시, default 6):
--   INSERT settings(key='weights_version', value_json='6', ...)
--
-- ★ 중요 (사용자 명시 lawear-e571):
--   - **기존 attempts.weights_json 컬럼은 절대 미터치** (마이그 X)
--   - 기존 attempts 의 채점 결과 (점수/grade) 도 그대로 유지
--   - v6 가중치는 신규 채점 (POST /api/attempts 의 auto 모드) 에만 적용
--
-- 영향:
--   1. settings.weights row 갱신 (v5 → v6).
--   2. settings.weights_version row 신설.
--   3. attempt_criteria / attempts 등 다른 테이블 무변경.
--
-- 멱등성: db.py user_version 가드로 한 번만 적용.

-- ─── 1. settings.weights row 갱신 (v5 → v6) ────────────────────────────
-- 사용자가 v5 가중치를 커스텀 조정했을 가능성 있음.
-- 일관성을 위해 디폴트 row 만 v6 로 자동 갱신 (커스텀이면 사용자가 PUT 다시).
-- Phase 4 사용자 명시 — 신규 default 가 v6 이므로 디폴트 row 갱신.
UPDATE settings
   SET value_json = '{"mnem":10,"color":8,"under":5,"outline":14,"sem":15,"rich":13,"miss":13,"articles":15,"case_apply":7}',
       updated_at = datetime('now')
 WHERE key = 'weights';

-- weights row 부재 시 보강 (멱등)
INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES
  ('weights', '{"mnem":10,"color":8,"under":5,"outline":14,"sem":15,"rich":13,"miss":13,"articles":15,"case_apply":7}', datetime('now'));

-- ─── 2. settings.weights_version 신설 (default v6) ─────────────────────
INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES
  ('weights_version', '6', datetime('now'));

UPDATE settings
   SET value_json = '6',
       updated_at = datetime('now')
 WHERE key = 'weights_version';

PRAGMA user_version = 7;
