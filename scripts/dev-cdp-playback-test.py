#!/usr/bin/env python3
"""실기기 CDP로 재생 연속성 + 음성 변경 검증 (실제 TTS 재생)"""
import json, sys, time, websocket, urllib.request, random

def get_ws():
    data = json.loads(urllib.request.urlopen("http://localhost:9222/json").read())
    return data[0]["webSocketDebuggerUrl"]

def ev(ws, expr):
    mid = random.randint(1, 999999)
    ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    for _ in range(50):
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            return msg.get("result", {}).get("result", {}).get("value")
    return None

def main():
    ws = websocket.create_connection(get_ws(), timeout=15, suppress_origin=True)

    print("[SETUP] 정지 + 홈 복귀")
    ev(ws, "window.__debug__?.stop();")
    ev(ws, "window.history.go(-10);")
    time.sleep(2)

    print("\n[TC-A] 실기기 전체재생 연속 재생 (5배속, 60초)")
    # 민법26 클릭
    ev(ws, """
      (() => {
        for (const el of document.querySelectorAll('div, button')) {
          const t = el.textContent || '';
          if (t.includes('민법') && t.includes('2026') && el.clientHeight > 30 && el.clientHeight < 300 && el.offsetParent) {
            el.scrollIntoView({block:'center'}); el.click(); return;
          }
        }
      })()
    """)
    time.sleep(2)

    # 5배속 설정
    ev(ws, "window.__debug__.setSpeed?.(5.0);")
    time.sleep(0.5)

    # 전체재생 클릭
    play_result = ev(ws, """
      (() => {
        for (const el of document.querySelectorAll('button')) {
          const t = (el.textContent || '').trim();
          if ((t === '전체 재생' || t === '전체재생') && el.offsetParent) {
            el.click(); return t;
          }
        }
        return 'not found';
      })()
    """)
    print(f"  전체재생 클릭: {play_result}")
    time.sleep(2)

    # 60초 폴링
    prev_pl = prev_sent = None
    pl_changes = 0
    sent_changes = 0
    for i in range(30):
        s = ev(ws, """JSON.stringify({
            pl: window.__debug__.state.playlistIndex,
            sent: window.__debug__.state.currentSentenceIndex,
            q: window.__debug__.state.currentQuestionId,
            playing: window.__debug__.state.isPlaying,
            mode: window.__debug__.state.repeatMode,
            count: window.__debug__.state.playlist?.length || 0
        })""")
        d = json.loads(s) if s else {}
        if prev_pl is not None and d.get("pl") != prev_pl: pl_changes += 1
        if prev_sent is not None and d.get("sent") != prev_sent: sent_changes += 1
        prev_pl, prev_sent = d.get("pl"), d.get("sent")
        if i % 3 == 0:
            print(f"  [{i*2}s] pl={d.get('pl')}, sent={d.get('sent')}, q={d.get('q')}, playing={d.get('playing')}")
        if pl_changes >= 2:
            print(f"  ✓ playlistIndex 2회 변경 ({i*2}초 경과) — 조기 종료")
            break
        time.sleep(2)

    print(f"\n  playlistIndex 변경 횟수: {pl_changes}")
    print(f"  currentSentenceIndex 변경: {sent_changes}")
    tc_a = "PASS" if pl_changes >= 1 else "FAIL"
    print(f"  → TC-A: {tc_a}")

    print("\n[TC-B] 음성 변경 (재생 중 → 일시정지 → 변경 → 재개)")
    # 정지
    ev(ws, "window.__debug__?.stop();")
    time.sleep(1)

    # 현재 voice 상태
    voice_info = ev(ws, """JSON.stringify({
        current: window.__debug__.state.selectedVoiceURI,
        hasSetVoice: typeof window.__debug__.setVoice,
    })""")
    print(f"  초기 상태: {voice_info}")

    # 재생 재시작
    ev(ws, """
      (() => {
        for (const el of document.querySelectorAll('button')) {
          const t = (el.textContent || '').trim();
          if ((t === '전체 재생' || t === '전체재생') && el.offsetParent) { el.click(); return; }
        }
      })()
    """)
    time.sleep(3)

    # 일시정지
    ev(ws, "window.__debug__.togglePlay();")
    time.sleep(1)
    paused = ev(ws, "window.__debug__.state.isPlaying")
    print(f"  일시정지 후 isPlaying: {paused}")

    # 음성 변경 — g01 시도
    new_voice = "kor-x-lvariant-g01"
    ev(ws, f"window.__debug__.setVoice('{new_voice}');")
    time.sleep(0.5)
    after_set = ev(ws, "window.__debug__.state.selectedVoiceURI")
    print(f"  setVoice('{new_voice}') 후: {after_set}")

    # 재개
    ev(ws, "window.__debug__.togglePlay();")
    time.sleep(2)
    resumed = ev(ws, "window.__debug__.state.isPlaying")
    final_voice = ev(ws, "window.__debug__.state.selectedVoiceURI")
    print(f"  재개 후 isPlaying: {resumed}, voice: {final_voice}")

    tc_b = "PASS" if final_voice == new_voice and resumed else f"FAIL (voice={final_voice}, playing={resumed})"
    print(f"  → TC-B: {tc_b}")

    # 정리
    ev(ws, "window.__debug__.stop();")

    print("\n" + "="*50)
    print(f"  TC-A 전체재생: {tc_a}")
    print(f"  TC-B 음성변경: {tc_b}")
    ws.close()

if __name__ == "__main__":
    main()
