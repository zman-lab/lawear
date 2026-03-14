import { usePlayer } from '../../context/PlayerContext';
import type { RepeatMode } from '../../types';

interface RepeatModeSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

const MODES: { value: RepeatMode; icon: string; label: string; desc: string }[] = [
  { value: 'stop-after-one', icon: '1', label: '1곡 후 정지', desc: '현재 문제만 재생 후 정지' },
  { value: 'stop-after-all', icon: '>', label: '전곡 후 정지', desc: '전체 문제 순서대로 재생 후 정지' },
  { value: 'repeat-all', icon: '\u{1F501}', label: '전곡 반복', desc: '전체 문제를 반복 재생' },
  { value: 'repeat-one', icon: '\u{1F502}', label: '1곡 반복', desc: '현재 문제만 반복 재생' },
  { value: 'shuffle', icon: '\u{1F500}', label: '셔플', desc: '랜덤 순서로 재생' },
];

export function RepeatModeSheet({ isOpen, onClose }: RepeatModeSheetProps) {
  const { state, setRepeatMode } = usePlayer();
  const currentMode = state.repeatMode;

  if (!isOpen) return null;

  const handleSelect = (mode: RepeatMode) => {
    setRepeatMode(mode);
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
            <h3 className="text-sm font-bold text-white">반복 모드</h3>
            <button
              className="text-xs text-[#8b949e] px-2 py-1"
              onClick={onClose}
              aria-label="닫기"
            >
              닫기
            </button>
          </div>

          <div className="space-y-1.5">
            {MODES.map(({ value, icon, label, desc }) => {
              const isActive = currentMode === value;
              return (
                <button
                  key={value}
                  className={`w-full text-left py-3 px-3 rounded-xl flex items-center gap-3 min-h-[44px] transition-colors ${
                    isActive
                      ? 'bg-blue-500/10 border border-blue-500/20'
                      : 'bg-white/5 active:bg-white/10'
                  }`}
                  onClick={() => handleSelect(value)}
                >
                  <span className="text-lg w-6 text-center shrink-0">{icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium ${isActive ? 'text-blue-400' : 'text-white'}`}>
                      {label}
                    </p>
                    <p className="text-[10px] text-[#8b949e] truncate">{desc}</p>
                  </div>
                  {isActive && (
                    <svg className="w-4 h-4 text-blue-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                    </svg>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
