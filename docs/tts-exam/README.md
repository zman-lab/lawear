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
├── index.html             — UI (Step 1 placeholder → Step 5 시안 이식)
├── requirements.txt       — anthropic SDK
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
| `ANTHROPIC_API_KEY` | (필수, Step 6~) | Claude 채점 호출. `~/.zshrc.tokens.local` 또는 `~/.config/lawear/.env`에 보관 |

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
| 1 | 부트스트랩 (server.py + launchd + requirements) | ✅ 본 단계 |
| 2 | DB 초기화 (5 테이블 v1) | ✅ 본 단계 |
| 3 | 17895 동기화 (`/api/sync` + content_hash diff) | 후속 |
| 4 | 케이스 API (`/api/cases`, `/api/cases/{id}`) | 후속 |
| 5 | UI 본체 이식 (`docs/tts-new/exam_mockup.html`) | 후속 |
| 6 | Claude 채점 (`/api/attempts`, grader.py) | 후속 |
| 7~12 | 북마크/설정/리포트/STT/QA/마무리 | 후속 |
