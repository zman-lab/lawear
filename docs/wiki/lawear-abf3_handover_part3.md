# lawear-abf3 인수인계 Part 3 — 실행 가이드 + check_items

> **선행 세션**: lawear-abf3 (2026-05-19 종료)
> **차기 세션**: lawear-XXXX (본 문서 수신자)
> **체인**: lawear-6381 → lawear-0183 → lawear-9632 → **lawear-abf3** → (수신자)
> **두레이**: skip (`feedback_no_dooray_registration`)

---

## 1. 전체 작업 맵 (14건)

| # | 작업 | 출처 | 우선순위 |
|---|------|------|:--:|
| A1 | 17897 카드 시스템 P1 (DB + build_cards.py + dry-run) | Part 2 §1.1 / 17897_anki_planning §6 | **P0** |
| A2 | 17897 P2 (server.py REST API) | 동 | P1 |
| A3 | 17897 P3 (index.html UI + 단축키) | 동 | P1 |
| A4 | 17897 P4 (Stats 3-tab) | 동 | P1 |
| A5 | 17897 P5 (launchd + 백업) | 동 | P1 |
| A6 | 17897 P6 (스킬 통합) | 동 | P1 |
| B1 | Lv.4 P2 5건 재처리 (미케03_29~33) | Part 1 §9.2 / Part 2 §2.2 | P1 |
| B2 | Lv.4 P3 입민법 28건 | Part 2 §1 | P2 |
| B3 | Lv.4 P4 4과목 전체 170건 | 동 | P2 |
| C1 | 형법 진입 (입문+예비) — 정답지 위치 확인 필수 | Part 2 §1, §2.3 | P2 |
| D1 | 두문자 라이브러리 형법 추가 | Part 2 §1 | P2 |
| D2 | 두문자 라이브러리 형소 추가 | 동 | P2 |
| D3 | 두문자 라이브러리 부등 추가 | 동 | P2 |
| E1 | Lv.4 [blank] 태그 통일 / 결론 누락 7개 .md | Part 2 §1 | P3 (회피 유지) |

---

## 2. 우선순위 매트릭스

| 우선순위 | 작업 | 비고 |
|:--:|------|------|
| **P0** | A1 (17897 P1 — 새 세션 1줄 복붙 가능) | 즉시 착수 가능 |
| P1 | A2~A6 (17897 P2~P6) / B1 (Lv.4 P2 재처리) | P1 dry-run 결과 사용자 OK 후 |
| P2 | B2 B3 (Lv.4 P3 P4) / C1 (형법) / D1 D2 D3 (두문자 라이브러리 확장) | |
| P3 | E1 ([blank] 통일 / 결론 누락) — **회피 유지** (β-2-a, γ-1 사용자 결정) | 현재 상태 보존 |

---

## 3. 사이클 분할

### 3.1 즉시 사이클 (다음 세션 첫 작업)

**옵션 A — 17897 P1 (권장, P0)**
- 새 세션 1줄: `docs/wiki/17897_session_kickoff.md 읽고 P1 시작해`
- 산출물: 워크트리 cards-srs / docs/tts-cards/ / migrations/001_initial.sql / build_cards.py / dry-run 결과
- 검수: 라이브러리 .md 138 항목이 카드로 정확히 추출되는지 (forward 138 + blank 96 = 234 카드 예상)

**옵션 B — Lv.4 P2 5건 재처리 (P1)**
- 대상 5건 (미케03_29 / 30 / 31 / 32 / 33)
- 입력: `docs/tts-new/두문자/민법.md` 정독 + 사용자 27건 패턴
- 검증: 메인 직접 git diff (R-09 본문 변경 0 byte)
- 룰: A → B → C → D 순서

### 3.2 다음 사이클 (P1 OK 후)

- 17897 P2~P6 순차
- Lv.4 P3 입민법 28건
- 두문자 라이브러리 형법/형소/부등 추가 (사용자 두문자.md 신규 시)

### 3.3 별건

- 형법 진입 (입문 → 예비) — 정답지 위치 확인 필요
- Lv.4 P4 (4과목 전체 170건)

---

## 4. 각 항목 상세 (P0/P1 위주)

### A1. 17897 카드 시스템 P1 — DB + build_cards.py + dry-run

**파일/경로**:
- 신설 워크트리: `wt/{차기세션ID}/cards-srs` → 디렉토리 `/Users/nhn/zman-lab/lawear-{차기세션ID}-cards-srs/`
- 신설 폴더: `/Users/nhn/zman-lab/lawear/docs/tts-cards/`
- 신설 마이그: `docs/tts-cards/migrations/001_initial.sql`
- 신설 스크립트: `docs/tts-cards/build_cards.py`

**DB 스키마 핵심** (17897_anki_planning.md §4.2):
```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE cards (
  card_id        TEXT PRIMARY KEY,
  subject        TEXT NOT NULL,
  subject_kor    TEXT NOT NULL,
  category       TEXT NOT NULL,
  section        TEXT NOT NULL,
  title          TEXT NOT NULL,
  card_type      TEXT NOT NULL CHECK (card_type IN ('forward','blank','reverse')),
  front          TEXT NOT NULL,
  back           TEXT NOT NULL,
  mnemonic       TEXT,
  source_md      TEXT NOT NULL,
  source_line    INTEGER,
  content_hash   TEXT NOT NULL,
  archived       INTEGER NOT NULL DEFAULT 0,
  archived_at    TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
-- + card_stats / reviews / bookmarks / settings (총 5 테이블)
```

**build_cards.py TC 5건**:
- TC-1 신규 라이브러리 (빈 DB) → 민법 76 + 민소 62 = 138 forward + ~96 blank
- TC-2 라이브러리 1 항목 추가 → +1~3 카드
- TC-3 라이브러리 1 항목 삭제 → archived=1
- TC-4 본문 수정 → content_hash 변경 → back 갱신 + stats 보존
- TC-5 두문자 변경 → 구 blank archived + 신규 blank

**공수**: 4h / **리스크**: R6 (자동 추출 정확성) — strict + dry-run 의무

### A2. 17897 P2 — server.py REST API

**파일/경로**: `/Users/nhn/zman-lab/lawear/docs/tts-cards/server.py`

**API 14 endpoint** (17897_anki_planning §4.6):
```
GET    /api/health
GET    /api/cards/next?mode=srs&subject=civil&bookmarks=1
GET    /api/cards/{card_id}
GET    /api/cards?subject=civil&category=...&search=...&limit=50
POST   /api/cards/{card_id}/review
GET    /api/stats/daily?days=30
GET    /api/stats/weak?limit=10&subject=civil
GET    /api/stats/progress
POST   /api/bookmarks/{card_id}
DELETE /api/bookmarks/{card_id}
GET    /api/bookmarks
GET    /api/settings
PUT    /api/settings
POST   /api/library/sync
GET    /api/library/diff
```

**환경변수**: `LAWEAR_CARDS_PORT=17897`, `LAWEAR_CARDS_BIND=127.0.0.1`

**공수**: 6h / **리스크**: R7 (SRS 알고리즘 튜닝)

### B1. Lv.4 P2 5건 재처리 (미케03_29~33)

**파일**:
- `/Users/nhn/zman-lab/lawear/docs/tts-new/입문_민법/2026_minbeop_immun_미케03_29.md`
- `/Users/nhn/zman-lab/lawear/docs/tts-new/입문_민법/2026_minbeop_immun_미케03_30.md`
- `/Users/nhn/zman-lab/lawear/docs/tts-new/입문_민법/2026_minbeop_immun_미케03_31.md`
- `/Users/nhn/zman-lab/lawear/docs/tts-new/입문_민법/2026_minbeop_immun_미케03_32.md`
- `/Users/nhn/zman-lab/lawear/docs/tts-new/입문_민법/2026_minbeop_immun_미케03_33.md`

**입력**: `docs/tts-new/두문자/민법.md` (842줄, 76 항목 — **정독 강제**)

**워크플로우**:
1. 라이브러리 정독 (헤더 + 풀이형 + 본문 템플릿 모두)
2. 5건 ## 원본 답안 섹션 vs Lv.4 번호 매핑 분석 (룰 D)
3. 강조 적용 (룰 A 핵심만, 룰 B 다중 분리)
4. 두문자 → 풀이형 본문 [blank2] 인라인 (룰 C)
5. 메인 직접 `git diff` byte 단위 검증 (R-09)
6. 사용자 검수 (게시판 또는 콘솔)

**예상 수정** (Part 1 §6 사례):
- 이행불능 풀이형 누락 → 라이브러리 매핑 참조 복원
- "차지권" 오해 → "이전등기청구권" 등 정확 복원

**공수**: 2h / **리스크**: R1 (서브에이전트 자평 신뢰 X) — **메인 직접 검증**

### C1. 형법 진입 (입문 + 예비)

**차단조건**: 정답지 위치 사용자 확인 필수

**예상 PDF 경로**:
- `/Users/nhn/myftp/2026_USB/2026_박문각_피뎁/입문_형법/`
- `/Users/nhn/myftp/2026_USB/2026_박문각_피뎁/예비_형법/`

**확인 사항**:
- 정답지 PDF 별도 vs 본문 PDF 안에 포함 여부
- 미케/모고 시리즈 구조 (민법 패턴과 동일 여부)
- 두문자.md 신규 추가 (`/Users/nhn/Documents/암기노트/형법/두문자_정리.md`)

**공수**: TBD (정답지 구조 확인 후 산정)

---

## 5. 착수 체크리스트

- [ ] 세션 ID 생성 (`python3 -c "import secrets; print(f'lawear-{secrets.token_hex(2)}')"`)
- [ ] Part 1/2/3 access (`docs/wiki/lawear-abf3_handover_part{1,2,3}.md`)
- [ ] 선행 체인 1건 이상 access (lawear-9632 #75/#77/#78)
- [ ] 사용자 27건 침범 0건 (`git status -s | grep "미케0[1-3]_"` → 0 라인)
- [ ] 메모리 핵심 11건 확인 (Part 2 §4)
- [ ] 룰 A/B/C/D 학습 가이드 §9 access
- [ ] 라이브러리 위치 인지 (`docs/tts-new/두문자/{민법,민소}.md`)
- [ ] 환경 확인 (뷰어 17895 ON / 게시판 10.77.11.110:8585 ON/OFF)
- [ ] 두레이 N/A 인지
- [ ] PR 생략 인지
- [ ] Opus 전용 인지 (서브에이전트도)

---

## 6. 판단 포인트

### 6.1 Lv.4 P2 5건 재처리 vs 17897 P1 우선순위

| 옵션 | 장점 | 단점 |
|------|------|------|
| **A. 17897 P1 우선** (P0) | 새 세션 1줄 복붙으로 즉시 진입 / 학습 시스템 핵심 인프라 / 라이브러리 활용 검증 채널 | Lv.4 P2 잔존 위반 미해소 (단 5건이라 위급 X) |
| B. Lv.4 P2 재처리 우선 (P1) | R-09/룰 C/D 정착 검증 / 라이브러리 1차 활용 사례 | 17897 P1 지연 |

**권장**: A. 17897 P1 우선. Lv.4 P2 5건은 라이브러리 정착 후 정확도 향상 기대 (라이브러리 1차 활용 사례로 17897 P1 dry-run 결과 검수 직후 진행).

### 6.2 형법 진입 시점

- 17897 P1~P6 완료 시 + 두문자.md 형법본 사용자 추가 시 → C1 + D1 동시 진행
- 이전: 형법 진입 보류 (정답지 위치 미확인)

### 6.3 두문자 라이브러리 보강 부분 검수

- 현재 1-6 채권자대위 5단계 표 확정 (계·승·국·사 / 지·패 / 패·총 / 청·취·통·개·류 X / 해·탈 O / 공분청)
- 다른 카테고리 (특히 풀이형 매핑 완비도) 사용자 검수 필요 시점 미정
- 17897 P1 dry-run 시 누락 매핑 자동 발견 채널로 활용 가능

---

## 7. 리스크 매트릭스 (Part 2 §6 + 신규)

| ID | 위험 | 완화 |
|----|------|------|
| R1 | 서브에이전트 자체 평가 신뢰 X | 메인 직접 git diff (byte 단위) |
| R2 | 게시판 IP 환경 의존 | 10.77.11.110 우선 / 위키 fallback |
| R3 | 라이브러리 풀이형 누락 | 사용자.md 전체 정독 |
| R4 | 사용자 27건 침범 (BLOCKER) | 매 자동화 후 git status 검증 |
| R5 | 17896 vs 17897 패러다임 차이 | 책임 분리 (sync 채널 1개) |
| R6 (신규) | 17897 카드 자동 추출 정확성 | strict + dry-run + TC 5건 |
| R7 (신규) | 17897 SRS 알고리즘 패턴 불일치 | settings.srs_params 핫 튜닝 |
| R8 (신규) | 17897 학습 데이터 손실 | WAL + 일배치 백업 + .gitignore |

---

## 8. 메모리 규칙 (Part 2 §4 인용)

핵심 11건:
- `reference_lawear_endpoints_libs.md` (신규 — 본 세션)
- `feedback_no_dooray_registration.md`
- `feedback_no_pr_workflow.md`
- `feedback_no_subagent_for_board.md`
- `reference_user_mnemonics.md`
- `feedback_emphasis_workflow.md`
- `reference_mock_exam_structure.md`
- `feedback_subject_order.md`
- `feedback_worktree_db_backup.md`
- `feedback_pdf_sanity_check.md`
- `feedback_score_in_origin.md`

본 세션 신규 제안 3건 (사용자 승인 대기):
1. `feedback_subagent_self_eval_unreliable.md`
2. `feedback_library_first_workflow.md`
3. `feedback_handover_board_env_dependency.md` (또는 기존 갱신)

---

## 9. 관련 링크

### 9.1 위키 (메인)
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part1.md`
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part2.md`
- `/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part3.md`
- `/Users/nhn/zman-lab/lawear/docs/wiki/17897_anki_planning.md`
- `/Users/nhn/zman-lab/lawear/docs/wiki/17897_session_kickoff.md`

### 9.2 게시판 글 (10.77.11.110:8585 OFF 시 위키 fallback)
- lawear-9632 Part 1/2/3: #75 #77 #78 (read 가능 시)
- 17897 게시판 인덱스: #127 (10.77.11.110)
- 본 세션 인수인계: 게시판 등재 시도 — 환경 의존

### 9.3 커밋
- lawear: `d355601` `8d8856c` `e1b35cb` `8565556`
- init: `738821a`

### 9.4 라이브러리 + 스킬
- `docs/tts-new/두문자/민법.md` (842줄)
- `docs/tts-new/두문자/민소.md` (762줄)
- `~/init/claude/commands/dev-lawear-shortcut-lib-update.md` (464줄)

---

## 10. 마지막 힌트

1. **첫 응답에 `docs/wiki/17897_session_kickoff.md 읽고 P1 시작해` 사용자가 입력하면 즉시 워크트리 생성 + DB 스키마 + build_cards.py 작성 + dry-run 진입**
2. **Lv.4 자동화 시 라이브러리 우선 정독** (`docs/tts-new/두문자/민법.md` 842줄 + `민소.md` 762줄). 헤더만 스캔 금지
3. **사용자 27건 (미케01_01~03_27) 절대 침범 X** — 매 자동화 후 git status 강제 확인
4. **메인이 모든 디스패치 후 git diff byte 단위 검증** — 서브에이전트 자평 신뢰 X
5. **게시판 = 10.77.11.110 우선 + 위키 메인** — 127.0.0.1만 작성하면 사용자 못 봄
6. **두레이 등록 절대 X / PR 생략** (lawear 절대 룰)
7. **Opus + ultrathink 전용** — 서브에이전트도 동일

---

## 11. 감사

37시간 단속 작업, 1.4B 토큰 (output 8.88M + cache_creation 35.7M + cache_read 1.36B), 1131 tool 호출, 106 서브에이전트 (전부 Opus + ultrathink). 5 커밋 + 1604줄 라이브러리 + 472줄 17897 기획 + 464줄 스킬.

차기 세션은 17897 카드 시스템 P1 즉시 진입 가능. Lv.4 자동화 사이클은 라이브러리 정착 후 정확도 향상 기대.

---

## 12. 차기 세션에

> 본 인수인계가 완료된 시점에서, 차기 세션이 가장 빠르게 가치를 만드는 길은 17897 P1 진입입니다. 새 세션 첫 발화로 다음을 복붙해주세요:
>
> ```
> docs/wiki/17897_session_kickoff.md 읽고 P1 시작해
> ```
>
> P1 dry-run 결과 검수 후, Lv.4 P2 5건 재처리(라이브러리 1차 활용)도 자연스럽게 이어집니다.

---

## 13. check_items (인수인계 품질 검증 YAML)

```yaml
check_items:
  checklist_version: "1.0.0"
  checklist_generated_at: "2026-05-19T04:00:00+09:00"
  sender_session: "lawear-abf3"

  # 하드 게이트 (weight 3, required)
  items:
    - id: parts_access
      question: "Part 1/2/3 전부 access?"
      answer_type: "file_access_all"
      expected:
        - "/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part1.md"
        - "/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part2.md"
        - "/Users/nhn/zman-lab/lawear/docs/wiki/lawear-abf3_handover_part3.md"
      fallback_post_ids: []   # 게시판 등재 성공 시 채움
      weight: 3
      required: true

    - id: opus_ultrathink
      question: "모든 서브에이전트 Opus+ultrathink?"
      answer_type: "bool"
      expected: true
      weight: 3
      required: true

    # 가중치 2 (중요)
    - id: prev_chain
      question: "선행 체인 1건 이상 접근?"
      answer_type: "post_id_any"
      expected: [75, 77, 78]   # lawear-9632 Part IDs
      fallback_files: [
        "/Users/nhn/.claude/handover-state/archive/lawear-9632.json",
        "/Users/nhn/.claude/handover-state/archive/lawear-0183.json",
        "/Users/nhn/.claude/handover-state/archive/lawear-6381.json"
      ]
      weight: 2

    - id: dooray_skip
      question: "두레이 skip 인지?"
      answer_type: "bool"
      expected: true   # lawear feedback_no_dooray_registration
      weight: 2

    - id: memory_rules
      question: "메모리 핵심 5건 접근?"
      answer_type: "file_access_any"
      expected:
        - "reference_lawear_endpoints_libs.md"
        - "feedback_no_dooray_registration.md"
        - "feedback_no_pr_workflow.md"
        - "feedback_no_subagent_for_board.md"
        - "reference_user_mnemonics.md"
      weight: 2

    - id: rule_abcd
      question: "룰 A/B/C/D 학습 가이드 §9 접근?"
      answer_type: "file_access_any"
      expected:
        - "/Users/nhn/.claude/handover-state/recv/lawear-abf3/lv4_learning_guide.md"
      weight: 2

    - id: library_location
      question: "두문자 라이브러리 위치 인지?"
      answer_type: "keyword_any"
      expected:
        - "docs/tts-new/두문자/"
        - "민법.md"
        - "민소.md"
      weight: 2

    - id: first_response_quality
      question: "첫 응답 템플릿 준수?"
      answer_type: "subjective"
      expected_signals:
        - "사전 확인"
        - "선행 체인"
        - "옵션 a/b/c/d/e"
        - "사용자 27건"
      weight: 2

    # 가중치 1 (선택)
    - id: anki_planning_17897
      question: "17897 카드 시스템 기획 인지?"
      answer_type: "file_access_any"
      expected:
        - "/Users/nhn/zman-lab/lawear/docs/wiki/17897_anki_planning.md"
        - "/Users/nhn/zman-lab/lawear/docs/wiki/17897_session_kickoff.md"
      weight: 1

    - id: r09_exception
      question: "룰 C PDF 인용 예외 인지?"
      answer_type: "keyword_any"
      expected:
        - "PDF 답안 인용"
        - "R-09 예외"
        - "(라) 방식"
      weight: 1

    - id: user_27_protection
      question: "사용자 27건 침범 0건 검증 필수 인지?"
      answer_type: "keyword_any"
      expected:
        - "27건"
        - "미케01_01~03_27"
        - "침범 0"
      weight: 1

    - id: viewer_ip_rule
      question: "뷰어 127.0.0.1 / 게시판 10.77.11.110 룰 인지?"
      answer_type: "keyword_any"
      expected:
        - "127.0.0.1:17895"
        - "10.77.11.110:8585"
      weight: 1

    - id: commits_authored
      question: "본 세션 커밋 5건 인지?"
      answer_type: "int"
      expected: 5   # d355601 + 8d8856c + e1b35cb + 8565556 + 738821a
      weight: 1

  total_weight_max: 25   # 3+3+2+2+2+2+2+2+1+1+1+1+1
  pass_threshold_percent: 75
  partial_threshold_percent: 50
  hard_gate_ids: ["parts_access", "opus_ultrathink"]
```

---

— lawear-abf3 sender, 2026-05-19
