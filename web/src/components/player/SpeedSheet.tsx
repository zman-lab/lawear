import { usePlayer } from '../../context/PlayerContext';
import type { Speed } from '../../types';

interface SpeedSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

const SPEEDS: { value: Speed; label: string }[] = [
  { value: 0.5, label: '0.5x' },
  { value: 0.8, label: '0.8x' },
  { value: 1.0, label: '1.0x' },
  { value: 1.2, label: '1.2x' },
  { value: 1.5, label: '1.5x' },
  { value: 2.0, label: '2.0x' },
  { value: 2.5, label: '2.5x' },
  { value: 3.0, label: '3.0x' },
];

export function SpeedSheet({ isOpen, onClose }: SpeedSheetProps) {
  const { state, setSpeed } = usePlayer();
  const currentSpeed = state.speed;

  if (!isOpen) return null;

  const handleSelect = (speed: Speed) => {
    setSpeed(speed);
    onClose();
  };

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
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white">재생 속도</h3>
            <button
              className="text-xs text-[#8b949e] px-2 py-1"
              onClick={onClose}
              aria-label="닫기"
            >
              닫기
            </button>
          </div>

          <div className="grid grid-cols-4 gap-2">
            {SPEEDS.map(({ value, label }) => {
              const isActive = currentSpeed === value;
              return (
                <button
                  key={value}
                  className={`py-3 rounded-xl text-sm font-bold transition-colors min-h-[44px] ${
                    isActive
                      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                      : 'bg-white/5 text-white active:bg-white/10'
                  }`}
                  onClick={() => handleSelect(value)}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
