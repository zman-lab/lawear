import { useRef, useCallback } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import type { Speed } from '../../types';

interface SpeedSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

const MIN_SPEED = 0.5;
const MAX_SPEED = 5.0;
const STEP = 0.1;
const PRESETS: Speed[] = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0];

function clampSpeed(v: number): Speed {
  return Math.round(Math.min(MAX_SPEED, Math.max(MIN_SPEED, v)) / STEP) * STEP;
}

export function SpeedSheet({ isOpen, onClose }: SpeedSheetProps) {
  const { state, setSpeed } = usePlayer();
  const currentSpeed = state.speed;

  // 드래그 상태
  const dragStartXRef = useRef<number | null>(null);
  const dragStartSpeedRef = useRef<number>(currentSpeed);
  const trackRef = useRef<HTMLDivElement>(null);

  const handlePreset = (speed: Speed) => {
    setSpeed(speed);
  };

  // 슬라이더 클릭 / 드래그 처리
  const speedFromPointerX = useCallback((clientX: number) => {
    const track = trackRef.current;
    if (!track) return null;
    const rect = track.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return clampSpeed(MIN_SPEED + ratio * (MAX_SPEED - MIN_SPEED));
  }, []);

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      dragStartXRef.current = e.clientX;
      dragStartSpeedRef.current = currentSpeed;
      (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);

      const s = speedFromPointerX(e.clientX);
      if (s !== null) setSpeed(s);
    },
    [currentSpeed, setSpeed, speedFromPointerX],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (dragStartXRef.current === null) return;
      const s = speedFromPointerX(e.clientX);
      if (s !== null) setSpeed(s);
    },
    [setSpeed, speedFromPointerX],
  );

  const onPointerUp = useCallback(() => {
    dragStartXRef.current = null;
  }, []);

  if (!isOpen) return null;

  const ratio = (currentSpeed - MIN_SPEED) / (MAX_SPEED - MIN_SPEED);
  const pct = `${(ratio * 100).toFixed(1)}%`;

  return (
    <>
      {/* backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-[60]"
        onClick={onClose}
      />
      {/* sheet */}
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d]">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3" />
        <div className="px-5 pt-4 pb-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-bold text-white">재생 속도</h3>
            <button
              className="text-xs text-[#8b949e] px-2 py-1"
              onClick={onClose}
              aria-label="닫기"
            >
              닫기
            </button>
          </div>

          {/* 현재 값 표시 */}
          <div className="text-center mb-4">
            <span className="text-3xl font-bold text-blue-400">
              {currentSpeed.toFixed(1)}x
            </span>
          </div>

          {/* 슬라이더 트랙 */}
          <div
            ref={trackRef}
            className="relative h-10 flex items-center cursor-pointer select-none touch-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            {/* 배경 바 */}
            <div className="absolute left-0 right-0 h-1.5 rounded-full bg-white/10" />
            {/* 채워진 바 */}
            <div
              className="absolute left-0 h-1.5 rounded-full bg-blue-500"
              style={{ width: pct }}
            />
            {/* 썸 */}
            <div
              className="absolute w-6 h-6 rounded-full bg-blue-400 shadow-lg border-2 border-[#161b22] -translate-x-1/2"
              style={{ left: pct }}
            />
          </div>

          {/* 범위 레이블 */}
          <div className="flex justify-between text-[10px] text-[#8b949e]/50 mt-1 mb-5">
            <span>0.5x</span>
            <span>5.0x</span>
          </div>

          {/* 프리셋 버튼 */}
          <div className="grid grid-cols-6 gap-1.5">
            {PRESETS.map((v) => {
              const isActive = Math.abs(currentSpeed - v) < 0.05;
              return (
                <button
                  key={v}
                  className={`py-2.5 rounded-xl text-xs font-bold transition-colors min-h-[40px] ${
                    isActive
                      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                      : 'bg-white/5 text-white active:bg-white/10'
                  }`}
                  onClick={() => handlePreset(v)}
                >
                  {v.toFixed(1)}x
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
