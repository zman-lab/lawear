# lawear-eef5 인수인계 Part 2 — 차기 가이드 (이월 항목 + 로드맵)

> **시리즈 목차** (3부작)
> - Part 1: 세션 요약 + 결과물 — `#<PART1_POST_ID>`
> - **Part 2: 차기 가이드 (이월 + 로드맵)** ← 본 글
> - Part 3: 검증 체크리스트 — `#<PART3_POST_ID>`
>
> **선행 체인**: `#1967` (lawear-a91b 사용자.md 백업 권고) → **lawear-eef5** → 차기 세션
> **세션**: lawear-eef5 (generic, 2026-05-19 ~ 2026-05-20)
> **게시판**: lawear-work
> **작성**: 2026-05-20

---

## 1. 이월 항목 매트릭스

차기 세션이 이어받을 작업을 우선순위/주체별로 분류. **P0는 사용자 결정 대기, P1은 사용자 직접 영역(메인 X), P2는 별도 세션 권고**.

### P0 — 즉시 (사용자 결정/외부 의존)

| # | 항목 | 결정 주체 | 의존 | 작업 위치 |
|:-:|------|:--------:|------|----------|
| **1** | **격 → 견 정정** | 사용자 → 강사 문의 | 강사 답변 | 라이브러리 + 사용자.md |

**상세**:
- **현상**: 민소 9-2 합의관할 항목에서 사용자.md(line 369)는 "격 (또는 격리)" 표기. 라이브러리 풀이형은 임시로 "격리"로 적용.
- **PDF 검증 결과**: 강사 두문자 정본 PDF(이혁준_두문자_민소_1~4) + 강사책 핵심암기장 민소 PDF 둘 다 **"격" 또는 "격리" 문구 부재**. 핵심어는 **"상호관련성(견련성)"**.
- **추정**: "격" → "견" 오타 가능성 높음 (사용자.md만의 표기). 단 강사 책 일부 페이지 OCR 불가 영역 잔존 → 강사 직접 문의 후 확정 필요.
- **결정 후 작업** (양쪽 동시):
  - `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민소.md` 9-2 항목 풀이형 "격리" → "견련성(상호관련성)" 정정
  - `/Users/nhn/myftp/2026_USB/두문자정리및책/민소/사용자정본_두문자.md` line 369 "격" → "견" 정정
- **자율 진행 권한**: 사용자 답변 받은 후 **자율 정정 가능** (단순 1글자 정정 + 양쪽 동기화). 단 사용자.md 수정은 메모리 `feedback_autonomous_execution_scope.md`에 따라 사용자 명시적 OK 필요.

### P1 — 사용자 직접 영역 (메인 X)

| # | 항목 | 주체 | 메인 역할 |
|:-:|------|:----:|----------|
| **2** | **사용자.md 백업** | 사용자 | 안내만 |

**상세**:
- **대상**: `/Users/nhn/myftp/2026_USB/두문자정리및책/` 폴더 전체 (git 외부 — 손실 시 복구 불가)
- **이번 세션 변경**: 민소 line ??? "죽" → "주" 정정 1건 (lawear-a91b → lawear-eef5 인계 시 이어진 정정)
- **백업 수단**: Time Machine / USB 외장디스크 / iCloud 등 사용자 자율 선택
- **메인 역할**: 차기 세션 첫 응답에서 **백업 여부 한 번 확인** 후 미완료 시 안내. 강제 X.
- **근거 메모리**: `feedback_worktree_db_backup.md` (gitignored 데이터 파일 손실 사고 후 룰)

### P2 — 장기 트랙 (별도 세션 권고)

| # | 항목 | 사이즈 | 예상 세션 | 사용자 발주 |
|:-:|------|:------:|:--------:|:----------:|
| **3** | **형법 라이브러리 진입** | L+ | 1라운드 후속 신규 | 발주 대기 |
| **4** | **부등(입문) 라이브러리 진입** | L | 형법 다음 | 발주 대기 |
| **5** | **형소(예비) 라이브러리 진입** | L | 부등 다음 | 발주 대기 |
| **6** | **17897 카드 시스템 P1** | L | 별도 세션 | 발주 대기 (lawear-abf3 권고) |
| **7** | **부록 인덱스 추적성 메타 sweep 보강** | M | 본 라이브러리 후속 | 자율 진행 가능 |

**상세** (각 항목):

**#3 형법 라이브러리 진입**
- 사용자 1라운드 과목 순서: 민법→민소→**형법**→부등(입문)→형소(예비) (메모리 `feedback_subject_order.md`)
- 워크플로우: 본 세션과 동일 (3단 byte 대조 + 부장판사+강사 Opus+ultrathink QA + 추적성 메타)
- **출처 자료** (확인 필요):
  - 사용자.md 형법: `/Users/nhn/myftp/2026_USB/두문자정리및책/형법/사용자정본_두문자.md` (존재 여부 미확인 — 차기 세션이 첫 진입 시 ls 확인)
  - 강사 두문자 정본 PDF: `/Users/nhn/myftp/2026_USB/두문자정리및책/형법/두문자_정본/` (확인 필요)
  - 강사책 핵심암기장 PDF: `/Users/nhn/myftp/2026_USB/두문자정리및책/형법/강사책_핵심암기장_형법.pdf` (확인 필요)
- **리스크**: 사용자.md 부재 시 강사 PDF 단독 출처 → 사용자 컨펌 강제 (R2 참조)

**#4/#5 부등/형소**
- 형법과 동일 워크플로우. 단 부등(입문)은 모고 X (메모리 `reference_mock_exam_structure.md`).

**#6 17897 카드 시스템**
- 기획: lawear-abf3 메모리 `reference_lawear_endpoints_libs.md` + `project_card_kickoff_pending.md`
- 차기 세션 시작 시 사용자 자동 질문: "17895에 두문자/요건사실론 암기카드 제작 시작할까요?" (사용자 OK 전 P1 자동 착수 금지)

**#7 부록 인덱스 추적성 메타 sweep 보강**
- 본문 ### 항목은 sweep 완료 (절대경로 + 페이지/라인 메타 적용)
- 부록 인덱스(A 검증용 + C 간단) 일부 항목은 절대경로 보강 가능
- **자율 진행 가능** (메인 단독 작업 — 사용자 영역 X)
- 우선순위 낮음 (사용자 흐름에 영향 X)

---

## 2. 다음 사이클 로드맵

```
[현재] lawear-eef5 종료
   │
   ├─ 격→견 결정 (P0/사용자 강사 문의)
   │     │
   │     └─→ 자율 정정 (라이브러리 + 사용자.md 양쪽)
   │
   ├─ 사용자.md 백업 (P1/사용자 직접)
   │
   └─→ 별도 세션
         │
         ├─ [A] 형법 라이브러리 진입 (1라운드 다음 순서)
         │     ├─ PDF 정독 (강사 정본 + 강사책 — 자료 존재 확인)
         │     ├─ 사용자.md 정독 (존재 시)
         │     ├─ 항목 추출 + 풀이형 매핑
         │     ├─ 본문 템플릿 적용 ([blue]제목 + [purple]본문)
         │     ├─ 3단 byte 대조 검증
         │     ├─ 부장판사+강사 QA (Opus+ultrathink)
         │     ├─ 추적성 메타 적용
         │     ├─ 부록 A/C 생성
         │     ├─ 17895 _file_index.json 등재
         │     └─ 사용자 컨펌 (절대경로 + 라인 + 발췌)
         │
         ├─ [B] 부등(입문) 라이브러리 진입 (형법 다음)
         │
         ├─ [C] 형소(예비) 라이브러리 진입 (부등 다음)
         │
         ├─ [D] 17897 카드 시스템 P1 (사용자 발주 시)
         │
         └─ [E] 부록 sweep 보강 (자율, 우선순위 낮음)
```

**중요**: 과목 진입 시 사용자 1라운드 순서 강제 (메모리 `feedback_subject_order.md`). 순환 X.

---

## 3. 주요 파일 참조 (절대경로)

### 라이브러리 (git 내)

| 파일 | 행수 | ### 개수 | 비고 |
|------|:----:|:--------:|------|
| `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민법.md` | 1468 | 76 | 본문 100% + 부록 A/C |
| `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민소.md` | 1362 | 65 | 본문 100% + 부록 A/C |
| `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민법.md` | 263 | 127 항목 | 강사 PDF 정리본 (참고용) |
| `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민소.md` | 212 | 106 항목 | 강사 PDF 정리본 (참고용) |

> **주의**: 인계 텍스트에 "74 ###" 표기 있었으나 실측 76 ### (민법). 차기 세션은 grep으로 재검증 권장.

### 사용자 정본 (git 외부)

| 파일 | 행수 | 항목 | 형법/형소/부등 |
|------|:----:|------|:--------------:|
| `/Users/nhn/myftp/2026_USB/두문자정리및책/민법/사용자정본_두문자.md` | 80 | 채권자대위/취소만 (부분) | — |
| `/Users/nhn/myftp/2026_USB/두문자정리및책/민소/사용자정본_두문자.md` | 477 | 60+ 항목 | — |
| `/Users/nhn/myftp/2026_USB/두문자정리및책/README.md` | 5.5KB | 인계 가이드 | 차기 세션 정독 필수 |
| 형법/형소/부등 사용자.md | ? | ? | **존재 여부 차기 세션 확인** |

### 강사 두문자 정본 PDF (git 외부)

- 민법: `/Users/nhn/myftp/2026_USB/두문자정리및책/민법/두문자_정본/이혁준_두문자_민법_{1~6}.pdf`
- 민소: `/Users/nhn/myftp/2026_USB/두문자정리및책/민소/두문자_정본/이혁준_두문자_민소_{1~4}.pdf`
- 형법/형소/부등: 차기 세션 진입 시 ls 확인

### 강사책 핵심암기장 PDF (git 외부, 대용량)

- `/Users/nhn/myftp/2026_USB/두문자정리및책/민법/강사책_핵심암기장_민법.pdf` — 110MB, 328pg (OCR 일부 불가)
- `/Users/nhn/myftp/2026_USB/두문자정리및책/민소/강사책_핵심암기장_민소.pdf` — 75MB, 208pg (OCR 일부 불가)
- 형법/형소/부등: 차기 세션 진입 시 ls 확인

### 17895 뷰어

| 파일 | 역할 |
|------|------|
| `/Users/nhn/zman-lab/lawear/docs/tts-new/merge.html` | 메인 페이지 |
| `/Users/nhn/zman-lab/lawear/docs/tts-new/_file_index.json` | 라이브러리 등재 (type: "library") |

### 인계 문서 (참조)

- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part{1,2,3}.md` — 직전 세션 인계 (참조 권장)
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part1.md` — 본 세션 Part 1
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part3.md` — 본 세션 Part 3 (검증 체크리스트)

---

## 4. 메모리 규칙 (계승 + 신규)

차기 세션이 **자동 로드**할 메모리 (인덱스 `MEMORY.md`에서 자동 노출). 이 8건은 본 세션이 핵심 룰로 확정/추가한 것.

| 메모리 | 룰 핵심 | 적용 시점 |
|--------|---------|----------|
| `feedback_qa_judge_lecturer.md` | 결과물 사용자 보고 전 **부장판사+강사 Opus+ultrathink QA 강제** (2개 서브 병렬). 일반 QA로 갈음 X. | 결과물 작성 후, 사용자 보고 전 |
| `feedback_three_stage_byte_compare.md` | **3단 byte 대조**: 사용자.md + 강사 정본 PDF + 강사책 PDF 셋 모두 일치 시 확정. 1개 부재 시 컨펌 강제. | 항목 추출/검증 시 |
| `feedback_user_confirmation_context.md` | 사용자 컨펌 시 **절대경로 + 라인 + 발췌 원문** 함께 제시. "X.md 보세요" 단독 금지. | 사용자 보고 시 |
| `feedback_pdf_first_for_typo_doubt.md` | **오타 의심 시 PDF 1차 비교** (사용자.md만 보지 말 것). 격→견, 죽→주 사고 후 룰. | 오타 후보 발견 시 |
| `feedback_fake_mnemonic_detection.md` | **AI 가짜 두문자 검출 강제** — 강사 PDF에 없는 두문자는 본문 진입 X. 매번 강사 PDF 대조. | 두문자 ↔ 풀이형 매핑 시 |
| `feedback_traceable_source_meta.md` | **추적성 메타** — 본문 ### 끝에 `📄 절대경로 \| 페이지 NN \| 라인 LLL` 형식. 사용자 검증 1초 가능. | 모든 본문 ### 항목 |
| `feedback_autonomous_execution_scope.md` | **자율 진행 권한 구분**: 단순 정정/검증/배포는 자율, **사용자.md 수정/카테고리 재분류**는 사용자 컨펌 강제. | 모든 작업 분기 시 |
| `feedback_library_template_color.md` | **본문 템플릿** — [blue]제목 + [purple]본문. 17895 컬러 태그 4종 (red/blue/purple/u). | 본문 ### 작성 시 |

**계승 메모리** (이전 세션부터 유지, 차기 세션도 적용):

- `feedback_main_context_priority.md` — 메인 맥락 보존 > 토큰 비용
- `feedback_subject_order.md` — 1라운드 과목 순서 강제
- `feedback_subagent_self_eval_unreliable.md` — 서브 자체 R-09 평가 신뢰 X
- `feedback_library_first_workflow.md` — Lv.4 자동화 전 라이브러리 우선
- `feedback_handover_board_env_dependency.md` — 게시판 OFF 시 위키 fallback
- `feedback_no_pr_workflow.md` — PR 생략, 메인 머지 일괄
- `feedback_no_dooray_registration.md` — 두레이 등록 금지
- `project_card_kickoff_pending.md` — 17897 카드 P1 발주 대기

---

## 5. 배포 경계 (lawear 정책)

차기 세션이 헷갈리지 않도록 명시.

### O (즉시 반영)

- **17895 뷰어**: `merge.html` + `_file_index.json` 수정 후 Ctrl+Shift+R 새로고침 즉시 반영. Python http.server PID 5539 (포트 17895) 재시작 불요.
- **라이브러리 .md**: git tracked. 수정 즉시 17895 좌측 트리 반영.

### O (커밋 + push)

- **git main 직접 커밋 OK** (lawear 정책 — 메모리 `feedback_no_pr_workflow.md`)
- 워크트리 작업 시 메인이 머지+정리 일괄. PR 생략.
- push 후 `git -C /Users/nhn/zman-lab/lawear reflog expire --expire=now --all && git -C /Users/nhn/zman-lab/lawear gc --prune=now` 권장.

### X (skip — 절대 금지)

- **두레이 등록 X** (메모리 `feedback_no_dooray_registration.md`) — dev-spec Phase 7 / dev-team 댓글 모두 skip.
- **PR 생성 X** (메모리 `feedback_no_pr_workflow.md`)
- **사용자.md 임의 수정 X** — 사용자 컨펌 강제 (메모리 `feedback_autonomous_execution_scope.md`)
- **TTS 변환 서브 위임 X** — 메인 직접 (메모리 `feedback_tts_team_structure.md`)

### 게시판

- **17895 뷰어와 별개**: 게시판은 우분투 10.77.11.110:8585. 우분투 OFF 시 위키 .md fallback (메모리 `feedback_handover_board_env_dependency.md`).
- 본 인계 Part 1/2/3는 게시판 + 위키 dual track으로 저장.

---

## 6. 위험 매트릭스

차기 세션 진행 시 미리 알아둘 위험.

| R# | 리스크 | 확률 | 영향 | 완화 |
|:--:|--------|:----:|:----:|------|
| **R1** | 격→견 결정 잘못 (강사 책에 "격리" 표기 가능성 잔존, OCR 일부 불가) | 중 | 시험 답안 흐름 깨짐 | **강사 직접 문의 후 결정**. 사용자.md 단독 출처로 판단 X. |
| **R2** | 형법/형소/부등 라이브러리 진입 시 사용자.md 없음 | 고 | 강사 PDF 단독 출처 | **PDF 1차 정독 + 사용자 컨펌 강제** (`feedback_user_confirmation_context.md`). 항목 추출 후 매 항목 사용자 OK 받기. |
| **R3** | 라이브러리 누락 잔존 (역방향 sweep 보완 가능) | 저 | 부분 누락 | PDF 원문 정리본(`_pdf_원문_민법.md` 127항목 vs 본문 76 ###) 활용 → 누락 항목 식별 후 부록 A에 보충 가능. |
| **R4** | 사용자.md 백업 안 함 → 데이터 손실 | 중 | 사용자 노트 손실 | **사용자에게 안내** (메인 영역 X). 첫 응답에서 한 번 확인. |
| **R5** | 17895 좌측 트리 안 보임 / 새로고침 무시 | 저 | UX 깨짐 | Python http.server PID 5539 살아있는지 `ps aux \| grep 17895` 확인. 죽었으면 재기동 (`cd /Users/nhn/zman-lab/lawear/docs/tts-new && python3 -m http.server 17895 &`). |
| **R6** | OCR 불가 페이지로 인한 항목 누락 | 중 | 일부 두문자 식별 실패 | PDF Direct Read sanity check (메모리 `feedback_pdf_sanity_check.md`) — Phase 1.5 증빙 적용. |
| **R7** | 차기 세션이 메모리 8건 로드 누락 | 저 | 룰 위반 | 첫 응답 템플릿에 "메모리 8건 자동 로드 확인" 체크 강제 (Section 7). |
| **R8** | 17897 카드 P1 자동 착수 | 저 | 사용자 발주 전 진행 | 메모리 `project_card_kickoff_pending.md` — 사용자 OK 전 자동 착수 금지 룰 명시. |

---

## 7. 착수 체크리스트

차기 세션 시작 시 **순서대로** 체크.

```
□ 1. git pull (main 최신화)
     git -C /Users/nhn/zman-lab/lawear pull origin main

□ 2. Part 1/2/3 정독 (본 세션 인계)
     - /Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part1.md
     - /Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part2.md  ← 본 글
     - /Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part3.md
     - (참고) lawear-abf3_handover_part{1,2,3}.md (직전 세션)

□ 3. ~/myftp/2026_USB/두문자정리및책/README.md 정독
     (사용자.md 인계 가이드 — 격→견 등 미결 사항 명시)

□ 4. 메모리 8건 자동 로드 확인
     - feedback_qa_judge_lecturer.md
     - feedback_three_stage_byte_compare.md
     - feedback_user_confirmation_context.md
     - feedback_pdf_first_for_typo_doubt.md
     - feedback_fake_mnemonic_detection.md
     - feedback_traceable_source_meta.md
     - feedback_autonomous_execution_scope.md
     - feedback_library_template_color.md

□ 5. 17895 뷰어 살아있는지 확인
     curl -s http://127.0.0.1:17895/merge.html | head -1
     (실패 시 재기동)

□ 6. 게시판 상태 확인 (우분투 ON/OFF)
     curl -sf http://10.77.11.110:8585/api/boards > /dev/null && echo ON || echo OFF
     (OFF면 위키 .md fallback)

□ 7. 사용자 강사 문의 답변 확인
     "격→견" 결정 받았는지 사용자에게 직접 물어보기

□ 8. 사용자.md 백업 여부 확인
     (P1 안내 — 강제 X)

□ 9. 옵션 제시 (첫 응답 템플릿 참조)
     (a) 격→견 정정
     (b) 형법 라이브러리 진입
     (c) 17897 카드 P1
     (d) 부록 sweep 보강
```

---

## 8. 첫 응답 템플릿

차기 세션이 그대로 복붙해서 사용.

```
세션 시작. lawear-XXXX.
~/myftp/2026_USB/두문자정리및책/README.md 정독 완료 (이전 세션 인계 참조).
선행 체인: #1967 (lawear-a91b) → lawear-eef5 (Part 1/2/3 #N/#N/#N) → lawear-XXXX.

라이브러리 현재 상태:
- 민법.md 76 ### + 민소.md 65 ### 본문 템플릿 100%
- 추적성 메타 적용 (절대경로 + 페이지/라인)
- 부록 A(검증용) + C(간단) 두 버전
- 17895 collapsible UI + 컬러 태그 4종 (red/blue/purple/u)

보류 사항:
- 격 → 견 (사용자 강사 문의 후)
- 사용자.md 백업 (사용자 직접)

옵션:
(a) 격→견 정정 (사용자 문의 답변 받음)
(b) 형법 라이브러리 진입 (1라운드 과목 순서 다음)
(c) 17897 카드 시스템 P1
(d) 부록 추적성 sweep 보강

어느 것부터?
```

---

## 9. 마지막 힌트 (차기 세션 절대 잊지 말 것)

1. **메인이 라이브러리 작업의 두뇌** — TTS 변환과 동일하게 라이브러리 본문/검증도 **메인 직접**. 서브에이전트는 컨텍스트 분산용으로만 (Opus만 사용, 결과 자체 평가 신뢰 X — 메모리 `feedback_subagent_self_eval_unreliable.md`).
2. **3단 byte 대조 빼먹지 말 것** — 사용자.md + 강사 정본 PDF + 강사책 PDF 셋 모두 일치할 때만 본문 진입. 부재 항목은 부록 A로.
3. **추적성 메타 = 본문 ### 끝 한 줄** — 형식 `📄 절대경로 | 페이지 NN | 라인 LLL`. 사용자가 1초에 검증 가능. 형법/형소/부등 진입 시도 동일 형식 강제.
4. **PDF 우선** — 오타 의심/매핑 의심 시 PDF 1차 비교. 사용자.md만 보고 결정 X (격→견 사고 재발 방지).
5. **사용자.md 수정은 사용자 컨펌 강제** — 단순 1글자 정정이라도. 자율 진행 권한은 라이브러리(git tracked)에만 적용.

---

## 10. 감사 + 체인 강조

직전 세션 **lawear-abf3** (project_card_kickoff_pending + lawear endpoints 정리), **lawear-a91b** (#1967 사용자.md 백업 권고 + 죽→주 정정) 두 세션의 기반 위에 본 세션 **lawear-eef5**가 라이브러리 본문 76+65 ###, 추적성 메타 sweep, 17895 컬러 태그 4종, QA 부장판사+강사 룰 확정을 쌓았습니다.

차기 세션은 본 인계 Part 1/2/3을 정독한 뒤 위 P0/P1/P2 분류에 따라 즉시 작업 가능합니다. 격→견 결정과 형법 진입이 다음 큰 마디입니다.

체인을 끊지 마세요. 한 글자가 달라도 답안이 틀어집니다.

— lawear-eef5 (2026-05-20)
