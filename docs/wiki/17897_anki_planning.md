# 17897 Anki 스타일 카드 시스템 기획

> **작성**: 2026-05-19 / 세션: lawear-1727
> **상태**: PLANNING (사용자 검수 대기)
> **참고**: 17895 (TTS 뷰어, 머지), 17896 (시험 콘솔, SRS 일부) 코드 실측 기반
> **위키 위치**: `/Users/nhn/zman-lab/lawear/docs/wiki/17897_anki_planning.md`
> **게시판 인덱스**: 작성 후 `lawear-work` 게시판에 링크 등록

---

## 1. 배경 / 결정 사항

### 1.1 사용자 요구
- 두문자/요건 라이브러리 (`docs/tts-new/두문자/{민법,민소}.md`) — 현재 민법 76항목 / 민소 62항목 — 을 **Anki 스타일 암기 카드**로 학습
- 사용자 명시 동작:
  1. **랜덤 추출** (마구잡이 모드)
  2. **자주 틀린 거** 우선 (약점 가중치)
  3. **오래 안 푼 거** 우선 (회상 한계 시점 강제)
  → 결론: **SM-2 약식 SRS + 약점 가중치 + 다중 모드 셀렉터**

### 1.2 17897 신설 결정
- 17896 답변 (Internal Review Console): 17895 통합 권장 (사이드바 라이브러리 탭에 카드 모드 끼우기) 였으나
- 사용자 결정: **17897 독립 서버**
  - 이유 (추정): 17895 = 머지/뷰어 (read+light edit), 17896 = 시험 콘솔 (시도/채점) 책임 명확. 17897 = 암기 (장기 반복) 별도 책임
  - 장점: DB / launchd / 백업 / 마이그 마다 독립 — 17895/17896 안정성 보호
  - 단점: 라이브러리 sync 채널 1개 추가 (17895 → 17897 단방향)

---

## 2. 17895 (뷰어, 포트 17895) 참고 부분

`/Users/nhn/zman-lab/lawear/docs/tts-new/server.py` + `merge.html` 실측 기반.

### 2.1 가져올 패턴
| 패턴 | 17895 위치 | 17897 적용 |
|------|----------|----------|
| `http.server.SimpleHTTPRequestHandler` + `socketserver.TCPServer(allow_reuse_address=True)` | server.py L23-141 | 동일 — Python stdlib 만 사용 |
| `PUT /api/save/{rel_path}` + Path traversal 방지 (`target.relative_to(ROOT)`) | server.py L24-77 | 카드 메타 저장 시 동일 가드 |
| `.md.bak` 자동 백업 (덮어쓰기 직전) | server.py L63-65 | DB는 SQLite + WAL 이라 다른 패턴 필요 (§4 백업 정책 참조) |
| CORS + `Cache-Control: no-store` | server.py L119-124 | 카드 학습은 즉시 반영 필요 → 동일 |
| `marked.parse()` 마크다운 렌더링 | merge.html L650 | 카드 back 본문 (`[red]…[/red]` 등 인라인 태그 포함 .md) 렌더링 |
| `type:"library"` 트리 분기 | merge.html (트리 빌드) | 17897 좌측 카테고리 트리 (과목 > 카테고리 > 항목) 패턴 차용 |
| `_file_index.json` 자동 인덱싱 | tts-new/_file_index.json | 17897 cards.db 가 마스터 — 단, 라이브러리 → DB 빌드 시점에 동일 인덱싱 발상 활용 |
| `_staging/` 임시 영역 | server.py L20, L79-117 | 라이브러리 갱신 시 17895 staging → 17897 sync 트리거 채널로 활용 |
| launchd `com.lawear.ttsmerger.plist` | (대응 plist) | 17897 신규 plist `com.lawear.cards.plist` 동일 패턴 |

### 2.2 가져오지 않을 부분
- merge.html 전체 1543줄 SPA — 17897 은 학습 UI라 본격 트리/탭/머지 다이얼로그 불필요. 카드 한 장 + 단축키만 있으면 됨.
- `/api/staging/upload/` AI 4 케이스 분석 흐름 — 17897 은 자동 라이브러리 파싱 (스크립트) 만 필요.

---

## 3. 17896 (시험 콘솔, 포트 17896) 참고 부분

`/Users/nhn/zman-lab/lawear/docs/tts-exam/server.py` + `index.html` + `migrations/001_initial.sql` 실측 기반.

### 3.1 가져올 패턴
| 패턴 | 17896 위치 | 17897 적용 |
|------|----------|----------|
| `ThreadingHTTPServer` + 환경변수 PORT/BIND | server.py L35, L54-55, L892 | 동일 — `LAWEAR_CARDS_PORT=17897`, `LAWEAR_CARDS_BIND=127.0.0.1` |
| `env_loader` (.env 자동 로드) | server.py L43, L51 | 동일 — 17897 도 익명/로컬, 단 키 의존 X (auto 채점 없음) |
| `db_mod.init_db()` 멱등 마이그 (`PRAGMA user_version`) | migrations/001-007 | 동일 — `migrations/` 폴더 + `user_version` 체크 |
| SQLite + WAL + `foreign_keys = ON` | 001_initial.sql L5-7 | 동일 |
| `_send_json(status, payload)` / `_send_error(status, error_code, message)` 헬퍼 | server.py L862-876 | 동일 — error_code 패턴 (`bad_request`, `card_not_found`, `internal_error` 등) |
| REST 라우팅 (GET/POST/PUT/DELETE 분기 + path prefix 검사) | server.py L72-292 | 동일 패턴, 라우트 수 적음 |
| `settings` 테이블 (key/value_json) 키-밸류 패턴 | 001_initial.sql L78-90 | 동일 — `srs_params`, `mode_default` 등 |
| `bookmarks` 테이블 (카드 즐겨찾기) | 001_initial.sql L72-75 | 동일 — `card_id PRIMARY KEY` |
| `reports/overall`, `reports/by-subject` 집계 패턴 | server.py L749-845, reports.py | 동일 — `/api/stats/daily`, `/api/stats/weak`, `/api/stats/progress` |
| 다크 모드 CSS 변수 (`--bg`, `--panel`, `--accent` 등) | index.html L9-31 | 동일 색상 변수 — 일관성 유지 |
| `applyStealth()` 영문 위장 + Z 단축키 | index.html L3377-3398, L3707 | 동일 — 카드 학습도 위장 모드 필요 (사용자 명시 요청 가능성) |
| `addEventListener('keydown')` 단축키 패턴 + textarea 가드 | index.html L3701-3748 | 단축키 표 (§5.4) — 1=Again 2=Hard 3=Good 4=Easy / Space=Show / S=Skip / B=Sidebar / Z=Stealth |
| Reports 3-tab (sub-tab-btn) | index.html L3409-3416 | 동일 — Daily / Weak Top10 / Progress |
| `Cache-Control: no-store` + CORS | server.py L847-853 | 동일 |
| ⓘ 툴팁 + i18n 사전 (한/영 위장용) | index.html L2834+, L3088+ | 동일 패턴 — 카드 모드 위장용 |
| `migrations/{NNN_*}.sql` + `mark_orphan_grading` 기동 시 healing | server.py L884-889 | 17897 healing — `mark_orphan_reviews()` (도중에 끊긴 review row 정리) |

### 3.2 가져오지 않을 부분
- 다중 설문 D안 (`subqs[]`, `answer_subq` 등) — 17897 카드는 단일 답안 (`back`) 만 가짐. 다중 카드는 카드 row 자체를 여러 개로 분리.
- 외부 채점 (Anthropic API + grader.py) — 17897 은 사용자 자가 평가 (Again/Hard/Good/Easy 4버튼). 자동 채점 없음.
- 사용자 manual 채점 워크플로우 (PUT /api/attempts/{id}/grade 외부 주입) — 17897 카드는 자가 평가라 단순.

---

## 4. 17897 디자인

### 4.1 인프라
| 항목 | 값 |
|------|-----|
| 포트 | **17897** (게시판 포트 등록 필요 — §7 참조) |
| 바인드 | `127.0.0.1` (로컬 전용) |
| 위치 | `/Users/nhn/zman-lab/lawear/docs/tts-cards/` |
| launchd | `com.lawear.cards.plist` (17896 plist 미러) |
| 로그 | `/tmp/lawear_cards.log`, `/tmp/lawear_cards.err` |
| DB | `cards.db` (SQLite + WAL) |
| 라이브러리 sync 채널 | `docs/tts-new/두문자/{민법,민소}.md` (read-only) → `python build_cards.py` → DB UPSERT |

### 4.2 DB 스키마

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

-- 1. cards (마스터 카드 메타)
CREATE TABLE cards (
  card_id        TEXT PRIMARY KEY,         -- ex: 'civil_1-1_a'  (subject_section_type)
  subject        TEXT NOT NULL,            -- 'civil' | 'civproc'
  subject_kor    TEXT NOT NULL,            -- '민법' | '민소'
  category       TEXT NOT NULL,            -- ex: '채권 일반 / 채무불이행'
  section        TEXT NOT NULL,            -- ex: '1-1'
  title          TEXT NOT NULL,            -- ex: '채무불이행 손해배상 요건'
  card_type      TEXT NOT NULL             -- 'forward' | 'blank' | 'reverse'
                 CHECK (card_type IN ('forward','blank','reverse')),
  front          TEXT NOT NULL,            -- 카드 앞면 (질문)
  back           TEXT NOT NULL,            -- 카드 뒷면 (본문 + 두문자 + 풀이형, .md 인라인 태그 보존)
  mnemonic       TEXT,                     -- 두문자 (예: '채·내·귀·법') — nullable
  source_md      TEXT NOT NULL,            -- 'docs/tts-new/두문자/민법.md'
  source_line    INTEGER,                  -- 파싱 시점 line — 라이브러리 갱신 추적용
  content_hash   TEXT NOT NULL,            -- back 의 sha256 (변경 감지)
  archived       INTEGER NOT NULL DEFAULT 0,  -- 라이브러리에서 삭제된 항목 보존 (1=archived)
  archived_at    TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_cards_subject_category ON cards(subject, category);
CREATE INDEX idx_cards_archived ON cards(archived);

-- 2. card_stats (학습 통계 + SRS 상태)
CREATE TABLE card_stats (
  card_id        TEXT PRIMARY KEY REFERENCES cards(card_id) ON DELETE CASCADE,
  ease_factor    REAL NOT NULL DEFAULT 2.5,  -- SM-2 ease (1.3 floor)
  interval_days  REAL NOT NULL DEFAULT 0,    -- 다음 복습까지 days
  due_at         TEXT,                       -- next_review timestamp (ISO-8601)
  last_review    TEXT,
  reviews_total  INTEGER NOT NULL DEFAULT 0,
  fails_total    INTEGER NOT NULL DEFAULT 0,  -- Again 누적
  hards_total    INTEGER NOT NULL DEFAULT 0,
  goods_total    INTEGER NOT NULL DEFAULT 0,
  easys_total    INTEGER NOT NULL DEFAULT 0,
  streak         INTEGER NOT NULL DEFAULT 0,  -- 연속 Good/Easy
  last_fail_at   TEXT,
  fails_30d      INTEGER NOT NULL DEFAULT 0   -- 30일 슬라이딩 fail (약점 모드용, 일배치 갱신)
);
CREATE INDEX idx_stats_due ON card_stats(due_at);
CREATE INDEX idx_stats_fails ON card_stats(fails_total DESC, fails_30d DESC);
CREATE INDEX idx_stats_last_review ON card_stats(last_review);

-- 3. reviews (각 리뷰 1 row — 히스토리)
CREATE TABLE reviews (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id        TEXT NOT NULL REFERENCES cards(card_id) ON DELETE CASCADE,
  reviewed_at    TEXT NOT NULL DEFAULT (datetime('now')),
  rating         TEXT NOT NULL CHECK (rating IN ('again','hard','good','easy')),
  response_ms    INTEGER,                   -- 카드 노출 → 평가까지 ms
  ease_before    REAL,
  ease_after     REAL,
  interval_before REAL,
  interval_after REAL,
  mode           TEXT,                       -- 'srs'|'weak'|'old'|'random'|'subject'
  session_id     TEXT                        -- 학습 세션 (UI 입장~퇴장)
);
CREATE INDEX idx_reviews_card ON reviews(card_id, reviewed_at DESC);
CREATE INDEX idx_reviews_date ON reviews(reviewed_at);

-- 4. bookmarks (즐겨찾기 — 17896 패턴 복제)
CREATE TABLE bookmarks (
  card_id        TEXT PRIMARY KEY REFERENCES cards(card_id) ON DELETE CASCADE,
  bookmarked_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 5. settings (17896 패턴)
CREATE TABLE settings (
  key            TEXT PRIMARY KEY,
  value_json     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES
  ('srs_params', '{"again_interval":0.0007,"hard_factor":1.2,"good_factor":null,"easy_factor":1.3,"ease_again_delta":-0.2,"ease_hard_delta":-0.15,"ease_easy_delta":0.15,"ease_floor":1.3,"ease_ceil":3.0}', datetime('now')),
  ('mode_default', '"srs"', datetime('now')),
  ('daily_target', '20', datetime('now')),
  ('stealth', 'false', datetime('now')),
  ('lang', '"ko"', datetime('now'));
```

### 4.3 카드 자동 추출 — `build_cards.py`

#### 4.3.1 라이브러리 파싱
- 입력: `docs/tts-new/두문자/{민법,민소}.md`
- 출력: `cards.db` UPSERT (`INSERT OR REPLACE` + content_hash 비교)

#### 4.3.2 추출 규칙 (실측 기반 — 민법.md L19-87 예시)
**소스 헤더 패턴**:
```
### 1-1. 채무불이행 손해배상 요건 (제390조)
- **두문자**: 채·내·귀·법
- **풀이형**: 채권 성립 / 채무내용에 좇은 이행을 하지 아니할 것 / ...
- **본문 템플릿**: ```...[red][blank2]채[/blank2]권 ...```
- **출처**: ...
- **연관 조문**: ...
```

**카드 1개 → 1~3 row**:

| `card_type` | front | back | 생성 조건 |
|-------------|-------|------|-----------|
| `forward` | 헤더 title (`채무불이행 손해배상 요건 (제390조)`) | 풀이형 + 본문 템플릿 + 두문자 | **항상 생성** |
| `blank` | 두문자 글자별 빈칸 (`[?]·내·귀·법`, `채·[?]·귀·법` ...) | 풀이형 + 정답 글자 강조 | 두문자 **3~6 글자**일 때만 (>6 자는 분할 X — UI 부담) — 민법 52건 / 민소 44건 |
| `reverse` | 풀이형 (`채권 성립 / 채무내용에 좇은 이행 ... / 위법`) | 헤더 title + 두문자 | 옵션 (settings 토글, 기본 OFF) — Lv.4 역방향 회상은 자가 평가 신뢰도 낮음 |

**예외 케이스**:
- 두문자 없는 항목 (민법 76 - 52 = 24건, 민소 62 - 44 = 18건): `forward` 만 생성
- 다중 두문자 (예: 민법 1-2 "무·도·가·귀·법 (또는 채·도·가·귀·법)"): 둘 다 별도 `blank` 카드 (alt 인덱스 추가)
- 사용자 두문자.md 인용 (예: 민법 1-6 4단계 표): 표 자체는 `forward` back 에 그대로 — 별도 카드 X (표는 시각 인덱스라 빈칸 부적합)

#### 4.3.3 카드 자동 추출 정확성 보장
- **content_hash 검증**: `back` 의 sha256 → 변경 시 stats 보존 + 카드 갱신 (Anki "update note" 패턴)
- **archived 보호**: 라이브러리에서 항목 삭제 시 카드 archived=1 (DELETE X) — fails_total 같은 사용자 학습 흔적 손실 방지
- **dry-run 모드**: `python build_cards.py --dry-run` → 신규/변경/삭제 카드 수 출력 (사용자 OK 후 실행)
- **테스트 케이스** (TC):
  - TC-1 신규 라이브러리 (빈 DB) → 민법 76 항목 → forward 76개 + blank 52~150개 (3~6글자 두문자 분할) + reverse 0개 (기본 OFF)
  - TC-2 라이브러리 1 항목 추가 → 카드 +1~3 (변경 외 row touch X)
  - TC-3 라이브러리 1 항목 삭제 → 카드 archived=1 (row 보존)
  - TC-4 라이브러리 1 항목 본문 수정 → content_hash 변경 → back 갱신 + stats 보존
  - TC-5 두문자 변경 (예: '채·내·귀·법' → '채·불·귀·법') → blank 카드 archived (구두문자) + 신규 blank 카드 생성
- **빠지면 안 되는 항목**: 모든 ### 헤더 = forward 카드 1개 보장 (assert 후 종료) — "라이브러리 76 항목인데 forward 75개" 같은 누락 즉시 fail

### 4.4 SRS 알고리즘 (SM-2 약식)

#### 4.4.1 수식 (settings.srs_params 기본값)
```
사용자 rating:
  again → interval = 1분(0.0007일) / ease -= 0.2  / streak = 0 / fails += 1
  hard  → interval = max(1, interval * 1.2) / ease -= 0.15  / streak preserve
  good  → interval = max(1, interval * ease) / ease 유지 / streak += 1
  easy  → interval = max(1, interval * ease * 1.3) / ease += 0.15 / streak += 1

ease = clamp(ease, 1.3, 3.0)
due_at = now + interval_days * 86400 sec

신규 카드 (last_review IS NULL):
  again → interval = 1분 (즉시 재시도)
  hard  → interval = 1일
  good  → interval = 1일
  easy  → interval = 4일
```

#### 4.4.2 튜닝 노트
- Anki 기본: again interval 1분 / good 신규 1일 — 본 안과 동일
- 사용자 학습 패턴 데이터 (1~2주 사용 후) 기반 튜닝 권장:
  - Lv.4 본문이 길어 again 빈도 높을 수 있음 → ease_floor 1.3 → 1.5 상향 검토
  - 시험 직전 (~30일) 모드 — interval cap (예: 7일) 적용해 강제 회상 빈도 증가
- 사용자에게 GUI 노출 X (settings.srs_params 는 코드 수정 / curl PUT 으로만 변경) — 복잡성 차단

### 4.5 모드 셀렉터

| 모드 | 쿼리 | 용도 |
|------|------|------|
| `srs` (기본) | `due_at <= now ORDER BY due_at ASC LIMIT 1` (없으면 신규 카드) | 사용자 명시 — "오래 안 푼 거" |
| `weak` | `ORDER BY fails_30d DESC, fails_total DESC, ease ASC LIMIT 1` | 사용자 명시 — "자주 틀린 거" |
| `old` | `ORDER BY last_review ASC NULLS FIRST LIMIT 1` | 사용자 명시 — "오래 안 푼 거" (SRS 와 별개 — 단순 시간순) |
| `random` | `ORDER BY RANDOM() LIMIT 1` | 사용자 명시 — "랜덤" |
| `subject` (필터) | 위 4 모드 + `WHERE subject = ?` 결합 | 민법/민소 격리 |
| `bookmarks` (필터) | + `WHERE card_id IN (SELECT card_id FROM bookmarks)` | 즐겨찾기만 |

**복합 가능**: `?mode=weak&subject=civil&bookmarks=1`

**없을 때 fallback**:
- srs 모드 + due 카드 0 → 신규 카드 (last_review IS NULL ORDER BY card_id) → 그래도 없으면 200 + `{"card": null, "reason": "all_caught_up"}`

### 4.6 REST API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/health` | 17896 패턴 미러 |
| GET | `/api/cards/next?mode=srs&subject=civil&bookmarks=1` | 다음 카드 1개 (모드/필터) |
| GET | `/api/cards/{card_id}` | 카드 + stats + 최근 reviews 10건 |
| GET | `/api/cards?subject=civil&category=...&search=...&limit=50` | 카드 리스트 (사이드바) |
| POST | `/api/cards/{card_id}/review` | `{rating, response_ms, mode, session_id}` → 새 review row + stats 갱신 |
| GET | `/api/stats/daily?days=30` | 일별 review count + accuracy |
| GET | `/api/stats/weak?limit=10&subject=civil` | 약점 Top N |
| GET | `/api/stats/progress` | 과목/카테고리별 진척률 |
| POST | `/api/bookmarks/{card_id}` | 17896 패턴 미러 |
| DELETE | `/api/bookmarks/{card_id}` | 동일 |
| GET | `/api/bookmarks` | 동일 |
| GET | `/api/settings` | 17896 패턴 미러 |
| PUT | `/api/settings` | 동일 |
| POST | `/api/library/sync` | `build_cards.py` 트리거 (dry-run 옵션 `?dry_run=1`) |
| GET | `/api/library/diff` | 라이브러리 .md ↔ DB 차이 미리보기 (없는 신규 / 변경 / 보관 후보) |

**에러 코드** (17896 미러):
- 400 `bad_request` / 404 `card_not_found`, `bookmark_not_found` / 409 `library_busy` (sync 중복) / 500 `internal_error`

### 4.7 UI (index.html — 단일 파일 SPA)

#### 4.7.1 레이아웃
```
┌─ topbar ────────────────────────────────────────────────┐
│ Lawear Cards   Review | Browse | Stats | Settings   👀Z │
├─ sidebar ───────────────┬─ content ───────────────────  │
│ [모드 셀렉터]            │                              │
│  ○ SRS    ● Weak        │   ┌─ Front ──────────────┐    │
│  ○ Old    ○ Random      │   │ 이행지체 성립 요건    │    │
│ [과목 필터]              │   │ (front)              │    │
│  ● 전체  ○ 민법  ○ 민소  │   │                      │    │
│ ☐ 즐겨찾기만             │   └──────────────────────┘    │
│                          │   [Space] 답 보기            │
│ [통계 위젯]              │                               │
│  오늘 23 / 20 (115%)     │   ┌─ Back ───────────────┐    │
│  연속 7일                 │   │ 두문자: 무·도·가·귀·법│   │
│                          │   │ 풀이형: 채무 이행기...│   │
│                          │   │ 본문: [blue]...      │    │
│                          │   └──────────────────────┘    │
│                          │   [1] Again [2] Hard [3] Good [4] Easy │
└──────────────────────────┴───────────────────────────────┘
```

#### 4.7.2 카드 학습 흐름
1. 페이지 진입 → `GET /api/cards/next?mode=...` → front 표시 + 타이머 시작
2. Space → back 노출 (4 버튼 활성)
3. 사용자 1~4 키 → `POST /api/cards/{id}/review` → 다음 카드 fetch (자동 재호출)
4. 모든 카드 due 처리 → "오늘 끝! +N 카드 정답률 X%" 안내 (17896 patterns)

#### 4.7.3 단축키 (17896 미러)
| 키 | 동작 |
|----|------|
| `Space` | back 노출 (이미 노출 시 무시) |
| `1` | Again |
| `2` | Hard |
| `3` | Good |
| `4` | Easy |
| `S` | Skip (review 기록 X, 다음 카드) |
| `B` | 사이드바 토글 |
| `Z` | 위장 모드 토글 (영문 + 사이드바 닫기) |
| `?` | 단축키 도움말 |
| `↑/↓` | (Browse 모드) 카드 리스트 이동 |

**가드**: `e.target.tagName === 'TEXTAREA' || 'INPUT'` → return (17896 L3702)

#### 4.7.4 Stats 3-tab (17896 Reports 미러)
- Daily: 30일 막대 (review count + accuracy %)
- Weak Top10: 약점 카드 10개 (card_id 클릭 → 카드 상세)
- Progress: 과목 + 카테고리별 진척률 (`/api/stats/progress`)

#### 4.7.5 위장 모드 (17896 L3377-3398 미러)
- Z 단축키 → 영문 i18n + 사이드바 닫기 + 통계 카드 닫기
- 위장 시 표시 텍스트 예: `Internal Memory Console` / `Forward 2 of 76 cards`

### 4.8 라이브러리 sync 워크플로우

```
[기존 워크플로우]
사용자 → /dev-lawear-shortcut-lib-update 호출
       → 두문자/{민법,민소}.md 갱신
       → 영향 .md 추출 + Lv.4 자동화 (기존 흐름)

[17897 추가]
       → POST http://127.0.0.1:17897/api/library/sync (dry-run)
       → 차이 리포트 (신규 N / 변경 N / 보관 후보 N)
       → 사용자 OK
       → POST /api/library/sync (실행)
       → cards.db UPSERT
       → 게시판 알림 (lawear-work)
```

**자동화 옵션**: `/dev-lawear-shortcut-lib-update` 스킬에 17897 sync 단계 추가 (사용자 OK 시).

---

## 5. 위험 / 이슈 / 백업

### 5.1 위험
| ID | 위험 | 완화 |
|----|------|------|
| R-1 | SRS 알고리즘 사용자 학습 패턴 불일치 | settings.srs_params 핫 튜닝 (코드 변경 X) — 1~2주 후 데이터 기반 조정 |
| R-2 | 카드 자동 추출 누락 (라이브러리 .md 파싱 오류) | `build_cards.py --strict` — 모든 ### → forward 카드 1개 assert / dry-run 차이 리포트 / TC 5건 (§4.3.3) |
| R-3 | DB 스키마 변경 시 마이그 손실 | migrations/{NNN_*}.sql + user_version (17896 패턴) + 매 마이그 직전 `cards.db.bak.{ts}` |
| R-4 | 사용자 학습 데이터 손실 (`reviews` row 누적 가치 큼) | (1) WAL + 매일 일배치 backup → `~/.lawear_backups/cards_{date}.db` (2) 워크트리 remove 전 DB 백업 (메모리 `feedback_worktree_db_backup.md`) (3) git LFS X — 학습 데이터는 git 추적 X (`.gitignore` 명시) |
| R-5 | 17895 라이브러리 ↔ 17897 카드 동기화 타이밍 (사용자가 라이브러리만 수정하고 sync 잊음) | (1) GET /api/library/diff 진입 페이지 상단 빨간 배지 (2) sync 트리거 스킬 통합 (§4.8) |
| R-6 | 다중 두문자 alt 인덱스 빈칸 카드 폭증 (민법 일부 항목 alt 3개 → blank 카드 9개) | settings 토글 `blank_alt_max` (기본 1 — 첫 두문자만) |
| R-7 | 사용자가 모든 카드 due 끝낸 후 SRS 모드 빈 화면 | fallback 메시지 "+ 신규 카드 N개 / 즐겨찾기 복습 / 약점 Top10" 3 액션 노출 |
| R-8 | 카드 자동 추출 시 `[red]`/`[blank2]`/`[u]`/`[bold]` 인라인 태그 깨짐 | 1차 안: back 에 .md 원문 그대로 저장 → 클라이언트 렌더링 시 인라인 태그 → HTML 변환 (간단 정규식) / 2차 안: marked.parse 사전 처리기 |

### 5.2 백업 정책 (R-4 상세)
- **일배치 백업** (launchd `com.lawear.cards.backup.plist` 매일 03:00):
  - `cp cards.db ~/.lawear_backups/cards_{YYYYMMDD}.db`
  - 30일 보관 (`find ~/.lawear_backups -name 'cards_*.db' -mtime +30 -delete`)
- **수동 백업 API**: `POST /api/admin/backup` → 즉시 백업 + 경로 반환
- **export/import**: `GET /api/admin/export` (JSON) — 다른 머신 (예: 우분투) 로 이전 시
- **gitignore**: `docs/tts-cards/cards.db*` 명시

---

## 6. 구현 단계 (6 phase)

| Phase | 산출물 | 의존 | 추정 |
|-------|--------|------|------|
| P1 | DB 스키마 + `build_cards.py` (dry-run + strict + TC 5건) | - | 4h |
| P2 | server.py (포트 17897, REST 14 endpoint) + env_loader + db_mod 미러 | P1 | 6h |
| P3 | index.html (카드 학습 + 단축키 + 위장 모드) | P2 | 6h |
| P4 | Stats 3-tab (Daily / Weak / Progress) | P2 | 3h |
| P5 | launchd plist + 일배치 백업 + .gitignore | P2 | 1h |
| P6 | `/dev-lawear-shortcut-lib-update` 스킬에 17897 sync 추가 | P1-5 | 2h |

**총 추정**: ~22h (분산 가능, P1+P2 우선 — 카드만 들어와도 curl 로 학습 가능)

**의존 검증 절차**:
- P1 dry-run 실행 → 사용자 OK 후 P2 진행
- P3 카드 학습 흐름 사용자 1회 시연 → OK 후 P4
- P5 launchd 등록 전 포트 8585 게시판 등록 (§7)

---

## 7. 포트 등록 (필수)

CLAUDE.md 글로벌 규칙 — 신규 서비스 포트 시 공지게시판 등록:

```
create_post(
  board_slug="notice",
  prefix="[포트]",
  title="lawear - 17897 Anki 카드 서버",
  content="포트 17897 — Lawear 두문자/요건 라이브러리 Anki 스타일 카드 시스템 (SRS + 자가 평가). 로컬 127.0.0.1 만 바인드. launchd com.lawear.cards.",
  author="lawear-{세션ID}"
)
```

**기존 등록 확인**: 17895 (TTS 머지), 17896 (Exam Console) → 17897 충돌 없음 (검증 후 등록).

---

## 8. 사용자 검수 권장 항목

다음 5개 항목 OK 여부 확인 후 구현 디스패치:

1. **포트 17897 신설** (17895 통합 X) — OK ?
2. **DB 스키마** (§4.2) — `card_stats` 분리 / `archived=1` 보존 정책 — OK ?
3. **카드 타입 3종** (forward / blank / reverse) — reverse 기본 OFF — OK ?
4. **SRS 수식** (§4.4) — Anki 기본값 기반 — OK ? (튜닝은 후속)
5. **라이브러리 sync 채널** (§4.8) — `/dev-lawear-shortcut-lib-update` 스킬 통합 — OK ?

---

## 9. 다음 단계

사용자 OK 후:
1. 워크트리 생성 (`wt/lawear-1727/cards-srs` 또는 사용자 명시 명칭)
2. P1 (DB + build_cards.py) 디스패치 → dry-run 결과 사용자 검수
3. P2 (server.py) 디스패치
4. P3 (UI) 디스패치 (P1 완료 후 carded.db 실데이터로 UI 검증)
5. P5 (launchd + 백업) — 첫 sync 전에 반드시
6. P6 (스킬 통합) — 마지막

---

## 10. 메모 — 추가 발견 사항

### 10.1 사용자 두문자.md 매핑 (민법 1-6 예)
- 라이브러리 민법 1-6 (`채권자대위권 요건`) 은 두문자 1개가 아니라 **4단계 표** (계·승·국·사 → 지·패 → 패·총 → 청·취·통·개·류) 로 분기
- → 단순 forward + blank 패턴 부적합
- → forward 1개 + (4단계 표를 풀이형으로 통째 back) — blank 자동 추출 SKIP (사용자가 추후 수동 분할 검토)
- → `build_cards.py` 에 "표 감지 → blank skip" 휴리스틱 추가 (`| 단계 |` 마크다운 표 시작 시)

### 10.2 부등법 / 형법 / 형소 라이브러리 (현재 미존재)
- 현재 `docs/tts-new/두문자/` 에 민법.md + 민소.md 만 존재 (확인 완료)
- 신규 과목 추가 시 `build_cards.py` 는 자동 인식 (`os.listdir('docs/tts-new/두문자')`)
- subject 매핑은 파일명 기반 (`민법.md` → subject='civil') — 신규 시 매핑 dict 추가 필요

### 10.3 사용자 위키 위치 (탐색 결과)
- lawear 메모리 `feedback_no_dooray_registration.md`: lawear 두레이 등록 금지 (개인 자료)
- → 결론: **로컬 `docs/wiki/`** = 사용자 개인 위키 위치 (본 문서)
- 사용자가 다른 위치 (예: 두레이 개인 위키, Notion, Obsidian) 원하면 알려달라고 안내
