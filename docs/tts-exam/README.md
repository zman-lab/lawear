# Lawear Exam Console (17896)

법무사 2차 시험 답안 작성 + Claude API 서버 사이드 채점 + SQLite 저장.

## 개요

- 포트: `17896` (127.0.0.1 바인드)
- 진입: `http://127.0.0.1:17896/`
- 사양: dev-design archive [#48](http://127.0.0.1:8585/post/48), dev-impl-plan archive [#51](http://127.0.0.1:8585/post/51)
- 17895 (`docs/tts-new`) 변경 0건 — 동기화 시점만 17895 fetch

## 디렉토리 구조

```
docs/tts-exam/
├── server.py              — ThreadingHTTPServer + 라우터 (Step 1)
├── db.py                  — SQLite 5 테이블 + 마이그레이션 v1 (Step 2)
├── syncer.py              — 17895 ↔ 17896 동기화 (Step 3)
├── cases.py               — 케이스 메타/.md 파싱 (Step 4)
├── grader.py              — Anthropic Claude API 7기준 채점 + mock (Step 6)
├── env_loader.py          — .env 파서 (Step 6)
├── index.html             — UI (시안 이식 Step 5)
├── requirements.txt       — anthropic SDK
├── .env.example           — env 키 안내 (.env 는 gitignore)
├── tests/
│   └── test_grader.py     — Grader 단위 테스트 (mock, 18 TC)
├── launchd/
│   └── com.lawear.examconsole.plist
├── migrations/
│   └── 001_initial.sql
├── exam.db                — SQLite (gitignore, 런타임 생성)
└── README.md
```

## 실행

### 로컬 (개발)

```bash
cd /Users/nhn/zman-lab/lawear/docs/tts-exam
python3 server.py
# → http://127.0.0.1:17896
```

### launchd (자동 실행)

```bash
# 설치 (사용자 직접)
cp launchd/com.lawear.examconsole.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lawear.examconsole.plist

# 로그
tail -f /tmp/lawear_examconsole.log
tail -f /tmp/lawear_examconsole.err

# 언로드
launchctl unload ~/Library/LaunchAgents/com.lawear.examconsole.plist
```

## 환경 변수

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `LAWEAR_EXAM_PORT` | `17896` | 서버 포트 |
| `LAWEAR_EXAM_BIND` | `127.0.0.1` | 바인드 주소 |
| `LAWEAR_EXAM_DB` | `exam.db` | SQLite 경로 |
| `LAWEAR_TTS_BASE` | `/Users/nhn/zman-lab/lawear/docs/tts-new` | 케이스 .md 베이스 |
| `LAWEAR_REMOTE_BASE` | `http://127.0.0.1:17895` | 17895 fetch URL |
| `ANTHROPIC_API_KEY` | (필수, Step 6~) | Claude 채점 호출. 미설정 시 grader 자동 mock 모드 |
| `LAWEAR_GRADER_MODEL` | `claude-opus-4-7` | Grader 모델 (advanced 오버라이드) |
| `LAWEAR_GRADER_MOCK` | `0` | `1` 강제 mock (테스트용) |

### .env 사용 (권장)

```bash
cp .env.example .env
# .env 에서 ANTHROPIC_API_KEY=sk-ant-... 채움
```

서버 시작 시 `env_loader.load_env()` 가 `docs/tts-exam/.env` 를 자동 로드합니다.
시스템 env 가 우선 (`.env` 가 덮어쓰지 않음).

## 헬스 체크

```bash
curl -sf http://127.0.0.1:17896/api/health
# → {"status":"ok","server":"lawear-examconsole","version":"0.1.0-bootstrap","phase":"bootstrap"}
```

## DB 초기화 (Step 2)

```bash
python3 -c "from db import init_db; init_db('exam.db')"
sqlite3 exam.db ".schema"
```

## Step 진척

| Step | 내용 | 상태 |
|------|------|------|
| 1 | 부트스트랩 (server.py + launchd + requirements) | OK |
| 2 | DB 초기화 (5 테이블 v1) | OK |
| 3 | 17895 동기화 (`/api/sync` + content_hash diff) | OK |
| 4 | 케이스 API (`/api/cases`, `/api/cases/{id}`) | OK |
| 5 | UI 시안 이식 (`index.html` 1787줄) | OK |
| 6 | Grader (Anthropic API + 7기준 + mock + env) | OK (본 커밋) |
| 7 | Attempts API (`POST /api/attempts` + background grader + 폴링) | 후속 |
| 8 | Settings API | 후속 |
| 9 | Bookmarks API | 후속 |
| 10 | Reports 집계 | 후속 |
| 11 | STT (Web Speech API) | 후속 |
| 12 | i18n + 단축키 폴리시 | 후속 |

## Grader 사용법 (Step 6)

### mock 단위 테스트 (API 키 불필요)

```bash
cd /Users/nhn/zman-lab/lawear/docs/tts-exam
python3 tests/test_grader.py
# → 18/18 passed
```

### 실 API 호출 (사용자 키 주입 후)

```bash
# 1. .env 에 ANTHROPIC_API_KEY 채우기
cp .env.example .env
# (편집 — sk-ant-... 입력)

# 2. CLI 로 단건 채점
python3 grader.py --case 2026_minbeop_immun_mike01_01 --answer "내 답안 텍스트"

# 3. mock 강제 (실 호출 차단)
python3 grader.py --case 2026_minbeop_immun_mike01_01 --mock
```

### Step 7 (Attempts API) 도입 후

`POST /api/attempts` 가 background thread 로 `grader.grade()` 를 호출하고
결과를 `attempts` + `attempt_criteria` 테이블에 저장합니다 (다음 커밋).
