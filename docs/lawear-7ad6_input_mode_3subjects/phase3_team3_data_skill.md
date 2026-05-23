# Phase 3 팀 3 보고서 — 데이터 폴더 + 샘플 + 스킬 백업

> **세션**: lawear-7ad6 / **모델**: Opus + ultrathink
> **소요**: ~5분 / **작업 5건 완료**

---

## 1. 데이터 폴더 3개 + .gitkeep (작업 1)

| 폴더 | .gitkeep |
|------|----------|
| `docs/tts-new/2026_사용자_부동산등기법/` | ✓ |
| `docs/tts-new/2026_사용자_부동산등기서류/` | ✓ |
| `docs/tts-new/2026_사용자_민사서류/` | ✓ |

폴더명: 기존 `2026_입문_민법` / `2026_예비_민법` 패턴 mirror — `2026_{카테고리}_{과목}` 형식 유지. design §5 `SUBJECT_ORDER`에 `'사용자'` append 전제.

---

## 2. 샘플 데이터 .md 3개 (작업 2)

| 파일 | 17895 태그 |
|------|----------|
| `2026_사용자_부동산등기법/sample_1-1.md` | [em1] [key] |
| `2026_사용자_부동산등기서류/sample_1.md` | [em1] [key] |
| `2026_사용자_민사서류/sample_1.md` | [em1] [key] |

**포맷** (design §4 mirror):
- `# {id}` + `## 메타` + `## 문제` + `## 답안` + `## 메모` (선택)
- frontmatter X (17895 기존 패턴 유지 — extractSection 충돌 없음)
- 파일명: `{year}_{subject_en}_user_{NN}.md`
- 메타 필드: 과목 / Case / 등록일 / 출처 / _addedBy (5종)
- 더미 placeholder text — 실제 사용자 입력은 input.html 통해 갱신

---

## 3. .gitignore 업데이트 (작업 3)

추가 (L47-50):
```
# 17896 채점 DB 백업 raw 파일 (lawear-7ad6) — git 용량 사고 방지
# rolling 2-slot로 자동 누적, .gitkeep만 tracked 유지
docs/tts-exam/backups/snapshots/*.sql.gz
!docs/tts-exam/backups/snapshots/.gitkeep
```

- `*.sql.gz` 추적 차단 (수 MB × 2개 누적 방지)
- `!.gitkeep` 예외로 빈 폴더 유지 (워크트리 head 손실 방지)
- 기존 `backups/` ignore와 별개로 명시 (snapshots만 sql.gz 제외, 그 외 백업물은 그대로)

---

## 4. dev-le-17896-grade.md §2.8.5 추가 (작업 4)

**위치**: §2.8 (사용자 27건 침범 검증) 직후, §2.9 (1줄 보고) 직전 — design §2 명세 정확 따름.

**섹션 헤더**: `#### 2.8.5 채점 DB 백업 (rolling 2-slot, lawear-7ad6)`

**구성**:
- bash inline 스크립트 (design §1 그대로 — `set -o pipefail` / 절대경로 / mkdir -p / TS / sqlite3 .dump|gzip if 분기 / 부분 삭제 / `tail -n +3|xargs -r rm -f` rolling)
- 주석 8개 (각 단계 # 설명 — 절대경로 / 디렉토리 / TS / dump / 부분파일 / rolling 등)
- `echo` 4단계: 시작 → dump 완료 → FAIL (분기) → rolling 결과
- R5 원칙 명시 (백업 실패 ≠ 채점 무효화 4 bullet)
- 복구 절차 4단계 (cp → gunzip|sqlite3 → launchctl → SELECT COUNT)

**자의 해석 X**: 모든 명세는 design §1 + impl_plan S1 그대로. 추가 로직/판단 0건.

---

## 5. snapshots .gitkeep 확인 (작업 5)

- 경로: `docs/tts-exam/backups/snapshots/.gitkeep`
- 상태: 이미 존재 (0 bytes, 2026-05-23 18:01 생성)
- 추가 작업 불필요

---

## 검증 체크

- [x] 폴더 3개 생성 + .gitkeep 3개
- [x] 샘플 .md 3개 (각 1건, 17895 태그 1~2개)
- [x] .gitignore 추가 (sql.gz 제외 + .gitkeep tracked)
- [x] 스킬 §2.8.5 신규 섹션 (design §1 스크립트 정확 mirror)
- [x] snapshots .gitkeep 존재 확인
- [x] 모든 .md/스크립트 주석 충실 (사용자 룰)
- [x] echo 단계마다 (시작/dump/FAIL/rolling)
- [x] 자의 해석 0건 (design/impl_plan 정확 따름)

---

| 일자 | 세션 | 내용 |
|------|------|------|
| 2026-05-23 | lawear-7ad6 | Phase 3 팀 3 (Opus + ultrathink, ~5분) |
