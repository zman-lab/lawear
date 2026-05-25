# dev-le-17895-restart — 17895 TTS 뷰어 서버 재시작 스킬

> 17895 (`docs/tts-new/server.py`, ttsmerger) launchd 기반 재시작 전용.
> 17896 (시험·채점, examconsole)는 손대지 않음.
> 메모리 룰 [feedback_skill_naming_dev_le_prefix.md] 부합 — dev-le-17895- prefix.
> (구 `le-restart`는 포트별 네이밍 정책으로 폐기 — 17895=ttsmerger / 17896=examconsole 분리.)

---

## 경로 상수

```
PROJECT=/Users/nhn/zman-lab/lawear
VIEWER_DIR=$PROJECT/docs/tts-new
VIEWER_PORT=17895
PLIST_NAME=com.lawear.ttsmerger.plist
PLIST_PATH=$HOME/Library/LaunchAgents/$PLIST_NAME
PLIST_TEMPLATE=$VIEWER_DIR/launchd/$PLIST_NAME   # 템플릿 있으면
LOG_DIR=$PROJECT/logs
FILE_INDEX=$VIEWER_DIR/_file_index.json
```

---

## 실행 순서 (1→6, 스킵 금지)

### 1. 현재 상태 확인

```bash
echo "=== 현재 17895 프로세스 ==="
lsof -i :17895 2>/dev/null | head -3 || echo "(미실행)"

echo "=== launchctl 등록 상태 ==="
launchctl list 2>/dev/null | grep -i ttsmerger || echo "(launchctl 미등록 — Step 2에서 plist 적재)"

echo "=== plist 활성 위치 ==="
ls -la "$HOME/Library/LaunchAgents/com.lawear.ttsmerger.plist" 2>&1 || echo "(plist 활성화 X)"

echo "=== _file_index 유효성 (서빙 데이터 무결성) ==="
python3 -c "import json;d=json.load(open('/Users/nhn/zman-lab/lawear/docs/tts-new/_file_index.json'));print('valid, files:',len(d['files']))" 2>&1
```

### 2. plist 활성화 (없으면 템플릿에서 복사)

```bash
PLIST_PATH="$HOME/Library/LaunchAgents/com.lawear.ttsmerger.plist"
PLIST_TEMPLATE=/Users/nhn/zman-lab/lawear/docs/tts-new/launchd/com.lawear.ttsmerger.plist

if [ ! -f "$PLIST_PATH" ]; then
  echo "plist 활성 위치에 없음 — 템플릿에서 복사"
  [ -f "$PLIST_TEMPLATE" ] && cp "$PLIST_TEMPLATE" "$PLIST_PATH" || echo "템플릿도 없음 — 사용자에게 plist 위치 확인 요청"
fi
ls -la "$PLIST_PATH" 2>&1
```

### 3. _file_index 백업 (재시작 전 안전망)

17895는 DB 없이 `_file_index.json`이 핵심 데이터. 메모리 룰 [feedback_worktree_db_backup] 준용.

```bash
ts=$(date +%Y%m%d_%H%M%S)
cp /Users/nhn/zman-lab/lawear/docs/tts-new/_file_index.json /tmp/file_index_backup_restart_${ts}.json
ls -la /tmp/file_index_backup_restart_${ts}.json
```

### 4. launchctl unload + load

```bash
PLIST_PATH="$HOME/Library/LaunchAgents/com.lawear.ttsmerger.plist"

echo "=== unload ==="; launchctl unload "$PLIST_PATH" 2>&1
sleep 2
echo "=== 포트 해제 확인 ==="; lsof -i :17895 2>/dev/null | head -3 || echo "(포트 해제 OK)"
echo "=== load ==="; launchctl load "$PLIST_PATH" 2>&1
sleep 4
```

### 5. 검증 (재시작 + 0.0.0.0 바인딩 + HTTP + 17896 미영향)

17895 server.py는 `BIND = "0.0.0.0"` 하드코딩 (line 28) — plist 환경변수 의존 없음. 그러나 검증은 필수.

```bash
echo "=== 새 17895 프로세스 + 바인딩 패턴 ==="
lsof -nP -iTCP:17895 -sTCP:LISTEN 2>/dev/null

echo "=== 바인딩 검증 (★ *:17895 패턴이어야 LAN/모바일 접근 가능) ==="
if lsof -nP -iTCP:17895 -sTCP:LISTEN 2>/dev/null | grep -qE "TCP \*:17895 \(LISTEN\)"; then
  echo "✅ 0.0.0.0 바인딩 확인 — LAN 접근 OK"
else
  echo "❌ loopback only — server.py line 28 BIND 값 확인 필요"
fi

echo "=== HTTP localhost ==="
curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://127.0.0.1:17895/merge.html

echo "=== HTTP LAN IP (모바일 접근 시뮬레이션) ==="
LAN_IP=$(ifconfig | grep -E "inet (10\.|192\.|172\.)" | grep -v 127 | head -1 | awk '{print $2}')
if [ -n "$LAN_IP" ]; then
  echo "맥북 LAN IP: $LAN_IP — 갤럭시/모바일 접속 URL: http://${LAN_IP}:17895/merge.html"
  curl -s -o /dev/null -w "$LAN_IP:17895 → HTTP %{http_code}\n" --max-time 5 "http://${LAN_IP}:17895/merge.html"
else
  echo "(LAN IP 미검출)"
fi

echo "=== 17896 미영향 확인 ==="
lsof -nP -iTCP:17896 -sTCP:LISTEN 2>/dev/null | tail -n+2 || echo "(17896 별개 프로세스 — 정상)"

echo "=== ngrok 현재 상태 + URL (서버 재시작과 무관, 사용자 안내용) ==="
# ngrok URL은 ngrok 프로세스 재시작 시에만 변경 (서버 재시작 시 그대로).
# 17895는 두 번째 ngrok 인스턴스 (config = ngrok-second.yml, inspect = 4041).
NGROK_URL_17895=$(curl -s http://127.0.0.1:4041/api/tunnels 2>/dev/null | python3 -c "import json,sys;data=json.load(sys.stdin);print(data['tunnels'][0]['public_url'])" 2>/dev/null)
if [ -n "$NGROK_URL_17895" ]; then
  echo "✅ ngrok-2 (17895): $NGROK_URL_17895"
else
  echo "⚠️ ngrok-2 (4041 instance) 미실행 — 모바일 접근 불가. 재시작 필요:"
  echo "  ngrok start --all --config \"\$HOME/Library/Application Support/ngrok/ngrok-second.yml\" --log=/tmp/ngrok-second.log --log-format=json > /tmp/ngrok-second.out 2>&1 &"
fi
```

### 6. 최신 로그 확인

```bash
ls -t /Users/nhn/zman-lab/lawear/logs/*.log 2>/dev/null | head -1 | xargs tail -30 2>/dev/null || echo "(로그 없음)"
```

---

## 보고 형식

```
## 17895 재시작 완료

| 항목 | 값 |
|------|-----|
| 이전 PID | {이전} |
| 새 PID | {신규} |
| 포트 | 17895 |
| 바인딩 | *:17895 (0.0.0.0) ✅ |
| _file_index | valid (files N) |
| HTTP localhost | {200/3xx} |
| HTTP LAN IP | {200} @ http://{LAN_IP}:17895/merge.html |
| **ngrok URL (모바일 접근)** | {NGROK_URL_17895} 또는 (미실행 시 경고) |
| 17896 영향 | 0 (별개 프로세스) |
| _file_index 백업 | /tmp/file_index_backup_restart_{ts}.json |
| 모바일 URL (LAN) | http://{LAN_IP}:17895/merge.html (ngrok 권장) |
```

---

## 트러블슈팅

### plist load 실패 / 포트 17895 해제 안 됨
```bash
launchctl unload ~/Library/LaunchAgents/com.lawear.ttsmerger.plist 2>&1
lsof -ti :17895 | xargs kill -9 2>/dev/null
sleep 2
launchctl load ~/Library/LaunchAgents/com.lawear.ttsmerger.plist
```

### HTTP timeout
- startup 부족 → `sleep 8`로 늘려 재검증
- server.py 자체 에러 → `tail /Users/nhn/zman-lab/lawear/logs/*.log`

### LAN IP HTTP 안 됨 (모바일에서 접속 안 됨)
- `lsof`가 `*:17895` 아닌 `127.0.0.1:17895` → `server.py` line 28 `BIND` 값 확인. 누군가 `127.0.0.1`로 바꿨다면 `0.0.0.0`으로 복구 후 재시작
- 맥 방화벽 활성 → `/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate` (Disabled 아니면 비활성화 또는 17895 허용)
- 갤럭시가 다른 WiFi (사내망 vs 공유기) → 같은 네트워크 확인

### 17896도 같이 죽었을 때
- 본 스킬은 17896 미손댐 — 별도. 17896 재시작은 `dev-le-17896-restart`.

---

## 워크트리 모드

워크트리에서 뷰어를 별도로 띄울 경우(코드 격리 테스트): 포트 충돌 회피 — 다른 포트(예 17899) 사용. `cd $WT/docs/tts-new && nohup python3 server.py >> $LOG_DIR/viewer-wt.log 2>&1 & disown` (server.py 포트 인자/환경변수 지원 시).

---

## 관련 자료

- 17895 코드: `docs/tts-new/server.py` (launchd com.lawear.ttsmerger, merge.html/input.html 서빙)
- 메모리 [reference_tts_viewer.md] — 17895 URL `http://127.0.0.1:17895`
- 메모리 [feedback_skill_naming_dev_le_prefix.md] — dev-le- prefix 네이밍
- 짝 스킬: `dev-le-17896-restart` (17896 시험·채점)

---

## 입력값
