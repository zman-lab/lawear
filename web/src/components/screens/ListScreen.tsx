import { useState } from 'react';
import { subjects } from '../../data/ttsData';
import { usePlayer } from '../../context/PlayerContext';
import type { Level, FileGroup, Question } from '../../types';

interface ListScreenProps {
  subjectId: string;
  onBack: () => void;
  onSelectQuestion: (subjectId: string, fileId: string, questionId: string) => void;
}

const LEVEL_LABELS: Record<Level, { short: string; long: string }> = {
  1: { short: 'Lv.1', long: '빠른복습' },
  2: { short: 'Lv.2', long: '인용판례' },
  3: { short: 'Lv.3', long: '풀버전' },
};

function formatTotalDuration(questions: Question[]): string {
  let totalSecs = 0;
  for (const q of questions) {
    const parts = q.duration.split(':').map(Number);
    if (parts.length === 2) {
      totalSecs += (parts[0] ?? 0) * 60 + (parts[1] ?? 0);
    }
  }
  const mins = Math.floor(totalSecs / 60);
  return `${mins}분`;
}

interface FileGroupCardProps {
  fileGroup: FileGroup;
  subjectId: string;
  isExpanded: boolean;
  onToggle: () => void;
  currentQuestionId: string | null;
  currentFileId: string | null;
  onSelectQuestion: (subjectId: string, fileId: string, questionId: string) => void;
}

function FileGroupCard({
  fileGroup,
  subjectId,
  isExpanded,
  onToggle,
  currentQuestionId,
  currentFileId,
  onSelectQuestion,
}: FileGroupCardProps) {
  const isCurrentFile = currentFileId === fileGroup.id;
  const totalDuration = formatTotalDuration(fileGroup.questions);

  return (
    <div className="mx-4 mb-3">
      <div
        className={`bg-[#161b22] border border-[#21262d] rounded-xl overflow-hidden ${
          !isExpanded ? 'bg-[#161b22]/60' : ''
        }`}
      >
        {/* 파일 그룹 헤더 */}
        <div
          className="px-4 py-2.5 flex items-center justify-between cursor-pointer"
          onClick={onToggle}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onToggle()}
        >
          <span className="text-xs font-bold text-[#8b949e]">{fileGroup.name}</span>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[#8b949e]/50">
              {fileGroup.questions.length}개 설문
              {isExpanded ? ` · ${totalDuration}` : ''}
            </span>
            {!isExpanded && (
              <svg
                className="w-3 h-3 text-[#8b949e]/40"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            )}
            {isExpanded && (
              <svg
                className="w-3 h-3 text-[#8b949e]/40 rotate-180"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            )}
          </div>
        </div>

        {/* 설문 목록 (펼쳐진 경우) */}
        {isExpanded && (
          <div className="divide-y divide-[#21262d] border-t border-[#21262d]">
            {fileGroup.questions.map((question, idx) => {
              const isNowPlaying =
                isCurrentFile && currentQuestionId === question.id;

              return (
                <div
                  key={question.id}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors active:bg-white/[0.06] ${
                    isNowPlaying
                      ? 'bg-[rgba(56,139,253,0.08)] border-l-[3px] border-[#388bfd]'
                      : ''
                  }`}
                  onClick={() => onSelectQuestion(subjectId, fileGroup.id, question.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) =>
                    e.key === 'Enter' && onSelectQuestion(subjectId, fileGroup.id, question.id)
                  }
                >
                  {/* 번호 아이콘 */}
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${
                      isNowPlaying
                        ? 'bg-blue-600/20 text-blue-400'
                        : 'bg-white/5 text-[#8b949e]'
                    }`}
                  >
                    {idx + 1}
                  </div>

                  {/* 텍스트 */}
                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm font-medium truncate ${
                        isNowPlaying ? 'text-white' : 'text-white/80'
                      }`}
                    >
                      {question.label}
                    </p>
                    <p className="text-[11px] text-[#8b949e] truncate">{question.subtitle}</p>
                  </div>

                  {/* 재생 상태 / 시간 */}
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[11px] text-[#8b949e]">{question.duration}</span>
                    {isNowPlaying && (
                      <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export function ListScreen({ subjectId, onBack, onSelectQuestion }: ListScreenProps) {
  const subject = subjects.find((s) => s.id === subjectId);
  const { state, setLevel } = usePlayer();
  const { level, currentFileId, currentQuestionId } = state;
  const [expandedFileIds, setExpandedFileIds] = useState<Set<string>>(
    () => new Set(subject?.files[0] ? [subject.files[0].id] : [])
  );

  if (!subject) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]">
        <p className="text-[#8b949e]">과목을 찾을 수 없습니다.</p>
      </div>
    );
  }

  const toggleFile = (fileId: string) => {
    setExpandedFileIds((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        next.add(fileId);
      }
      return next;
    });
  };

  return (
    <div
      className="absolute inset-0 flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1e3a5f 0%, #0d1117 50%)' }}
    >
      {/* 헤더 */}
      <header className="px-4 pt-4 pb-3 flex items-center gap-3 shrink-0">
        <button
          className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center min-w-[32px]"
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
        <div className="flex-1 min-w-0">
          <h2 className="font-bold text-white">{subject.name}</h2>
          <p className="text-[11px] text-[#8b949e]">
            {subject.files.length} 파일 · {subject.totalQuestions} 설문
          </p>
        </div>
      </header>

      {/* 레벨 토글 */}
      <div className="px-4 pb-3 flex gap-2 shrink-0">
        {([1, 2, 3] as Level[]).map((lv) => (
          <button
            key={lv}
            className={`flex-1 py-2 rounded-xl text-center transition-all border ${
              level === lv
                ? 'bg-[rgba(56,139,253,0.2)] text-[#58a6ff] border-[rgba(56,139,253,0.3)]'
                : 'border-[#21262d] text-[#8b949e]'
            }`}
            onClick={() => setLevel(lv)}
          >
            <span className="block text-[13px] font-bold">{LEVEL_LABELS[lv].short}</span>
            <span className="block text-[10px] opacity-60 mt-0.5">{LEVEL_LABELS[lv].long}</span>
          </button>
        ))}
      </div>

      {/* 파일 그룹 목록 */}
      <div className="flex-1 overflow-y-auto pb-24">
        {subject.files.map((fileGroup) => (
          <FileGroupCard
            key={fileGroup.id}
            fileGroup={fileGroup}
            subjectId={subjectId}
            isExpanded={expandedFileIds.has(fileGroup.id)}
            onToggle={() => toggleFile(fileGroup.id)}
            currentQuestionId={currentQuestionId}
            currentFileId={currentFileId}
            onSelectQuestion={onSelectQuestion}
          />
        ))}
        {subject.files.length === 0 && (
          <div className="flex items-center justify-center h-40">
            <p className="text-[#8b949e] text-sm">아직 콘텐츠가 없습니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
