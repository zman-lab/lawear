import { useState } from 'react';
import { usePlayer } from '../../context/PlayerContext';

interface SleepTimerSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

const PRESETS = [
  { label: '5분', seconds: 5 * 60 },
  { label: '10분', seconds: 10 * 60 },
  { label: '15분', seconds: 15 * 60 },
  { label: '30분', seconds: 30 * 60 },
  { label: '1시간', seconds: 60 * 60 },
];

export function SleepTimerSheet({ isOpen, onClose }: SleepTimerSheetProps) {
  const { state, setSleepTimer, sleepTimerRemaining } = usePlayer();
  const [customMode, setCustomMode] = useState(false);
  const [hours, setHours] = useState(0);
  const [minutes, setMinutes] = useState(15);
  const [seconds, setSeconds] = useState(0);

  const handlePreset = (secs: number) => {
    setSleepTimer(secs);
    onClose();
  };

  const handleCustom = () => {
    const total = hours * 3600 + minutes * 60 + seconds;
    if (total > 0) {
      setSleepTimer(total);
      onClose();
    }
  };

  const handleCancel = () => {
    setSleepTimer(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <>
      {/* 백드롭 */}
      <div
        className="fixed inset-0 bg-black/40 z-[60]"
        onClick={onClose}
      />
      {/* 시트 */}
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d]">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3" />
        <div className="px-5 pt-4 pb-6">
          <h3 className="text-sm font-bold text-white mb-4">슬립 타이머</h3>

          {/* 타이머 활성 상태 표시 */}
          {state.sleepTimer && sleepTimerRemaining !== null && (
            <div className="mb-4 p-3 bg-blue-500/10 rounded-xl flex items-center justify-between">
              <span className="text-xs text-blue-400">타이머 활성</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono font-bold text-blue-400">
                  {formatRemaining(sleepTimerRemaining)}
                </span>
                <button
                  className="text-[10px] text-red-400 bg-red-400/10 rounded px-2 py-0.5"
                  onClick={handleCancel}
                >
                  해제
                </button>
              </div>
            </div>
          )}

          {!customMode ? (
            <>
              {/* 프리셋 버튼 그리드 */}
              <div className="grid grid-cols-3 gap-2 mb-4">
                {PRESETS.map(p => (
                  <button
                    key={p.seconds}
                    className="py-3 rounded-xl bg-white/5 text-sm font-medium text-white active:bg-white/10 transition-colors"
                    onClick={() => handlePreset(p.seconds)}
                  >
                    {p.label}
                  </button>
                ))}
                <button
                  className="py-3 rounded-xl bg-white/5 text-sm font-medium text-[#8b949e] active:bg-white/10 transition-colors"
                  onClick={() => setCustomMode(true)}
                >
                  직접설정
                </button>
              </div>
            </>
          ) : (
            <>
              {/* 커스텀 시:분:초 선택 */}
              <div className="flex items-center justify-center gap-3 mb-4">
                <div className="text-center">
                  <label className="text-[10px] text-[#8b949e] block mb-1">시간</label>
                  <select
                    className="bg-white/5 text-white text-lg font-mono rounded-lg px-3 py-2 text-center appearance-none"
                    value={hours}
                    onChange={e => setHours(Number(e.target.value))}
                  >
                    {Array.from({ length: 13 }, (_, i) => (
                      <option key={i} value={i}>{String(i).padStart(2, '0')}</option>
                    ))}
                  </select>
                </div>
                <span className="text-white/40 text-lg mt-4">:</span>
                <div className="text-center">
                  <label className="text-[10px] text-[#8b949e] block mb-1">분</label>
                  <select
                    className="bg-white/5 text-white text-lg font-mono rounded-lg px-3 py-2 text-center appearance-none"
                    value={minutes}
                    onChange={e => setMinutes(Number(e.target.value))}
                  >
                    {Array.from({ length: 60 }, (_, i) => (
                      <option key={i} value={i}>{String(i).padStart(2, '0')}</option>
                    ))}
                  </select>
                </div>
                <span className="text-white/40 text-lg mt-4">:</span>
                <div className="text-center">
                  <label className="text-[10px] text-[#8b949e] block mb-1">초</label>
                  <select
                    className="bg-white/5 text-white text-lg font-mono rounded-lg px-3 py-2 text-center appearance-none"
                    value={seconds}
                    onChange={e => setSeconds(Number(e.target.value))}
                  >
                    {Array.from({ length: 60 }, (_, i) => (
                      <option key={i} value={i}>{String(i).padStart(2, '0')}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  className="flex-1 py-2.5 rounded-xl bg-white/5 text-sm text-[#8b949e]"
                  onClick={() => setCustomMode(false)}
                >
                  뒤로
                </button>
                <button
                  className="flex-1 py-2.5 rounded-xl bg-blue-600 text-sm font-bold text-white"
                  onClick={handleCustom}
                >
                  시작
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function formatRemaining(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}
