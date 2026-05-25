# dev-le-17896-restart — 17896 시험·채점 서버 재시작 스킬

> 17896 (`docs/tts-exam/`, examconsole) launchd 기반 재시작 전용.
> 17895 (TTS 뷰어, 별개 프로세스)는 손대지 않음.
> 메모리 룰 [feedback_skill_naming_dev_le_prefix.md] 부합 — dev-le-17896- prefix.

---

## 경로 상수

```
PROJECT=/Users/nhn/zman-lab/lawear
EXAM_DIR=$PROJECT/docs/tts-exam
EXAM_PORT=17896
PLIST_NAME=com.lawear.examconsole.plist
PLIST_PATH=$HOME/Library/LaunchAgents/$PLIST_NAME
PLIST_TEMPLATE=$EXAM_DIR/launchd/$PLIST_NAME
LOG_DIR=$PROJECT/logs
EXAM_DB=$EXAM_DIR/exam.db
```

---

## 실행 순서 (1→6 순서대로, 스킵 금지)

### 1. 현재 상태 확인

```bash
echo "=== 현재 17896 프로세스 ==="
lsof -i :17896 2>/dev/null | head -3 || echo "(미실행)"

echo "=== launchctl 등록 상태 ==="
launchctl list 2>/dev/null | grep -i lawear || echo "(launchctl에 등록 X — Step 2에서 plist 적재)"

echo "=== plist 활성 위치 ==="
ls -la "$HOME/Library/LaunchAgents/com.lawear.examconsole.plist" 2>&1 || echo "(plist 활성화 X — Step 2에서 복사)"

echo "=== 현재 DB user_version ==="
sqlite3 /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db "PRAGMA user_version;" 2>&1
```

### 2. plist 활성화 + 0.0.0.0 바인딩 강제

```bash
PLIST_PATH="$HOME/Library/LaunchAgents/com.lawear.examconsole.plist"
PLIST_TEMPLATE=/Users/nhn/zman-lab/lawear/docs/tts-exam/launchd/com.lawear.examconsole.plist

if [ ! -f "$PLIST_PATH" ]; then
  echo "plist 활성 위치에 없음 — 템플릿에서 복사"
  cp "$PLIST_TEMPLATE" "$PLIST_PATH"
fi

# 0.0.0.0 바인딩 강제 (사용자 정책 2026-05-25 — 모바일/LAN 접근 보장)
# LAWEAR_EXAM_BIND 컨텍스트 한정 교체 (다른 127.0.0.1 오염 방지)
for P in "$PLIST_PATH" "$PLIST_TEMPLATE"; do
  [ -f "$P" ] || continue
  if perl -0ne 'exit 0 if /<key>LAWEAR_EXAM_BIND<\/key>\s*<string>127\.0\.0\.1<\/string>/s; exit 1' "$P"; then
    echo "⚠️ $P — LAWEAR_EXAM_BIND가 127.0.0.1 — 0.0.0.0으로 자동 교체"
    perl -i -0pe 's|(<key>LAWEAR_EXAM_BIND</key>\s*<string>)127\.0\.0\.1(</string>)|${1}0.0.0.0${2}|s' "$P"
  fi
done

ls -la "$PLIST_PATH"
grep -A1 "LAWEAR_EXAM_BIND" "$PLIST_PATH"
```

### 3. DB 백업 (재시작 전 안전망)

메모리 룰 [feedback_worktree_db_backup] — DB 변경 가능성 있는 작업 전 백업.

```bash
ts=$(date +%Y%m%d_%H%M%S)
cp /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db /tmp/exam_backup_restart_${ts}.db
ls -la /tmp/exam_backup_restart_${ts}.db
```

### 4. launchctl unload + load

```bash
PLIST_PATH="$HOME/Library/LaunchAgents/com.lawear.examconsole.plist"

echo "=== unload ==="
launchctl unload "$PLIST_PATH" 2>&1
sleep 2

echo "=== 포트 해제 확인 ==="
lsof -i :17896 2>/dev/null | head -3 || echo "(포트 해제 OK)"

echo "=== load ==="
launchctl load "$PLIST_PATH" 2>&1
sleep 4
```

### 5. 검증 (재시작 + 0.0.0.0 바인딩 + 마이그레이션 + HTTP)

```bash
echo "=== 새 17896 프로세스 + 바인딩 패턴 ==="
lsof -nP -iTCP:17896 -sTCP:LISTEN 2>/dev/null

echo "=== 바인딩 검증 (★ *:17896 패턴이어야 LAN/모바일 접근 가능) ==="
if lsof -nP -iTCP:17896 -sTCP:LISTEN 2>/dev/null | grep -qE "TCP \*:17896 \(LISTEN\)"; then
  echo "✅ 0.0.0.0 바인딩 확인 — LAN 접근 OK"
else
  echo "❌ loopback only (127.0.0.1) — Step 2 plist LAWEAR_EXAM_BIND 확인 필요"
fi

echo "=== DB user_version (마이그레이션 자동 적용 여부) ==="
sqlite3 /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db "PRAGMA user_version;" 2>&1

echo "=== HTTP localhost (loopback 응답) ==="
curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://localhost:17896/

echo "=== HTTP LAN IP (모바일 접근 시뮬레이션) ==="
LAN_IP=$(ifconfig | grep -E "inet (10\.|192\.|172\.)" | grep -v 127 | head -1 | awk '{print $2}')
if [ -n "$LAN_IP" ]; then
  echo "맥북 LAN IP: $LAN_IP — 갤럭시/모바일 접속 URL: http://${LAN_IP}:17896"
  curl -s -o /dev/null -w "$LAN_IP:17896 → HTTP %{http_code}\n" --max-time 5 "http://${LAN_IP}:17896/"
else
  echo "(LAN IP 미검출 — 유선/WiFi 연결 확인)"
fi

echo "=== 17895 미영향 확인 ==="
lsof -nP -iTCP:17895 -sTCP:LISTEN 2>/dev/null | tail -n+2 || echo "(17895 별개 프로세스 — 정상)"

echo "=== ngrok 현재 상태 + URL (서버 재시작과 무관, 사용자 안내용) ==="
# ngrok URL은 ngrok 프로세스 재시작 시에만 변경 (서버 재시작 시 그대로).
# 매번 사용자에게 알려서 혹시 변경됐을 때 즉시 인지 가능.
NGROK_URL_17896=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "import json,sys;data=json.load(sys.stdin);print(data['tunnels'][0]['public_url'])" 2>/dev/null)
if [ -n "$NGROK_URL_17896" ]; then
  echo "✅ ngrok-1 (17896): $NGROK_URL_17896"
else
  echo "⚠️ ngrok-1 (4040 instance) 미실행 — 모바일 접근 불가. 재시작 필요:"
  echo "  ngrok start --all --log=/tmp/ngrok.log --log-format=json > /tmp/ngrok.out 2>&1 &"
fi
```

### 6. 최신 로그 확인 (오류 점검)

```bash
ls -t /Users/nhn/zman-lab/lawear/logs/*.log 2>/dev/null | head -1 | xargs tail -30 2>/dev/null || echo "(로그 없음)"
```

---

## 보고 형식

```
## 17896 재시작 완료

| 항목 | 값 |
|------|-----|
| 이전 PID | {이전} |
| 새 PID | {신규} |
| 포트 | 17896 |
| 바인딩 | *:17896 (0.0.0.0) ✅ |
| DB user_version | {이전 → 신규, 예 8 → 9} |
| HTTP localhost | {200/303 등} |
| HTTP LAN IP | {200} @ http://{LAN_IP}:17896 |
| **ngrok URL (모바일 접근)** | {NGROK_URL_17896} 또는 (미실행 시 경고) |
| 17895 영향 | 0 (별개 프로세스) |
| DB 백업 | /tmp/exam_backup_restart_{ts}.db |
| 모바일 URL | http://{LAN_IP}:17896 |
```

---

## 트러블슈팅

### plist load 실패 ("Bootstrap failed: 5: Input/output error" 등)
- 이미 load 상태에서 다시 load 시도 → 먼저 unload (Step 4의 unload 실패 시 무시하고 load 시도)
- 또는 SIP 권한 문제 → 사용자에게 비밀번호 요청

### 포트 17896 해제 안 됨
```bash
# 좀비 프로세스 강제 종료 (launchd 자동 재시작 막기 위해 unload 먼저)
launchctl unload ~/Library/LaunchAgents/com.lawear.examconsole.plist 2>&1
lsof -ti :17896 | xargs kill -9 2>/dev/null
sleep 2
launchctl load ~/Library/LaunchAgents/com.lawear.examconsole.plist
```

### 마이그레이션 자동 적용 안 됨 (user_version 그대로)
- server.py 시작 시 db.py가 자동 마이그레이션. 안 되면 server.py 로그에서 에러 확인.
- 수동 적용 (서버 중지 상태에서):
```bash
launchctl unload ~/Library/LaunchAgents/com.lawear.examconsole.plist
sqlite3 /Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db < /Users/nhn/zman-lab/lawear/docs/tts-exam/migrations/009_civil_doc_minsaseoryu.sql
launchctl load ~/Library/LaunchAgents/com.lawear.examconsole.plist
```

### HTTP 응답 timeout/연결 실패
- 서버 startup 시간 부족 → `sleep 8`로 늘려 재검증
- server.py 자체 에러 → 로그 확인 (`tail /Users/nhn/zman-lab/lawear/logs/*.log`)

### LAN IP HTTP 안 됨 (모바일에서 접속 안 됨)
- `lsof`가 `*:17896` 아닌 `127.0.0.1:17896` → plist `LAWEAR_EXAM_BIND` 확인 (`grep -A1 LAWEAR_EXAM_BIND ~/Library/LaunchAgents/com.lawear.examconsole.plist`)
- Step 2의 perl 교체 누락 — 수동 교체 후 unload/load 재시도
- 맥 방화벽 활성 → `/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate` (Disabled 아니면 비활성화 또는 17896 허용)
- 갤럭시가 다른 WiFi (사내망 vs 공유기) → 같은 네트워크 확인

### 17895도 같이 죽었을 때
- 본 스킬은 17895 미손댐 — 별도 프로세스 문제. 17895 재시작은 별도 스킬/명령 (없으면 신설 필요).

---

## 워크트리 모드

워크트리에서 17896 서버를 별도로 띄울 경우 (코드 격리 테스트):
- 포트 충돌 회피 — 워크트리는 다른 포트 (예 17898) 사용 권장
- 본 스킬은 메인 트리 launchd plist 기반 — 워크트리 별도 띄우려면 plist 복사 + 포트 변경 후 별도 등록

---

## 관련 자료

- 17896 코드: `docs/tts-exam/server.py` + `db.py` (TARGET_SCHEMA_VERSION)
- 마이그레이션: `docs/tts-exam/migrations/0NN_*.sql`
- 메모리 [reference_tts_viewer.md] — 17896 URL `http://127.0.0.1:17896`
- 메모리 [feedback_worktree_db_backup] — DB 백업 룰

---

## 입력값
