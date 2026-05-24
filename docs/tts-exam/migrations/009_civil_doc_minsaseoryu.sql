-- migrations/009_civil_doc_minsaseoryu.sql
-- 17896 민사서류 작성연습 트랙 — 1라운드 MVP
-- 적용일: 2026-05-25 lawear-23d9
-- 근거: docs/민사서류_작성연습_설계/design_mvp1.md (v2, 결정 1)
--
-- 핵심 변경:
--   1) cases.subject_type 컬럼은 migration 008에서 이미 존재 ('lv1234'/'problem_answer' 2종)
--      → 본 마이그레이션은 schema 변경 X. 'civil_doc' 신규 값은 free-form text라 그대로 사용 가능.
--   2) cases.subject_type='civil_doc' UPDATE — subject_kor='민사서류' 또는 subject='minsaseoryu' 인 기존 row 백필
--      (현재는 0건일 가능성 높음 — _file_index.json 등재 + syncer 실행 후 생성)
--   3) idx_cases_subject_type 인덱스는 008에서 이미 생성 — 추가 인덱스 없음.
--   4) attempts.grading_mode 컬럼은 008에서 추가됨 — 본 마이그레이션은 'civil_doc_cloze' 값을 그대로 사용.
--
-- ⚠️ 메모리 [feedback_sqlite_unique_expression] 룰 — UNIQUE expression 금지, CREATE INDEX 패턴 준수.
-- 본 마이그레이션은 schema 변경 0 (UPDATE + PRAGMA user_version 만).

BEGIN TRANSACTION;

-- 1) 기존 row 백필 (subject_kor='민사서류' 또는 subject='minsaseoryu')
--    syncer 가 _file_index.json 의 'civil_doc' entry 를 읽어 cases 에 INSERT 한 후 본 마이그레이션 재실행해도 멱등.
UPDATE cases
   SET subject_type = 'civil_doc'
 WHERE (subject_kor = '민사서류' OR subject = 'minsaseoryu')
   AND (subject_type IS NULL OR subject_type = 'lv1234');

-- 2) PRAGMA user_version 갱신 (db.py TARGET_SCHEMA_VERSION 동기화)
PRAGMA user_version = 9;

COMMIT;

-- 검증 query (수동):
--   SELECT COUNT(*), subject_type FROM cases WHERE subject_kor='민사서류' GROUP BY subject_type;
--   PRAGMA user_version;
