import { useEffect, useRef, useState, useMemo } from 'react';
import { subjects } from '../../data/ttsData';
import { usePlayer } from '../../context/PlayerContext';
import { log } from '../../services/logger';
import type { ViewMode, TocItem } from '../../types';

interface PlayerScreenProps {
  subjectId: string;
  fileId: string;
  questionId: string;
  onBack: () => void;
}

// 아코디언 섹션
interface AccordionSectionProps {
  isOpen: boolean;
  onToggle: () => void;
  badge: string;
  badgeColorClass: string;
  labelColorClass: string;
  label: string;
  children: React.ReactNode;
}

function AccordionSection({
  isOpen,
  onToggle,
  badge,
  badgeColorClass,
  labelColorClass,
  label,
  children,
}: AccordionSectionProps) {
  return (
    <div className="mb-2">
      <button
        className="w-full flex items-center justify-between py-2.5 text-left"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2">
          <span
            className={`w-5 h-5 rounded ${badgeColorClass} flex items-center justify-center text-[10px] font-black`}
          >
            {badge}
          </span>
          <span className={`text-xs font-bold tracking-wide ${labelColorClass}`}>{label}</span>
        </div>
        <svg
          className={`w-3.5 h-3.5 text-[#8b949e]/40 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div
        className="overflow-hidden transition-all duration-300"
        style={{ maxHeight: isOpen ? '3000px' : '0px' }}
      >
        {children}
      </div>
    </div>
  );
}

// 문장 컴포넌트 (리더 뷰)
interface SentenceProps {
  text: string;
  index: number;
  currentIndex: number;
  sentenceRef: (el: HTMLParagraphElement | null) => void;
  onClick: (index: number) => void;
  repeatStart: number | null;
  repeatEnd: number | null;
  repeatActive: boolean;
}

function Sentence({ text, index, currentIndex, sentenceRef, onClick, repeatStart, repeatEnd, repeatActive }: SentenceProps) {
  const isActive = index === currentIndex;
  const isPast = index < currentIndex;
  const isSectionStart = repeatStart !== null && index === repeatStart;
  const isSectionEnd = repeatEnd !== null && index === repeatEnd;
  const isInSection = repeatActive && repeatStart !== null && repeatEnd !== null && index >= repeatStart && index <= repeatEnd;

  // 구간 반복 보더 우선 적용
  let borderClass = 'border-transparent';
  if (isActive) {
    borderClass = 'border-[#388bfd]';
  } else if (isSectionStart) {
    borderClass = 'border-green-500';
  } else if (isSectionEnd) {
    borderClass = 'border-red-500';
  }

  return (
    <div className="relative">
      {isSectionStart && repeatActive && (
        <span className="absolute left-0.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-green-500 text-white text-[10px] flex items-center justify-center font-bold z-10">A</span>
      )}
      {isSectionEnd && repeatActive && (
        <span className="absolute left-0.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center font-bold z-10">B</span>
      )}
      <p
        ref={sentenceRef}
        className={`text-sm leading-relaxed py-[5px] rounded-md border-l-[3px] mb-0.5 cursor-pointer transition-all duration-300 ${
          (isSectionStart || isSectionEnd) && repeatActive ? 'pl-6 pr-2' : 'px-2'
        } ${
          isActive
            ? `bg-[rgba(56,139,253,0.12)] ${borderClass} text-[#e6edf3]`
            : isPast
            ? `${borderClass} text-[#e6edf3] opacity-30`
            : `${borderClass} text-[#e6edf3]`
        } ${isSectionStart && !isActive && repeatActive ? 'bg-green-500/10' : ''} ${isSectionEnd && !isActive && repeatActive ? 'bg-red-500/10' : ''} ${isInSection && !isActive && !isSectionStart && !isSectionEnd ? 'bg-green-500/[0.06]' : ''}`}
        style={isActive ? { textShadow: '0 0 12px rgba(56,139,253,0.25)' } : undefined}
        onClick={() => onClick(index)}
      >
        {text}
      </p>
    </div>
  );
}

// 목차 항목 (리더 뷰)
interface TocItemRowProps {
  item: TocItem;
  index: number;
  offset: number;
  currentIndex: number;
  sentenceRef: (el: HTMLElement | null) => void;
  onClick: (index: number) => void;
  repeatStart: number | null;
  repeatEnd: number | null;
  repeatActive: boolean;
}

function TocItemRow({ item, index, offset, currentIndex, sentenceRef, onClick, repeatStart, repeatEnd, repeatActive }: TocItemRowProps) {
  const globalIndex = offset + index;
  const isActive = globalIndex === currentIndex;
  const isPast = globalIndex < currentIndex;
  const isSectionStart = repeatStart !== null && globalIndex === repeatStart;
  const isSectionEnd = repeatEnd !== null && globalIndex === repeatEnd;
  const isInSection = repeatActive && repeatStart !== null && repeatEnd !== null && globalIndex >= repeatStart && globalIndex <= repeatEnd;

  let borderClass = 'border-transparent';
  if (isActive) {
    borderClass = 'border-[#388bfd]';
  } else if (isSectionStart) {
    borderClass = 'border-green-500';
  } else if (isSectionEnd) {
    borderClass = 'border-red-500';
  }

  return (
    <div className="relative">
      {isSectionStart && repeatActive && (
        <span className="absolute left-0.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-green-500 text-white text-[10px] flex items-center justify-center font-bold z-10">A</span>
      )}
      {isSectionEnd && repeatActive && (
        <span className="absolute left-0.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center font-bold z-10">B</span>
      )}
      <div
        ref={sentenceRef as (el: HTMLDivElement | null) => void}
        className={`flex gap-2 text-sm ${item.indent > 0 ? 'ml-4' : ''} py-[5px] rounded-md border-l-[3px] mb-1.5 cursor-pointer transition-all duration-300 ${
          (isSectionStart || isSectionEnd) && repeatActive ? 'pl-6 pr-2' : 'px-2'
        } ${
          isActive
            ? `bg-[rgba(56,139,253,0.12)] ${borderClass}`
            : isPast
            ? `${borderClass} opacity-30`
            : borderClass
        } ${isSectionStart && !isActive && repeatActive ? 'bg-green-500/10' : ''} ${isSectionEnd && !isActive && repeatActive ? 'bg-red-500/10' : ''} ${isInSection && !isActive && !isSectionStart && !isSectionEnd ? 'bg-green-500/[0.06]' : ''}`}
        onClick={() => onClick(globalIndex)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onClick(globalIndex)}
      >
        <span
          className={`${
            item.indent > 0 ? 'text-emerald-500/20 w-6' : 'text-emerald-500/40 w-5'
          } text-[10px] font-mono mt-1 shrink-0 text-right`}
        >
          {item.number}
        </span>
        <span className="text-[#e6edf3]">{item.text}</span>
      </div>
    </div>
  );
}

// 웨이브 애니메이션
function WaveAnimation({ isPlaying }: { isPlaying: boolean }) {
  return (
    <div className="flex items-end gap-[1px] h-[12px]">
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className="inline-block w-[2.5px] rounded-sm bg-[#388bfd]"
          style={
            isPlaying
              ? {
                  animation: `lawear-wave 1s ease-in-out infinite`,
                  animationDelay: `${i * 0.12}s`,
                }
              : { height: '3px' }
          }
        />
      ))}
    </div>
  );
}

export function PlayerScreen({ subjectId, fileId, questionId, onBack }: PlayerScreenProps) {
  const {
    state,
    setViewMode,
    setSentenceIndex,
    play,
  } = usePlayer();

  const { isPlaying, currentSentenceIndex, viewMode, currentSubjectId, currentFileId, currentQuestionId, repeatSectionStart, repeatSectionEnd, isRepeatingSectionActive, level } = state;

  // 표시할 데이터 결정:
  // - props(subjectId, fileId, questionId)는 "사용자가 클릭한 케이스"를 의미.
  // - 자동 다음곡 전환 시 context의 currentXxxId가 props보다 앞서 변경됨.
  //   이때는 context를 우선 사용해야 PlayerScreen 내용이 자동으로 업데이트됨.
  // - 취약재생 등 크로스 과목 playlist의 경우 과목이 달라도 context를 우선해야 함.
  //
  // 해결: playlist 재생 중이고 context의 currentQuestionId가 playlist에 존재하면
  // context를 우선 사용. 단, props와 context가 동일하면 그대로 props 사용.
  const { playlist } = state;
  const displaySubjectId = useMemo(() => {
    if (currentSubjectId && currentQuestionId && currentQuestionId !== questionId) {
      const inPlaylist = playlist.some((item) => item.questionId === currentQuestionId);
      if (inPlaylist) {
        return currentSubjectId;
      }
    }
    return subjectId;
  }, [currentSubjectId, subjectId, currentQuestionId, questionId, playlist]);

  const displayFileId = useMemo(() => {
    if (currentFileId && currentQuestionId && currentQuestionId !== questionId) {
      const inPlaylist = playlist.some((item) => item.questionId === currentQuestionId);
      if (inPlaylist) {
        return currentFileId;
      }
    }
    return fileId;
  }, [currentFileId, fileId, currentQuestionId, questionId, playlist]);

  const displayQuestionId = useMemo(() => {
    if (currentQuestionId && currentQuestionId !== questionId) {
      const inPlaylist = playlist.some((item) => item.questionId === currentQuestionId);
      if (inPlaylist) {
        return currentQuestionId;
      }
    }
    return questionId;
  }, [currentQuestionId, questionId, playlist]);

  // 아코디언 상태
  const [accordion, setAccordion] = useState({
    problem: true,
    toc: true,
    answer: true,
  });

  // 데이터 로드 (PlayerContext state 기반)
  const subject = subjects.find((s) => s.id === displaySubjectId);
  const fileGroup = subject?.files.find((f) => f.id === displayFileId);
  const question = fileGroup?.questions.find((q) => q.id === displayQuestionId);

  // 플레이어 초기화 (처음 마운트 시 또는 문제/레벨 변경 시)
  // 단, playSelected/playSubject 등으로 이미 재생 중이고 playlist에 해당 문제가 있으면
  // selectQuestion을 호출하지 않는다 (selectQuestion은 isPlaying=false로 만들어 재생을 중단시킴)
  const prevLevelRef = useRef(level);

  useEffect(() => {
    const levelChanged = prevLevelRef.current !== level;
    prevLevelRef.current = level;

    if (levelChanged) {
      // 사용자 확정 스펙: "같은 케이스 Lv 전환 → 새 Lv로 처음부터 재생"
      log.nav('level_change_replay', { subjectId, fileId, questionId, level });
      play(subjectId, fileId, questionId);
      return;
    }

    log.nav('player_open', { subjectId, fileId, questionId });
    const isAlreadyPlayingThis =
      state.isPlaying &&
      state.playlist.length > 0 &&
      state.playlist.some(
        (item) =>
          item.subjectId === subjectId &&
          item.fileId === fileId &&
          item.questionId === questionId,
      ) &&
      state.currentQuestionId === questionId;
    if (!isAlreadyPlayingThis) {
      // 케이스 클릭 = 즉시 재생 (MP3 플레이어 방식)
      play(subjectId, fileId, questionId);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjectId, fileId, questionId, level]);

  // 문장 ref 맵
  const sentenceRefs = useRef<Map<number, HTMLElement | null>>(new Map());

  // 현재 문장 자동 스크롤
  useEffect(() => {
    const el = sentenceRefs.current.get(currentSentenceIndex);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [currentSentenceIndex]);

  if (!question || !subject || !fileGroup) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]">
        <p className="text-[#8b949e]">콘텐츠를 찾을 수 없습니다.</p>
      </div>
    );
  }

  const { problem, toc, answer, answer_lv2, answer_lv3 } = question.content;

  // level에 따라 표시할 답안 배열 결정
  const displayAnswer: string[] = (() => {
    if (level === 2 && answer_lv2 && answer_lv2.length > 0) return answer_lv2;
    if (level === 3 && answer_lv3 && answer_lv3.length > 0) return answer_lv3;
    return answer;
  })();

  // 전체 문장 배열 (가사 뷰용)
  const allSentences: string[] = [
    ...problem,
    ...toc.map((t) => `${t.number}. ${t.text}`),
    ...displayAnswer,
  ];

  // 섹션별 오프셋
  const tocOffset = problem.length;
  const answerOffset = problem.length + toc.length;

  const setRef = (globalIndex: number) => (el: HTMLElement | null) => {
    sentenceRefs.current.set(globalIndex, el);
  };

  return (
    <div
      className="absolute inset-0 flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1e3a5f 0%, #0d1117 50%)' }}
    >
      {/* 상단 헤더 */}
      <header className="px-4 pt-4 pb-2 flex items-center justify-between shrink-0">
        <button
          className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center shrink-0"
          onClick={onBack}
          aria-label="뒤로가기"
        >
          <svg
            className="w-4 h-4 text-white/60"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <div className="text-center">
          <p className="text-[10px] text-[#8b949e] uppercase tracking-widest">
            {subject.shortName} · {fileGroup.name}
          </p>
          <p className="text-xs font-semibold text-white">{question.label}</p>
        </div>
        <div className="flex items-center gap-2">
          <WaveAnimation isPlaying={isPlaying} />
        </div>
      </header>

      {/* 뷰 모드 토글 */}
      <div className="px-4 py-2 flex gap-2 shrink-0">
        {(['reader', 'lyrics'] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold text-center transition-all ${
              viewMode === mode
                ? 'bg-[rgba(56,139,253,0.15)] text-[#58a6ff]'
                : 'text-[#8b949e]'
            }`}
            onClick={() => setViewMode(mode)}
          >
            {mode === 'reader' ? (
              <>
                <svg
                  className="w-3.5 h-3.5 inline mr-1 -mt-0.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h12"
                  />
                </svg>
                리더
              </>
            ) : (
              <>
                <svg
                  className="w-3.5 h-3.5 inline mr-1 -mt-0.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                  />
                </svg>
                가사
              </>
            )}
          </button>
        ))}
      </div>

      {/* 리더 뷰 */}
      {viewMode === 'reader' && (
        <div className="flex-1 overflow-y-auto px-4 pb-44">
          {/* 문제 아코디언 */}
          <AccordionSection
            isOpen={accordion.problem}
            onToggle={() => setAccordion((prev) => ({ ...prev, problem: !prev.problem }))}
            badge="Q"
            badgeColorClass="bg-blue-500/20 text-blue-400"
            labelColorClass="text-blue-400"
            label="문제"
          >
            <div className="space-y-0.5 pb-3">
              {problem.map((text, i) => (
                <Sentence
                  key={i}
                  text={text}
                  index={i}
                  currentIndex={currentSentenceIndex}
                  sentenceRef={setRef(i) as (el: HTMLParagraphElement | null) => void}
                  onClick={setSentenceIndex}
                  repeatStart={repeatSectionStart}
                  repeatEnd={repeatSectionEnd}
                  repeatActive={isRepeatingSectionActive}
                />
              ))}
            </div>
          </AccordionSection>

          {/* 목차 아코디언 */}
          <AccordionSection
            isOpen={accordion.toc}
            onToggle={() => setAccordion((prev) => ({ ...prev, toc: !prev.toc }))}
            badge="i"
            badgeColorClass="bg-emerald-500/20 text-emerald-400"
            labelColorClass="text-emerald-400"
            label="목차"
          >
            <div className="space-y-1.5 pb-3 text-sm">
              {toc.map((item, i) => (
                <TocItemRow
                  key={i}
                  item={item}
                  index={i}
                  offset={tocOffset}
                  currentIndex={currentSentenceIndex}
                  sentenceRef={setRef(tocOffset + i)}
                  onClick={setSentenceIndex}
                  repeatStart={repeatSectionStart}
                  repeatEnd={repeatSectionEnd}
                  repeatActive={isRepeatingSectionActive}
                />
              ))}
            </div>
          </AccordionSection>

          {/* 답안 아코디언 */}
          <AccordionSection
            isOpen={accordion.answer}
            onToggle={() => setAccordion((prev) => ({ ...prev, answer: !prev.answer }))}
            badge="A"
            badgeColorClass="bg-amber-500/20 text-amber-400"
            labelColorClass="text-amber-400"
            label="답안"
          >
            <div className="space-y-0.5 pb-3">
              {displayAnswer.map((text, i) => {
                const globalIndex = answerOffset + i;
                const isActive = globalIndex === currentSentenceIndex;
                const isPast = globalIndex < currentSentenceIndex;
                const isSectionStart = repeatSectionStart !== null && globalIndex === repeatSectionStart;
                const isSectionEnd = repeatSectionEnd !== null && globalIndex === repeatSectionEnd;
                const isInSection = isRepeatingSectionActive && repeatSectionStart !== null && repeatSectionEnd !== null && globalIndex >= repeatSectionStart && globalIndex <= repeatSectionEnd;

                let borderClass = 'border-transparent';
                if (isActive) {
                  borderClass = 'border-[#388bfd]';
                } else if (isSectionStart) {
                  borderClass = 'border-green-500';
                } else if (isSectionEnd) {
                  borderClass = 'border-red-500';
                }

                return (
                  <div key={i} className="relative">
                    {isSectionStart && isRepeatingSectionActive && (
                      <span className="absolute left-0.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-green-500 text-white text-[10px] flex items-center justify-center font-bold z-10">A</span>
                    )}
                    {isSectionEnd && isRepeatingSectionActive && (
                      <span className="absolute left-0.5 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center font-bold z-10">B</span>
                    )}
                    <p
                      ref={setRef(globalIndex) as (el: HTMLParagraphElement | null) => void}
                      className={`text-sm leading-relaxed py-[5px] rounded-md border-l-[3px] mb-0.5 cursor-pointer transition-all duration-300 ${
                        (isSectionStart || isSectionEnd) && isRepeatingSectionActive ? 'pl-6 pr-2' : 'px-2'
                      } ${
                        i === 0 ? 'font-medium text-white/90' : ''
                      } ${
                        isActive
                          ? `bg-[rgba(56,139,253,0.12)] ${borderClass} text-[#e6edf3]`
                          : isPast
                          ? `${borderClass} text-[#e6edf3] opacity-30`
                          : `${borderClass} text-[#e6edf3]`
                      } ${isSectionStart && !isActive && isRepeatingSectionActive ? 'bg-green-500/10' : ''} ${isSectionEnd && !isActive && isRepeatingSectionActive ? 'bg-red-500/10' : ''} ${isInSection && !isActive && !isSectionStart && !isSectionEnd ? 'bg-green-500/[0.06]' : ''}`}
                      style={isActive ? { textShadow: '0 0 12px rgba(56,139,253,0.25)' } : undefined}
                      onClick={() => setSentenceIndex(globalIndex)}
                    >
                      {text}
                    </p>
                  </div>
                );
              })}
            </div>
          </AccordionSection>
        </div>
      )}

      {/* 가사 뷰 */}
      {viewMode === 'lyrics' && (
        <div className="flex-1 overflow-y-auto px-5 pb-44">
          <div className="space-y-4 text-center py-8">
            {allSentences.map((text, i) => {
              const isActive = i === currentSentenceIndex;
              const isPast = i < currentSentenceIndex;
              const isInSection = isRepeatingSectionActive && repeatSectionStart !== null && repeatSectionEnd !== null && i >= repeatSectionStart && i <= repeatSectionEnd;
              const isSectionBoundary = (repeatSectionStart !== null && i === repeatSectionStart) || (repeatSectionEnd !== null && i === repeatSectionEnd);

              const isSectionStart = repeatSectionStart !== null && i === repeatSectionStart;
              const isSectionEnd = repeatSectionEnd !== null && i === repeatSectionEnd;

              return (
                <div key={i} className="relative">
                  {isSectionStart && isRepeatingSectionActive && (
                    <span className="absolute -left-1 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-green-500 text-white text-[10px] flex items-center justify-center font-bold z-10">A</span>
                  )}
                  {isSectionEnd && isRepeatingSectionActive && (
                    <span className="absolute -left-1 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center font-bold z-10">B</span>
                  )}
                  <p
                    ref={setRef(i) as (el: HTMLParagraphElement | null) => void}
                    className={`text-sm leading-relaxed transition-all duration-300 cursor-pointer py-2 ${
                      isActive
                        ? 'text-white font-semibold'
                        : isPast
                        ? 'opacity-20'
                        : 'opacity-40'
                    } ${isSectionStart && !isActive && isRepeatingSectionActive ? 'bg-green-500/10 rounded-md' : ''} ${isSectionEnd && !isActive && isRepeatingSectionActive ? 'bg-red-500/10 rounded-md' : ''} ${isInSection && !isActive && !isSectionStart && !isSectionEnd ? 'bg-green-500/[0.06] rounded-md' : ''} ${isSectionBoundary && !isActive ? 'ring-1 ring-green-500/30 rounded-md' : ''}`}
                    style={
                      isActive
                        ? {
                            fontSize: '1.1rem',
                            transform: 'scale(1.03)',
                            textShadow: '0 0 16px rgba(56,139,253,0.4)',
                          }
                        : undefined
                    }
                    onClick={() => setSentenceIndex(i)}
                  >
                    {text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 웨이브 keyframe 인라인 스타일 */}
      <style>{`
        @keyframes lawear-wave {
          0%, 100% { height: 3px; }
          50% { height: 12px; }
        }
      `}</style>
    </div>
  );
}

