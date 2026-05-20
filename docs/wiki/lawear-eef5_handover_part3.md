# lawear-eef5 인수인계 Part 3 — 실행 가이드 + check_items

> **선행 세션**: lawear-eef5 (2026-05-20 종료)
> **차기 세션**: lawear-XXXX (본 문서 수신자)
> **체인**: ... → lawear-abf3 → lawear-a91b → **lawear-eef5** → (수신자)
> **두레이**: skip (`feedback_no_dooray_registration`)
>
> **시리즈 목차**:
> - Part 1 — 회고/기록: `docs/wiki/lawear-eef5_handover_part1.md`
> - Part 2 — 차기 가이드: `docs/wiki/lawear-eef5_handover_part2.md`
> - Part 3 — 실행 가이드 + check_items (본 문서)

---

## 1. 전체 작업 맵 (5건)

| # | 작업 | 출처 | 우선순위 | 공수 | 차단조건 |
|---|------|------|:--:|:---:|---------|
| 1 | **격 → 견 정정** (사용자 강사 답 받은 후) | Part 1 강사 문의 / Part 2 §P0 | **P0** | 10분 | 사용자 강사 답 |
| 2 | 사용자.md 백업 | Part 1 USB 보호 / Part 2 §P1 | P1 | 사용자 결정 | - |
| 3 | 형법 라이브러리 진입 | Part 2 §P2 / 1라운드 과목 순서 | P2 | 8~10h | 사용자.md 형법본 위치 확인 |
| 4 | 17897 카드 시스템 P1 | Part 2 §P2 / `project_card_kickoff_pending` | P2 | 4h | 사용자 별도 발주 (자동 X) |
| 5 | 부록 추적성 sweep 보강 | Part 2 §P3 | P3 | 1~2h | - |

---

## 2. 우선순위 매트릭스

| 우선 | 항목 | 이유 | 즉시 실행 가능? |
|:----:|------|------|:---------------:|
| **P0** | #1 격→견 정정 | 사용자 강사 답 받으면 즉시 (10분, 3-4 Edit + commit) | 답 받은 후 즉시 |
| P1 | #2 사용자.md 백업 | 사용자 영역, USB git 외부, 데이터 보호 | 사용자 결정 |
| P2 | #3 형법 진입 | 1라운드 과목 순서: 민법→민소→**형법**→부등→형소 | 사용자.md 위치 확인 후 |
| P2 | #4 17897 카드 P1 | `project_card_kickoff_pending` 권고 (lawear-abf3) | 사용자 별도 발주 |
| P3 | #5 부록 sweep 보강 | 라이브러리 부록 인덱스 A 일부 누락 | 언제든 |

---

## 3. 사이클 분할

### 3.1 P0 즉시 사이클 (사용자 강사 답 후)

**#1. 격 → 견 정정** (3-4 Edit + git diff 검증 + commit)
- 사용자가 강사에게 "격리/추가 이익이 맞나, 견련성/추가 이익이 맞나" 답을 받는 즉시 트리거
- "견"으로 결정 시 (예상):
  1. `/Users/nhn/myftp/2026_USB/두문자정리및책/민소/사용자정본_두문자.md` line 369 "격" → "견" (사용자 본인 정정 권장)
  2. `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민소.md` 9-2 병합 적법성 영역:
     - 풀이형 "본소와 격리·추가 이익" → "본소와 견련성(상호관련성)·추가 이익"
     - 본문 템플릿 [purple] 안 두문자 [blank2]격[/blank2] → [blank2]견[/blank2]
  3. git diff byte 검증 (다른 영역 0 byte) + commit `[근형] fix(두문자): 민소 9-2 격→견 정정 (강사 컨펌)`
- "격리"로 결정 시 (이혁준 자체 약어 유지): 작업 없음, Part 1에 기록만

### 3.2 P1 사용자 영역 사이클

**#2. 사용자.md 백업**
- 위치: `/Users/nhn/myftp/2026_USB/두문자정리및책/` (git 외부, USB)
- 사용자 직접 결정 (메인 영역 X)
- 선택지:
  - Time Machine (사용자 맥북 표준)
  - 별도 USB 사본
  - 클라우드 (Google Drive / iCloud)
  - cp 명령 (`cp -r ~/myftp/2026_USB/두문자정리및책 ~/Documents/backup/두문자_$(date +%Y%m%d)`)
- 본 세션 변경분: 민소 죽→주 정정 1건 + (격→견 정정 시 1건 추가)

### 3.3 P2 장기 트랙 사이클

**#3. 형법 라이브러리 진입** (전체 흐름)
1. 사용자.md 형법본 위치 확인:
   - 예상: `/Users/nhn/myftp/2026_USB/두문자정리및책/형법/사용자정본_두문자.md`
   - 없으면 사용자에게 위치 또는 작성 의향 확인
2. 강사 두문자 정본 PDF (형법) 위치 확인:
   - 예상: `/Users/nhn/myftp/2026_USB/두문자정리및책/형법/` 안 PDF
   - 강사책 PDF + 정본 PDF 모두 위치 인지
3. PDF 원문 정리 → `_pdf_원문_형법.md` 생성 (민법/민소 패턴 동일)
4. 사용자.md 정독 → 라이브러리 `형법.md` 신설 ([blue]제목 + [purple]본문 + [blank2]두문자)
5. 부장판사+강사 QA (`feedback_qa_judge_lecturer`)
6. 17895 등재 (`type:"library"` 분기)
7. 추적성 메타 + 부록 A/C 인덱스 (`feedback_traceable_source_meta`)

**#4. 17897 카드 시스템 P1**
- 메모리: `project_card_kickoff_pending.md` (lawear-abf3 권고)
- 사용자 OK 전 자동 착수 절대 X
- 첫 진입 시: `docs/wiki/17897_session_kickoff.md` 1줄 복붙 (lawear-abf3 Part 3 §12 참조)

**#5. 부록 sweep 보강**
- 위치: `docs/tts-new/두문자/{민법,민소}.md` 끝 부록 인덱스
- A 버전(검증용 절대경로 + 페이지/라인) 일부 누락 가능 — 항목별 100% 채움
- C 버전(간단)은 현재 양호

---

## 4. 각 항목 상세

### #1. 격 → 견 정정 (P0)

**파일/라인 (정확)**:
- `/Users/nhn/myftp/2026_USB/두문자정리및책/민소/사용자정본_두문자.md`
  - line 369: "반소: 격,추 이익" → "반소: 견,추 이익" (예상)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민소.md`
  - 9-2 병합 적법성 영역 (line ~480 근처)
  - 풀이형 "본소와 격리·추가 이익" → "본소와 견련성(상호관련성)·추가 이익"
  - 본문 [purple] 안 [blank2]격[/blank2] → [blank2]견[/blank2]

**출처 강사 PDF 검증** (Part 1 §강사문의):
- PDF 4 line 41 "예·선·공 필·독·반 부(기·용)" 영역
- 강사책 p.165-166 "상호관련성" 본문
- 민법 정본 PDF 5 No.38 유치권 "견련성" (개념 동일성 확인)

**수정 방향**:
1. 사용자.md = 사용자 본인 영역. AI Edit 가능하나 사용자 컨펌 후 진행
2. 라이브러리 풀이형: "견련성(상호관련성)" 명시 — 강사책 본문 표현 그대로
3. 본문 템플릿 두문자: 1자만 변경 ([blank2]격 → [blank2]견)
4. git diff: 9-2 영역만 변경, 다른 영역 0 byte
5. commit 메시지: `[근형] fix(두문자): 민소 9-2 격→견 정정 (강사 컨펌, 견련성)`

**예상 공수**: 10분 (Edit 3-4건 + git diff 검증 + commit)

**리스크**:
- 강사가 "격리"로 답할 가능성 (이혁준 강사 자체 약어) → 사용자 답 그대로 따름, 코드 변경 없음
- "격"이 사용자 정본에 들어있는데 라이브러리만 "견"으로 바꾸면 불일치 → 사용자.md 동시 갱신 필수

---

### #2. 사용자.md 백업 (P1)

**위치**: `/Users/nhn/myftp/2026_USB/두문자정리및책/`
- `민법/사용자정본_두문자.md`
- `민소/사용자정본_두문자.md`
- (형법/형소/부등 — 향후 추가 예상)

**리스크**:
- 본 세션 변경분: 민소 죽→주 정정 1건 (Part 1 기록), 격→견 정정 시 1건 추가 가능
- 사용자.md = git 외부, USB 단일 파일 → 손실 시 복구 불가
- AI 자동화가 사용자.md 자체를 수정한 사례 없음 (R-09 보호) — 그러나 향후 사용자 요청 시 백업 선행

**수정 방향** (사용자 직접):
- 사용자가 결정. 메인 영역 X (lawear 정책: 사용자.md = 사용자 본인 영역)
- 메인이 백업 명령 실행 시 사용자 컨펌 필수

**공수**: 사용자 결정 (자동화 대상 X)

---

### #3. 형법 라이브러리 진입 (P2)

**차단조건 확인**:
- 사용자.md 형법본 존재 여부:
  - 확인: `ls /Users/nhn/myftp/2026_USB/두문자정리및책/형법/`
  - 없으면 → 사용자에게 형법 두문자 정리 의향 확인
- 강사 PDF 형법:
  - 예상 위치: `/Users/nhn/myftp/2026_USB/두문자정리및책/형법/`
  - 강사책 PDF + 정본 PDF (필요 시 2개)

**워크플로우** (민법/민소 패턴 그대로):
1. PDF 원문 추출 → `docs/tts-new/두문자/_pdf_원문_형법.md`
2. 사용자.md 전체 정독 (헤더만 스캔 금지 — `feedback_library_first_workflow`)
3. 라이브러리 `docs/tts-new/두문자/형법.md` 신설:
   - [blue]제목 + [purple]본문 + [blank2]두문자 (`feedback_library_template_color`)
4. 부장판사+강사 QA (`feedback_qa_judge_lecturer`)
5. 가짜 두문자 검출 (`feedback_fake_mnemonic_detection`)
6. 추적성 메타 (`feedback_traceable_source_meta`)
7. 부록 A(검증용) + C(간단) 인덱스
8. 17895 등재 (`_file_index.json` type:"library" 분기)
9. 3단 byte 대조 (`feedback_three_stage_byte_compare`)

**공수**: 약 8~10시간 (민법 8h + 민소 6h 평균)

**리스크**:
- 사용자.md 미정리 시 → PDF 1차 작성 + 사용자 컨펌 (정확도 저하)
- 형법 두문자가 민법/민소보다 양 적을 수 있음 → 부분 진행
- 강사가 다른 강사일 가능성 (사용자 컨펌 — `feedback_user_confirmation_context`)

---

### #4. 17897 카드 시스템 P1 (P2)

**메모리 참조**: `project_card_kickoff_pending.md` (lawear-abf3 권고)

**원칙**:
- 사용자 별도 세션 발주 예정 (선행 세션 권고 사항)
- 사용자 OK 전 자동 착수 절대 X
- 다음 세션 시작 시 자동 질문 (`project_card_kickoff_pending`):
  > "17895에 두문자/요건사실론 암기카드 제작 시작할까요?"

**진입 시**: lawear-abf3 Part 3 §12 1줄 복붙 가이드 활용
- `docs/wiki/17897_session_kickoff.md 읽고 P1 시작해`
- 워크트리 `wt/{차기세션ID}/cards-srs` 생성
- DB 스키마 + build_cards.py + dry-run

**공수**: P1 4h (lawear-abf3 §A1 견적)

---

### #5. 부록 추적성 sweep 보강 (P3)

**위치**:
- `docs/tts-new/두문자/민법.md` 끝 부록 A/C 인덱스
- `docs/tts-new/두문자/민소.md` 끝 부록 A/C 인덱스

**현재 상태**:
- A 버전(검증용 절대경로 + 페이지/라인): 일부 누락 가능 (de044a7 commit으로 1차 sweep)
- C 버전(간단 카테고리/항목): 양호

**워크플로우**:
1. 민법/민소 항목 전수 (각 76 + 62 = 138 항목)
2. A 버전에 절대경로 + 페이지/라인 누락 검출
3. 누락분 보강 (`feedback_traceable_source_meta` 룰)
4. C 버전 정합 확인

**공수**: 1~2시간

---

## 5. 착수 체크리스트

차기 세션 시작 시 반드시 확인:

- [ ] 세션 ID 생성 (`python3 -c "import secrets; print(f'lawear-{secrets.token_hex(2)}')"`)
- [ ] Part 1/2/3 access (`docs/wiki/lawear-eef5_handover_part{1,2,3}.md`)
- [ ] 선행 체인 #1967 access (lawear-a91b → lawear-eef5)
- [ ] 메모리 신규 8건 access (Part 2 §메모리 참조 또는 본 Part §8)
- [ ] 라이브러리 위치 인지 (`docs/tts-new/두문자/{민법,민소,_pdf_원문_민법,_pdf_원문_민소}.md`)
- [ ] PDF 원문 위치 인지 (`~/myftp/2026_USB/2026_박문각_피뎁/` + `~/myftp/2026_USB/두문자정리및책/`)
- [ ] 사용자.md 위치 인지 (`~/myftp/2026_USB/두문자정리및책/{민법,민소}/사용자정본_두문자.md`)
- [ ] 17895 뷰어 URL (`http://127.0.0.1:17895/merge.html`) 인지
- [ ] 게시판 = 10.77.11.110:8585 (127.0.0.1 X) 인지
- [ ] 두레이 N/A 인지 (`feedback_no_dooray_registration`)
- [ ] PR 생략 인지 (`feedback_no_pr_workflow`)
- [ ] Opus + ultrathink 전용 인지 (서브에이전트도 동일)
- [ ] 메인 직접 git diff byte 검증 인지 (`feedback_three_stage_byte_compare`)

---

## 6. 판단 포인트

### 💡 6.1 격 → 견 정정 트리거 (사용자 결정 필요)

| 결정 | 후속 |
|------|------|
| 강사 답이 "견(견련성)" | #1 즉시 실행 (3-4 Edit + commit) |
| 강사 답이 "격(격리)" | 라이브러리 풀이형은 "격리"로 정정 (강사 자체 약어 존중), 본문 두문자 그대로 |
| 사용자 답이 늦어짐 | 다른 작업 진행, 답 받으면 즉시 전환 |

### 💡 6.2 형법 진입 vs 17897 카드 우선순위

| 옵션 | 장점 | 단점 |
|------|------|------|
| A. 형법 진입 우선 | 1라운드 과목 순서 정합, 라이브러리 완성도 ↑ | 8~10h 대공수, 사용자.md 위치 확인 필수 |
| B. 17897 카드 P1 우선 | 카드 시스템 인프라 빠른 진입, 라이브러리 활용 채널 | 사용자 별도 발주 대기 |
| C. 부록 sweep 우선 (#5) | 짧은 공수(1~2h), 라이브러리 완성도 ↑ | 차기 작업 가치 적음 |

**권장**: 사용자 발화 따라 결정. 17897은 사용자 OK 명시 후, 형법은 사용자.md 확인 후.

### 💡 6.3 사용자.md 백업 책임 분담

- 사용자 본인 직접 (메인 X) — 사용자 자료 영역
- 메인이 cp 명령 실행 시 사용자 컨펌 필수
- 백업 위치/주기는 사용자 결정

---

## 7. 리스크 매트릭스

| ID | 위험 | 영향 | 완화 |
|----|------|:--:|------|
| R1 | 격→견 변경 시 사용자.md 미동기 → 불일치 | 中 | 사용자.md 동시 갱신 필수 (사용자 컨펌 후) |
| R2 | 사용자.md 백업 없이 손실 (USB 단일) | 高 | 사용자에게 백업 권유 (Time Machine/별도 USB) |
| R3 | 형법 사용자.md 미존재 → PDF만으로 작성 → 정확도 저하 | 中 | 사용자 컨펌 후 진행, 컨펌 없으면 보류 |
| R4 | 17897 자동 착수 → 사용자 의도 어긋남 | 高 | `project_card_kickoff_pending` 룰 준수, 사용자 OK 전 X |
| R5 | 라이브러리 R-09 위반 (자의적 풀이형 추가) | 高 | 부장판사+강사 QA + 3단 byte 대조 (`feedback_three_stage_byte_compare`) |
| R6 | 가짜 두문자 침투 (강사·사용자 출처 없음) | 中 | `feedback_fake_mnemonic_detection` 검출 룰 |
| R7 | 라이브러리 본문 템플릿 컬러 일관성 ([red] 잔존) | 低 | `feedback_library_template_color` ([purple] 통일) |
| R8 | 게시판 10.77.11.110 OFF 시 사용자 못 봄 | 中 | 위키 .md fallback이 메인 (`feedback_handover_board_env_dependency`) |

---

## 8. 메모리 규칙 (신규 8건 + 핵심)

### 본 세션 신규 8건 (필수 access)

| 메모리 | 핵심 룰 |
|--------|---------|
| `feedback_qa_judge_lecturer.md` | 라이브러리 변경 시 부장판사 QA + 강사 QA 강제 |
| `feedback_user_confirmation_context.md` | 사용자 컨펌 맥락 (강사 / 출처 / 두문자 기준) |
| `feedback_pdf_first_for_typo_doubt.md` | 두문자 오타 의심 시 PDF 원문 1차 검증 |
| `feedback_fake_mnemonic_detection.md` | 가짜 두문자 검출 (강사·사용자 출처 0건 = 가짜) |
| `feedback_three_stage_byte_compare.md` | 3단 byte 대조 (PDF ↔ 사용자.md ↔ 라이브러리) |
| `feedback_traceable_source_meta.md` | 추적성 메타 (페이지/라인/절대경로) 강제 |
| `feedback_autonomous_execution_scope.md` | 자율 진행 권한 범위 (코드 변경 X 인스턴스) |
| `feedback_library_template_color.md` | [blue]제목 + [purple]본문 + [blank2]두문자 통일 |

### 핵심 기존 메모리

- `feedback_no_dooray_registration.md` (두레이 절대 X)
- `feedback_no_pr_workflow.md` (PR 생략)
- `feedback_no_subagent_for_board.md` (Opus 전용)
- `reference_lawear_endpoints_libs.md` (뷰어 + 게시판 IP + 라이브러리 위치)
- `reference_user_mnemonics.md` (사용자 두문자.md 위치)
- `feedback_emphasis_workflow.md` (Lv.4 3단)
- `feedback_subject_order.md` (1라운드 과목 순서)
- `feedback_subagent_self_eval_unreliable.md` (서브에이전트 자평 신뢰 X)
- `feedback_library_first_workflow.md` (라이브러리 우선 + 사용자.md 정독)
- `feedback_handover_board_env_dependency.md` (게시판 IP 환경 의존)
- `feedback_score_in_origin.md` (`## 원본 (NN점)`)
- `feedback_pdf_sanity_check.md` (R-28 sanity check)
- `project_card_kickoff_pending.md` (17897 카드 — 자동 X)

---

## 9. 관련 링크

### 9.1 위키 (메인)

- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part1.md`
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part2.md`
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part3.md` (본 문서)
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part{1,2,3}.md` (선행 인계)
- `/Users/nhn/zman-lab/lawear/docs/wiki/17897_anki_planning.md` (17897 기획)
- `/Users/nhn/zman-lab/lawear/docs/wiki/17897_session_kickoff.md` (17897 1줄 진입)

### 9.2 게시판 (http://10.77.11.110:8585)

- #1967 — 선행 인계 (lawear-a91b)
- #1970 — eef5 댓글
- #1977 — eef5 댓글
- #1980 — eef5 댓글
- #1981 — eef5 댓글
- #1986 — eef5 댓글
- #1995 — eef5 댓글
- #2002 — eef5 댓글

### 9.3 커밋 (lawear repo, main)

8건 (시간순):
- `f0d4c4b` — R-09 정리 4건 + 누락 4건 신설 + 오타/번호/출처 8건
- `de044a7` — 라이브러리 추적성 메타 sweep + cross-reference
- `d230292` — 부록 A 버전 (검증용 절대경로 + 페이지/라인) 추가
- `cc993be` — 17895 라이브러리 두문자 페이지 collapsible UI
- `74d1524` — 본문 템플릿 sweep + summary 카테고리 제거 + 1-6 4요건 정정
- `d54e201` — 민소 2-4 채권자대위 4요건 본문 템플릿 (옵션 C)
- `72078e9` — PDF 원문 정리본 + 컬러 태그 4종 + 17895 등재
- `ee32834` — PDF 역방향 sweep + [red]→[purple] 컬러 통일

### 9.4 라이브러리 (절대경로)

- `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민법.md` (1468줄)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민소.md` (1362줄)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민법.md` (263줄)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민소.md` (212줄)

### 9.5 사용자.md (절대경로, USB)

- `/Users/nhn/myftp/2026_USB/두문자정리및책/민법/사용자정본_두문자.md`
- `/Users/nhn/myftp/2026_USB/두문자정리및책/민소/사용자정본_두문자.md`

### 9.6 17895 뷰어

- URL: `http://127.0.0.1:17895/merge.html`
- 라이브러리 type:"library" 분기 + 두문자 페이지 collapsible UI 적용 완료

### 9.7 메모리 디렉토리

- `/Users/nhn/.claude/projects/-Users-nhn-zman-lab-lawear/memory/`

---

## 10. 마지막 힌트

1. **사용자 강사 답 받으면 즉시 #1 실행** (10분, 3-4 Edit + commit). 답 없으면 다른 작업 진행
2. **메인이 모든 디스패치 후 git diff byte 단위 검증** — 서브에이전트 자평 신뢰 X (`feedback_subagent_self_eval_unreliable`)
3. **라이브러리 변경 시 부장판사+강사 QA 강제** — 정확도 + 시험 관점 동시 (`feedback_qa_judge_lecturer`)
4. **가짜 두문자 검출 룰** — 강사·사용자 출처 0건 = 가짜 (`feedback_fake_mnemonic_detection`)
5. **추적성 메타 강제** — 페이지/라인/절대경로 (`feedback_traceable_source_meta`)
6. **본문 템플릿 컬러 일관성** — [blue]제목 + [purple]본문 + [blank2]두문자 ([red] 신규 사용 X, `feedback_library_template_color`)
7. **17897 자동 착수 X** — 사용자 명시 OK 필수 (`project_card_kickoff_pending`)
8. **게시판 = 10.77.11.110:8585 만** (127.0.0.1 X — 다른 머신 못 봄)
9. **두레이 절대 X / PR 생략 / Opus + ultrathink 전용**
10. **부록 추적성 sweep 시 라이브러리 .md 끝 부록 A/C 두 인덱스 모두 검사**

---

## 11. 감사

본 세션 lawear-eef5는 lawear-a91b로부터 두문자 라이브러리 작업을 인계받아 다음을 완료:
- 라이브러리 본문 템플릿 sweep (민법 76 + 민소 62 = 138 항목)
- PDF 원문 정리본 신설 (`_pdf_원문_민법.md` 263줄 + `_pdf_원문_민소.md` 212줄)
- 부록 A 검증용(절대경로+페이지/라인) 신설 + C 간단 인덱스 정합
- 17895 라이브러리 두문자 페이지 collapsible UI
- 컬러 태그 4종 정착 ([blue]/[purple]/[blank]/[blank2]) + [red] 통일 작업
- 메모리 신규 8건 (QA/byte 대조/가짜 검출/추적성/컬러/사용자 컨펌/PDF 1차/자율 권한)
- 게시판 댓글 7건 (#1970/#1977/#1980/#1981/#1986/#1995/#2002)
- 커밋 8건 (`f0d4c4b` → `ee32834`)

차기 세션은 사용자 강사 답 후 #1 격→견 즉시 실행 가능, 1라운드 과목 순서대로 형법 진입 또는 17897 카드 시스템 P1 (사용자 OK 후) 진행 가능 상태.

---

## 12. 차기 세션에

> 본 인수인계가 완료된 시점에서, 차기 세션이 가장 빠르게 가치를 만드는 길은 사용자 강사 답을 받은 직후 `#1 격→견 정정` (10분) 즉시 실행입니다. 답을 아직 못 받았으면 다음 중 선택:
>
> ```
> (a) #2 사용자.md 백업 권유 (사용자 결정 영역)
> (b) #3 형법 라이브러리 진입 (사용자.md 형법본 위치 확인 후)
> (c) #4 17897 카드 시스템 P1 (사용자 별도 발주 OK 후)
> (d) #5 부록 추적성 sweep 보강 (1~2h, 즉시 가능)
> ```
>
> 시작 시 다음 메모리 우선 확인:
>
> - 신규 8건 (`feedback_qa_judge_lecturer` / `feedback_three_stage_byte_compare` / `feedback_fake_mnemonic_detection` / `feedback_traceable_source_meta` / `feedback_library_template_color` / `feedback_user_confirmation_context` / `feedback_pdf_first_for_typo_doubt` / `feedback_autonomous_execution_scope`)
> - 핵심 기존 (`feedback_no_dooray_registration` / `feedback_no_pr_workflow` / `feedback_no_subagent_for_board` / `project_card_kickoff_pending`)

---

## 13. check_items (인수인계 품질 검증 YAML)

```yaml
check_items:
  checklist_version: "1.0.0"
  checklist_generated_at: "2026-05-20T14:00:00+09:00"
  sender_session: "lawear-eef5"

  items:
    # === 하드 게이트 (weight 3, required) ===
    - id: parts_access
      question: "Part 1/2/3 전부 access?"
      answer_type: "post_id_set"
      expected_files:
        - "/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part1.md"
        - "/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part2.md"
        - "/Users/nhn/zman-lab/lawear/docs/wiki/lawear-eef5_handover_part3.md"
      fallback_post_ids: []   # 게시판 등재 시 채움 (lawear-work)
      weight: 3
      required: true

    - id: opus_ultrathink
      question: "모든 서브에이전트 Opus+ultrathink?"
      answer_type: "bool"
      expected: true
      weight: 3
      required: true

    # === 중요 (weight 2) ===
    - id: prev_chain
      question: "선행 #1967 access?"
      answer_type: "post_id_any"
      expected: [1967]
      fallback_files:
        - "/Users/nhn/.claude/handover-state/archive/lawear-a91b.json"
        - "/Users/nhn/.claude/handover-state/archive/lawear-abf3.json"
      weight: 2

    - id: memory_rules
      question: "메모리 신규 8건 access?"
      answer_type: "file_access_any"
      expected:
        - "feedback_qa_judge_lecturer.md"
        - "feedback_user_confirmation_context.md"
        - "feedback_pdf_first_for_typo_doubt.md"
        - "feedback_fake_mnemonic_detection.md"
        - "feedback_three_stage_byte_compare.md"
        - "feedback_traceable_source_meta.md"
        - "feedback_autonomous_execution_scope.md"
        - "feedback_library_template_color.md"
      weight: 2

    - id: key_files
      question: "라이브러리 + PDF 원문 + 사용자.md 절대경로 3+ 인식?"
      answer_type: "file_line_count"
      expected_min: 3
      expected_files:
        - "/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민법.md"
        - "/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민소.md"
        - "/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민법.md"
        - "/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민소.md"
        - "/Users/nhn/myftp/2026_USB/두문자정리및책/민법/사용자정본_두문자.md"
        - "/Users/nhn/myftp/2026_USB/두문자정리및책/민소/사용자정본_두문자.md"
      weight: 2

    - id: first_response_quality
      question: "Part 2의 첫 응답 템플릿 준수?"
      answer_type: "subjective"
      expected_signals:
        - "사전 확인"
        - "선행 체인"
        - "옵션"
        - "사용자 강사 답"
        - "격→견"
      weight: 2

    - id: dooray_skip
      question: "두레이 skip 인지 (lawear 정책)?"
      answer_type: "subjective"
      expected_signals:
        - "feedback_no_dooray_registration"
        - "두레이 N/A"
        - "lawear 절대 룰"
      weight: 2

    # === 선택 (weight 1) ===
    - id: memory_additions_count
      question: "메모리 신규 8건 인식?"
      answer_type: "int"
      expected: 8
      weight: 1

    - id: library_state
      question: "라이브러리 본문 템플릿 100% 인지 ([blue]+[purple]+[blank2])?"
      answer_type: "subjective"
      expected_signals:
        - "[blue]"
        - "[purple]"
        - "[blank2]"
        - "feedback_library_template_color"
      weight: 1

    - id: pdf_원문_files
      question: "_pdf_원문_*.md 위치 인지?"
      answer_type: "file_access_any"
      expected:
        - "/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민법.md"
        - "/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/_pdf_원문_민소.md"
      weight: 1

    - id: viewer_url
      question: "17895 URL 인지?"
      answer_type: "keyword_any"
      expected:
        - "http://127.0.0.1:17895/merge.html"
        - "127.0.0.1:17895"
        - "17895"
      weight: 1

    - id: commits_authored
      question: "본 세션 커밋 8건 인지?"
      answer_type: "int"
      expected: 8
      expected_hashes:
        - "f0d4c4b"
        - "de044a7"
        - "d230292"
        - "cc993be"
        - "74d1524"
        - "d54e201"
        - "72078e9"
        - "ee32834"
      weight: 1

  # === 메타 ===
  total_weight_max: 23   # 3+3+2+2+2+2+2+1+1+1+1+1
  pass_threshold_percent: 75
  partial_threshold_percent: 50
  hard_gate_ids: ["parts_access", "opus_ultrathink"]
```

---

— lawear-eef5 sender, 2026-05-20
