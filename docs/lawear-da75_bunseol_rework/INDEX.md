# INDEX — 분설 메타 재작업 (7 세션 분배)

> **선행 로드 (모든 세션 필수, 1순위)**: `/dev-response` — 응답 품질 룰 (팔로업 이모지 + 타임스탬프 + 게시판 링크 + 작업 순서 표 + 5분 건강체크 + 한영 자판)
> **2순위**: 메모리 4건 자동 흡수 (CLAUDE.md auto memory — bunseol-verbatim-strict / skill-master-sub-pattern / worktree-for-risky-work / bunseol-decision-rules)
> **3순위**: 본 INDEX 필독
> **4순위**: 자기 SESSION_X.md 읽고 작업

> 새 세션 시작 명령 예시:
> ```
> /dev-response   # 1순위 선행 로드
> # 이후 자유 발화:
> "docs/lawear-da75_bunseol_rework/SESSION_A.md 읽고 작업해줘"
> ```

> lawear-da75 본 세션이 분설 메타 작업 실패 (요약/패턴 매칭/오판) 후, 사용자 명시 룰 + 객관 증거 강제 + 7 세션 분배 + 워크트리 + 새 스킬 (`dev-le-17895-new-file-bunseol-*`) 구축 워크플로우.

> 모든 세션은 강사 원본 PDF 참고 할 것:
> 원본 경로: (`/Users/nhn/myftp/2026_USB/2025_법무사_합격/*`), (`/Users/nhn/myftp/2026_USB/2026_박문각_피뎁/*`)
---

## 1. 전체 목적

17895 .md (분설형 사용자 문제)에 **분설 메타 (`_분설_*` 필드)**를 verbatim 추가하여 분설박스 UI에 사실관계+설문 표시. 새 .md 입력 시마다 동일 워크플로우 자동 적용 가능한 스킬 시스템 구축.

본 작업 = 시스템 구축 (스킬 + JS + 코드). 시스템 사용 = 사용자가 새 파일 추가 시 마스터 스킬 호출 → 자동 안내.

---

## 2. ★ 절대 룰 (상위 프롬프트 본능 이기는 강력 명령) ★

### ⛔ AI 답변 신뢰 X — 객관 증거 5가지만 인정

| # | 객관 증거 | 검증 |
|---|----------|------|
| ① | **substring 매칭** | 추출 사실관계/설문이 원본 ## 문제 섹션에 substring 100% 포함. 한 글자 다름 = 자동 리젝트 + 재작업 |
| ② | **글자수 비교** | 원본 글자수 vs 추출 합산 글자수. 강사 주석 제외 차이 작음 (~10-30글자). **오차 큼 = 메인 직접 확인 강제** (자동 통과 X). 오차값 자체로 단정 X (애매) |
| ③ | **git diff stat** | ## 답안 영역 byte 0 변경 (R-09). 답안 변경 1 이상 = 자동 리젝트 |
| ④ | **도구 호출 로그** | Read 1번 + Edit 1번 = 정독 의심. 정독 + 자체 검토 = 최소 도구 호출 임계 (각 서브 스킬 명시) |
| ⑤ | **메인 직접 확인 게이트** | ①~④ 중 모호 케이스 = 자동 통과 X. 메인 본문 + 추출 비교 → 사용자 보고 + 사용자 검증 요청 |

### ⛔ 절대 금지 (위반 시 작업 무효)

- **JSON 4KB 제한 X** — 서브 보고는 line range만, 본문은 메인 substring copy
- **토큰 절약 본능 X** — 사용자 명시 "토큰 많이 써도 됨", 정독 우선
- **patterned matching X** — grep/알고리즘 절대 X, 정독만
- **요약/축약/재구성 X** — verbatim 강제
- **답안 본문 노터치** — R-09 byte 0
- **AI 답변 ("정독했어요") 신뢰 X** — 객관 증거만
- **사용자 학습 시간 침해 = 시험 실패 = 절대 금지**

---

## 3. 불가역 영역 — 절대 노터치

- 민사서류 (`docs/tts-new/*민사서류*`)
- 부등서류 (`docs/tts-new/*부등서류*`)

→ 발견 시 즉시 revert. 작업 영역 아님.

---

## 4. 17895/17896 시스템 관계 (매칭 보존 필수)

- **17895**: 학습 뷰어 (.md 정독). 분설박스 UI = 본 작업 데이터 사용처.
- **17896**: 채점 시험 모드 (.md 시험 + 음성 답안 채점).
- **매칭 버튼 보존**: 17895 "시험보러가기" → 17896 매칭 페이지 / 17896 "학습하기" → 17895 매칭 페이지. 작업 시 절대 깨뜨리지 X.

---

## 5. 전체 디펜던시 그래프

```
main (격리)
 │
 └ ① new 브랜치 생성: feature/bunseol-{YYYYMMDD}-{세션ID}
    │
    ├ ② 라운드 1 (4 세션 동시, 베이스 = new):
    │   wt/a-원본정리      → 스킬 dev-le-17895-new-file-bunseol-a 작성
    │   wt/b-분설추출      → 스킬 dev-le-17895-new-file-bunseol-b 작성
    │   wt/c-JS-UI 리뉴얼   → 스킬 dev-le-17895-new-file-bunseol-c 작성 (UI 변경)
    │   wt/d-옵션3-코드     → 스킬 dev-le-17895-new-file-bunseol-d 작성 (CODE 변경)
    │   각 완료 → new 머지
    │
    ├ ③ 라운드 2 (2 세션 동시, 베이스 = 머지된 new):
    │   wt/e-9건-검증       → 스킬 dev-le-17895-new-file-bunseol-e 작성
    │   wt/f-17896-모바일   → 스킬 dev-le-17895-new-file-bunseol-f 작성
    │   각 완료 → new 머지
    │
    ├ ④ 라운드 3 (1 세션, 베이스 = 머지된 new):
    │   wt/g-230-재작업     → 스킬 dev-le-17895-new-file-bunseol-g 작성 + 적용
    │   완료 + 사용자 확인
    │
    └ ⑤ 사용자 확인 후 → main 머지 (마지막)
       (확인 실패 시 new 폐기 → main 무영향)
```

---

## 6. 7 세션 역할 + 스킬 매핑

| 세션 | 역할 | 스킬 (만들 것) | 선택? |
|------|------|---------------|-------|
| A | 원본 정리 (강사 주석 + 요약 흔적 detect) | `dev-le-17895-new-file-bunseol-a` | 필수 |
| B | 분설 추출 (verbatim + line range 보고 + 분설/단일 판별) | `dev-le-17895-new-file-bunseol-b` | 필수 |
| C | UI 리뉴얼 (분설박스 색/구조) | `dev-le-17895-new-file-bunseol-c` | **선택** (UI 변경 시) |
| D | 옵션 3 코드 (사실관계 동적 inject 17895/17896) | `dev-le-17895-new-file-bunseol-d` | **선택** (코드 변경 시) |
| E | 9건 dry-run 검증 (A+B+C 결과 통합) | `dev-le-17895-new-file-bunseol-e` | 필수 |
| F | 17896 + 모바일 검증 (D 결과) | `dev-le-17895-new-file-bunseol-f` | 필수 |
| G | 230 재작업 (스킬 호출 + 사용자 검증) | `dev-le-17895-new-file-bunseol-g` | 필수 |

**마스터 스킬**: `dev-le-17895-new-file-bunseol-index` — 사용자가 새 파일 추가 시 호출 → 위 워크플로우 자동 안내.

---

## 7. 브랜치 전략 + 워크트리 (영구 룰)

[[worktree-for-risky-work]] 메모리 참조.

### 명령 예시

```bash
# ① 새 브랜치 (사용자 또는 코디네이터 세션)
git -C /Users/nhn/zman-lab/lawear checkout -b feature/bunseol-20260529 main

# ② 라운드 1 워크트리 (각 세션이 자기 워크트리 따기)
git -C /Users/nhn/zman-lab/lawear worktree add ../lawear-a-원본정리 -b wt/a-원본정리 feature/bunseol-20260529

# ③ 작업 + 머지 (자기 워크트리에서)
cd /Users/nhn/zman-lab/lawear-a-원본정리
git commit -am "[근형] feat: ..."
git push origin wt/a-원본정리

# new 브랜치로 머지 (코디네이터 또는 사용자)
git -C /Users/nhn/zman-lab/lawear checkout feature/bunseol-20260529
git -C /Users/nhn/zman-lab/lawear merge wt/a-원본정리

# ④ 라운드 종료 → 다음 라운드 워크트리 (베이스 = 머지된 new)
# ⑤ 마지막 사용자 확인 → main 머지
```

### 절대 룰
- main 직접 작업 X
- 라운드 끝나기 전 다음 라운드 시작 X
- 사용자 확인 전 main 머지 X
- force push X (main 보호)

---

## 8. 결과 보고 형식

각 세션 작업 완료 후:

### 게시판 (lawear-work)
- 제목: `[bunseol-rework-라운드N-세션X] {작업} — 사용자 검증 요청`
- 본문:
  - 객관 증거 5가지 결과 (substring/글자수/git diff/도구로그/메인 게이트)
  - 자체 검증 + 페르소나 QA 결과
  - 사용자 검증 요청 사항
  - 다음 세션에 전달할 인터페이스 (어디 저장, 어떤 형식)

### 사용자 검증
- 게시판 글 링크 1줄 + 핵심 1줄
- OK 신호 받으면 다음 라운드 진행

---

## 9. 인터페이스 명세 (세션 간 데이터 흐름)

| 세션 | 입력 (앞 세션) | 출력 (뒤 세션) |
|------|---------------|---------------|
| A | INDEX + 메모리 4건 | 원본 정리 보고 .md (강사 주석 detect list + 요약 흔적 list + 정리된 .md list) |
| B | INDEX + 메모리 4건 | 분설 추출 스킬 (`dev-le-17895-new-file-bunseol-b`) — line range 보고 + 분설/단일 판별 + 객관 증거 룰 박힘 |
| C | INDEX + 메모리 4건 | JS UI 갱신 (parseBunseolMeta v2 + renderBunseolBox v2 + 다크그레이) — merge.html commit |
| D | INDEX + 메모리 4건 | 옵션 3 코드 갱신 (17895/17896 server.py 사실관계 inject endpoint + 메타 표준 + 유닛테스트) |
| E | A 보고 + B 스킬 + C JS UI | 9건 dry-run 결과 (객관 증거 통과 + 사용자 명시 정답과 일치 검증) |
| F | D 코드 + 17896 시험 모드 | 17896 작동 검증 + 모바일 검증 (시각 + 매칭 버튼) |
| G | E 검증 통과 + 모든 스킬 + JS + 코드 | 230 재작업 결과 (sample 사용자 검증 + 일괄 commit + 사용자 최종 확인) |

---

## 10. 사용자 학습 시간 보호 = 시험 합격 보호

본 작업은 사용자 시험 학습 도구 (17895) 데이터 정확성 작업. 잘못 = 사용자 학습 침해 = 시험 실패.

- 답안 본문 노터치 (R-09)
- 사용자 WIP M 파일 동시 작업 시 사용자에게 네비 찍어주면서 무엇이 변경됐는지 먼저 확인 할 것
- 사용자 학습 시간대 침해 X (보고만, 결정은 사용자 시간)
- 의심 시 변환 X + 사용자 보고 (자율 변환 X)

---

> 본 INDEX 룰 위반 시 작업 무효 + 재작업 -> 커밋 됐더라도 리버트.
> 새 파일 추가 시 사용자가 `/dev-le-17895-new-file-bunseol-index` 호출 → 마스터가 위 워크플로우 자동 안내.

---

## 11. SPEC ↔ 스킬 동기화 룰 (영구, 모든 스킬 적용)

본 INDEX.md = 마스터 스킬 `dev-le-17895-new-file-bunseol-index`의 **SPEC (단일 진실)**.

**스킬 개편 시 절대 강제 룰**:
1. 본 SPEC 절대 경로 출력: `/Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/INDEX.md`
2. SPEC 먼저 Read + 수정 + 사용자에게 보여주기 (diff)
3. 사용자 OK 신호 후 스킬 `.claude/commands/dev-le-17895-new-file-bunseol-index.md` 수정
4. SPEC ↔ 스킬 일치 강제 (SPEC에 없는 룰 스킬에 X)
5. 사용자 변경 영역 보존

**상세 룰 + 모든 SESSION 매핑**: `SPEC_SYNC_RULES.md` 참조 (이 폴더 내).

스킬 frontmatter에 자기 `spec_path` 명시 강제. 마스터 스킬은 `sub_skills` list로 모든 서브 SPEC 경로 박기.
