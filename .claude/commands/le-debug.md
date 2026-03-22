# le-debug — Lawear 무선 디버깅 + CDP 자동 QA 스킬

> 갤럭시 무선 adb + Chrome DevTools Protocol로 앱 설치/실행/테스트/크래시 분석을 자동화한다.
> adb input tap은 WebView에서 안 먹히므로 **CDP Runtime.evaluate + DOM API**로 UI 제어.

## 언제 사용하나

- 앱 크래시 디버깅 (네이티브 Java 크래시 포함)
- 새 빌드 설치 후 자동 테스트
- TTS 재생/배속/연속재생 등 기능 테스트
- 사용자 대신 QA 수행

## 기기 정보

- 기기: zman20 noteultra (갤럭시)
- IP 대역: 10.77.76.x (사내망)
- 패키지: com.zmanlab.lawear
- 액티비티: com.zmanlab.lawear/.MainActivity
- 해상도: 720x1544 (override)

## Phase 1: 무선 디버깅 연결

```
1. adb devices → 이미 연결됐는지 확인

2. 연결 안 됨 → 사용자에게:
   "갤럭시 설정 → 개발자 옵션 → 무선 디버깅 ON
    → '페어링 코드로 기기 페어링' 탭
    → IP:포트 + 페어링코드, 그리고 아래 연결용 IP:포트도 알려주세요"

3. 페어링 + 연결 (포트 2개 다름!)
   adb pair <IP>:<페어링포트> <코드>
   adb connect <IP>:<연결포트>

4. 연결 안정성 (화면 잠금 시 끊김 방지)
   - 개발자 옵션 → "충전 중 화면 켜짐 유지" ON
   - 또는 충전기 연결
```

## Phase 2: 빌드 + 설치

```
1. cd /Users/nhn/zman-lab/lawear/web && npx vite build
2. npx cap sync android
3. cd android && ./gradlew assembleDebug
4. adb -s <기기> uninstall com.zmanlab.lawear   (레거시 클린)
5. adb -s <기기> install <APK경로>
6. adb -s <기기> shell am start -n com.zmanlab.lawear/.MainActivity
```

## Phase 3: CDP 연결 (UI 자동 제어)

**핵심: adb input tap은 WebView에서 안 먹힘. CDP만 사용.**

```
1. WebView DevTools 소켓 찾기
   adb -s <기기> shell cat /proc/net/unix | grep webview_devtools_remote_

2. 포트 포워딩
   adb -s <기기> forward tcp:9222 localabstract:webview_devtools_remote_<PID>

3. 페이지 URL 확인
   curl -s http://localhost:9222/json

4. WebSocket 연결 (suppress_origin=True 필수!)
   import websocket
   ws = websocket.create_connection(ws_url, timeout=15, suppress_origin=True)

5. JS 실행
   ws.send(json.dumps({
     "id": 1, "method": "Runtime.evaluate",
     "params": {"expression": "...", "returnByValue": True}
   }))
```

### CDP UI 클릭 방법 (우선순위)

```javascript
// 방법 A: el.click() — React 18에서 정상 동작 (대부분 이것만으로 충분)
(function() {
  const els = document.querySelectorAll('div, button');
  for (const el of els) {
    if (el.textContent.includes('민사소송법') && el.offsetParent !== null) {
      el.click(); return 'clicked';
    }
  }
  return 'NOT FOUND';
})()

// 방법 B: React __reactProps$ 직접 호출 (el.click() 안 먹힐 때)
const propsKey = Object.keys(el).find(k => k.startsWith('__reactProps$'));
el[propsKey].onClick({preventDefault:()=>{}, stopPropagation:()=>{}, ...});

// 방법 C: Touch+Pointer 풀 시퀀스 (모바일 전용 이벤트에 반응하는 경우)
el.dispatchEvent(new TouchEvent('touchstart', {bubbles:true, ...}));
el.dispatchEvent(new TouchEvent('touchend', {bubbles:true, ...}));
el.click();
```

### CDP 스크린샷

```python
ws.send(json.dumps({"id":N, "method":"Page.captureScreenshot", "params":{"format":"png"}}))
# 응답의 result.data를 base64 디코딩하면 PNG
```

## Phase 4: 자동 QA 스크립트

```bash
# 전체 테스트 실행
python3 scripts/dev-cdp-qa.py <기기IP:포트>

# 테스트 항목:
# 01. 앱 실행 + 홈 화면 확인
# 02. 과목 → 케이스 네비게이션
# 03. TTS 재생 + 크래시 확인
# 04. 배속 변경 (1.0x → 2.0x → 5.0x)
# 05. TTS 다음 라인 연속 재생
# 06. 정지/재개
```

### 추가 테스트 (test_07~10) — 테스트과목 전제

> 아래 테스트는 앱에 "테스트과목"이 존재해야 실행 가능.
> 테스트과목: T-1~T-6, 각 4줄 (T-{n}-첫째줄 ~ T-{n}-넷째줄)
> 없으면 → 사용자에게 "테스트과목이 없습니다. le-dev에서 먼저 생성해주세요" 보고 후 스킵.

**공통 전제:**
- 5배속 강제 설정: `window.__debug__.setSpeed(5.0)`
- 각 스텝마다 로그 캡처 + 사용자에게 스텝별 로그 붙여넣기 보고
- **TC별 60초 타임아웃**: 각 TC를 독립 실행, 60초 초과 시 FAIL 처리 후 다음 TC
- **`window.__debug__` 함수 직접 호출 우선** (바텀시트 DOM 클릭보다 안정적):
  - `window.__debug__.setRepeatMode('repeat-one')` — 반복모드 변경
  - `window.__debug__.setSpeed(5.0)` — 배속 변경
  - `window.__debug__.playSelected([...])` — 플레이리스트 재생
  - `window.__debug__.play(subjectId, fileId, questionId)` — 단일 재생
  - `window.__debug__.stop()` — 정지
- **`window.__cdp.click(text)` 사용** (scrollIntoView 자동, DOM 클릭 시)
- **상태 확인**: `window.__debug__.state` (isPlaying, repeatMode, currentSentenceIndex, playlistIndex 등)

**테스트과목 진입 패턴:**
```javascript
// 1. 홈으로 이동 (뒤로가기 반복)
// 2. 테스트과목 카드 정확 클릭 (textContent에 '테스트과목' + '6 설문' 포함)
(function(){ const els=document.querySelectorAll('div');
  for(const el of els){ if(el.textContent&&el.textContent.includes('테스트과목')&&el.textContent.includes('6 설문')&&el.clientHeight>30&&el.clientHeight<200){ el.scrollIntoView({block:'center'}); el.click(); return 'ok';}} return 'no';})()
// 3. T-1 케이스 선택 후 재생 버튼 (aria-label='재생')
```

**test_07: 반복모드 전환** (60초)
1. 테스트과목 → T-1 선택 + 재생
2. `window.__debug__.setRepeatMode('repeat-one')` → state 확인
3. `window.__debug__.setRepeatMode('repeat-all')` → state 확인
4. `window.__debug__.setRepeatMode('shuffle')` → state 확인
5. PASS: 3개 모드 전부 정확히 반영

**test_08: 1곡 반복 실제 루프** (60초)
1. 테스트과목 → T-1 선택, 5배속, repeat-one 모드
2. `window.__debug__.state.currentSentenceIndex` 폴링 (1초 간격, 15초)
3. PASS: 인덱스 3→0 전환 1회 이상 + playlistIndex 불변

**test_09: 전곡 반복 트랙 전환** (60초)
1. 테스트과목 "전체 재생" (UI) 또는 `window.__debug__.playSelected` (6곡 playlist)
2. `window.__debug__.setRepeatMode('repeat-all')`, 5배속
3. `playlistIndex` + `currentQuestionId` 폴링 (1초 간격, 20초)
4. PASS: playlistIndex 0→1 전환 또는 questionId 변경

**test_10: 1곡 후 정지** (60초)
1. 테스트과목 재생 중 `window.__debug__.setRepeatMode('stop-after-one')`
2. `isPlaying` 폴링 (1초 간격, 15초)
3. PASS: isPlaying == false

### 테스트 결과 보고 형식

각 테스트 완료 시:
```
[test_07] PASS/FAIL
  step 1: 테스트과목 → T-1 선택 ✅ (로그: ...)
  step 2: 5배속 설정 ✅ (로그: ...)
  step 3: 반복모드 전환 ✅ (window.__debug__.state.repeatMode = 'repeat-one')
  ...
```

**전제조건 체크 (Phase 4 시작 시):**
1. `window.__debug__` 존재 확인 → 없으면 "PlayerContext에 debug 노출이 필요합니다" 보고 + test_07~10 스킵
2. "테스트과목" 존재 확인 → 없으면 "테스트과목이 없습니다" 보고 + test_07~10 스킵
3. 기존 test_01~06은 전제조건 없이 항상 실행

## Phase 4.5: QA 실패 대응

test_01~10 중 FAIL 발생 시 아래 단계로 대응:

### 1차: 서브에이전트 재시도
- 서브에이전트(Opus)가 실패 원인 분석 + 수정 + 재테스트
- CDP 스크립트 오류인지, 실제 코드 버그인지 구분

### 1차 실패 → 메인 Opus 직접 실행
- 메인이 Bash로 python3 CDP 스크립트를 직접 실행
- 실패 → 즉시 원인 파악 → 스크립트 수정 → 재시도 (같은 컨텍스트)
- 서브에이전트보다 효과적인 이유: 반복 학습 + 상태 인식 + 에러 대응이 동일 세션에서 가능

### CDP 자동화 안정성 규칙
- **모든 클릭 전 `window.__cdp.click(text)` 사용** (scrollIntoView 자동)
- **상태 조회는 `window.__debug__.state` 사용** (DOM 파싱 불필요)
- **바텀시트 옵션 선택은 `window.__debug__` 함수 직접 호출 우선** (DOM 클릭보다 안정적)
  - 예: `window.__debug__.setRepeatMode('repeat-one')` > `__cdp.click('1곡 반복')`
- **WebSocket idle 15초 초과 시 끊김** → 3초 간격 폴링으로 keepalive

## Phase 5: 크래시 분석

```
1. logcat에서 FATAL EXCEPTION 확인
   adb -s <기기> logcat -d | grep -A 25 "FATAL EXCEPTION"

2. Java 네이티브 크래시 → 해당 플러그인 Java 소스 **전체** 분석
   ⚠️ 크래시 라인만 보지 말고 null 가능 필드 전부 확인!

3. JS 에러 → CDP Console.enable으로 수집
   또는 window.__LOGS__ 배열로 console 후킹

4. 수정 → Phase 2 (빌드+설치) → Phase 4 (재테스트)
```

## 주의사항

- **페어링 포트 ≠ 연결 포트**: 매번 다름, 사용자에게 둘 다 확인
- **무선 디버깅은 화면 잠금/Wi-Fi 전환 시 끊김**: 충전 + 화면 켜짐 유지 권장
- **CDP suppress_origin=True 필수**: Chrome 145 WebView가 origin 거부
- **앱 재시작 시 PID 변경됨**: CDP forward를 다시 해야 함
- **프로덕션 빌드에서 console.log 안 나옴**: CDP console 후킹으로 대체
- **cap sync 필수**: vite build만 하고 sync 안 하면 APK에 반영 안 됨

## 입력값

$ARGUMENTS
