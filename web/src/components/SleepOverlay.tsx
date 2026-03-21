import { useEffect, useRef, useState, useCallback } from 'react';
import { Capacitor, registerPlugin } from '@capacitor/core';
import { usePlayer } from '../context/PlayerContext';

// 네이티브 밝기 조절용 TTSFile 플러그인 (setSleepMode)
interface TTSFilePluginSleep {
  setSleepMode(opts: { enabled: boolean }): Promise<void>;
}

// PlayerContext에서 이미 'TTSFile'을 registerPlugin으로 등록했으므로
// 같은 이름으로 다시 registerPlugin 해도 캐싱되어 동일 인스턴스 반환
function getNativePlugin(): TTSFilePluginSleep | null {
  if (!Capacitor.isNativePlatform()) return null;
  return registerPlugin<TTSFilePluginSleep>('TTSFile');
}

const UNLOCK_TIMEOUT_MS = 5_000;      // UNLOCK_PROMPT → SLEEP (5초)
const TAP_WINDOW_MS = 2000;           // 노크 템포: 2초 이내 3탭
const TAP_MIN_INTERVAL_MS = 50;       // 최소 탭 간격 (바운스 방지)
const TAP_MOVE_THRESHOLD = 10;        // 드래그 필터: 10px 이상 이동 시 무시
const REQUIRED_TAPS = 3;              // 해제에 필요한 탭 수
const SLEEP_TIMEOUT_KEY = 'lawear-sleep-timeout';
const SLEEP_TIMEOUT_DEFAULT = 10;     // 기본값 10초
const SLEEP_SETTINGS_EVENT = 'lawear-sleep-settings-changed';

function getSleepTimeoutMs(): number {
  const raw = localStorage.getItem(SLEEP_TIMEOUT_KEY);
  const secs = raw !== null ? Number(raw) : SLEEP_TIMEOUT_DEFAULT;
  if (isNaN(secs) || secs < 0) return SLEEP_TIMEOUT_DEFAULT * 1000;
  return secs * 1000;
}

/** 설정 변경 시 SleepOverlay에 알림 (SettingsScreen에서 호출) */
export function notifySleepSettingsChanged(): void {
  window.dispatchEvent(new CustomEvent(SLEEP_SETTINGS_EVENT));
}

// 슬립 상태 머신
// AWAKE: 오버레이 없음 (일반 모드)
// SLEEP: 검정 화면 + "탭해서 깨우기"
// UNLOCK_PROMPT: 반투명 + 탭 카운트 인디케이터 + "잠금 해제"
type SleepState = 'AWAKE' | 'SLEEP' | 'UNLOCK_PROMPT';

export function SleepOverlay() {
  const { state } = usePlayer();
  const { isPlaying } = state;

  const [sleepState, setSleepState] = useState<SleepState>('AWAKE');
  const [tapCount, setTapCount] = useState(0);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unlockTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tapTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tapCountRef = useRef(0);
  const pluginRef = useRef<TTSFilePluginSleep | null>(null);

  // 노크 방식: 터치 위치 + 타이밍 추적
  const touchStartPos = useRef<{ x: number; y: number } | null>(null);
  const firstTapTime = useRef<number>(0);   // 첫 탭 시각
  const lastTapTime = useRef<number>(0);    // 마지막 탭 시각

  // 플러그인 초기화 (1회)
  useEffect(() => {
    pluginRef.current = getNativePlugin();
  }, []);

  // 네이티브 밝기 + FLAG_KEEP_SCREEN_ON 제어
  const applyNativeSleepMode = (enabled: boolean) => {
    pluginRef.current?.setSleepMode({ enabled }).catch(() => {
      // 네이티브 미지원 환경에서 무시
    });
  };

  // 잠금 해제 타이머 정리
  const clearUnlockTimer = () => {
    if (unlockTimerRef.current) {
      clearTimeout(unlockTimerRef.current);
      unlockTimerRef.current = null;
    }
  };

  // 탭 카운트 타이머 정리
  const clearTapTimer = () => {
    if (tapTimerRef.current) {
      clearTimeout(tapTimerRef.current);
      tapTimerRef.current = null;
    }
  };

  // 탭 카운트 초기화
  const resetTapCount = () => {
    clearTapTimer();
    tapCountRef.current = 0;
    setTapCount(0);
  };

  // SLEEP 진입 (ref 기반 — setTimeout 콜백에서 stale closure 방지)
  const enterSleep = useCallback(() => {
    console.log('[Sleep] enterSleep called', { isPlaying, sleepState });
    clearUnlockTimer();
    resetTapCount();
    setSleepState('SLEEP');
    applyNativeSleepMode(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const enterSleepRef = useRef(enterSleep);
  enterSleepRef.current = enterSleep;

  // AWAKE 복귀
  const exitToAwake = () => {
    console.log('[Sleep] exitToAwake');
    clearUnlockTimer();
    resetTapCount();
    setSleepState('AWAKE');
    applyNativeSleepMode(false);
    resetIdleTimer();
  };

  // 아이들 타이머 리셋 (AWAKE 상태에서 무조작 → SLEEP, localStorage 값 참조)
  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    const timeoutMs = getSleepTimeoutMs();
    console.log('[Sleep] resetIdleTimer', { timeoutMs, isPlaying });
    if (timeoutMs === 0) return; // 슬립 비활성화
    idleTimerRef.current = setTimeout(() => enterSleepRef.current(), timeoutMs);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 터치 이벤트 핸들러 (드래그 필터링 + 노크 템포) ──────────────────

  // touchstart: 위치 기록
  const handleTouchStart = (e: React.TouchEvent) => {
    e.preventDefault();
    e.stopPropagation();
    touchStartPos.current = {
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
    };
  };

  // 드래그 판정 유틸
  const isDrag = (e: React.TouchEvent): boolean => {
    if (!touchStartPos.current) return true;
    const dx = e.changedTouches[0].clientX - touchStartPos.current.x;
    const dy = e.changedTouches[0].clientY - touchStartPos.current.y;
    return Math.sqrt(dx * dx + dy * dy) > TAP_MOVE_THRESHOLD;
  };

  // 바운스 체크
  const isBounce = (): boolean => {
    const now = Date.now();
    return now - lastTapTime.current < TAP_MIN_INTERVAL_MS;
  };

  // SLEEP → 첫 탭: UNLOCK_PROMPT로 전환 (touchend만)
  const handleSleepTouchEnd = (e: React.TouchEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isDrag(e)) return;
    if (isBounce()) return;

    const now = Date.now();
    lastTapTime.current = now;
    firstTapTime.current = now;

    // 밝기 복원 (오버레이는 유지)
    applyNativeSleepMode(false);
    setSleepState('UNLOCK_PROMPT');
    // 탭 카운트 초기화 후 1로 시작
    resetTapCount();
    tapCountRef.current = 1;
    setTapCount(1);
    // 0.8초 내 추가 탭 대기
    clearTapTimer();
    tapTimerRef.current = setTimeout(() => {
      tapCountRef.current = 0;
      setTapCount(0);
    }, TAP_WINDOW_MS);
    // 5초 무조작 시 다시 SLEEP
    clearUnlockTimer();
    unlockTimerRef.current = setTimeout(() => enterSleepRef.current(), UNLOCK_TIMEOUT_MS);
  };

  // UNLOCK_PROMPT 탭: 카운트 증가, 3탭 시 해제 (touchend만)
  const handleUnlockPromptTouchEnd = (e: React.TouchEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isDrag(e)) return;
    if (isBounce()) return;

    const now = Date.now();
    // 첫 탭으로부터 0.8초 초과 → 리셋 후 1부터 재시작
    if (now - firstTapTime.current > TAP_WINDOW_MS) {
      firstTapTime.current = now;
      lastTapTime.current = now;
      tapCountRef.current = 1;
      setTapCount(1);
      clearTapTimer();
      tapTimerRef.current = setTimeout(() => {
        tapCountRef.current = 0;
        setTapCount(0);
      }, TAP_WINDOW_MS);
      clearUnlockTimer();
      unlockTimerRef.current = setTimeout(() => enterSleepRef.current(), UNLOCK_TIMEOUT_MS);
      return;
    }

    lastTapTime.current = now;
    const newCount = tapCountRef.current + 1;
    tapCountRef.current = newCount;
    setTapCount(newCount);

    if (newCount >= REQUIRED_TAPS) {
      // 3탭 달성 → AWAKE 복귀
      exitToAwake();
      return;
    }

    // 아직 부족 → 0.8초 타이머 리셋 (카운트 유지, 첫 탭 기준)
    clearTapTimer();
    const remaining = TAP_WINDOW_MS - (now - firstTapTime.current);
    tapTimerRef.current = setTimeout(() => {
      tapCountRef.current = 0;
      setTapCount(0);
    }, Math.max(remaining, 0));

    // 5초 무조작 타이머도 리셋
    clearUnlockTimer();
    unlockTimerRef.current = setTimeout(() => enterSleepRef.current(), UNLOCK_TIMEOUT_MS);
  };

  // isPlaying을 ref로도 추적 (이벤트 핸들러에서 최신값 참조)
  const isPlayingRef = useRef(isPlaying);
  isPlayingRef.current = isPlaying;

  const sleepStateRef = useRef(sleepState);
  sleepStateRef.current = sleepState;

  // 재생 상태 변화에 따른 타이머 관리
  useEffect(() => {
    console.log('[Sleep] isPlaying changed', { isPlaying, sleepState });
    if (isPlaying) {
      resetIdleTimer();
    } else {
      // 정지 시: 슬립 해제 + 타이머 취소
      if (idleTimerRef.current) {
        clearTimeout(idleTimerRef.current);
        idleTimerRef.current = null;
      }
      clearUnlockTimer();
      resetTapCount();
      if (sleepState !== 'AWAKE') {
        setSleepState('AWAKE');
        applyNativeSleepMode(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying]);

  // 사용자 인터랙션 이벤트 → 아이들 타이머 리셋 (AWAKE 상태에서만)
  // 디바운스 적용: 연속 터치 이벤트에 의한 과도한 리셋 방지
  useEffect(() => {
    if (!isPlaying) return;

    let debounceTimer: ReturnType<typeof setTimeout> | null = null;

    const handleActivity = () => {
      // ref로 최신 sleepState 참조 (stale closure 방지)
      if (sleepStateRef.current !== 'AWAKE') return;
      // 디바운스: 1초 이내 연속 이벤트는 무시
      if (debounceTimer) return;
      console.log('[Sleep] user activity → resetIdleTimer');
      resetIdleTimer();
      debounceTimer = setTimeout(() => { debounceTimer = null; }, 1000);
    };

    // Android에서 mousemove는 터치 시 phantom 이벤트 발생 가능 → touchstart만 사용
    // 데스크톱 환경에서는 mousemove도 추가
    window.addEventListener('touchstart', handleActivity, { passive: true });
    if (!Capacitor.isNativePlatform()) {
      window.addEventListener('mousemove', handleActivity, { passive: true });
    }

    return () => {
      window.removeEventListener('touchstart', handleActivity);
      if (!Capacitor.isNativePlatform()) {
        window.removeEventListener('mousemove', handleActivity);
      }
      if (debounceTimer) clearTimeout(debounceTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying]);

  // 설정 변경 감지 → 타이머 재설정
  useEffect(() => {
    const handleSettingsChanged = () => {
      console.log('[Sleep] settings changed, resetting timer');
      if (isPlayingRef.current && sleepStateRef.current === 'AWAKE') {
        resetIdleTimer();
      }
    };
    window.addEventListener(SLEEP_SETTINGS_EVENT, handleSettingsChanged);
    return () => window.removeEventListener(SLEEP_SETTINGS_EVENT, handleSettingsChanged);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 언마운트 시 정리
  useEffect(() => {
    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      clearUnlockTimer();
      clearTapTimer();
    };
  }, []);

  // AWAKE: 오버레이 없음
  if (sleepState === 'AWAKE') return null;

  // SLEEP: 검정 화면 + "탭해서 깨우기" (터치 전용)
  if (sleepState === 'SLEEP') {
    return (
      <div
        className="fixed inset-0 z-[200] bg-black flex items-center justify-center"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleSleepTouchEnd}
      >
        <p
          className="text-white text-xs select-none pointer-events-none"
          style={{ opacity: 0.1 }}
        >
          탭해서 깨우기
        </p>
      </div>
    );
  }

  // UNLOCK_PROMPT: bg-black/80 + 탭 인디케이터 (터치 전용)
  const indicators = Array.from({ length: REQUIRED_TAPS }, (_, i) => i < tapCount);

  return (
    <div
      className="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleUnlockPromptTouchEnd}
    >
      <div className="flex flex-col items-center gap-4 select-none pointer-events-none">
        <p className="text-white text-lg font-medium">잠금 해제</p>
        <div className="flex gap-3">
          {indicators.map((filled, i) => (
            <span
              key={i}
              className={`text-2xl transition-opacity duration-100 ${filled ? 'opacity-100' : 'opacity-30'}`}
            >
              ●
            </span>
          ))}
        </div>
        <p className="text-white text-xs opacity-50">화면을 3번 탭하세요</p>
      </div>
    </div>
  );
}
