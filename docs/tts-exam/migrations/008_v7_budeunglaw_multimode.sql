-- migrations/008_v7_budeunglaw_multimode.sql
-- 부등법(부동산등기법) 5모드 채점 시스템 — weights_version=7 신규
-- 적용일: 2026-05-24 lawear-0d65
-- 메인 종합 안 + 사용자 요청: 5모드(judge/lecturer/hybrid/main_opus/strict_outline) 비교 채점

BEGIN TRANSACTION;

-- 1) attempts 테이블에 grading_mode 컬럼 추가
--    민법/민소 attempts는 NULL (기존 v6 그대로)
--    부등법 attempts는 mode 필수 (judge/lecturer/hybrid/main_opus/strict_outline)
ALTER TABLE attempts ADD COLUMN grading_mode TEXT DEFAULT NULL;

-- 2) attempts 테이블에 multi_mode_results JSON 컬럼 추가
--    부등법 1답안 → 5 mode 결과를 한 row에 JSON으로 묶어 저장 가능
--    {"judge": {...}, "lecturer": {...}, ...}
--    null이면 단일 모드(기존 민법/민소) 또는 부등법 단일 mode 채점
ALTER TABLE attempts ADD COLUMN multi_mode_results TEXT DEFAULT NULL;

-- 3) attempts 테이블에 absolute_score / absolute_max 컬럼 추가
--    사용자 요청: 50점짜리 문제에서 10점 → "10/50 (20/100)" 표시
--    민법/민소도 동일 적용 (호환)
--    NULL이면 기존 방식 (pct만 표시)
ALTER TABLE attempts ADD COLUMN absolute_score INTEGER DEFAULT NULL;
ALTER TABLE attempts ADD COLUMN absolute_max INTEGER DEFAULT NULL;

-- 4) cases 테이블에 subject_type 컬럼 추가 (부등법 분기 식별용)
--    민법/민소: subject_type='lv1234' (Lv.1~Lv.4 구조)
--    부등법:    subject_type='problem_answer' (## 문제 + ## 답안 2섹션)
--    부등서류/민사서류/형법/형소도 추후 확장
ALTER TABLE cases ADD COLUMN subject_type TEXT DEFAULT 'lv1234';

-- subject_kor가 '부동산등기법'인 기존 case는 'problem_answer'로 backfill
UPDATE cases
SET subject_type = 'problem_answer'
WHERE subject_kor = '부동산등기법'
   OR subject = 'budeunglaw';

-- 5) cases 테이블에 outline_category 컬럼 추가 (만능목차 카테고리)
--    기본/첨부서면/등기절차/부수절차/unknown (budeunglaw_modes.guess_outline_category)
--    채점 시 outline 키 가중치 적용에 사용
ALTER TABLE cases ADD COLUMN outline_category TEXT DEFAULT NULL;

-- 6) 인덱스 — multi_mode 조회 성능
CREATE INDEX IF NOT EXISTS idx_attempts_grading_mode ON attempts(grading_mode) WHERE grading_mode IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cases_subject_type ON cases(subject_type);

-- 7) weights_version 'v7_budeunglaw_*' 5종 등록 (참고용 메타 테이블, 있다면)
--    weights_versions 테이블이 있을 경우 INSERT, 없으면 skip
-- INSERT OR IGNORE INTO weights_versions(version, label, created_at)
-- VALUES
--   ('v7_budeunglaw_judge',          '부등법 부장판사 안',       datetime('now')),
--   ('v7_budeunglaw_lecturer',       '부등법 강사 김기찬 안',    datetime('now')),
--   ('v7_budeunglaw_hybrid',         '부등법 하이브리드 합의',   datetime('now')),
--   ('v7_budeunglaw_main_opus',      '부등법 메인 Opus 독립',    datetime('now')),
--   ('v7_budeunglaw_strict_outline', '부등법 만능목차 엄격',     datetime('now'));

COMMIT;

-- 검증 query (수동):
-- SELECT name FROM pragma_table_info('attempts') WHERE name IN ('grading_mode','multi_mode_results','absolute_score','absolute_max');
-- SELECT name FROM pragma_table_info('cases') WHERE name IN ('subject_type','outline_category');
-- SELECT count(*), subject_type FROM cases GROUP BY subject_type;
