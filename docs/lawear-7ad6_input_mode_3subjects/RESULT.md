# lawear-7ad6 자율주행 종합 결과

**기간**: 2026-05-23 17:30 ~ 20:00 (약 2.5h)
**모델**: Opus 4.7 + ultrathink (Sonnet/Haiku 0건)
**워크트리**: `wt/lawear-7ad6/input-mode-and-backup` (base main b20fba0)
**디렉토리**: `/Users/nhn/zman-lab/lawear-lawear-7ad6-input-mode-and-backup`

---

## TL;DR

작업 A (3과목 입력+뷰어 모드) + 작업 B (17896 채점 DB 백업 자동화) 동시 완료. 28 pytest + 8 curl + 12 Playwright + 임팩트/완성도 리뷰 모두 PASS (1 FAIL → 즉시 fix). **기존 17895 무손상 확인 (회귀 P9~P12 4/4 PASS)**.

---

## 작업 A — 3과목 입력 + 뷰어 모드

### 변경/추가 파일
| 파일 | 변경 |
|------|------|
| `docs/tts-new/server.py` | 142L → **433L** (+291) — POST /api/create + _handle_create + _append_index_entry + 별도 lock file (TC14 race fix) + ALLOWED_NEW_DIRS 화이트리스트 + ALLOWED_STAGING_SUBJECTS 확장 |
| `docs/tts-new/merge.html` | 1914L → **1999L** (+85) — type:"user_input" 분기 (라이브러리 mirror) + `.compare-table.cols-2` 신규 CSS + stealthCategoryMap['사용자'] (W1 fix) + 편집 버튼 encodeURIComponent (P8 fix) |
| `docs/tts-new/input.html` | **신규 33KB** — 17895 다크 톤 mirror + 25 태그 툴바 + 실시간 split 미리보기 + Cmd+S |
| `docs/tts-new/2026_사용자_부동산등기법/` | 신규 폴더 + sample_1-1.md + .gitkeep |
| `docs/tts-new/2026_사용자_부동산등기서류/` | 신규 폴더 + sample_1.md + .gitkeep |
| `docs/tts-new/2026_사용자_민사서류/` | 신규 폴더 + sample_1.md + .gitkeep |
| `docs/tts-new/tests/test_input_mode_api.py` | 신규 — pytest **20 TC** |

### 검증
- **pytest 20/20 PASS** (0.08s) — 정상 4 / 음성 6 / 엣지 5 / 인덱스 5
- **curl 8/8 의도 동작** — POST 정상/traversal/화이트리스트/.md/충돌 409/메타 400/GET/PUT 회귀
- **Playwright 9 PASS + 2 PARTIAL + 1 FAIL** (P8 즉시 fix 완료)
- **회귀 P9~P12 4/4 PASS** — 17895 민법/민소/형법/형소 4탭 + 라이브러리 + 편집 + 위장 + 다운로드 모두 무손상

---

## 작업 B — 17896 채점 DB 백업 자동화

### 변경/추가 파일
| 파일 | 변경 |
|------|------|
| `.claude/commands/dev-le-17896-grade.md` | §2.8.5 신규 섹션 추가 (L468 부근, bash inline + DB 존재 체크 + stderr 검증 + SQL 헤더 검증 + rolling 2-slot) |
| `docs/tts-exam/backups/snapshots/.gitkeep` | 신규 |
| `.gitignore` | `*.sql.gz` 제외 추가 |
| `docs/tts-exam/tests/test_grade_backup_2slot.py` | 신규 — pytest **8 TC**, 스킬 .md 직접 read 패턴 (하드코딩 X) |

### 정책
- 파일명: `exam_YYYYMMDD_HHMM.sql.gz` (채점 단위, 시각 유니크)
- 보관: 항상 2개 (rolling)
- 매 채점 종료 hook (`dev-le-17896-grade` 마지막 단계 박힘)
- 안전장치: 절대경로 + glob 고정 + DB 존재 체크 + SQL 헤더 검증
- 사용자 우려 해결: 잊을 일 없음 (스킬 본문 박힘) + 깃 용량 사고 X (`.gitignore`)

### 검증
- **pytest 8/8 PASS** (0.40s) — 정상 3 / sqlite 실패 / 디렉토리 부재 / 동시 충돌 / 권한 실패 / 복구

---

## 리뷰 결과

### 임팩트 리뷰 (review_impact.md, 3.98KB)
- **APPROVE**
- 기존 API 5개 진입점 무손상 PASS
- merge.html 4탭/라이브러리/편집/위장/다운로드 무손상 PASS
- _file_index.json superset (3필드 추가, 호환성)
- 워크트리 remove로 완전 롤백 가능
- 위험 2건 (모두 비블로커):
  - W1: stealthCategoryMap['사용자'] 미등록 → **즉시 1줄 fix 완료**
  - W2: ALLOWED_STAGING_SUBJECTS에 '부등법' 누락 ('부등'만) — 작업 A 의도 확인 필요 (입력모드와 staging은 별개 기능, 머지 차단 X)

### 완성도 리뷰 (review_completeness.md, 3.14KB)
- **APPROVE**
- 사용자 룰 8개 전부 PASS (근거 라인번호 명시)
- 28 자동 TC 실측 ALL PASS
- 누락 엣지 4건 (추후 작업 가능):
  - E1 UTF-8 BOM (M)
  - E2 1MB+ body (L)
  - E3 brace { } 특수문자 미리보기 (L)
  - **E4 동시 PUT /save (H — 본 PR 범위 외)** — 후속 PR에서 처리 권장
- 개선 3건 (머지 차단 X):
  - lock 파일명 mismatch
  - META 정규식 BOM 처리
  - assembleMd 메모 round-trip

---

## 코드 품질

- **server.py logging.info 10건** (단계별 로그 — 사용자 룰 #2)
- **input.html console.log 18건** (단계별 로그)
- **server.py + input.html 주석 충실** (각 함수 docstring + 인라인 — 사용자 룰 #3)
- **테스트 fixture는 스킬 .md 직접 read** (DRY 원칙 + 동기 누락 위험 제거)

---

## 다음 단계 (사용자 결정 필요)

1. **머지 검토** — 워크트리 → main 머지 (push)
2. **누락 엣지 후속 PR** — E4 동시 PUT /save flock (H) / E1 BOM / E2 1MB / E3 brace 미리보기
3. **W2 확인** — ALLOWED_STAGING_SUBJECTS에 '부등법' 추가할지 (입력모드와 staging 별개 기능)
4. **17895 launchd reload** — 워크트리 머지 후 launchctl unload/load (기존 17895 server.py 갱신)

## 새 메모리 9건
- [[project_input_mode_3subjects]] [[project_grade_backup_2slot]]
- [[feedback_input_mode_design]] [[feedback_grade_backup_2slot_policy]] [[feedback_17895_no_tts_section_correction]] [[feedback_3subjects_split_view_pattern]] [[feedback_autonomous_run_lessons_lawear_7ad6]]
- [[reference_input_mode_files]] [[reference_grade_backup_files]]

## 산출 문서 11개
- 17895_analysis.md (32KB)
- dev-spec_1_impact.md / dev-spec_2_design.md (작업 A+B 각 1) / dev-spec_3_impl_plan.md (작업 A+B 각 1)
- phase3_team2a_merge_html.md / phase3_team3_data_skill.md / phase3_team5_playwright.md
- review_impact.md / review_completeness.md
- RESULT.md (본 파일)
- + playwright_screenshots/ 13장

## 토큰/시간 (자율주행 누적)
- 서브에이전트 발사: 17팀 (Opus + ultrathink 전부)
- 사용자 룰 #6 준수: Sonnet/Haiku 0건
