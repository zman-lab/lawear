# SESSION A — 원본 정리

> **시작 전 필독**: `INDEX.md` + 메모리 4건 (`bunseol-verbatim-strict`, `skill-master-sub-pattern`, `worktree-for-risky-work`, `bunseol-decision-rules`)
> **베이스 브랜치**: `feature/bunseol-{YYYYMMDD}-{세션ID}` (NOT main)
> **워크트리**: `git worktree add ../lawear-a-원본정리 -b wt/a-원본정리 feature/bunseol-{YYYYMMDD}`

---

## [배경]

강사 PDF 추출 .md에 노이즈 누적:
- **강사 주석** (`"2020년 변호사 1회차 모의고사 기출쟁점"`, `"대판 2020.10.15, 2020다227523 사안 기초"` 같은 출처 메모)
- **요약 흔적** (원본 추출 단계에서 AI가 요약한 결과 — 본 작업 사고 원인)
- **엔터 노이즈** (민법/민소 이혁준 강사 PDF — 사용자 명시)

→ 정리 안 하면 B 세션 분설 추출 시 정독 방해 + 잘못된 verbatim 추출. **B 작업 선행 필수**.

다른 세션 관계:
- A 출력 = B 입력 (정리 보고 .md + 정리된 .md list)
- A는 변환 X (정리 흔적만 detect + 사용자 검증 요청). 자율 변환 = 사용자 학습 침해 위험.

---

## [입력]
- INDEX.md (룰 + 객관 증거 + 브랜치 전략)
- 메모리 4건 (verbatim/skill/worktree/decision)
- 17895 사용자 .md 전수 (`docs/tts-new/{년도}_사용자_*` + `docs/tts-new/{년도}_{순환}_*`)
- 민사서류/부등서류 = 불가역 영역 (절대 노터치)

---

## [본 작업 — 스킬 만들기]

### 작성 스킬: `dev-le-17895-new-file-bunseol-a`

**저장 위치**: `/Users/nhn/zman-lab/lawear/.claude/commands/dev-le-17895-new-file-bunseol-a.md`

**스킬 책임 (1만)**: 강사 주석 노이즈 + 요약 흔적 detect → 정리 가이드 보고 (변환 X)

**스킬 룰**:
1. **변환 X** — sed/Edit 절대 X. 정리는 사용자 또는 별도 작업.
2. **detect만** — 강사 주석 패턴 + 요약 흔적 패턴 식별
3. **사용자 보고** — 발견 패턴 list + 트리 네비 경로 + 의심 사유
4. **객관 증거**:
   - 강사 주석 패턴 (예: "20YY년 변호사 N차 모의고사 기출쟁점", "대판 YYYY.M.D, NNNN다NNNNN 사안 기초")
   - 글자수 비교: 원본 PDF 글자수 vs .md ## 원본 글자수. 차이 너무 크면 요약 의심
5. **검증 게이트**: 의심 케이스 자동 통과 X → 메인 본문 직접 확인 → 사용자 보고

**스킬 입력**: 처리할 .md path list
**스킬 출력**: `docs/lawear-da75_bunseol_rework/A_정리_보고.md` (강사 주석 list + 요약 흔적 list + 정리된/미정리 .md 분류 + 트리 네비 경로)

---

## [검증]

### 공통 (모든 세션 강제)
- 유닛테스트 (강사 주석 패턴 detect 정확도 검증)
- 자체 체크리스트:
  - [ ] 변환 0 건 (detect만 했는지)
  - [ ] 민사서류/부등서류 X
  - [ ] 패턴 매칭 false positive 0 (sample 10건 메인 직접 확인)
  - [ ] 글자수 비교 오차 큼 케이스 = 사용자 검증 요청
- 별도 페르소나 QA (Opus+ultrathink):
  - **부장판사 QA**: detect 누락 검증 (실제 강사 주석인데 미발견 0)
  - **강사 QA**: detect 정확성 검증 (강사 주석 아닌데 발견 false positive 0)
- **실패 1건 = 전체 리젝트 + 재작업**

### 특화
- 사용자 검증 사례 3건 (`feedback_bunseol_decision_rules.md` 참조 — 민법/민소 강사 주석 케이스)
- 요약 흔적 detect: 원본 PDF substring 매칭 (PDF 본문 → .md ## 원본 verbatim 여부)

---

## [출력]

`docs/lawear-da75_bunseol_rework/A_정리_보고.md`:
```
# A 원본 정리 보고

## 강사 주석 detect (N건)
- 트리 네비 경로 + 본문 line + 강사 주석 verbatim

## 요약 흔적 detect (N건)
- 트리 네비 경로 + 본문 line + 원본 PDF 글자수 vs .md 글자수 차이

## 정리 후 .md list (B 세션 사용 가능)
- 강사 주석 + 요약 흔적 없는 .md path list

## 사용자 검증 요청
- 의심 케이스 (오차 큼 등) — 메인 직접 확인 결과
```

→ **B 세션이 입력으로 사용** (정리된 .md list만 분설 추출 진행)

---

## [결과 보고]

게시판 (lawear-work):
- 제목: `[bunseol-rework-라운드1-A] 원본 정리 detect 보고 — 사용자 검증 요청`
- 본문: 위 출력 .md 핵심 + 객관 증거 5가지 결과 + 사용자 검증 요청 사항
- 사용자 OK 신호 받으면 라운드 1 종료 (B/C/D 결과와 함께 new 머지)
