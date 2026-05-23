# 임팩트 리뷰 (lawear-7ad6 Phase 3 팀 6A)

> Opus+ultrathink / 2026-05-23 / 룰: 기존 17895 무손상

## 1. 기존 API 무손상 — **PASS**

- **PUT /api/save/** (L64-117) 무변경. body/`.bak`/`relative_to` 그대로.
- **PUT /api/staging/upload/** (L66-68 분기, L119-157 핸들러) 무변경. `ALLOWED_STAGING_SUBJECTS` (L34-37)에 `민사서류/부등서류` 2건 set 확장만 → 기존 5과목 영향 0.
- **GET /\*** 기본 미오버라이드. `end_headers` (L288-294)에 `POST` 추가만 → CORS preflight만 영향.
- **`do_POST`** (L162-167) `/api/create/` 단일, 기타 404. PUT 비간섭.

## 2. merge.html 기존 동작 무손상 — **PASS**

- **4탭(원본/전체/Lv.1/Lv.4)** — `tabKeys` (L1517) 무변경. user_input 분기(L1555-1601)는 `return` (L1600)로 4탭 진입 차단.
- **`type:"library"` 분기** (L1523-1547) 무변경. user_input(L1555)은 library **다음** 배치 → **R1 회피 OK**.
- **renderTree 5단 트리** — L1059 library 우선 + L1064 `subjectKor && category && fileKor` → user_input entry 3필드 충족 → 정상 노출.
- **편집/위장/다운로드** — `if (editorWrap) content.appendChild(editorWrap)` (L1582) library 패턴 mirror → editorWrap 보존, 무손상.
- **localStorage/launchd** 키 영향 0.

**Minor W1** (블로커 X): `stealthCategoryMap`에 `'사용자'` 미등록 (impact spec L19 명시했으나 diff 미반영) → 스텔스 시 한글 노출. `CATEGORY_ORDER` 도 누락 → categoryRank 999 fallback (5단 트리 맨 뒤, 허용).

## 3. _file_index.json 스키마 호환성 — **PASS**

- 신규 entry는 기존 superset (`type/_addedBy/_year` 3개 추가). 기존 entry 무변경.
- `_append_index_entry` (L308-420): 별도 `.json.lock` flock + atomic rename + .bak + 중복 id 스킵(L379) + .bak 복원(L368-374). **TC14 race fix** 코멘트(L356-360) → R3 회피.

## 4. 스킬 §2.8.5 후처리 영향 — **PASS**

- **§2.8** (L463-466) 0줄 검증 후 §2.8.5 진입 → 무결성 보장.
- **§2.8.5** `set -o pipefail` + `[ -f $DB_PATH ]` (L493) + stderr/gunzip header 검증(L501-503) + 부분파일 rm(L508) + `xargs -r` (L515) → R4 회피.
- **§2.9 1줄 보고** (L522) `[backup] OK/FAIL` 별도 줄, 5체크 추가 X (L523) → 형식 무손상.
- **R5** PUT /grade 200 후 무조건, 실패 시 채점 보존 (L519-521).
- **R9** 절대경로 `/Users/nhn/zman-lab/lawear/docs/tts-exam/backups/` (L480-481) → 워크트리 remove 무관.

## 5. 롤백 (워크트리 remove 충분) — **PASS**

- 모든 변경이 워크트리 브랜치 한정. 머지 전이면 워크트리 remove로 완전 롤백.
- `_file_index.json` test_c1 entry 1건 워크트리 내, main 무영향.
- 백업 .gz는 .gitignore L47로 untracked → remove 무관 (필요 시 수동 rm).
- 머지 후: `git revert <merge>` (5파일). DB는 §2.8.5 슬롯 복구.

## 6. .gitignore 영향 — **PASS**

- 5줄 추가(L46-50): `docs/tts-exam/backups/snapshots/*.sql.gz` + `.gitkeep` 예외. 기존 룰(L1-45)/`backups/`(L45)와 다른 디렉토리 → 비충돌. 영향 0.

## 7. 발견된 위험 (2건, 비블로커)

| # | 위험 | 판정 |
|---|------|------|
| W1 | `stealthCategoryMap['사용자']` 누락 → 스텔스 한글 노출 | impact spec L19 명시했으나 diff 미반영. 별도 1줄 fix 권장. 회귀 아님 → 블로커 X |
| W2 | `ALLOWED_STAGING_SUBJECTS`에 `'부등법'` 누락 (`'부등'`만) | 입력모드와 staging은 별개 기능. spec L22 의도와 차이 → 작업 A 범위 외, 본 PR 차단 X |

## 8. 최종 verdict: **APPROVE**

**사유**:
1. 기존 17895 5개 진입점 무손상 (PUT /save, PUT /staging, GET, 4탭, library).
2. 신규 진입점 R1~R9 회피 (traversal/화이트리스트/.md/flock/atomic/409/rolling/절대경로).
3. 채점 스킬 §2.8/§2.9 무손상 + R5 보존.
4. 롤백 워크트리 remove로 완결.
5. W1/W2 비블로커.

**Follow-up**: W1 (L755 `'사용자':'User'` 1줄), W2 (`'부등법'` set 추가 의도 확인).
