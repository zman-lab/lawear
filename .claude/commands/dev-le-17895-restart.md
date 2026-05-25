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

### 5. 검증 (재시작 + HTTP + 17896 미영향)

```bash
echo "=== 새 17895 프로세스 ==="; lsof -i :17895 2>/dev/null | head -3
echo "=== HTTP 응답 (200/3xx 정상) ==="; curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://127.0.0.1:17895/merge.html
echo "=== 17896 미영향 확인 ==="; lsof -i :17896 2>/dev/null | head -3 || echo "(17896 별개 프로세스 — 정상)"
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
| _file_index | valid (files N) |
| HTTP | {200/3xx} |
| 17896 영향 | 0 (별개 프로세스) |
| _file_index 백업 | /tmp/file_index_backup_restart_{ts}.json |
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
