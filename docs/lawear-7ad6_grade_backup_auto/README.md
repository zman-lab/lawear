# lawear-7ad6 — 17896 채점 DB 백업 자동화

자율주행 진행 중 (2026-05-23~). lawear-7ad6 세션.

## 목표
- 매 채점 종료 시 자동 백업 (사용자 잊을 우려 제거)
- `dev-le-17896-grade` 스킬 마지막 후처리 단계에 박음 (우회 불가)
- 항상 2개만 유지 (오늘 백업 실수해도 직전 백업 복구 가능)

## 정책
| 항목 | 값 |
|------|------|
| 파일명 | `exam_YYYYMMDD_HHMM.sql.gz` (채점 단위 백업, 시각 유니크) |
| 저장 위치 | `/Users/nhn/zman-lab/lawear/docs/tts-exam/backups/snapshots/` |
| 보관 | 항상 2개 (rolling — 새 백업 시 가장 오래된 1개 삭제) |
| dry-run | 없음 (사용자 단순화 의사) |
| cleanup 옵션 | 없음 |
| 안전 | 절대 경로 + 명확한 glob 고정 (rm 패턴 사고 방지) |

## 구현 위치
- 스킬: `.claude/commands/dev-le-17896-grade.md` (수정)
- 백업 디렉토리: `docs/tts-exam/backups/snapshots/`

## 복구 명령
```bash
gunzip -c docs/tts-exam/backups/snapshots/exam_YYYYMMDD_HHMM.sql.gz | sqlite3 docs/tts-exam/exam.db
```

## 관련 메모리
- [[project_grade_backup_2slot]]
- [[feedback_grade_backup_2slot_policy]]
- [[reference_grade_backup_files]]
- [[feedback_worktree_db_backup]]
