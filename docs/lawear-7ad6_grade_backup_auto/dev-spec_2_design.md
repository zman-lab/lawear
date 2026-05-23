# dev-spec Phase 2-2: 설계 (작업 B — 17896 백업 자동화)

> **세션**: lawear-7ad6 / **모델**: Opus + ultrathink
> **베이스**: Phase 2-1 §2 + `_grade_backup_auto/README.md`

---

## 1. 백업 스크립트 (절대경로 + 명확 glob)

**결정**: bash inline (.md 본문에 직접 박음, 별도 .sh X — 짧음+추적성).

```bash
# === 17896 채점 DB 자동 백업 (rolling 2-slot) ===
set -o pipefail
BACKUP_DIR="/Users/nhn/zman-lab/lawear/docs/tts-exam/backups/snapshots"
DB_PATH="/Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db"
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M)
TARGET="$BACKUP_DIR/exam_${TS}.sql.gz"

if sqlite3 "$DB_PATH" .dump | gzip > "$TARGET"; then
  echo "[backup] OK $TARGET ($(wc -c < "$TARGET") bytes)"
else
  rm -f "$TARGET"
  echo "[backup] FAIL — 채점 결과는 보존됨"
fi

ls -1t "$BACKUP_DIR"/exam_*.sql.gz 2>/dev/null | tail -n +3 | xargs -r rm -f
```

**R4 안전장치**: 절대경로 변수 / glob 고정 / `xargs -r` / `tail -n +3` / `2>/dev/null` / `set -o pipefail`.

---

## 2. 스킬 후처리 위치

**결정**: `dev-le-17896-grade.md` §2.8 (사용자 27건 침범 검증) **다음**, §2.9 (1줄 보고) **직전**에 신규 `§2.8.5 채점 DB 백업` 섹션.

**근거**: §2.6 PUT /grade 200 + §2.7 answer_text = DB 변경 완료. §2.8 git 0줄 = 정상 상태. §2.9 직전이라야 보고에 백업 결과 포함.

**수정 위치**:
- 파일: `/Users/nhn/zman-lab/lawear/.claude/commands/dev-le-17896-grade.md`
- 삽입: L466 다음 줄부터
- 헤더: `#### 2.8.5 채점 DB 백업 (rolling 2-slot, lawear-7ad6)`
- 본문: §1 스크립트 + "백업 실패는 채점 결과 보존, 보고만"

**보고 형식**: 기존 §2.9 1줄 유지 + 별도 줄 `[backup] OK ...` 또는 `[backup] FAIL — ...`. 5체크에 `백업✓` 추가 X (일관성 약화).

---

## 3. 에러 처리

| 단계 | 실패 | 처리 |
|------|------|------|
| `mkdir -p` | 권한/RO FS | 후속 실패 → `[backup] FAIL` + 채점 보존 |
| `sqlite3 .dump` | DB 락/손상 | pipefail로 if false → 부분 .gz 삭제 + 보고 |
| `gzip` | 디스크 풀 | pipefail로 if false → 부분 파일 삭제 + 보고 |
| rolling `rm` | 권한 | 백업 자체 성공 → 다음 백업 시 자동 복구 |

**R5 원칙**: 백업 실패 ≠ 채점 무효화. PUT /grade 200 이미 DB 반영 → 백업은 사후 보조. 다음 attempt 진행.

---

## 4. 복구 절차

```bash
# 1. 현재 DB 백업 (롤백 대비)
cp /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db /tmp/exam_before_restore_$(date +%s).db
# 2. 복원
rm /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db
gunzip -c /Users/nhn/zman-lab/lawear/docs/tts-exam/backups/snapshots/exam_YYYYMMDD_HHMM.sql.gz \
  | sqlite3 /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db
# 3. server 재시작 (DB connection 캐시 비우기)
launchctl unload ~/Library/LaunchAgents/com.lawear.exam17896.plist
launchctl load ~/Library/LaunchAgents/com.lawear.exam17896.plist
# 4. 검증
sqlite3 /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db "SELECT COUNT(*) FROM attempts;"
```

---

## 5. 테스트 시나리오

| # | 시나리오 | 기대 |
|---|---------|------|
| 1 | 첫 백업 (snapshots 비어있음) | 1개 생성, `ls\|wc -l`=1 |
| 2 | 2번째 백업 | 2개 보존, `ls\|wc -l`=2 |
| 3 | 3번째 (rolling) | 가장 오래된 삭제, 최신 2개 |
| 4 | 동시 채점 분 내 충돌 | 같은 `<TS>` 덮어씀 — DB ± α 사고 X |
| 5 | 백업 실패 (DB 락) | `[backup] FAIL` + 부분 삭제 + 채점 `완료✓` |
| 6 | rolling 실패 (rm 권한) | 백업 OK → 다음 백업 자동 복구 |
| 7 | 복구 검증 | attempts row 수 = 백업 시점 동일 |

**R9 (워크트리 손실)**: 백업은 **메인 레포 절대경로**로 누적 → 워크트리 remove와 무관. `.gitignore`에 `docs/tts-exam/backups/snapshots/*.sql.gz` 추가 (선택).

---

| 일자 | 세션 | 내용 |
|------|------|------|
| 2026-05-23 | lawear-7ad6 | Phase 2-2 design 작업 B (Opus + ultrathink) |
