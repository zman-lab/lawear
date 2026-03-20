import { useEffect, useRef, useState } from 'react';
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

const IDLE_TIMEOUT_MS = 10_000; // 10초 무조작

export function SleepOverlay() {
  const { state } = usePlayer();
  const { isPlaying } = state;

  const [isSleeping, setIsSleeping] = useState(false);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pluginRef = useRef<TTSFilePluginSleep | null>(null);

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

  // 슬립 진입
  const enterSleep = () => {
    setIsSleeping(true);
    applyNativeSleepMode(true);
  };

  // 슬립 해제
  const exitSleep = () => {
    setIsSleeping(false);
    applyNativeSleepMode(false);
    resetIdleTimer();
  };

  // 아이들 타이머 리셋
  const resetIdleTimer = () => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    idleTimerRef.current = setTimeout(enterSleep, IDLE_TIMEOUT_MS);
  };

  // 재생 상태 변화에 따른 타이머 관리
  useEffect(() => {
    if (isPlaying) {
      resetIdleTimer();
    } else {
      // 정지 시: 슬립 해제 + 타이머 취소
      if (idleTimerRef.current) {
        clearTimeout(idleTimerRef.current);
        idleTimerRef.current = null;
      }
      if (isSleeping) {
        setIsSleeping(false);
        applyNativeSleepMode(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying]);

  // 사용자 인터랙션 이벤트 → 아이들 타이머 리셋
  useEffect(() => {
    if (!isPlaying) return;

    const handleActivity = () => {
      if (!isSleeping) {
        resetIdleTimer();
      }
    };

    window.addEventListener('touchstart', handleActivity, { passive: true });
    window.addEventListener('mousemove', handleActivity, { passive: true });

    return () => {
      window.removeEventListener('touchstart', handleActivity);
      window.removeEventListener('mousemove', handleActivity);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying, isSleeping]);

  // 언마운트 시 정리
  useEffect(() => {
    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    };
  }, []);

  if (!isSleeping) return null;

  return (
    <div
      className="fixed inset-0 z-[200] bg-black flex items-center justify-center"
      onClick={exitSleep}
      onTouchEnd={(e) => {
        e.preventDefault();
        exitSleep();
      }}
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
