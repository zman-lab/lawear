import { useState, useRef, useEffect, useCallback } from 'react';
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

// ── 스크롤 피커 컴포넌트 (CSS scroll-snap 기반) ──────────────────────────────
interface ScrollPickerProps {
  values: number[];
  selectedValue: number;
  onChange: (value: number) => void;
  label: string;
  formatValue?: (v: number) => string;
}

const ITEM_HEIGHT = 44;
const VISIBLE_COUNT = 5;
const PICKER_HEIGHT = ITEM_HEIGHT * VISIBLE_COUNT;
const PADDING_ITEMS = Math.floor(VISIBLE_COUNT / 2); // 위아래 패딩 아이템 수 (2개)

function ScrollPicker({ values, selectedValue, onChange, label, formatValue }: ScrollPickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isUserScrolling = useRef(false);
  const scrollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const didInitialScroll = useRef(false);

  const fmt = formatValue ?? ((v: number) => String(v).padStart(2, '0'));

  // 선택된 값의 인덱스
  const selectedIdx = values.indexOf(selectedValue);

  // 초기 스크롤 위치 설정 (마운트 시 1회만)
  useEffect(() => {
    const el = containerRef.current;
    if (!el || didInitialScroll.current) return;
    const idx = values.indexOf(selectedValue);
    if (idx >= 0) {
      // 즉시 설정 (smooth 아님) -> 초기 렌더링이므로 애니메이션 불필요
      el.scrollTop = idx * ITEM_HEIGHT;
      didInitialScroll.current = true;
    }
  }, [values, selectedValue]);

  // selectedValue prop이 외부에서 변경되면 스크롤 위치 동기화
  useEffect(() => {
    if (!didInitialScroll.current) return; // 초기 설정 전이면 무시
    if (isUserScrolling.current) return; // 유저가 스크롤 중이면 무시
    const el = containerRef.current;
    if (!el) return;
    const idx = values.indexOf(selectedValue);
    if (idx >= 0) {
      const targetTop = idx * ITEM_HEIGHT;
      if (Math.abs(el.scrollTop - targetTop) > ITEM_HEIGHT / 2) {
        el.scrollTo({ top: targetTop, behavior: 'smooth' });
      }
    }
  }, [selectedValue, values]);

  // 스크롤 이벤트 -> debounce로 스냅 값 감지
  const handleScroll = useCallback(() => {
    isUserScrolling.current = true;

    if (scrollTimer.current) {
      clearTimeout(scrollTimer.current);
    }

    scrollTimer.current = setTimeout(() => {
      isUserScrolling.current = false;
      const el = containerRef.current;
      if (!el) return;

      // 현재 스크롤 위치에서 가장 가까운 아이템 인덱스 계산
      const idx = Math.round(el.scrollTop / ITEM_HEIGHT);
      const clamped = Math.max(0, Math.min(idx, values.length - 1));

      // 정확한 위치로 스냅 (CSS scroll-snap이 처리하지만, 보험)
      const targetTop = clamped * ITEM_HEIGHT;
      if (Math.abs(el.scrollTop - targetTop) > 1) {
        el.scrollTo({ top: targetTop, behavior: 'smooth' });
      }

      // 값 변경 알림
      if (values[clamped] !== selectedValue) {
        onChange(values[clamped]);
      }
    }, 120);
  }, [values, selectedValue, onChange]);

  // 아이템 클릭으로 선택
  const handleItemClick = useCallback((idx: number) => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: idx * ITEM_HEIGHT, behavior: 'smooth' });
    onChange(values[idx]);
  }, [values, onChange]);

  // cleanup
  useEffect(() => {
    return () => {
      if (scrollTimer.current) clearTimeout(scrollTimer.current);
    };
  }, []);

  return (
    <div className="flex flex-col items-center">
      <label className="text-[10px] text-[#8b949e] mb-1">{label}</label>
      <div
        className="relative overflow-hidden"
        style={{ height: PICKER_HEIGHT, width: 64 }}
      >
        {/* 선택 인디케이터 (중앙 하이라이트) */}
        <div
          className="absolute left-0 right-0 pointer-events-none z-10 border-t border-b border-blue-500/30 bg-blue-500/5"
          style={{ top: ITEM_HEIGHT * PADDING_ITEMS, height: ITEM_HEIGHT }}
        />
        {/* 위아래 페이드 그라디언트 */}
        <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-[#161b22] to-transparent z-10 pointer-events-none" />
        <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-[#161b22] to-transparent z-10 pointer-events-none" />

        <div
          ref={containerRef}
          className="h-full overflow-y-auto scrollbar-hide"
          style={{
            scrollSnapType: 'y mandatory',
            WebkitOverflowScrolling: 'touch',
          }}
          onScroll={handleScroll}
          data-testid={`scroll-picker-${label}`}
        >
          {/* 상단 패딩 아이템 (빈 공간 -> 첫 번째 값이 중앙에 올 수 있게) */}
          {Array.from({ length: PADDING_ITEMS }).map((_, i) => (
            <div key={`pad-top-${i}`} style={{ height: ITEM_HEIGHT }} aria-hidden />
          ))}
          {values.map((v, idx) => {
            const isSelected = idx === selectedIdx;
            return (
              <div
                key={v}
                className={`flex items-center justify-center cursor-pointer select-none transition-colors ${
                  isSelected ? 'text-blue-400 font-bold text-xl' : 'text-white/40 text-lg'
                }`}
                style={{
                  height: ITEM_HEIGHT,
                  scrollSnapAlign: 'start',
                }}
                onClick={() => handleItemClick(idx)}
                data-testid={`picker-item-${label}-${v}`}
                role="option"
                aria-selected={isSelected}
              >
                {fmt(v)}
              </div>
            );
          })}
          {/* 하단 패딩 아이템 */}
          {Array.from({ length: PADDING_ITEMS }).map((_, i) => (
            <div key={`pad-bot-${i}`} style={{ height: ITEM_HEIGHT }} aria-hidden />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 메인 컴포넌트 ──────────────────────────────────────────────────────────
export function SleepTimerSheet({ isOpen, onClose }: SleepTimerSheetProps) {
  const { state, setSleepTimer, sleepTimerRemaining } = usePlayer();
  const [customMode, setCustomMode] = useState(false);
  const [hours, setHours] = useState(0);
  const [minutes, setMinutes] = useState(15);
  const [seconds, setSeconds] = useState(0);

  // 시트가 닫힐 때 커스텀 모드 초기화
  useEffect(() => {
    if (!isOpen) {
      setCustomMode(false);
    }
  }, [isOpen]);

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

  const hourValues = Array.from({ length: 13 }, (_, i) => i);
  const minuteValues = Array.from({ length: 60 }, (_, i) => i);
  const secondValues = Array.from({ length: 60 }, (_, i) => i);

  const isCustomValid = hours * 3600 + minutes * 60 + seconds > 0;

  return (
    <>
      {/* backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-[60]"
        onClick={onClose}
        data-testid="sleep-timer-backdrop"
      />
      {/* sheet */}
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d]">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3" />
        <div className="px-5 pt-4 pb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white">슬립 타이머</h3>
            <button
              className="text-xs text-[#8b949e] px-2 py-1"
              onClick={onClose}
              aria-label="닫기"
            >
              닫기
            </button>
          </div>

          {/* 타이머 활성 상태 표시 */}
          {state.sleepTimer && sleepTimerRemaining !== null && (
            <div className="mb-4 p-3 bg-blue-500/10 rounded-xl flex items-center justify-between" data-testid="active-timer-display">
              <span className="text-xs text-blue-400">타이머 활성</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono font-bold text-blue-400" data-testid="timer-remaining">
                  {formatRemaining(sleepTimerRemaining)}
                </span>
                <button
                  className="text-[10px] text-red-400 bg-red-400/10 rounded px-2 py-0.5"
                  onClick={handleCancel}
                  data-testid="cancel-timer-btn"
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
                    className="py-3 rounded-xl bg-white/5 text-sm font-medium text-white active:bg-white/10 transition-colors min-h-[44px]"
                    onClick={() => handlePreset(p.seconds)}
                    data-testid={`preset-${p.seconds}`}
                  >
                    {p.label}
                  </button>
                ))}
                <button
                  className="py-3 rounded-xl bg-white/5 text-sm font-medium text-[#8b949e] active:bg-white/10 transition-colors min-h-[44px]"
                  onClick={() => setCustomMode(true)}
                  data-testid="custom-mode-btn"
                >
                  직접설정
                </button>
              </div>

              {/* 닫기 버튼 */}
              <button
                className="w-full py-2.5 rounded-xl bg-white/5 text-sm text-[#8b949e] active:bg-white/10 transition-colors"
                onClick={onClose}
                data-testid="cancel-btn"
              >
                취소
              </button>
            </>
          ) : (
            <>
              {/* 커스텀 시:분:초 스크롤 피커 */}
              <div className="flex items-center justify-center gap-2 mb-4">
                <ScrollPicker
                  values={hourValues}
                  selectedValue={hours}
                  onChange={setHours}
                  label="시간"
                />
                <span className="text-white/40 text-lg mt-4">:</span>
                <ScrollPicker
                  values={minuteValues}
                  selectedValue={minutes}
                  onChange={setMinutes}
                  label="분"
                />
                <span className="text-white/40 text-lg mt-4">:</span>
                <ScrollPicker
                  values={secondValues}
                  selectedValue={seconds}
                  onChange={setSeconds}
                  label="초"
                />
              </div>
              <div className="flex gap-2">
                <button
                  className="flex-1 py-2.5 rounded-xl bg-white/5 text-sm text-[#8b949e] min-h-[44px]"
                  onClick={() => setCustomMode(false)}
                  data-testid="back-btn"
                >
                  뒤로
                </button>
                <button
                  className={`flex-1 py-2.5 rounded-xl text-sm font-bold min-h-[44px] transition-colors ${
                    isCustomValid
                      ? 'bg-blue-600 text-white'
                      : 'bg-white/5 text-white/30 cursor-not-allowed'
                  }`}
                  onClick={handleCustom}
                  disabled={!isCustomValid}
                  data-testid="start-btn"
                >
                  시작
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* scrollbar-hide 스타일 */}
      <style>{`
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>
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
