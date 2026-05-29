# SESSION D — 옵션 3 코드 (선택)

> **시작 전 필독**: `INDEX.md` + 메모리 4건
> **베이스 브랜치**: `feature/bunseol-{YYYYMMDD}` (NOT main)
> **워크트리**: `git worktree add ../lawear-d-옵션3 -b wt/d-옵션3 feature/bunseol-{YYYYMMDD}`
> **선택**: 사실관계 inject 로직 변경 시만 호출.

---

## [배경]

**옵션 3 (사실관계 동적 inject)** — 사용자 동의 + 신뢰 부족 우려:

문제: 1개 문제 안 하위 분설 .md 쪼개기 vs 사실관계 복붙 딜레마. 사용자 명시 "옵션 3 우아하지만 신뢰 부족, 유닛테스트 + QA 페르소나 강화 필요".

해결: 메타 표준 정의 + 17895/17896 server.py가 사실관계 자동 inject + 매칭 버튼 보존 + 모바일 작동.

작업:
- 17895 server.py: `GET /api/inherited_facts/{path}` endpoint (직전 .md 사실관계 자동 추출)
- 17896 server.py: 동일 endpoint
- merge.html: 답안/Lv.1 렌더 시 사실관계 prepend (인계 메타 있을 때)
- exam_mockup.html: 시험 모드 동일

**우려**: 도비 실패 패턴 (이전 7/9). 옵션 3 = 큰 변경 = 더 엄격 검증.

---

## [입력]
- INDEX.md + 메모리 4건
- 현재 17895/17896 server.py + merge.html
- B 분설 추출 스킬 (메타 표준 확인)

---

## [본 작업 — 스킬 + 코드]

### 작성 스킬: `dev-le-17895-new-file-bunseol-d`

**저장 위치**: `/Users/nhn/zman-lab/lawear/.claude/commands/dev-le-17895-new-file-bunseol-d.md`

**스킬 책임 (1만)**: 사실관계 동적 inject 코드 갱신 가이드 + 메타 표준 + 유닛테스트

### 코드 변경

#### 메타 표준 (B 스킬과 일관)
- `_분설_사실관계_source: "직전 .md path 또는 'self'"`
- inheritance flag → server.py가 직전 .md 사실관계 추출

#### 17895 server.py 신규 endpoint
- `GET /api/inherited_facts/{path}`
- 입력: .md path
- 처리: 메타 `_분설_사실관계_source` 파싱 → 외부 인계면 직전 .md ## 문제 사실관계 verbatim 추출 → JSON 반환
- 출력: `{"verbatim": "...", "source": "직전 .md path"}`

#### 17896 server.py 동일 endpoint

#### merge.html JS
- 답안/Lv.1 렌더 시 메타 인계 flag 있으면 server.py 호출 → 사실관계 prepend
- 인계 사실관계 표시 영역 (분설박스 위 또는 답안 위)

#### exam_mockup.html
- 시험 모드 동일 prepend
- **매칭 버튼 보존** (17895 ↔ 17896)

---

## [검증]

### 공통
- 유닛테스트 (강화):
  - server.py endpoint 정상 (sample 5건)
  - 직전 .md 사실관계 verbatim 정확
  - 인계 메타 없는 .md = endpoint 호출 X (사이드 효과 0)
  - 17896 시험 모드 normal 작동
- 자체 체크리스트:
  - [ ] 17895 학습 모드 사실관계 inject 정상
  - [ ] 17896 시험 모드 사실관계 inject 정상
  - [ ] 매칭 버튼 보존 (17895 ↔ 17896)
  - [ ] 모바일 반응형
  - [ ] 답안 본문 byte 0 (R-09)
- 별도 페르소나 QA (강화):
  - **부장판사 QA**: 인계 사실관계 verbatim 정확
  - **강사 QA**: 직전 .md 인식 정확 (잘못된 인계 0)
  - **QA 코디네이터 페르소나** (신규): 유닛테스트 통과 + 사용자 시나리오 7가지 검증

### 특화 (옵션 3 우려 반영)
- 유닛테스트 강화 — 사용자 명시 "유닛테스트 + QA 페르소나 + 체크리스트 강제"
- **F 세션 검증 통과 후만 채택** — 옵션 3 신뢰 부족 → F 세션이 17896+모바일 실제 검증

---

## [출력]

- `17895/server.py` + `17896/server.py` 신규 endpoint (commit)
- `merge.html` + `exam_mockup.html` JS prepend (commit)
- `dev-le-17895-new-file-bunseol-d.md` 스킬 (commit)
- 유닛테스트 파일 (`tests/test_inherited_facts.py`)

**F 세션이 입력으로 사용** (17896 시험 모드 + 모바일 실제 검증).

---

## [결과 보고]

게시판:
- 제목: `[bunseol-rework-라운드1-D] 옵션 3 사실관계 동적 inject — 유닛테스트 + QA + 사용자 검증 요청`
- 본문: 코드 변경 + 유닛테스트 통과 결과 + QA 코디네이터 검증 결과 + 사용자 시나리오 7가지 결과
- 사용자 OK 신호 받으면 라운드 1 종료. **F 세션 검증 후 최종 채택 결정**.

---

## [SPEC ↔ 스킬 동기화]

본 SESSION_D.md = 스킬 `dev-le-17895-new-file-bunseol-d`의 **SPEC (단일 진실)**.

**스킬 개편 시 절대 강제 룰**:
1. 본 SPEC 절대 경로 출력: `/Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SESSION_D.md`
2. SPEC 먼저 Read + 수정 + 사용자에게 보여주기 (diff)
3. 사용자 OK 후 스킬 `.claude/commands/dev-le-17895-new-file-bunseol-d.md` 수정
4. SPEC ↔ 스킬 일치 강제 (SPEC에 없는 룰 X)
5. 사용자 변경 영역 보존

**상세**: `SPEC_SYNC_RULES.md` 참조.

스킬 frontmatter에 명시 강제:
```yaml
spec_path: /Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SESSION_D.md
master_skill: dev-le-17895-new-file-bunseol-index
```
