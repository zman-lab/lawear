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
python3 scripts/cdp_qa.py <기기IP:포트>

# 테스트 항목:
# 01. 앱 실행 + 홈 화면 확인
# 02. 과목 → 케이스 네비게이션
# 03. TTS 재생 + 크래시 확인
# 04. 배속 변경 (1.0x → 2.0x → 5.0x)
# 05. TTS 다음 라인 연속 재생
# 06. 정지/재개
```

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
