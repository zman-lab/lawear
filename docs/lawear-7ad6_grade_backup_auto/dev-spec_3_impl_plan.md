# dev-spec Phase 2-3: 구현 계획 (작업 B — 17896 백업 자동화)

> **세션**: lawear-7ad6 / **모델**: Opus + ultrathink
> **베이스**: Phase 2-1 §2 + Phase 2-2 design

---

## 1. 구현 순서 (단계별, 총 ~1.5h)

| 단계 | 작업 | 추정 | 산출물 |
|------|------|------|--------|
| S1 | `dev-le-17896-grade.md` §2.8.5 추가 | 0.3h | bash inline (.md 본문) |
| S2 | `docs/tts-exam/backups/snapshots/` + `.gitkeep` | 0.1h | 빈 폴더 (idempotent) |
| S3 | `.gitignore`에 `*.sql.gz` 추가 (선택) | 0.1h | git 추적 차단 |
| S4 | pytest 8 TC (`tests/test_backup_script.py`) | 0.5h | 정상+음성+rolling |
| S5 | 실 채점 1~3회 dry-run 검증 | 0.5h | D1~D3 |

**의존**: S1 → S2 (스크립트 mkdir -p 자동, S2는 git 추적 시 .gitkeep만). S4 병렬 OK.

---

## 2. pytest TC (TC1~TC8, `tests/test_backup_script.py`)

bash 직접 — `subprocess.run(['bash','-c',SCRIPT],...)`.

- **TC1**: 첫 백업 (snapshots 비어) → 1개 `exam_*.sql.gz` + `gunzip -t` valid
- **TC2**: 2번째 (TS mock으로 1분 차이) → 2개 보존
- **TC3**: rolling 2-slot 발동 (3회) → `ls\|wc -l == 2`, 오래된 1개 삭제
- **TC4**: sqlite3 실패 (잘못된 DB 경로) → `[backup] FAIL` + 부분 .gz 삭제 + 채점 보존
- **TC5**: 디렉토리 부재 시 자동 생성 (`rm -rf $BACKUP_DIR` 후 실행) → mkdir -p + 백업 OK
- **TC6**: 동시 채점 분 단위 충돌 (같은 TS 2회) → 두 번째 덮어씀, DB ±α 사고 X
- **TC7**: rolling 권한 실패 (`chmod 444` 가장 오래된) → 백업 OK, rm 실패만, 다음 백업 자동 복구
- **TC8**: 복구 검증 — `gunzip -c | sqlite3 /tmp/restore.db` → `SELECT COUNT(*) FROM attempts` 동일

---

## 3. 동작 검증 시나리오 (실 채점 dry-run, M=3)

```bash
SCRIPT="bash /tmp/backup_inline.sh"  # §2.8.5에서 추출
SNAPS=/Users/nhn/zman-lab/lawear/docs/tts-exam/backups/snapshots

# D1: 첫 채점
$SCRIPT && ls -1 $SNAPS/exam_*.sql.gz | wc -l   # expect: 1

# D2: 두 번째 (1분 후)
sleep 60 && $SCRIPT && ls -1 $SNAPS/exam_*.sql.gz | wc -l   # expect: 2

# D3: 세 번째 (rolling)
sleep 60 && $SCRIPT && ls -1 $SNAPS/exam_*.sql.gz | wc -l   # expect: 2
ls -1t $SNAPS/exam_*.sql.gz | head -1   # expect: 최신 TS
```

---

## 4. 사이드 이펙트

| ID | 영역 | 영향 | 차단 |
|----|------|------|------|
| SE1 | `dev-le-17896-grade.md` +~30줄 | 후처리 1단계 추가 | §2.9 직전 위치 고정, 보고 영향 0 |
| SE2 | 디스크 누적 | rolling 2-slot로 2개 (~수 MB) | `tail -n +3\|xargs -r rm -f` 자동 |
| SE3 | snapshots/ git 비대화 | commit 비대화 | `.gitignore` 추가 (S3) |
| SE4 | 채점 시간 +N초 | sqlite3 .dump + gzip | DB ~MB → 1~3초 |
| SE5 | 백업 실패 시 채점 오해 | 보고 혼란 | 보고 분리 (§2.9 + `[backup]`) + R5 명시 |

---

## 5. 롤백 (워크트리 remove로 복구)

1. `git -C /Users/nhn/zman-lab/lawear worktree remove lawear-lawear-7ad6-input-mode-and-backup`
2. (선택) `rm -rf $SNAPS` (메인 누적분 정리)
3. 메인 무변경 확인 — 다음 채점부터 기존 §2.9 보고만

**부분 롤백** (머지 후): §2.8.5 섹션 직접 삭제 + 커밋. **복구 보장**: .md inline만, 코드 0, 폴더 idempotent.

---

## 6. dev-team Phase 3 첫 작업 (S1)

`.claude/commands/dev-le-17896-grade.md` §2.8 종료(L466 부근) 다음 줄에 `#### 2.8.5 채점 DB 백업 (rolling 2-slot, lawear-7ad6)` + design §1 스크립트(`set -o pipefail`/절대경로/`mkdir -p`/`TS`/`sqlite3 .dump|gzip` if 분기/실패 시 부분 삭제/`tail -n +3|xargs -r rm -f` rolling). 본문 끝에 "백업 실패는 채점 보존, 보고만". §2.9에 `[backup] OK/FAIL` 1줄 가이드 추가. D1~D3 dry-run + pytest TC1~TC8.

**선행 체크**: 워크트리 상태 / `exam.db` 읽기 / `which sqlite3 gzip`.

---

| 일자 | 세션 | 내용 |
|------|------|------|
| 2026-05-23 | lawear-7ad6 | Phase 2-3 impl-plan 작업 B (Opus + ultrathink) |
