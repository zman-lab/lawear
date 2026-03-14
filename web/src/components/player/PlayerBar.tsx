import { useRef, useState } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';
import { SleepTimerSheet } from './SleepTimerSheet';
import { VoiceSheet } from './VoiceSheet';
import { SpeedSheet } from './SpeedSheet';
import { RepeatModeSheet } from './RepeatModeSheet';
import type { Speed, RepeatMode } from '../../types';

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function parseDuration(duration: string): number {
  const parts = duration.split(':').map(Number);
  if (parts.length === 2) {
    return (parts[0] ?? 0) * 60 + (parts[1] ?? 0);
  }
  return 0;
}

const SPEED_LABELS: Record<Speed, string> = {
  0.5: '0.5x',
  0.8: '0.8x',
  1.0: '1.0x',
  1.2: '1.2x',
  1.5: '1.5x',
  2.0: '2.0x',
  2.5: '2.5x',
  3.0: '3.0x',
};


const REPEAT_MODE_LABELS: Record<RepeatMode, string> = {
  'stop-after-one': '1곡 후 정지',
  'stop-after-all': '전곡 후 정지',
  'repeat-all': '전곡 반복',
  'repeat-one': '1곡 반복',
  shuffle: '셔플',
};

function RepeatModeIcon({ mode }: { mode: RepeatMode }) {
  switch (mode) {
    case 'stop-after-one':
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
          <text x="18" y="20" fontSize="9" fontWeight="bold" fill="currentColor" stroke="none">1</text>
        </svg>
      );
    case 'stop-after-all':
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4 2-4 2" />
        </svg>
      );
    case 'repeat-all':
      return (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z" />
        </svg>
      );
    case 'repeat-one':
      return (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z" />
          <text x="12" y="15" fontSize="8" fontWeight="bold" textAnchor="middle" fill="currentColor">1</text>
        </svg>
      );
    case 'shuffle':
      return (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z" />
        </svg>
      );
  }
}

export function PlayerBar() {
  const {
    state,
    isTTSSupported,
    togglePlay,
    sleepTimerRemaining,
    nextSentence,
    prevSentence,
    setSentenceIndex,
  } = usePlayer();

  const [showTimerSheet, setShowTimerSheet] = useState(false);
  const [showVoiceSheet, setShowVoiceSheet] = useState(false);
  const [showSpeedSheet, setShowSpeedSheet] = useState(false);
  const [showRepeatSheet, setShowRepeatSheet] = useState(false);

  const {
    isPlaying,
    speed,
    repeatMode,
    currentSubjectId,
    currentFileId,
    currentQuestionId,
    currentSentenceIndex,
  } = state;

  const progressBarRef = useRef<HTMLDivElement>(null);

  // 현재 재생 중인 설문 데이터 찾기
  const subject = currentSubjectId ? subjects.find((s) => s.id === currentSubjectId) : null;
  const fileGroup = subject?.files.find((f) => f.id === currentFileId);
  const question = fileGroup?.questions.find((q) => q.id === currentQuestionId);

  // 총 문장 수 계산
  const totalSentences = question
    ? question.content.problem.length +
      question.content.toc.length +
      question.content.answer.length
    : 0;

  // 진행률 (문장 기반)
  const progressPercent =
    totalSentences > 0
      ? Math.min(100, (currentSentenceIndex / Math.max(1, totalSentences - 1)) * 100)
      : 0;

  // 시간 표시 (duration 기반 추정)
  const totalSeconds = question ? parseDuration(question.duration) : 0;
  const currentSeconds =
    totalSentences > 0
      ? Math.floor((currentSentenceIndex / Math.max(1, totalSentences - 1)) * totalSeconds)
      : 0;

  // 프로그레스 바 클릭 seek
  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!progressBarRef.current || totalSentences === 0) return;
    const rect = progressBarRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const targetIndex = Math.round(ratio * (totalSentences - 1));
    setSentenceIndex(targetIndex);
  };

  // 재생 중인 것이 없으면 최소 UI
  const hasContent = !!question;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-50"
      style={{
        background: 'rgba(13,17,23,0.92)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* E-01/E-02: TTS 미지원 안내 */}
      {!isTTSSupported && (
        <div className="px-4 pt-2 pb-1">
          <p className="text-[10px] text-amber-400/80 bg-amber-400/10 rounded-md px-2 py-1 text-center">
            이 브라우저에서는 음성 재생이 지원되지 않습니다. 텍스트만 표시됩니다.
          </p>
        </div>
      )}
      {/* 프로그레스 바 */}
      <div className="px-4 pt-3">
        <div
          ref={progressBarRef}
          className="h-1 bg-white/5 rounded-full overflow-hidden cursor-pointer"
          onClick={handleProgressClick}
          role="slider"
          aria-label="재생 위치"
          aria-valuenow={currentSentenceIndex}
          aria-valuemin={0}
          aria-valuemax={totalSentences}
        >
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[10px] text-[#8b949e]/50">
            {hasContent ? formatTime(currentSeconds) : '0:00'}
          </span>
          <span className="text-[10px] text-[#8b949e]/50">
            {hasContent ? formatTime(totalSeconds) : '0:00'}
          </span>
        </div>
      </div>

      {/* 컨트롤 */}
      <div className="px-4 pb-3 pt-1 flex items-center justify-between">
        {/* 속도 버튼 — 탭: 시트, 길게 누르기: 순환 */}
        <button
          className="text-xs font-bold text-blue-400 bg-blue-400/10 rounded-md px-2 py-1 min-w-[3rem] text-center min-h-[44px]"
          onClick={() => setShowSpeedSheet(true)}
          aria-label={`재생 속도: ${SPEED_LABELS[speed]}`}
        >
          {SPEED_LABELS[speed]}
        </button>

        {/* 반복 모드 — 탭: 시트 열기 */}
        <button
          className={`min-w-[44px] min-h-[44px] flex items-center justify-center transition-colors ${
            repeatMode === 'stop-after-one'
              ? 'text-[#8b949e]'
              : 'text-blue-400'
          }`}
          onClick={() => setShowRepeatSheet(true)}
          aria-label={`반복 모드: ${REPEAT_MODE_LABELS[repeatMode]}`}
          title={REPEAT_MODE_LABELS[repeatMode]}
        >
          <RepeatModeIcon mode={repeatMode} />
        </button>

        {/* 중앙 컨트롤 */}
        <div className="flex items-center gap-6">
          {/* 이전 */}
          <button
            className="text-[#8b949e] active:text-white transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
            onClick={prevSentence}
            aria-label="이전 문장"
            disabled={!hasContent}
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
            </svg>
          </button>

          {/* 재생/일시정지 */}
          <button
            className="w-[52px] h-[52px] rounded-full bg-white flex items-center justify-center active:scale-95 transition-transform shadow-lg shadow-white/10 shrink-0"
            onClick={togglePlay}
            aria-label={isPlaying ? '일시정지' : '재생'}
          >
            {isPlaying ? (
              // 일시정지 아이콘
              <svg className="w-6 h-6" fill="#0d1117" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              </svg>
            ) : (
              // 재생 아이콘
              <svg className="w-6 h-6" fill="#0d1117" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>

          {/* 다음 */}
          <button
            className="text-[#8b949e] active:text-white transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
            onClick={nextSentence}
            aria-label="다음 문장"
            disabled={!hasContent}
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
            </svg>
          </button>
        </div>

        {/* 우: 타이머 + 음성 */}
        <div className="flex items-center gap-1.5">
          {/* 슬립 타이머 */}
          {sleepTimerRemaining !== null ? (
            <button
              className="text-xs font-mono text-blue-400 bg-blue-400/10 rounded-md px-2 py-1 min-w-[3rem] text-center"
              onClick={() => setShowTimerSheet(true)}
              aria-label="슬립 타이머 설정"
            >
              {formatTimerDisplay(sleepTimerRemaining)}
            </button>
          ) : (
            <button
              className="text-[#8b949e] min-w-[36px] min-h-[44px] flex items-center justify-center"
              onClick={() => setShowTimerSheet(true)}
              aria-label="슬립 타이머 설정"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </button>
          )}

          {/* 음성 선택 */}
          <button
            className={`min-w-[36px] min-h-[44px] flex items-center justify-center ${
              state.selectedVoiceURI ? 'text-blue-400' : 'text-[#8b949e]'
            }`}
            onClick={() => setShowVoiceSheet(true)}
            aria-label="음성 선택"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          </button>
        </div>
      </div>

      {/* 슬립 타이머 바텀시트 */}
      <SleepTimerSheet isOpen={showTimerSheet} onClose={() => setShowTimerSheet(false)} />

      {/* 음성 선택 바텀시트 */}
      <VoiceSheet isOpen={showVoiceSheet} onClose={() => setShowVoiceSheet(false)} />

      {/* 속도 선택 바텀시트 */}
      <SpeedSheet isOpen={showSpeedSheet} onClose={() => setShowSpeedSheet(false)} />

      {/* 반복 모드 바텀시트 */}
      <RepeatModeSheet isOpen={showRepeatSheet} onClose={() => setShowRepeatSheet(false)} />
    </div>
  );
}

function formatTimerDisplay(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}
