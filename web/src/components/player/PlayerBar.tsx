import { useRef, useState } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';
import { SleepTimerSheet } from './SleepTimerSheet';
import { VoiceSheet } from './VoiceSheet';
import { SpeedSheet } from './SpeedSheet';
import { RepeatModeSheet } from './RepeatModeSheet';
import { PlaylistSheet } from './PlaylistSheet';
import type { Speed, RepeatMode } from '../../types';

function speedLabel(speed: Speed): string {
  return `${speed.toFixed(1)}x`;
}

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
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
          <text x="18" y="20" fontSize="9" fontWeight="bold" fill="currentColor" stroke="none">1</text>
        </svg>
      );
    case 'stop-after-all':
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4 2-4 2" />
        </svg>
      );
    case 'repeat-all':
      return (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z" />
        </svg>
      );
    case 'repeat-one':
      return (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z" />
          <text x="12" y="15" fontSize="8" fontWeight="bold" textAnchor="middle" fill="currentColor">1</text>
        </svg>
      );
    case 'shuffle':
      return (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
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
    nextQuestion,
    prevQuestion,
    setSentenceIndex,
  } = usePlayer();

  const [showTimerSheet, setShowTimerSheet] = useState(false);
  const [showVoiceSheet, setShowVoiceSheet] = useState(false);
  const [showSpeedSheet, setShowSpeedSheet] = useState(false);
  const [showRepeatSheet, setShowRepeatSheet] = useState(false);
  const [showPlaylistSheet, setShowPlaylistSheet] = useState(false);

  const {
    isPlaying,
    speed,
    repeatMode,
    currentSubjectId,
    currentFileId,
    currentQuestionId,
    currentSentenceIndex,
    playlist,
    playlistIndex,
  } = state;

  const hasPlaylist = playlist.length > 1;

  const progressBarRef = useRef<HTMLDivElement>(null);

  const subject = currentSubjectId ? subjects.find((s) => s.id === currentSubjectId) : null;
  const fileGroup = subject?.files.find((f) => f.id === currentFileId);
  const question = fileGroup?.questions.find((q) => q.id === currentQuestionId);

  const totalSentences = question
    ? question.content.problem.length +
      question.content.toc.length +
      question.content.answer.length
    : 0;

  const progressPercent =
    totalSentences > 0
      ? Math.min(100, (currentSentenceIndex / Math.max(1, totalSentences - 1)) * 100)
      : 0;

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!progressBarRef.current || totalSentences === 0) return;
    const rect = progressBarRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const targetIndex = Math.round(ratio * (totalSentences - 1));
    setSentenceIndex(targetIndex);
  };

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
      {/* TTS 미지원 안내 */}
      {!isTTSSupported && (
        <div className="px-4 pt-2 pb-1">
          <p className="text-[10px] text-amber-400/80 bg-amber-400/10 rounded-md px-2 py-1 text-center">
            이 브라우저에서는 음성 재생이 지원되지 않습니다. 텍스트만 표시됩니다.
          </p>
        </div>
      )}

      {/* 플레이리스트 트랙 정보 */}
      {hasPlaylist && hasContent && (
        <div className="px-4 pt-2 pb-0.5 flex items-center justify-between">
          <p className="text-[10px] text-[#8b949e] truncate flex-1">
            {question?.label}
          </p>
          <span className="text-[10px] text-blue-400/60 font-mono ml-2 shrink-0">
            {playlistIndex + 1}/{playlist.length}
          </span>
        </div>
      )}

      {/* 프로그레스 바 */}
      <div className={`px-4 ${hasPlaylist && hasContent ? 'pt-1' : 'pt-3'}`}>
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
            {hasContent ? `${currentSentenceIndex + 1}문장` : '—'}
          </span>
          <span className="text-[10px] text-[#8b949e]/50">
            {hasContent ? `${totalSentences}문장` : '—'}
          </span>
        </div>
      </div>

      {/* 상단 줄: 보조 컨트롤 5개 */}
      <div className="px-4 pt-1 pb-0 flex items-center justify-around">
        {/* 속도 */}
        <button
          className="text-xs font-bold text-blue-400 bg-blue-400/10 rounded-md px-2.5 py-1 min-h-[36px] min-w-[44px] text-center"
          onClick={() => setShowSpeedSheet(true)}
          aria-label={`재생 속도: ${speedLabel(speed)}`}
        >
          {speedLabel(speed)}
        </button>

        {/* 반복 모드 */}
        <button
          className={`min-w-[44px] min-h-[36px] flex items-center justify-center transition-colors ${
            repeatMode === 'stop-after-one' ? 'text-[#8b949e]' : 'text-blue-400'
          }`}
          onClick={() => setShowRepeatSheet(true)}
          aria-label={`반복 모드: ${REPEAT_MODE_LABELS[repeatMode]}`}
          title={REPEAT_MODE_LABELS[repeatMode]}
        >
          <RepeatModeIcon mode={repeatMode} />
        </button>

        {/* 플레이리스트 */}
        <button
          className={`min-w-[44px] min-h-[36px] flex items-center justify-center transition-colors ${
            hasPlaylist ? 'text-blue-400' : 'text-[#8b949e]'
          }`}
          onClick={() => setShowPlaylistSheet(true)}
          aria-label="플레이리스트"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h10m4 0v6m-3-3h6" />
          </svg>
        </button>

        {/* 슬립 타이머 */}
        {sleepTimerRemaining !== null ? (
          <button
            className="text-xs font-mono text-blue-400 bg-blue-400/10 rounded-md px-2 py-1 min-w-[44px] min-h-[36px] text-center"
            onClick={() => setShowTimerSheet(true)}
            aria-label="슬립 타이머 설정"
          >
            {formatTimerDisplay(sleepTimerRemaining)}
          </button>
        ) : (
          <button
            className="text-[#8b949e] min-w-[44px] min-h-[36px] flex items-center justify-center"
            onClick={() => setShowTimerSheet(true)}
            aria-label="슬립 타이머 설정"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>
        )}

        {/* 음성 선택 */}
        <button
          className={`min-w-[44px] min-h-[36px] flex items-center justify-center ${
            state.selectedVoiceURI ? 'text-blue-400' : 'text-[#8b949e]'
          }`}
          onClick={() => setShowVoiceSheet(true)}
          aria-label="음성 선택"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </button>
      </div>

      {/* 하단 줄: 핵심 재생 컨트롤 */}
      <div className="px-4 pb-4 pt-1 flex items-center justify-center gap-2">
        {/* 이전 트랙 (플레이리스트 모드) */}
        {hasPlaylist && (
          <button
            className={`min-w-[36px] min-h-[44px] flex items-center justify-center transition-colors ${
              playlistIndex > 0 ? 'text-[#8b949e] active:text-white' : 'text-[#8b949e]/20'
            }`}
            onClick={prevQuestion}
            aria-label="이전 트랙"
            disabled={!hasContent || playlistIndex <= 0}
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
            </svg>
          </button>
        )}

        {/* 이전 문장 */}
        <button
          className="text-[#8b949e] active:text-white transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
          onClick={prevSentence}
          aria-label="이전 문장"
          disabled={!hasContent}
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M11 18V6l-8.5 6 8.5 6zm.5-6l8.5 6V6l-8.5 6z" />
          </svg>
        </button>

        {/* 재생/일시정지 */}
        <button
          className="w-[52px] h-[52px] rounded-full bg-white flex items-center justify-center active:scale-95 transition-transform shadow-lg shadow-white/10 shrink-0"
          onClick={togglePlay}
          aria-label={isPlaying ? '일시정지' : '재생'}
        >
          {isPlaying ? (
            <svg className="w-6 h-6" fill="#0d1117" viewBox="0 0 24 24">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
            </svg>
          ) : (
            <svg className="w-6 h-6" fill="#0d1117" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>

        {/* 다음 문장 */}
        <button
          className="text-[#8b949e] active:text-white transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
          onClick={nextSentence}
          aria-label="다음 문장"
          disabled={!hasContent}
        >
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z" />
          </svg>
        </button>

        {/* 다음 트랙 (플레이리스트 모드) */}
        {hasPlaylist && (
          <button
            className={`min-w-[36px] min-h-[44px] flex items-center justify-center transition-colors ${
              playlistIndex < playlist.length - 1 ? 'text-[#8b949e] active:text-white' : 'text-[#8b949e]/20'
            }`}
            onClick={nextQuestion}
            aria-label="다음 트랙"
            disabled={!hasContent || playlistIndex >= playlist.length - 1}
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
            </svg>
          </button>
        )}
      </div>

      {/* 바텀시트 */}
      <SleepTimerSheet isOpen={showTimerSheet} onClose={() => setShowTimerSheet(false)} />
      <VoiceSheet isOpen={showVoiceSheet} onClose={() => setShowVoiceSheet(false)} />
      <SpeedSheet isOpen={showSpeedSheet} onClose={() => setShowSpeedSheet(false)} />
      <RepeatModeSheet isOpen={showRepeatSheet} onClose={() => setShowRepeatSheet(false)} />
      <PlaylistSheet isOpen={showPlaylistSheet} onClose={() => setShowPlaylistSheet(false)} />
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
