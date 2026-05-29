# SESSION G — 230 재작업 + 신규 적용

> **시작 전 필독**: `INDEX.md` + 메모리 4건
> **베이스 브랜치**: `feature/bunseol-{YYYYMMDD}` (라운드 2 머지된 new)
> **워크트리**: `git worktree add ../lawear-g-230-재작업 -b wt/g-230-재작업 feature/bunseol-{YYYYMMDD}`

---

## [배경]

라운드 1+2 모두 통과 (E + F 사용자 OK). 최종 단계: 230건 (sender 126 + da75 114 = 240 — 사용자 검증 7 제외 = 233) 일괄 재작업 + 사용자 최종 확인 + main 머지.

이전 사고 (lawear-da75): 230건 main 직접 작업 → 사용자 검증 결과 7/9 실패 → 리버트 비용 ↑.

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
1. **대상 식별**: sender + da75 분설 메타 작업 대상 (sed로 제거된 240건 — 또는 새 파일 추가 시 신규 .md)
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
  - B 스킬 일괄 호출 (230건 정상 처리)
  - 객관 증거 게이트 자동 검증
  - 모호 케이스 자동 detect → 메인 확인 강제
- 자체 체크리스트:
  - [ ] 230건 verdict 분류 (분설/단일/missing/split)
  - [ ] verbatim 매칭 100% (전 건)
  - [ ] 점수 표기 정확
  - [ ] 답안 본문 byte 0 (R-09)
  - [ ] split/missing = 변환 X (게시판 보고만)
  - [ ] sample 10건 사용자 검증 통과
- 별도 페르소나 QA:
  - **부장판사 QA**: sample 10건 verbatim 정확성
  - **강사 QA**: 분설/단일 판별 정확성 (E 9건 룰 적용 일관)
  - **QA 코디네이터**: 전체 통계 (verdict 분포 + 객관 증거 통과율)
- **sample 1건 실패 = 전체 리젝트** + B 세션 룰 재검토

### 특화
- 230건 통계: 분설 N / 단일 N / missing N / split N
- 과목별 분포 (부등/형법/형소/민법/민소)
- sample 사용자 검증 10건 (과목별 2건)
- main 머지 = 사용자 확인 후만 (B 옵션 strict)

---

## [출력]

- 230 .md 분설 메타 적용 (워크트리 commit) → new 브랜치 머지
- `docs/lawear-da75_bunseol_rework/G_230_재작업_결과.md`:
  - 230건 통계 + verdict 분포
  - 객관 증거 5가지 통과율
  - sample 10건 사용자 검증 결과
  - split/missing 케이스 list (변환 X) → 사용자 후속 처리
- `dev-le-17895-new-file-bunseol-g.md` 스킬 (commit)

**사용자 확인 후 → main 머지** (브랜치 전략 ⑤단계).

---

## [결과 보고]

게시판:
- 제목: `[bunseol-rework-라운드3-G] 230 재작업 + 사용자 최종 확인 — main 머지 요청`
- 본문: 230 통계 + sample 10건 검증 결과 + main 머지 권고
- 사용자 OK 신호 받으면 main 머지 → 본 분설 재작업 완료
- 사용자 거부 시 new 브랜치 폐기 → main 무영향 (안전)
