import { useRef } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';
import type { Speed } from '../../types';

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
  0.8: '0.8x',
  1.0: '1.0x',
  1.2: '1.2x',
  1.5: '1.5x',
  2.0: '2.0x',
};

const SPEEDS: Speed[] = [0.8, 1.0, 1.2, 1.5, 2.0];

export function PlayerBar() {
  const {
    state,
    isTTSSupported,
    togglePlay,
    setSpeed,
    nextSentence,
    prevSentence,
    setSentenceIndex,
  } = usePlayer();

  const {
    isPlaying,
    speed,
    currentSubjectId,
    currentFileId,
    currentQuestionId,
    currentSentenceIndex,
  } = state;

  const cycleSpeed = () => {
    const idx = SPEEDS.indexOf(speed);
    const next = SPEEDS[(idx + 1) % SPEEDS.length];
    setSpeed(next);
  };

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
        {/* 속도 버튼 */}
        <button
          className="text-xs font-bold text-blue-400 bg-blue-400/10 rounded-md px-2 py-1 min-w-[3rem] text-center"
          onClick={cycleSpeed}
          aria-label={`재생 속도: ${SPEED_LABELS[speed]}`}
        >
          {SPEED_LABELS[speed]}
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

        {/* 재생목록 */}
        <button
          className="text-[#8b949e] min-w-[44px] min-h-[44px] flex items-center justify-center"
          aria-label="재생목록"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h7"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
