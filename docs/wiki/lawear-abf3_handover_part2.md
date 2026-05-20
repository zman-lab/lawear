# lawear-abf3 인수인계 Part 2 — 차기 세션 가이드

> **선행 세션**: lawear-abf3 (2026-05-19 종료)
> **차기 세션**: lawear-XXXX (본 문서 수신자)
> **체인**: lawear-6381 → lawear-0183 → lawear-9632 → **lawear-abf3** → (본 문서 수신자)
> **두레이**: skip (lawear `feedback_no_dooray_registration` 절대 규칙)

---

## 1. 이월 항목 매트릭스 (8건)

| # | 항목 | 우선순위 | 공수 | 차단조건 | 비고 |
|---|------|:--:|:---:|---------|------|
| 1 | **17897 카드 시스템 P1 구현** (DB + build_cards.py + dry-run) | **P0** | 4h | - | 새 세션 1줄 복붙 가능 |
| 2 | Lv.4 P2 5건 룰 C/D 재처리 (미케03_29~33) | P1 | 2h | 라이브러리 정독 | 사용자 27건 침범 0건 강제 |
| 3 | 17897 P2~P6 (server.py / index.html / Stats / launchd / 스킬 통합) | P1 | 18h | P1 dry-run OK | P1 검수 후 단계별 |
| 4 | Lv.4 P3 (입민법 나머지 28건) | P2 | 4h | P2 OK | 라이브러리 활용 |
| 5 | Lv.4 P4 (4과목 전체 170건) | P2 | 12h | P3 OK | |
| 6 | 형법 진입 (입문 + 예비) | P2 | TBD | 정답지 위치 사용자 확인 필수 | `feedback_subject_order` 순서 |
| 7 | 두문자 라이브러리 형법/형소/부등 추가 | P2 | 각 2h | 사용자 두문자.md 추가 | 스킬 자동 트리거 |
| 8 | Lv.4 [blank] 태그 통일 + 결론 누락 7개 .md | P3 | 회피 유지 | β-2-a / γ-1 사용자 결정 | 현재 상태 보존 |

---

## 2. 다음 사이클 로드맵

### 2.1 17897 카드 시스템 (P0)

- **P1 (4h)**: 워크트리 `wt/{세션ID}/cards-srs` + `docs/tts-cards/` + `migrations/001_initial.sql` (5테이블 cards/card_stats/reviews/bookmarks/settings) + `build_cards.py` dry-run + TC 5건 (라이브러리 추가/삭제/수정 + 두문자 변경 + 빈 DB)
- **P2 (6h)**: `server.py` (포트 17897, REST 14 endpoint, env_loader, db_mod 미러)
- **P3 (6h)**: `index.html` (카드 학습 + 단축키 1234/Space/Z/B/S + 위장 모드)
- **P4 (3h)**: Stats 3-tab (Daily / Weak Top10 / Progress)
- **P5 (1h)**: launchd plist `com.lawear.cards.plist` + 일배치 백업 + .gitignore
- **P6 (2h)**: `/dev-lawear-shortcut-lib-update` 스킬에 17897 sync 단계 추가

**의존 검증 절차**:
- P1 dry-run 결과 사용자 OK 후 P2 진행
- P3 카드 학습 1회 시연 OK 후 P4
- P5 launchd 등록 전 포트 17897 공지 게시판 [포트] 등록 필수

### 2.2 Lv.4 P2 재처리 (P1)

- 대상: `docs/tts-new/입문_민법/2026_minbeop_immun_미케03_29~33.md` (5건)
- 입력: `docs/tts-new/두문자/민법.md` (842줄, 76 항목) + 사용자 27건 패턴
- 검증: 메인 직접 `git diff <commit>~ HEAD` 본문 byte 단위 (R-09 위반 0건 확인)
- 룰 우선순위: R-09 → A → B → C → D → §4 → §5
- 예상 수정: 이행불능 풀이형 누락 / "차지권" 오해 등 (Part 1 §6 사례)

### 2.3 형법 진입 (P2)

- **차단조건**: 정답지 위치 사용자 확인 필수
- 후보 위치:
  - `/Users/nhn/myftp/2026_USB/2026_박문각_피뎁/입문_형법/` (별도 정답지 가능)
  - `/Users/nhn/myftp/2026_USB/2026_박문각_피뎁/예비_형법/`
- 순서: 입문 → 예비 (`feedback_subject_order` 순서: 민법→민소→형법→부등(입문)→형소(예비))

---

## 3. 주요 파일 참조 (절대경로)

### 3.1 라이브러리 (본 세션 신설)

- `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민법.md` (842줄)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/두문자/민소.md` (762줄)
- `/Users/nhn/Documents/암기노트/민법/두문자_정리.md` (사용자 두문자 정본 — 라이브러리 갱신 시 정독 필수)
- `/Users/nhn/Documents/암기노트/민소/두문자_정리.md` (사용자 두문자 정본)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/_file_index.json` (두문자 2건 type:"library" 등재)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/merge.html` (좌측 사이드바 SUBJECT_ORDER 최상위 + 두문자 카드 탭 제거 + marked.parse)
- `/Users/nhn/zman-lab/lawear/docs/tts-new/server.py` (`/api/staging/upload/{과목}` endpoint)

### 3.2 17897 카드 시스템 (기획)

- `/Users/nhn/zman-lab/lawear/docs/wiki/17897_anki_planning.md` (472줄 — DB 스키마 / API 14 / UI / 위험 매트릭스)
- `/Users/nhn/zman-lab/lawear/docs/wiki/17897_session_kickoff.md` (83줄 — 새 세션 1줄 복붙)

### 3.3 인수인계

- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part1.md` (회고)
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part2.md` (본 문서)
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part3.md` (실행 가이드 + check_items YAML)
- `/Users/nhn/.claude/handover-state/recv/lawear-abf3/lv4_learning_guide.md` (룰 A/B/C/D §9)
- `/Users/nhn/.claude/handover-state/lawear-abf3_session_sketch.md` (sketch 원본)
- `/Users/nhn/.claude/handover-state/archive/lawear-abf3.json` (sender archive — finalize 시 작성)

### 3.4 스킬

- `/Users/nhn/init/claude/commands/dev-lawear-shortcut-lib-update.md` (464줄, 5단계 워크플로우 + 4 자연어 트리거 + 17895 staging 트리거)

### 3.5 사용자 27건 (침범 0건 검증 대상)

- `/Users/nhn/zman-lab/lawear/docs/tts-new/입문_민법/2026_minbeop_immun_미케01_01.md` ~ `2026_minbeop_immun_미케03_27.md` (총 27건)

---

## 4. 메모리 규칙 필수 확인

차기 세션 시작 시 아래 메모리 우선 확인:

| 메모리 | 핵심 룰 |
|--------|---------|
| `reference_lawear_endpoints_libs.md` | 뷰어 127.0.0.1:17895 / 게시판 10.77.11.110:8585 / 라이브러리 위치 / 룰 C PDF 인용 예외 / 17897 기획 |
| `feedback_no_dooray_registration.md` | **두레이 등록 절대 금지** (개인 자료) |
| `feedback_no_pr_workflow.md` | PR 생략, 워크트리 작업 후 메인 머지 일괄 |
| `feedback_no_subagent_for_board.md` | Opus만 (Sonnet/Haiku 절대 금지). 게시판 작성도 Opus |
| `reference_user_mnemonics.md` | 사용자 두문자.md 위치 + 두문자 풀이형 변환 룰 |
| `feedback_emphasis_workflow.md` | Lv.4 강조 3단 워크플로우 (자동 41% + 메인 수동 95% + 추출 보강) |
| `reference_mock_exam_structure.md` | 모고는 예비순환만 (입문은 미케 — lawear-abf3 8/8 정합 검증 후 정정) |
| `feedback_subject_order.md` | 1라운드 과목 순서: 민법→민소→형법→부등(입문)→형소(예비) |
| `feedback_worktree_db_backup.md` | 워크트리 remove 전 DB 백업 필수 (cards.db 등 gitignored) |
| `feedback_pdf_sanity_check.md` | R-28 PDF Direct Read sanity check (Phase 1.5 증빙) |
| `feedback_score_in_origin.md` | `## 원본 (NN점)` 형식. 메타 + 원본 두 곳 이중 기록 |

---

## 5. 배포 경계

- **lawear는 배포 X** (학습 자동화 도구)
- **17895 뷰어**: 본 세션 두문자 라이브러리 통합 완료. 사용자가 즉시 사용 가능 (`http://127.0.0.1:17895`).
- **17896 시험**: lawear-e571 세션 영역 — 본 세션 영향 X
- **17897 카드**: 신설 계획. P1 dry-run 완료 후 P2~P6 단계별 (총 ~22h)
- **launchd**: `com.lawear.ttsmerger.plist`(17895), `com.lawear.exam.plist`(17896) 운영 중. 17897용 신규 `com.lawear.cards.plist` 추가 예정

---

## 6. 위험 매트릭스

| ID | 위험 | 영향 | 완화 |
|----|------|:--:|------|
| R1 | 서브에이전트 자체 평가 신뢰 X (R-09 위반 자평 0건 → 실제 위반) | 高 | 메인 직접 git diff 검증 필수 (byte 단위) |
| R2 | 게시판 IP 환경 의존 (10.77.11.110 OFF 시 127.0.0.1 fallback이지만 다른 머신 접근 X) | 中 | 룰 명시 — 게시판 = 10.77.11.110 우선. OFF 시 위키 .md fallback |
| R3 | 라이브러리 풀이형 매핑 누락 (1차 사고 — 1-6 채권자대위 헤더만 봄) | 高 | 사용자 두문자.md 전체 정독 강제 (헤더만 스캔 금지) |
| R4 | **사용자 27건 침범 가능성** (미케01_01~03_27) | 高 (BLOCKER) | 매 자동화 시 git status 검증 + 강조 태그 카운트 |
| R5 | 17896 (시험 콘솔) vs 17897 (카드) 패러다임 차이 | 中 | 17897 신설로 분리. sync 채널 1개만 (17895 → 17897 단방향) |
| R6 (신규) | **17897 카드 자동 추출 정확성** (라이브러리 .md 파싱 오류 → 카드 누락/오생성) | 中 | `build_cards.py --strict` (모든 ### → forward 카드 1개 assert) + dry-run 차이 리포트 + TC 5건 |
| R7 (신규) | 17897 SRS 알고리즘 사용자 패턴 불일치 (Lv.4 본문이 길어 again 빈도 高 가능성) | 中 | settings.srs_params 핫 튜닝 (코드 변경 X) — 1~2주 후 데이터 기반 조정 |
| R8 (신규) | 17897 학습 데이터(`reviews` row 누적 가치 큼) 손실 | 高 | (1) WAL + 매일 일배치 backup `~/.lawear_backups/cards_{date}.db` (2) 워크트리 remove 전 DB 백업 (3) git 추적 X (.gitignore) |

---

## 7. 착수 체크리스트

차기 세션 시작 시 반드시 확인:

- [ ] 세션 ID 생성 (`python3 -c "import secrets; print(f'lawear-{secrets.token_hex(2)}')"`)
- [ ] 선행 체인 1건 이상 access (lawear-9632 #75/#77/#78 또는 본 Part 1/2/3)
- [ ] 메모리 11건 핵심 룰 확인 (Part 2 §4)
- [ ] 사용자 27건 (미케01_01~03_27) 침범 0건 확인 (`git status -s | grep 미케0[1-3]_`)
- [ ] 뷰어 127.0.0.1:17895 / 게시판 10.77.11.110:8585 환경 ON 확인
- [ ] 두문자 라이브러리 위치 인지 (`docs/tts-new/두문자/{민법,민소}.md`)
- [ ] 룰 A/B/C/D 학습 가이드 §9 access (`recv/lawear-abf3/lv4_learning_guide.md` 또는 인용)
- [ ] 두레이 N/A 인지 (`feedback_no_dooray_registration`)
- [ ] PR 생략 인지 (`feedback_no_pr_workflow`)
- [ ] Opus 전용 인지 (`feedback_no_subagent_for_board` — 서브에이전트도 Opus + ultrathink)

---

## 8. 첫 응답 템플릿 (차기 세션)

```
# 세션 시작 (lawear-XXXX) — 인수인계 받음

사전 확인
- 선행 세션 lawear-abf3 인수인계 받음 (Part 1/2/3 = docs/wiki/lawear-abf3_handover_part{1,2,3}.md)
- 선행 체인 lawear-6381 → 0183 → 9632 → abf3 → 본 세션
- 사용자 27건 (미케01_01~03_27) 침범 0건 확인 (git status -s 확인 결과 첨부)
- 두레이 N/A (lawear 절대 룰 — feedback_no_dooray_registration)
- 뷰어 127.0.0.1:17895 ON / 게시판 10.77.11.110:8585 {ON|OFF} 확인
- Opus + ultrathink (서브에이전트 동일)

💡 어느 작업부터?
- (a) **17897 카드 시스템 P1** — `docs/wiki/17897_session_kickoff.md` 1줄 복붙 (워크트리 cards-srs + DB + build_cards.py dry-run)
- (b) Lv.4 P2 5건 재처리 (미케03_29~33 라이브러리 활용, 룰 C/D 보강) — `docs/tts-new/두문자/민법.md` 정독 후
- (c) Lv.4 P3 입민법 28건 (P2 OK 후)
- (d) 형법 진입 — 정답지 위치 사용자 확인 필수 (입문 → 예비)
- (e) 두문자 라이브러리 형법/형소/부등 추가 (사용자 두문자.md 신규 시 스킬 트리거)
```

---

## 9. 마지막 힌트 (7개)

1. **라이브러리 sync 워크플로우**: 사용자가 뷰어에서 📤 업로드 → `_staging/{과목}_{ts}.md` 저장 → AI 호출 시 `/dev-lawear-shortcut-lib-update` 자동 트리거 → 4 케이스 분류 (A 동일 / B 변경 / C 신규 / D 누락) → D 의도 확인 필수 → 머지 후 PUT /api/save
2. **룰 우선순위 (최종)**: R-09 → 룰 A → 룰 B → 룰 C → 룰 D → §4 강조 적용 룰 → §5 4종 리소스 통합. R-09는 자의적 해석 금지가 핵심 — PDF 답안 인용 풀이형 복원은 예외 (메타 표기 필수)
3. **게시판 환경 의존**: 본 세션 중 10.77.11.110:8585 OFF/ON 변동 사례 발견. 게시판 = 10.77.11.110만 사용 룰(다른 머신 접근 위해). OFF 시 위키 .md fallback이 메인. **127.0.0.1:8585에 작성하면 사용자가 못 봄** — 발견 시 10.77.11.110에 재발행 필요
4. **사용자 27건 침범 검증**: 매 자동화 디스패치 직후 `git status` + `git diff --name-only`로 미케01_01~03_27 외 영역만 수정 확인. 강조 태그 카운트 변경 시 메인 직접 확인
5. **17897 신설 책임 분리**: 17895 통합 X 결정. cards.db 학습 데이터는 별도 launchd + 일배치 백업. sync 채널 1개만 (17895 → 17897 단방향). 17895/17896 안정성 보호
6. **메인 직접 git diff 검증**: 서브에이전트 자체 평가 신뢰 X. 모든 디스패치 후 메인이 `git diff <commit>~ HEAD <파일>` 실행 + 본문 byte 단위 확인. R-09 위반 = 즉시 revert
7. **워크트리 신설 시 DB 백업**: 17897 카드 시스템 P1 워크트리 cards-srs 신설 → cards.db 작업 중 → 워크트리 remove 전 백업 필수 (`feedback_worktree_db_backup` 메모리 — 사고 1건 발생 후 룰)

---

## 10. 감사

lawear-9632 → lawear-abf3 계승 받아 1라운드 민법 메타 정합화 / Lv.4 자동화 시도 → 룰 도출 / 라이브러리 우선 워크플로우 정착 / 17897 카드 시스템 기획까지 완료.

차기 세션은 17897 카드 시스템 P1을 즉시 착수할 수 있는 상태(킥오프 1줄 복붙). 또는 Lv.4 P2 5건 재처리도 라이브러리 준비 완료 상태에서 정확도 향상 기대.

— lawear-abf3 sender, 2026-05-19
