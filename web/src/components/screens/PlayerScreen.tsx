import { useEffect, useRef, useState } from 'react';
import { subjects } from '../../data/ttsData';
import { usePlayer } from '../../context/PlayerContext';
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
}

function Sentence({ text, index, currentIndex, sentenceRef, onClick }: SentenceProps) {
  const isActive = index === currentIndex;
  const isPast = index < currentIndex;

  return (
    <p
      ref={sentenceRef}
      className={`text-sm leading-relaxed px-2 py-[5px] rounded-md border-l-[3px] mb-0.5 cursor-pointer transition-all duration-300 ${
        isActive
          ? 'bg-[rgba(56,139,253,0.12)] border-[#388bfd] text-[#e6edf3]'
          : isPast
          ? 'border-transparent text-[#e6edf3] opacity-30'
          : 'border-transparent text-[#e6edf3]'
      }`}
      style={isActive ? { textShadow: '0 0 12px rgba(56,139,253,0.25)' } : undefined}
      onClick={() => onClick(index)}
    >
      {text}
    </p>
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
}

function TocItemRow({ item, index, offset, currentIndex, sentenceRef, onClick }: TocItemRowProps) {
  const globalIndex = offset + index;
  const isActive = globalIndex === currentIndex;
  const isPast = globalIndex < currentIndex;

  return (
    <div
      ref={sentenceRef as (el: HTMLDivElement | null) => void}
      className={`flex gap-2 text-sm ${item.indent > 0 ? 'ml-4' : ''} px-2 py-[5px] rounded-md border-l-[3px] mb-1.5 cursor-pointer transition-all duration-300 ${
        isActive
          ? 'bg-[rgba(56,139,253,0.12)] border-[#388bfd]'
          : isPast
          ? 'border-transparent opacity-30'
          : 'border-transparent'
      }`}
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
    selectQuestion,
  } = usePlayer();

  const { isPlaying, currentSentenceIndex, viewMode } = state;

  // 아코디언 상태
  const [accordion, setAccordion] = useState({
    problem: true,
    toc: true,
    answer: true,
  });

  // 데이터 로드
  const subject = subjects.find((s) => s.id === subjectId);
  const fileGroup = subject?.files.find((f) => f.id === fileId);
  const question = fileGroup?.questions.find((q) => q.id === questionId);

  // 플레이어 초기화 (처음 마운트 시 또는 문제 변경 시)
  useEffect(() => {
    selectQuestion(subjectId, fileId, questionId);
  }, [subjectId, fileId, questionId, selectQuestion]);

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

  const { problem, toc, answer } = question.content;

  // 전체 문장 배열 (가사 뷰용)
  const allSentences: string[] = [
    ...problem,
    ...toc.map((t) => `${t.number}. ${t.text}`),
    ...answer,
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
              {answer.map((text, i) => {
                const globalIndex = answerOffset + i;
                const isActive = globalIndex === currentSentenceIndex;
                const isPast = globalIndex < currentSentenceIndex;

                return (
                  <p
                    key={i}
                    ref={setRef(globalIndex) as (el: HTMLParagraphElement | null) => void}
                    className={`text-sm leading-relaxed px-2 py-[5px] rounded-md border-l-[3px] mb-0.5 cursor-pointer transition-all duration-300 ${
                      i === 0 ? 'font-medium text-white/90' : ''
                    } ${
                      isActive
                        ? 'bg-[rgba(56,139,253,0.12)] border-[#388bfd] text-[#e6edf3]'
                        : isPast
                        ? 'border-transparent text-[#e6edf3] opacity-30'
                        : 'border-transparent text-[#e6edf3]'
                    }`}
                    style={isActive ? { textShadow: '0 0 12px rgba(56,139,253,0.25)' } : undefined}
                    onClick={() => setSentenceIndex(globalIndex)}
                  >
                    {text}
                  </p>
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

              return (
                <p
                  key={i}
                  ref={setRef(i) as (el: HTMLParagraphElement | null) => void}
                  className={`text-sm leading-relaxed transition-all duration-300 cursor-pointer py-2 ${
                    isActive
                      ? 'text-white font-semibold'
                      : isPast
                      ? 'opacity-20'
                      : 'opacity-40'
                  }`}
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

