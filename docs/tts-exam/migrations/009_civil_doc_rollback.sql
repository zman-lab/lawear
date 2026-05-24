-- migrations/009_civil_doc_rollback.sql
-- 17896 민사서류 작성연습 트랙 1라운드 MVP — ROLLBACK (v9 → v8)
-- 사용 시점: v9 적용 후 문제 발견 시 다운그레이드
-- 실행 방법: sqlite3 exam.db < migrations/009_civil_doc_rollback.sql
--
-- 주의:
--   - v9 마이그레이션은 UPDATE 만 수행했으므로 cases.subject_type='civil_doc' 인 row 를 'lv1234'로 복원
--   - schema 변경은 없으므로 ALTER 불필요
--   - 데이터 손실 없음 (subject_type 컬럼은 유지)

BEGIN TRANSACTION;

-- 1) civil_doc row 를 기본값 'lv1234' 로 복원
UPDATE cases
   SET subject_type = 'lv1234'
 WHERE subject_type = 'civil_doc';

-- 2) PRAGMA user_version 다운그레이드
PRAGMA user_version = 8;

COMMIT;
