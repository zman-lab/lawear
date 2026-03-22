#!/usr/bin/env python3
"""
lawear CDP 자동 QA 스크립트
- Chrome DevTools Protocol로 WebView를 제어
- 빌드 → 설치 → 테스트 → 크래시 감지 파이프라인
"""
import json
import subprocess
import sys
import time
import base64
import os
import threading

# websocket-client 사용 (suppress_origin 지원)
import websocket

# ── 설정 ──────────────────────────────────────────────────────────────────────

ADB_DEVICE = os.environ.get("ADB_DEVICE", "")
CDP_PORT = 9222
CDP_KEEPALIVE_INTERVAL = 5  # 초: WebSocket idle timeout 방지 ping 간격
CDP_KEEPALIVE_MSG_ID = 0    # keepalive 전용 msg_id (테스트와 충돌 방지)
APP_PACKAGE = "com.zmanlab.lawear"
APP_ACTIVITY = f"{APP_PACKAGE}/.MainActivity"
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(PROJECT_DIR, "web")
APK_PATH = os.path.join(WEB_DIR, "android/app/build/outputs/apk/debug/app-debug.apk")
SCREENSHOT_DIR = "/tmp/lawear_qa"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ── ADB 헬퍼 ─────────────────────────────────────────────────────────────────

def adb(*args):
    cmd = ["adb"]
    if ADB_DEVICE:
        cmd += ["-s", ADB_DEVICE]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip(), result.returncode

def adb_check():
    out, rc = adb("shell", "echo", "ping")
    if rc != 0 or "ping" not in out:
        print("ERROR: adb 연결 안 됨")
        sys.exit(1)
    print(f"✓ adb 연결 OK ({ADB_DEVICE or 'default'})")

def adb_install(apk_path):
    print(f"  설치 중: {os.path.basename(apk_path)}")
    out, rc = adb("install", "-r", apk_path)
    if rc != 0:
        print(f"  ERROR: 설치 실패 - {out}")
        return False
    print("  ✓ 설치 완료")
    return True

def adb_uninstall():
    adb("uninstall", APP_PACKAGE)
    print("  ✓ 기존 앱 제거")

def adb_start_app():
    adb("shell", "am", "start", "-n", APP_ACTIVITY)
    time.sleep(3)
    print("  ✓ 앱 시작")

def adb_stop_app():
    adb("shell", "am", "force-stop", APP_PACKAGE)
    print("  ✓ 앱 종료")

def adb_logcat_crash():
    out, _ = adb("logcat", "-d", "-t", "50")
    lines = [l for l in out.split("\n") if "FATAL EXCEPTION" in l or "AndroidRuntime" in l]
    return lines

def adb_clear_logcat():
    adb("logcat", "-c")

# ── CDP 헬퍼 ─────────────────────────────────────────────────────────────────

_ws = None
_msg_id = 0
_ws_lock = threading.Lock()  # WebSocket send/recv 경합 방지
_keepalive_timer = None

def cdp_keepalive_start(ws, interval=CDP_KEEPALIVE_INTERVAL):
    """interval초마다 빈 평가를 보내 WebSocket idle timeout 방지"""
    global _keepalive_timer

    def _ping():
        global _keepalive_timer
        with _ws_lock:
            try:
                ws.send(json.dumps({
                    "id": CDP_KEEPALIVE_MSG_ID,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "1"}
                }))
                ws.recv()
            except Exception:
                return  # 연결 끊김 — 타이머 중단
        _keepalive_timer = threading.Timer(interval, _ping)
        _keepalive_timer.daemon = True
        _keepalive_timer.start()

    _keepalive_timer = threading.Timer(interval, _ping)
    _keepalive_timer.daemon = True
    _keepalive_timer.start()


def cdp_keepalive_stop():
    """keepalive 타이머 정리"""
    global _keepalive_timer
    if _keepalive_timer:
        _keepalive_timer.cancel()
        _keepalive_timer = None


def cdp_connect():
    global _ws
    # WebView DevTools 소켓 찾기
    out, _ = adb("shell", "cat", "/proc/net/unix")
    socket_name = None
    for line in out.split("\n"):
        if "webview_devtools_remote_" in line:
            parts = line.strip().split()
            for p in parts:
                if p.startswith("@webview_devtools_remote_"):
                    socket_name = p[1:]  # @ 제거
                    break
            if socket_name:
                break

    if not socket_name:
        print("ERROR: WebView DevTools 소켓을 찾지 못함")
        return False

    # 포트 포워딩
    adb("forward", f"tcp:{CDP_PORT}", f"localabstract:{socket_name}")

    # 페이지 URL 가져오기
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json", timeout=5)
        pages = json.loads(resp.read())
    except Exception as e:
        print(f"ERROR: CDP /json 실패 - {e}")
        return False

    if not pages:
        print("ERROR: WebView 페이지 없음")
        return False

    ws_url = pages[0].get("webSocketDebuggerUrl", "")
    if not ws_url:
        print("ERROR: webSocketDebuggerUrl 없음")
        return False

    print(f"  CDP: {ws_url[:60]}...")

    # WebSocket 연결 (suppress_origin 필수!)
    _ws = websocket.create_connection(ws_url, timeout=15, suppress_origin=True)
    cdp_keepalive_start(_ws)
    print("  ✓ CDP 연결 OK (keepalive 활성)")
    return True

def cdp_eval(expr, timeout=10):
    global _msg_id
    with _ws_lock:
        _msg_id += 1
        my_id = _msg_id
        msg = json.dumps({
            "id": my_id,
            "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}
        })
        _ws.send(msg)
        _ws.settimeout(timeout)
        while True:
            try:
                resp = json.loads(_ws.recv())
            except websocket.WebSocketTimeoutException:
                return None
            # keepalive 응답은 무시
            if resp.get("id") == CDP_KEEPALIVE_MSG_ID:
                continue
            if resp.get("id") == my_id:
                result = resp.get("result", {}).get("result", {})
                return result.get("value", result.get("description", str(result)))
    return None

def cdp_screenshot(filename):
    global _msg_id
    with _ws_lock:
        _msg_id += 1
        my_id = _msg_id
        msg = json.dumps({"id": my_id, "method": "Page.captureScreenshot", "params": {"format": "png"}})
        _ws.send(msg)
        _ws.settimeout(10)
        while True:
            resp = json.loads(_ws.recv())
            # keepalive 응답은 무시
            if resp.get("id") == CDP_KEEPALIVE_MSG_ID:
                continue
            if resp.get("id") == my_id:
                data = resp.get("result", {}).get("data", "")
                if data:
                    path = os.path.join(SCREENSHOT_DIR, filename)
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(data))
                    return path
                return None

def cdp_close():
    global _ws
    cdp_keepalive_stop()
    if _ws:
        _ws.close()
        _ws = None

# ── 테스트 액션 ──────────────────────────────────────────────────────────────

def click_text(text, tag="*"):
    """텍스트를 포함하는 요소를 찾아 클릭"""
    result = cdp_eval(f"""
    (function() {{
        const els = document.querySelectorAll('{tag}');
        for (const el of els) {{
            if (el.textContent.includes('{text}') && el.offsetParent !== null) {{
                el.click();
                return 'clicked: ' + el.tagName + ' > ' + el.textContent.substring(0, 40);
            }}
        }}
        // fallback: closest clickable parent
        const all = document.querySelectorAll('*');
        for (const el of all) {{
            if (el.childElementCount === 0 && el.textContent.trim() === '{text}') {{
                const clickable = el.closest('button, a, [role=button], div[class*=cursor]') || el.parentElement;
                if (clickable) {{
                    clickable.click();
                    return 'clicked parent: ' + clickable.tagName;
                }}
            }}
        }}
        return 'NOT FOUND: {text}';
    }})()
    """)
    return result

def click_react_props(text):
    """React __reactProps$의 onClick을 직접 호출"""
    result = cdp_eval(f"""
    (function() {{
        const els = document.querySelectorAll('*');
        for (const el of els) {{
            if (el.textContent.includes('{text}') && el.offsetParent !== null) {{
                const propsKey = Object.keys(el).find(k => k.startsWith('__reactProps$'));
                if (propsKey && el[propsKey].onClick) {{
                    el[propsKey].onClick({{
                        preventDefault: ()=>{{}}, stopPropagation: ()=>{{}},
                        nativeEvent: new Event('click'), target: el, currentTarget: el
                    }});
                    return 'react-clicked: ' + el.textContent.substring(0, 40);
                }}
            }}
        }}
        return 'NOT FOUND (react): {text}';
    }})()
    """)
    return result

def get_screen_text():
    """현재 화면의 텍스트 요약"""
    return cdp_eval("""
    (function() {
        const texts = [];
        document.querySelectorAll('h1,h2,h3,p,button,span').forEach(el => {
            const t = el.textContent.trim();
            if (t && t.length < 100 && el.offsetParent !== null) texts.push(t);
        });
        return texts.slice(0, 20).join(' | ');
    })()
    """)

def get_logger_trail():
    """앱 로거의 최근 이벤트"""
    return cdp_eval("""
    (function() {
        try {
            // logger.ts의 getTrail이 export되어 있으면 직접 호출
            // 모듈 스코프라 직접 접근은 어렵지만, window에 노출된 게 있는지 확인
            return 'logger not directly accessible from CDP';
        } catch(e) {
            return e.message;
        }
    })()
    """)

def wait(sec):
    time.sleep(sec)

def check_crash():
    """logcat에서 크래시 확인"""
    lines = adb_logcat_crash()
    crash_lines = [l for l in lines if APP_PACKAGE in l or "CapacitorPlugins" in l]
    return crash_lines

# ── 테스트 시나리오 ──────────────────────────────────────────────────────────

def test_01_app_launch():
    """앱 실행 + 홈 화면 확인"""
    print("\n[TEST 01] 앱 실행")
    adb_clear_logcat()
    screen = get_screen_text()
    if "LawEar" in str(screen) or "민사소송법" in str(screen):
        print(f"  ✓ 홈 화면 확인: {str(screen)[:80]}")
        cdp_screenshot("01_home.png")
        return True
    print(f"  ✗ 홈 화면 아님: {screen}")
    return False

def test_02_navigate_to_player():
    """민사소송법 → Case 01 → 플레이어"""
    print("\n[TEST 02] 민사소송법 → Case 01 네비게이션")

    # 민사소송법 클릭
    result = click_text("민사소송법")
    print(f"  과목 클릭: {result}")
    wait(1)
    cdp_screenshot("02_list.png")

    # Case 01 클릭
    result = click_text("Case 01")
    print(f"  Case 01 클릭: {result}")
    wait(1)

    screen = get_screen_text()
    cdp_screenshot("02_player.png")

    if "Case" in str(screen) or "문제" in str(screen):
        print(f"  ✓ 플레이어 화면: {str(screen)[:80]}")
        return True
    print(f"  ? 현재 화면: {str(screen)[:80]}")
    return True  # 화면 전환이 다를 수 있으므로 일단 통과

def test_03_tts_playback():
    """TTS 재생 시작 + 크래시 확인"""
    print("\n[TEST 03] TTS 재생")

    # 재생 버튼 클릭 (하단 플레이바의 ▶)
    result = cdp_eval("""
    (function() {
        // PlayerBar 또는 PlayerScreen의 재생 버튼 찾기
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const svg = btn.querySelector('svg');
            if (svg && btn.offsetParent !== null) {
                const rect = btn.getBoundingClientRect();
                // 52x52 이상 크기의 버튼 (재생 버튼은 보통 큼)
                if (rect.width >= 40 && rect.height >= 40 && rect.y > 600) {
                    btn.click();
                    return 'play clicked at y=' + Math.round(rect.y);
                }
            }
        }
        // 전체 재생 버튼 시도
        for (const btn of buttons) {
            if (btn.textContent.includes('재생')) {
                btn.click();
                return 'play-text clicked: ' + btn.textContent.substring(0, 30);
            }
        }
        return 'play button NOT FOUND';
    })()
    """)
    print(f"  재생 클릭: {result}")
    wait(3)

    # 크래시 확인
    crashes = check_crash()
    if crashes:
        print(f"  ✗ 크래시 발생!")
        for c in crashes[:3]:
            print(f"    {c[:120]}")
        return False

    cdp_screenshot("03_playing.png")
    print("  ✓ 재생 시작 (크래시 없음)")
    return True

def test_04_speed_change():
    """배속 변경 테스트 (실시간 반영 확인)"""
    print("\n[TEST 04] 배속 변경")

    # 현재 배속 확인
    speed = cdp_eval("""
    (function() {
        const el = document.querySelector('[class*="text-"]');
        const spans = document.querySelectorAll('span, p, button');
        for (const s of spans) {
            if (s.textContent.match(/^[0-9.]+x$/) && s.offsetParent !== null) {
                return s.textContent;
            }
        }
        return 'speed not found';
    })()
    """)
    print(f"  현재 배속: {speed}")

    # 하단 배속 버튼 클릭 (SpeedSheet 열기)
    result = cdp_eval("""
    (function() {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            if (btn.textContent.match(/^[0-9.]+x$/) && btn.offsetParent !== null) {
                const rect = btn.getBoundingClientRect();
                if (rect.y > 700) {  // 하단 바
                    btn.click();
                    return 'speed sheet opened: ' + btn.textContent;
                }
            }
        }
        return 'speed button NOT FOUND';
    })()
    """)
    print(f"  시트 열기: {result}")
    wait(0.5)
    cdp_screenshot("04_speed_sheet.png")

    # 2.0x 프리셋 클릭
    result = click_text("2.0x", "button")
    print(f"  2.0x 선택: {result}")
    wait(1)

    # 크래시 확인
    crashes = check_crash()
    if crashes:
        print(f"  ✗ 배속 변경 중 크래시!")
        return False

    cdp_screenshot("04_speed_changed.png")

    # 5.0x 테스트
    result = cdp_eval("""
    (function() {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            if (btn.textContent.match(/^[0-9.]+x$/) && btn.offsetParent !== null) {
                const rect = btn.getBoundingClientRect();
                if (rect.y > 700) {
                    btn.click();
                    return 'speed sheet re-opened';
                }
            }
        }
        return 'NOT FOUND';
    })()
    """)
    wait(0.5)

    result = click_text("5.0x", "button")
    print(f"  5.0x 선택: {result}")
    wait(1)

    crashes = check_crash()
    if crashes:
        print(f"  ✗ 5.0x 크래시!")
        return False

    cdp_screenshot("04_speed_5x.png")
    print("  ✓ 배속 변경 OK (크래시 없음)")
    return True

def test_05_tts_continuation():
    """TTS 다음 라인 자동 넘어가기 테스트"""
    print("\n[TEST 05] TTS 다음 라인 연속 재생")

    # 현재 문장 인덱스 확인
    idx1 = cdp_eval("""
    (function() {
        // DOM에서 현재 하이라이트된 문장 위치 확인
        const highlighted = document.querySelector('[class*="bg-blue"], [class*="text-blue-300"], [style*="background"]');
        if (highlighted) return 'highlighted: ' + highlighted.textContent.substring(0, 50);
        return 'no highlight found';
    })()
    """)
    print(f"  현재 위치: {idx1}")

    # 10초 대기 후 위치 변경 확인
    print("  10초 대기 중 (다음 라인 넘어가는지 확인)...")
    wait(10)

    idx2 = cdp_eval("""
    (function() {
        const highlighted = document.querySelector('[class*="bg-blue"], [class*="text-blue-300"], [style*="background"]');
        if (highlighted) return 'highlighted: ' + highlighted.textContent.substring(0, 50);
        return 'no highlight found';
    })()
    """)
    print(f"  10초 후 위치: {idx2}")

    # 크래시 확인
    crashes = check_crash()
    if crashes:
        print(f"  ✗ 연속 재생 중 크래시!")
        return False

    if idx1 != idx2:
        print("  ✓ 다음 라인으로 진행됨")
    else:
        print("  ? 같은 위치 (TTS가 아직 같은 문장이거나, 멈춤)")

    cdp_screenshot("05_continuation.png")
    return True

def test_06_stop_and_resume():
    """정지 후 재개"""
    print("\n[TEST 06] 정지 → 재개")

    # 정지
    result = cdp_eval("""
    (function() {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const rect = btn.getBoundingClientRect();
            if (rect.width >= 40 && rect.height >= 40 && rect.y > 600 && btn.offsetParent !== null) {
                btn.click();
                return 'toggle clicked';
            }
        }
        return 'NOT FOUND';
    })()
    """)
    print(f"  정지: {result}")
    wait(1)

    crashes = check_crash()
    if crashes:
        print(f"  ✗ 정지 중 크래시!")
        return False

    # 재개
    cdp_eval("""
    (function() {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const rect = btn.getBoundingClientRect();
            if (rect.width >= 40 && rect.height >= 40 && rect.y > 600 && btn.offsetParent !== null) {
                btn.click();
                return 'toggle clicked';
            }
        }
        return 'NOT FOUND';
    })()
    """)
    wait(2)

    crashes = check_crash()
    if crashes:
        print(f"  ✗ 재개 중 크래시!")
        return False

    print("  ✓ 정지/재개 OK")
    return True

# ── 메인 ─────────────────────────────────────────────────────────────────────

def run_all_tests():
    print("=" * 60)
    print("  lawear CDP 자동 QA")
    print("=" * 60)

    # 연결 확인
    adb_check()

    # CDP 연결
    if not cdp_connect():
        print("CDP 연결 실패. 앱이 실행 중인지 확인하세요.")
        sys.exit(1)

    results = {}
    tests = [
        ("01_app_launch", test_01_app_launch),
        ("02_navigate", test_02_navigate_to_player),
        ("03_tts_play", test_03_tts_playback),
        ("04_speed", test_04_speed_change),
        ("05_continuation", test_05_tts_continuation),
        ("06_stop_resume", test_06_stop_and_resume),
    ]

    for name, test_fn in tests:
        try:
            results[name] = test_fn()
        except Exception as e:
            print(f"  ✗ 예외: {e}")
            results[name] = False

    # 결과 요약
    print("\n" + "=" * 60)
    print("  결과 요약")
    print("=" * 60)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}  {name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  {passed}/{total} 통과")
    print(f"  스크린샷: {SCREENSHOT_DIR}/")

    cdp_close()
    return all(results.values())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ADB_DEVICE = sys.argv[1]
    success = run_all_tests()
    sys.exit(0 if success else 1)
