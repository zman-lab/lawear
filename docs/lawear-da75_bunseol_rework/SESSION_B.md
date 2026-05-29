# SESSION B — 분설 추출 스킬

> **시작 전 필독**: `INDEX.md` + 메모리 4건
> **베이스 브랜치**: `feature/bunseol-{YYYYMMDD}` (NOT main)
> **워크트리**: `git worktree add ../lawear-b-분설추출 -b wt/b-분설추출 feature/bunseol-{YYYYMMDD}`

---

## [배경]

17895 .md `## 문제` 섹션 정독 → 사실관계 + 설문 **verbatim** 추출 + 분설/단일 판별 + missing/split 식별.

**본 세션 = 핵심 스킬 작성**. 다른 세션은 본 스킬을 호출하거나 결과 검증.

이전 사고 (lawear-da75 분설 메타 7/9 실패):
- AI 토큰 절약 본능 → JSON 4KB 보고 → verbatim 모순 → 요약
- 답안 목차 분기를 분설로 오판
- 단일 설문 안 (1)(2)(3) 하위를 분설로 오판
- 사실관계 분기 ㄱ/ㄴ을 분설로 오판

**본 작업 = 위 사고 막는 스킬 설계**.

---

## [입력]
- INDEX.md + 메모리 4건
- A 정리 보고 .md (정리된 .md list만 처리 대상)
- 사용자 검증 사례 (`feedback_bunseol_decision_rules.md` 4 케이스)

---

## [본 작업 — 스킬 만들기]

### 작성 스킬: `dev-le-17895-new-file-bunseol-b`

**저장 위치**: `/Users/nhn/zman-lab/lawear/.claude/commands/dev-le-17895-new-file-bunseol-b.md`

**스킬 책임 (1만)**: ## 문제 섹션에서 사실관계+설문 verbatim 추출 + 분설/단일/missing/split 판별

### 핵심 룰 (스킬에 박힘)

#### ① 정독 + line range 보고만
- 서브에이전트: ## 문제 섹션 전체 Read (답안 절대 X) → 사실관계 line range + 설문 line range 보고만
- **본문 verbatim은 메인이 substring copy** (서브가 안 들고옴)
- JSON 4KB 제한 X — line range는 짧음 (수십 바이트)
- 토큰 절약 본능 차단 (서브가 보고 못 줄임)

#### ② 분설 결정 룰 ([[bunseol-decision-rules]] 참조)
- 분설 = 각 설문별 점수 표기 `(10점)(5점)`
- 단일 = 전체 1 점수 + 하위 (1)(2)(3)
- 사실관계 분기 (ㄱ/ㄴ) = 단일
- 단독 N문제 + 공통 사실관계 0 = split 권고 (변환 X)
- 위 사안에서 + 사실관계 부재 = missing (변환 X)
- 의심 시 단일 (오버분설 X)

#### ③ 메인 직접 substring copy (verbatim 100% 보장)
- 서브가 line range 보고 → 메인이 ## 문제 섹션 본문에서 정확 substring copy
- 메타 추가는 메인이 직접 (서브 X)
- 변경 영역 = `## 메타` YAML 섹션 _분설_* 라인만

#### ④ 객관 증거 5가지 (INDEX 절대 룰 따름)
- substring 매칭 (추출 = 원본 100% 일치)
- 글자수 비교 (오차 큼 = 메인 게이트)
- git diff stat (## 답안 byte 0)
- 도구 호출 로그 (Read 깊이 임계)
- 메인 직접 확인 게이트

---

## [검증]

### 공통
- 유닛테스트:
  - 분설/단일 판별 (사용자 4 케이스 통과)
  - verbatim 100% 검증 (substring 매칭)
  - missing/split detect 통과
- 자체 체크리스트:
  - [ ] 답안 본문 byte 0 (R-09)
  - [ ] 사실관계/설문 substring 100% 매칭
  - [ ] 점수 표기 정확 추출
  - [ ] 의심 시 단일 (오버분설 0)
  - [ ] missing/split = 변환 X (게시판 보고만)
- 별도 페르소나 QA:
  - **부장판사 QA**: 분설 판별 오판 검증 (단일을 분설로 X)
  - **강사 QA**: verbatim 정확성 + 사실관계 다층 인식
- **실패 1건 = 전체 리젝트**

### 특화
- 9 사용자 명시 케이스 dry-run (E 세션 통과 검증과 분리, B 세션 자체 검증)
- 사용자 검증 4 사례 ([[bunseol-decision-rules]]):
  - 답안 목차 분기 → 단일
  - 전체 1 점수 + 하위 (1)(2)(3) → 단일
  - 사실관계 분기 ㄱ/ㄴ → 단일
  - 단독 N문제 + 공통 사실관계 0 → split 권고

---

## [출력]

스킬 자체: `dev-le-17895-new-file-bunseol-b.md` (워크트리 commit)

**E 세션이 입력으로 사용** (9 dry-run에서 본 스킬 호출).

---

## [결과 보고]

게시판:
- 제목: `[bunseol-rework-라운드1-B] 분설 추출 스킬 작성 — 사용자 검증 요청`
- 본문: 스킬 룰 13개 + 객관 증거 검증 결과 + 자체 유닛테스트 통과 결과 + 페르소나 QA 결과
- 사용자 OK 신호 받으면 라운드 1 종료
