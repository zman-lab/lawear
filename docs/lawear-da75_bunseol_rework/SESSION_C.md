# SESSION C — JS UI 리뉴얼 (선택)

> **시작 전 필독**: `INDEX.md` + 메모리 4건
> **베이스 브랜치**: `feature/bunseol-{YYYYMMDD}` (NOT main)
> **워크트리**: `git worktree add ../lawear-c-JS-UI -b wt/c-JS-UI feature/bunseol-{YYYYMMDD}`
> **선택**: UI 변경 시만 호출. 안 쓰면 스킵.

---

## [배경]

분설박스 UI 리뉴얼:
- **다크그레이 (#1f2937)** — 회사 환경 보안 (사용자 명시 "몰래 공부")
- **이모지 제거** — 시각 자극 ↓
- **multi-line YAML pipe `|` 지원** — verbatim 본문 표시
- **신규 필드**: `_분설_사실관계`, `_분설_설문_N`, `_분설_설문_N_점수`
- **legacy 호환**: `_분설_*_요약` (sender 작업 — 이미 sed 제거됨, 안전)

이전 살구색 (#fef3c7) → 다크그레이 변경. 사용자 절대 룰 (회사 환경 노출 X).

---

## [입력]
- INDEX.md + 메모리 4건
- 현재 merge.html (`docs/tts-new/merge.html`) — 살구색 분설박스 CSS 존재
- B 세션 분설 추출 스킬 결과 (메타 필드 형식 확인)

---

## [본 작업 — 스킬 + 코드]

### 작성 스킬: `dev-le-17895-new-file-bunseol-c`

**저장 위치**: `/Users/nhn/zman-lab/lawear/.claude/commands/dev-le-17895-new-file-bunseol-c.md`

**스킬 책임 (1만)**: 분설박스 UI 리뉴얼 가이드 (CSS + parseBunseolMeta + renderBunseolBox 변경 명세 + 사이드 효과 검증)

### 코드 변경

#### CSS (`.bunseol-box` 영역)
- background `#fef3c7` → `#1f2937` (다크그레이)
- color `#1a1d23` → `#d1d5db` (gray-300)
- border-left `#d97706` → `#4b5563` (gray-600)
- 이모지 "📋" 제거
- multi-line 사실관계 표시 (`.bunseol-fact` `white-space: pre-wrap`)
- 설문 점수 강조 (`.bunseol-score`)

#### `parseBunseolMeta` (신규 필드 + YAML pipe + legacy 호환)
- 신규 필드: `_분설_사실관계`, `_분설_설문_N`, `_분설_설문_N_점수`
- YAML pipe `|` multi-line 처리
- legacy `_분설_*_요약` fallback (점진 마이그레이션)

#### `renderBunseolBox` (verbatim 표시)
- 사실관계 verbatim 표시 (multi-line)
- 설문 verbatim + 점수
- 답안 쟁점 노출 X (스포일러 방지)

---

## [검증]

### 공통
- 유닛테스트 (JS):
  - parseBunseolMeta 신규 필드 추출 정확
  - parseBunseolMeta legacy `_분설_*_요약` 호환
  - YAML pipe multi-line 파싱
  - renderBunseolBox HTML escape (XSS 방지)
- 자체 체크리스트:
  - [ ] 다크그레이 적용 (시각 검증)
  - [ ] 이모지 제거
  - [ ] multi-line 줄바꿈 정상
  - [ ] 모바일 반응형 (@media 767px)
  - [ ] 단일 .md (분설 메타 부재) = 박스 안 렌더 (UI 영향 0)
  - [ ] 사이드 효과 검증 9종 (`feedback_3col_ui_workflow.md` 참조)
- 페르소나 QA:
  - **시각 QA**: 다크 보안 충족 + 살구색 잔존 0
  - **사용자 시험관 QA**: 회사 환경 안전 + 학습 시 정독 가능

### 특화
- 17895 모든 페이지에서 분설박스 시각 검증 (다른 색 잔존 X)
- 시험 모드 (17896)는 영향 X (별도 코드)

### dev-team Phase 1~6 호출 권장 (코드 작업)

본 세션 = 실제 코드 작업 (parseBunseolMeta + renderBunseolBox + CSS 다크그레이). dev-team 워크플로우 적용 권장.

**호출 명령**: 워크트리 안에서 `/dev-team merge.html 분설박스 UI 리뉴얼 다크그레이 + multi-line YAML pipe + 이모지 제거 + 신규 필드 호환`

**Phase 매핑**:
| Phase | 역할 | 본 세션 적용 |
|-------|------|-----------|
| 1 분석가 | 영향 범위 (수정 파일 + 호출자/피호출자 + 영향 받는 파일) | merge.html 함수 사용처 + 다른 .md 렌더 영향 |
| 2 테크리드 | 설계 방향 (하드코딩 방지 + 설정값 분리 + 네이밍) | 다크그레이 컬러 변수화 + multi-line 파싱 알고리즘 + legacy 호환 fallback |
| 3 개발자 | 구현 (코딩 규칙 강제) | parseBunseolMeta v2 + renderBunseolBox v2 + CSS 갱신 |
| 4 QA | 테스트 + 커버리지 + BDD-style 의도 + 예상 출력 명시 | parseBunseolMeta unit (신규/legacy/multi-line 케이스) + renderBunseolBox XSS escape + 모바일 반응형 |
| 5 리뷰어 | 독립 코드 리뷰 (구현자 ≠ 리뷰어, 별도 Opus) | 사이드 효과 검증 9종 + 다른 색 잔존 0 + 단일 .md 영향 0 |
| 6 dev-qa 게이트 | 최종 검증 | 17895 새로고침 시각 검증 + 사용자 OK 신호 |

**분설 작업 룰 우선**: 본 SESSION_C.md 룰 (verbatim, 객관 증거, 정독 강제) > dev-team. Phase 1 14항목 중 N/A (proto/DB 등) 면제.

**메인 직접 수정 룰**: 1회 실패 시 메인 직접 수정 가능. 단 Phase 5 리뷰는 별도 Opus 서브에이전트 강제 (자기 코드 자기 리뷰 X).

---

## [출력]

- `merge.html` 변경 (commit)
- `dev-le-17895-new-file-bunseol-c.md` 스킬 (commit)

**E 세션이 입력으로 사용** (9 dry-run에서 시각 + 사이드 효과 검증).

---

## [결과 보고]

게시판:
- 제목: `[bunseol-rework-라운드1-C] 분설박스 UI 리뉴얼 + 다크그레이 — 사용자 검증 요청`
- 본문: 변경 영역 + 사이드 효과 검증 9종 결과 + 17895 새로고침 검증 결과
- 사용자 OK 신호 (17895 새로고침 후 시각 확인) 받으면 라운드 1 종료

---

## [SPEC ↔ 스킬 동기화]

본 SESSION_C.md = 스킬 `dev-le-17895-new-file-bunseol-c`의 **SPEC (단일 진실)**.

**스킬 개편 시 절대 강제 룰**:
1. 본 SPEC 절대 경로 출력: `/Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SESSION_C.md`
2. SPEC 먼저 Read + 수정 + 사용자에게 보여주기 (diff)
3. 사용자 OK 후 스킬 `.claude/commands/dev-le-17895-new-file-bunseol-c.md` 수정
4. SPEC ↔ 스킬 일치 강제 (SPEC에 없는 룰 X)
5. 사용자 변경 영역 보존

**상세**: `SPEC_SYNC_RULES.md` 참조.

스킬 frontmatter에 명시 강제:
```yaml
spec_path: /Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SESSION_C.md
master_skill: dev-le-17895-new-file-bunseol-index
```
