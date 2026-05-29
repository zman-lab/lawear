# SESSION G — 대량 재작업 + 신규 적용 (대상 수는 작업 시점 동적 산출)

> ⚠️ **상수 박지 말 것**: 본 SESSION 작성 시점에는 sender 126 + da75 114 = 240 대상 (사용자 검증 7 제외 ≈ 233)이었으나, **실제 작업 시점에는 대상 수 다름** (이미 적용된 .md 제외, 신규 .md 추가, 사용자 직접 작업한 .md 등). 동적 산출 강제.

**대상 발견 방법** (작업 시점 동적):
- `git log --grep="분설"` 으로 기 적용 .md 식별 → 차집합
- `grep -L "_분설_" docs/tts-new/**/*.md` 미적용 .md 식별
- A 정리 보고 .md (정리된 .md list)
- B 스킬 호출 시 자동 detect (분설 형식 vs 단일)
- 사용자 wip M 파일 제외

**전체 N건** (N = 동적 산출 결과)

> **시작 전 필독**: `INDEX.md` + 메모리 4건
> **베이스 브랜치**: `feature/bunseol-{YYYYMMDD}` (라운드 2 머지된 new)
> **워크트리**: `git worktree add ../lawear-g-230-재작업 -b wt/g-230-재작업 feature/bunseol-{YYYYMMDD}`

---

## [배경]

라운드 1+2 모두 통과 (E + F 사용자 OK). 최종 단계: 전 대상 .md (작업 시점 N건 동적 산출) 일괄 재작업 + 사용자 최종 확인 + main 머지.

이전 사고 (lawear-da75): 대량 main 직접 작업 → 사용자 검증 결과 7/9 실패 → 리버트 비용 ↑.

본 세션 = 클린 룰 + B 스킬 호출 + 객관 증거 5가지 + 사용자 sample 검증 + 일괄 commit.

---

## [입력]
- INDEX.md + 메모리 4건
- E 9건 dry-run 통과 결과
- F 17896 + 모바일 검증 통과 결과
- B 분설 추출 스킬 (검증 통과)
- C JS UI (다크그레이 적용 main)
- D 옵션 3 (사용자 OK 시만)

---

## [본 작업 — 스킬 + 일괄 적용]

### 작성 스킬: `dev-le-17895-new-file-bunseol-g`

**저장 위치**: `/Users/nhn/zman-lab/lawear/.claude/commands/dev-le-17895-new-file-bunseol-g.md`

**스킬 책임 (1만)**: 다수 .md (예: 230건) 일괄 분설 메타 적용 + 객관 증거 게이트 + 사용자 sample 검증

### 일괄 적용 단계
1. **대상 식별 (동적)**: 작업 시점 git log + grep + A 정리 보고 .md으로 N건 산출. 상수 박지 X. 산출 결과 사용자 보고 (네비 찍기).
2. **B 스킬 호출** (대상 .md 각각): line range 보고 + 메인 substring copy → 메타 추가
3. **객관 증거 게이트 (각 .md)**:
   - substring 매칭 PASS
   - 글자수 비교 정상 (오차 작음)
   - git diff stat ## 답안 byte 0
   - 도구 호출 로그 임계 통과
4. **메인 직접 확인 (모호 케이스)**: 자동 통과 X → 사용자 보고
5. **split/missing 케이스 = 변환 X** (게시판 보고만)
6. **sample 사용자 검증**: 10건 (과목별 2건씩) → 사용자 OK 신호 후 일괄 commit
7. **일괄 commit + push** (워크트리 → new 브랜치 머지)
8. **사용자 최종 확인** → new 브랜치 main 머지

---

## [검증]

### 공통
- 유닛테스트:
  - B 스킬 일괄 호출 (N건 정상 처리 — N = 작업 시점 동적 산출)
  - 객관 증거 게이트 자동 검증
  - 모호 케이스 자동 detect → 메인 확인 강제
- 자체 체크리스트:
  - [ ] N건 verdict 분류 (분설/단일/missing/split) — N = 동적
  - [ ] verbatim 매칭 100% (전 건)
  - [ ] 점수 표기 정확
  - [ ] 답안 본문 byte 0 (R-09)
  - [ ] split/missing = 변환 X (게시판 보고만, 네비 찍기 강제 — INDEX §10 룰)
  - [ ] sample 10건 사용자 검증 통과 — **각 sample 트리 네비 경로 명시 강제** (`{년도}/{과목}/{순환}/{회차}/{제목}` + 본문 line + 변경 영역 발췌)
- 별도 페르소나 QA:
  - **부장판사 QA**: sample 10건 verbatim 정확성
  - **강사 QA**: 분설/단일 판별 정확성 (E 9건 룰 적용 일관)
  - **QA 코디네이터**: 전체 통계 (verdict 분포 + 객관 증거 통과율)
- **sample 1건 실패 = 전체 리젝트** + B 세션 룰 재검토

### 특화
- 전체 N건 통계 (동적): 분설 / 단일 / missing / split
- 과목별 분포 (부등/형법/형소/민법/민소)
- sample 사용자 검증 10건 (과목별 2건) — **각 sample 네비 강제**
- main 머지 = 사용자 확인 후만 (B 옵션 strict)

---

## [출력]

- N .md 분설 메타 적용 (워크트리 commit) → new 브랜치 머지 (N = 동적)
- `docs/lawear-da75_bunseol_rework/G_재작업_결과.md`:
  - 전체 N건 통계 + verdict 분포 (동적)
  - 객관 증거 5가지 통과율
  - sample 10건 사용자 검증 결과 — **각 sample 네비 명시**
  - split/missing 케이스 list (변환 X, 네비 찍기) → 사용자 후속 처리
- `dev-le-17895-new-file-bunseol-g.md` 스킬 (commit)

**사용자 확인 후 → main 머지** (브랜치 전략 ⑤단계).

---

## [결과 보고]

게시판:
- 제목: `[bunseol-rework-라운드3-G] N건 재작업 + 사용자 최종 확인 — main 머지 요청` (N = 동적)
- 본문: 전체 N 통계 + sample 10건 검증 결과 (각 네비) + split/missing 네비 list + main 머지 권고
- 사용자 OK 신호 받으면 main 머지 → 본 분설 재작업 완료
- 사용자 거부 시 new 브랜치 폐기 → main 무영향 (안전)

---

## [SPEC ↔ 스킬 동기화]

본 SESSION_G.md = 스킬 `dev-le-17895-new-file-bunseol-g`의 **SPEC (단일 진실)**.

**스킬 개편 시 절대 강제 룰**:
1. 본 SPEC 절대 경로 출력: `/Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SESSION_G.md`
2. SPEC 먼저 Read + 수정 + 사용자에게 보여주기 (diff)
3. 사용자 OK 후 스킬 `.claude/commands/dev-le-17895-new-file-bunseol-g.md` 수정
4. SPEC ↔ 스킬 일치 강제 (SPEC에 없는 룰 X)
5. 사용자 변경 영역 보존

**상세**: `SPEC_SYNC_RULES.md` 참조.

스킬 frontmatter에 명시 강제:
```yaml
spec_path: /Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SESSION_G.md
master_skill: dev-le-17895-new-file-bunseol-index
```
