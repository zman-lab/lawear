# Lawear Exam Console (17896)

법무사 2차 시험 답안 작성 + Claude API 서버 사이드 채점 + SQLite 저장 + 리포트.

- 포트: `17896` (127.0.0.1 바인드)
- 진입: `http://127.0.0.1:17896/`
- 사양:
  - dev-impact archive [#45](http://10.77.11.110:8585/post/45)
  - dev-design archive [#48](http://10.77.11.110:8585/post/48)
  - dev-impl-plan archive [#51](http://10.77.11.110:8585/post/51)
- **17895 (`docs/tts-new`) 변경 0건** — Sync 시점만 17895 fetch (오프라인 OK)

## 1. 17895 와의 관계

| 항목 | 17895 (tts-new viewer) | 17896 (exam-console) |
|------|------------------------|----------------------|
| 포트 | 17895 | 17896 |
| 역할 | 케이스 `.md` 정적 서빙 + PUT 저장 | 채점 + DB + UI + 외부 API |
| 부팅 시 의존 | — | **없음** (17895 OFF여도 17896 부팅 정상) |
| 데이터 흐름 | `_file_index.json` + `.md` 본문 → | content_hash diff → SQLite `cases` 테이블 UPSERT |
| 시점 | 항상 | 사용자가 Settings → Resync 누를 때만 |
| 코드 변경 | **0건** (CORS 이미 OK) | 신규 9 모듈 + index.html (1787 → ~3200줄) |

## 2. 디렉토리 구조

```
docs/tts-exam/
├── server.py              — ThreadingHTTPServer + 라우터 (Step 1~11)
├── db.py                  — SQLite 5 테이블 + 마이그레이션 v1/v2 (Step 2, 7)
├── env_loader.py          — .env 자동 로더 (Step 6)
├── syncer.py              — 17895 ↔ 17896 동기화 (Step 3)
├── cases.py               — 케이스 메타/.md 파싱 (Step 4)
├── grader.py              — Anthropic Claude API 7기준 채점 + mock (Step 6)
├── attempts.py            — 답안 제출 + background 채점 (Step 7)
├── settings.py            — Settings (weights/bias/voice) (Step 8)
├── bookmarks.py           — 즐겨찾기 토글 (Step 9)
├── reports.py             — Overall/By Subject/By Case 집계 (Step 10)
├── index.html             — 시안 UI 이식 + Step 5~11 wire
├── requirements.txt       — anthropic SDK
├── .env.example           — env 키 안내 (.env 는 gitignore)
├── .gitignore             — exam.db / __pycache__ / .env
├── migrations/
│   ├── 001_initial.sql    — v1 (cases / attempts / attempt_criteria / bookmarks / settings)
│   └── 002_attempts_extras.sql  — v2 (attempts 추가 컬럼)
├── launchd/
│   └── com.lawear.examconsole.plist
├── tests/
│   ├── __init__.py
│   ├── test_grader.py     — Grader 단위 (mock) 13 TC
│   └── test_reports.py    — Reports 집계 25 TC
├── exam.db                — SQLite (gitignore, 런타임 생성)
└── README.md
```

## 3. 실행

### 3-1. 로컬 (개발)

```bash
cd /Users/nhn/zman-lab/lawear/docs/tts-exam
python3 server.py
# → http://127.0.0.1:17896
```

### 3-2. launchd (자동 실행)

```bash
# 설치 (사용자 직접)
cp launchd/com.lawear.examconsole.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.lawear.examconsole.plist

# 상태 확인
launchctl list | grep examconsole

# 로그
tail -f /tmp/lawear_examconsole.log
tail -f /tmp/lawear_examconsole.err

# 언로드
launchctl unload -w ~/Library/LaunchAgents/com.lawear.examconsole.plist
```

**plist 환경변수**: `LAWEAR_EXAM_PORT=17896`, `LAWEAR_EXAM_BIND=127.0.0.1`. `ANTHROPIC_API_KEY` 는 `.env` 파일 (워킹디렉토리 `docs/tts-exam/.env`) 로 주입.

### 3-3. 첫 사용

1. 서버 실행 → `http://127.0.0.1:17896/` 접속 → 케이스 0건 (DB 비어있음)
2. Settings 탭 → "Preview Diff" → 17895 fetch (오프라인이면 빨간 메시지)
3. "⟳ Resync from 17895" 클릭 → cases 테이블 UPSERT
4. 사이드바에 케이스 목록 표시 → 케이스 선택 → 답안 작성 → "Submit for Evaluation"
5. Evaluation 탭에 채점 결과 (mock 모드는 1초 내, 실 API 는 10~30초)

## 4. 환경 변수

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `LAWEAR_EXAM_PORT` | `17896` | 서버 포트 |
| `LAWEAR_EXAM_BIND` | `127.0.0.1` | 바인드 주소 |
| `LAWEAR_EXAM_DB` | `exam.db` (워킹디렉토리) | SQLite 파일 경로 |
| `LAWEAR_TTS_BASE` | `/Users/nhn/zman-lab/lawear/docs/tts-new` | 케이스 `.md` 베이스 |
| `LAWEAR_REMOTE_BASE` | `http://127.0.0.1:17895` | 17895 fetch URL |
| `LAWEAR_REMOTE_TIMEOUT` | `10` | 17895 HTTP 타임아웃 (초) |
| `ANTHROPIC_API_KEY` | (필수, Step 6~) | Claude 채점 호출. 미설정 시 grader 자동 mock |
| `LAWEAR_GRADER_MODEL` | `claude-opus-4-7` | Grader 모델 (advanced 오버라이드) |
| `LAWEAR_GRADER_MOCK` | `0` | `1` 강제 mock (테스트용) |

### 4-1. `.env` 사용 (권장)

```bash
cp .env.example .env
# .env 에서 ANTHROPIC_API_KEY=sk-ant-... 채움
```

서버 시작 시 `env_loader.load_env()` 가 `docs/tts-exam/.env` 를 자동 로드합니다.
시스템 env 가 우선 (`.env` 가 덮어쓰지 않음). `.env` 는 gitignore 처리 — git 추적 X.

## 5. 키보드 단축키

| 키 | 동작 | 비고 |
|----|------|------|
| `Z` | 위장(Stealth) 토글 — 사이드바·라벨·섹션 일괄 위장 | textarea/input 포커스 시 무시 |
| `B` | 사이드바 토글 (열기/닫기) | textarea 포커스 시 무시 |
| `1` | Review 탭 | textarea 포커스 시 무시 |
| `2` | Evaluation 탭 | textarea 포커스 시 무시 |
| `3` | Reports 탭 | textarea 포커스 시 무시 |
| `4` | Settings 탭 | textarea 포커스 시 무시 |

수정자 키(Ctrl/Cmd/Alt) 와 함께 누르면 무시 (시안 단축키 1596~1610).

## 6. 음성 입력 (Web Speech API · Step 11)

- 브라우저 STT 사용 — 서버 사이드 STT 없음 (`/api/stt` 는 501 `stt_not_implemented`).
- 지원: Chrome / Edge (데스크탑·모바일).
- 부분 지원: Safari 일부 버전.
- 미지원: Firefox (마이크 버튼 자동 비활성 + 툴팁 안내).
- 마이크 권한: 첫 사용 시 브라우저가 자동 요청. 거부 시 토스트 안내.
- 무음 자동 정지: Settings → Voice Input → `Auto-stop (silence sec)` 슬라이더 (기본 3초).
- 언어: Settings → Voice Input → `Language` (`ko-KR` / `en-US`).
- 인식 결과:
  - **interim** (실시간 중간 결과): textarea 아래 회색 영역 미리보기.
  - **final** (확정 결과): textarea 끝에 자동 append + 자동저장 트리거.
- HTTPS 불필요: `127.0.0.1` 은 secure context 로 인정되어 HTTP OK.

## 7. API 엔드포인트

| 메서드 | 경로 | 용도 | Step |
|--------|------|------|------|
| GET | `/` | 정적 `index.html` 서빙 | 1, 5 |
| GET | `/api/health` | 헬스 체크 (version/phase) | 1 |
| GET | `/api/cases?filter=…&subject=…&category=…&file=…&search=…` | 케이스 목록 | 4 |
| GET | `/api/cases/{id}` | 케이스 단건 (메타 + .md 본문) | 4 |
| POST | `/api/attempts` | 답안 제출 (즉시 응답 + background 채점) | 7 |
| GET | `/api/attempts/{id}` | 채점 결과 폴링 | 7 |
| GET | `/api/attempts?case_id=…&subject=…&from=…&to=…&limit=…&offset=…` | 시도 히스토리 | 7 |
| GET | `/api/sync/preview` | 17895 fetch + diff (DB 변경 X) | 3 |
| POST | `/api/sync` | UPSERT cases + UPDATE attempts.is_stale | 3 |
| POST | `/api/bookmarks/{case_id}` | 즐겨찾기 추가 | 9 |
| DELETE | `/api/bookmarks/{case_id}` | 즐겨찾기 제거 | 9 |
| GET | `/api/bookmarks` | 즐겨찾기 목록 (옵션) | 9 |
| GET | `/api/settings` | weights/bias/voice 조회 | 8 |
| PUT | `/api/settings` | weights/bias/voice 저장 (sum=100 검증) | 8 |
| GET | `/api/reports/overall` | Overall KPI + Trend + Recent | 10 |
| GET | `/api/reports/by-subject?subject=…` | 과목별 KPI + 케이스 테이블 | 10 |
| GET | `/api/reports/by-case?case_id=…` | 케이스별 시도 히스토리 + 기준 평균 | 10 |
| GET | `/api/reports/subjects` | 과목 필터 탭용 picker | 10 |
| GET | `/api/reports/cases?subject=…` | By Case 셀렉터용 picker | 10 |
| POST | `/api/stt` | (501) STT placeholder — Web Speech API 사용 권장 | 11 |

상세 메시지 정의 + ErrorCode 는 dev-design [#48](http://10.77.11.110:8585/post/48) §3-1~§3-3 참조.

### 7-1. 헬스 체크 샘플

```bash
curl -sf http://127.0.0.1:17896/api/health
# → {"status":"ok","server":"lawear-examconsole","version":"0.8.0-stt-placeholder","phase":"stt-placeholder"}
```

### 7-2. ErrorCode 요약

| HTTP | error_code | 설명 |
|------|------------|------|
| 400 | `bad_request` | 입력 검증 실패 |
| 404 | `case_not_found` / `attempt_not_found` / `bookmark_not_found` | 리소스 없음 |
| 405 | `method_not_allowed` | HTTP 메서드 미허용 |
| 409 | `weights_invalid` | 가중치 합계 ≠ 100 |
| 429 | `anthropic_rate_limit` | Claude 429 (grader 1초 백오프 3회) |
| 500 | `internal_error` | 기타 |
| 501 | `stt_not_implemented` / `not_implemented` | 미구현 endpoint |
| 502 | `remote_unreachable` / `anthropic_bad_gateway` | 외부 호출 실패 |
| 503 | `api_key_missing` | `ANTHROPIC_API_KEY` 미설정 (grader 의 강제 mock 모드면 200) |

## 8. DB 스키마 + 마이그레이션

5 테이블 — `cases` / `attempts` / `attempt_criteria` / `bookmarks` / `settings`.

- `migrations/001_initial.sql` — v1 (5 테이블 + 6 인덱스 + 초기 settings 3 row)
- `migrations/002_attempts_extras.sql` — v2 (attempts 추가 컬럼: model / weights_json / eval_notes_json / diff_json / raw_response / error_code / is_stale)

서버 시작 시 `db.init_db()` 가 `user_version` 을 확인하고 누락 마이그를 멱등 적용.

### 8-1. DB 초기화/조회

```bash
# 초기화 (수동 — 통상 서버가 자동)
python3 -c "from db import init_db; init_db('exam.db')"

# 스키마 보기
sqlite3 exam.db ".schema"

# user_version 보기 (현재 2)
sqlite3 exam.db "PRAGMA user_version"

# settings 디폴트 확인
sqlite3 exam.db "SELECT key, value_json FROM settings"
```

### 8-2. 잔존 'grading' row 마킹 (Q24)

서버가 채점 background thread 실행 중 죽거나 SIGKILL 되면 `attempts.status='grading'` 행이 남는다. 다음 부팅 시 `attempts.mark_orphan_grading()` 이 모두 `status='error', error_code='server_restart'` 로 마킹.

## 9. 시험/테스트

### 9-1. 단위 테스트 (mock 모드, API 키 불필요)

```bash
cd /Users/nhn/zman-lab/lawear
python3 -m pytest docs/tts-exam/tests/ -v
# → 38 passed
```

### 9-2. 실 API 호출 (사용자 키 주입 후)

```bash
# 1. .env 에 ANTHROPIC_API_KEY 채우기
cp docs/tts-exam/.env.example docs/tts-exam/.env
# (편집 — sk-ant-... 입력)

# 2. CLI 단건 채점
cd docs/tts-exam
python3 grader.py --case 2026_minbeop_immun_mike01_01 --answer "내 답안 텍스트"
```

## 10. 트러블슈팅

### 10-1. 17895 viewer 오프라인 (Sync 실패)

증상: Settings → "Preview Diff" 시 빨간 메시지.

원인: 17895 (`com.lawear.ttsmerger`) 가 실행 중이지 않음.

조치:
```bash
launchctl list | grep ttsmerger
launchctl load -w ~/Library/LaunchAgents/com.lawear.ttsmerger.plist
# 또는
cd /Users/nhn/zman-lab/lawear/docs/tts-new && python3 server.py &
```

### 10-2. `ANTHROPIC_API_KEY` 미설정

증상: `POST /api/attempts` 가 즉시 401/503 또는 `grader.py` 가 mock 응답 반환.

조치: `docs/tts-exam/.env` 에 `ANTHROPIC_API_KEY=sk-ant-…` 추가. 서버 재시작.

서버 OFF 없이 mock 강제 테스트: `LAWEAR_GRADER_MOCK=1 python3 server.py`.

### 10-3. 포트 17896 충돌

```bash
lsof -nP -iTCP:17896 -sTCP:LISTEN
# 충돌 PID 발견 시
launchctl unload ~/Library/LaunchAgents/com.lawear.examconsole.plist
# 또는 LAWEAR_EXAM_PORT 로 다른 포트 사용
LAWEAR_EXAM_PORT=17996 python3 server.py
```

### 10-4. DB 마이그 v1→v2 (기존 DB 보유)

증상: v1 으로 만든 `exam.db` 에 v2 컬럼 없어 attempt 저장 실패.

조치: 서버 재시작만으로 자동 마이그 (멱등). 강제 재구성은 `rm exam.db` 후 서버 재시작.

### 10-5. 마이크 권한 거부 / 음성 인식 안 됨

- Chrome: `chrome://settings/content/microphone` 에서 `http://127.0.0.1:17896` 허용.
- Edge: `edge://settings/content/microphone` 동일.
- Safari: Safari → 설정 → 웹사이트 → 마이크.
- Firefox: 마이크 버튼 자동 비활성 (Web Speech API 미지원). 다른 브라우저 사용.

### 10-6. ThreadingHTTPServer + SQLite BUSY

증상: 동시 채점 + Resync 시 `database is locked`.

조치: 자동 처리됨 (`PRAGMA busy_timeout=5000`). 5초 이상 lock 지속 시 dev-impl-plan #51 §5-3 참조.

## 11. 브라우저 호환성

| 브라우저 | 본체 (Z/1~4/B/Fetch/SVG) | Web Speech API (마이크) |
|---------|--------------------------|------------------------|
| Chrome (데스크탑) | OK | OK |
| Edge (데스크탑) | OK | OK |
| Chrome (Android) | OK | OK |
| Safari (macOS) | OK | 부분 (Safari 14.1+) |
| Safari (iOS) | OK | 부분 (iOS 14.5+) |
| Firefox (전 버전) | OK | 미지원 (마이크 비활성) |

권장: **Chrome 또는 Edge** (마이크 STT 안정성 최상).

## 12. Step 진척

| Step | 내용 | 상태 | 커밋 |
|------|------|------|------|
| 1 | 부트스트랩 (server.py + launchd + requirements) | OK | `d08b0cd` |
| 2 | DB 초기화 (5 테이블 v1) | OK | `3c6e73e` |
| 3 | 17895 동기화 (`/api/sync` + content_hash diff) | OK | `1ddb8a7` |
| 4 | 케이스 API (`/api/cases`, `/api/cases/{id}`) | OK | `d3fed1b` |
| 5 | UI 시안 이식 + 케이스/동기화 API wire | OK | `f4155f3` |
| 6 | Grader (Anthropic API + 7기준 + mock + env) | OK | `e2af4e6` |
| 7 | Attempts API + DB v2 마이그 + Evaluation wire | OK | `71060b4` / `013264e` / `0207a5c` |
| 8 | Settings API (weights/bias/voice + sum=100 검증) | OK | `e38294e` |
| 9 | Bookmarks API + 사이드바 ★ 토글 | OK | `e38294e` |
| 10 | Reports 집계 (overall/by-subject/by-case + 3 sub-tab wire) | OK | `c6acfb4` |
| 11 | STT (Web Speech API 클라이언트 + 서버 placeholder 501) | OK | 본 커밋 |
| 12 | README + i18n 보강 + 폴리시 | OK | 본 커밋 |

## 13. 후속 (Step 12 이후)

- 실 사용자 채점 시나리오 검증 (사용자 OK 대기)
- 토큰 사용량 최적화 (system prompt cache 모니터링)
- Settings → 모델명 advanced UI (Q11)
- 채점 결과 export (CSV/JSON)
- 다국어 추가 (현재 en/ko)
