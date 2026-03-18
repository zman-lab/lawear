import { useState } from 'react';
import { subjects } from '../../data/ttsData';
import { usePlayer } from '../../context/PlayerContext';
import { log } from '../../services/logger';
import type { Level, FileGroup, Question, PlaylistItem } from '../../types';

interface ListScreenProps {
  subjectId: string;
  onBack: () => void;
  onSelectQuestion: (subjectId: string, fileId: string, questionId: string) => void;
  onOpenFavorites?: () => void;
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

// 재생 아이콘 (삼각형)
function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className ?? 'w-4 h-4'} fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

interface FileGroupCardProps {
  fileGroup: FileGroup;
  subjectId: string;
  isExpanded: boolean;
  onToggle: () => void;
  currentQuestionId: string | null;
  currentFileId: string | null;
  onSelectQuestion: (subjectId: string, fileId: string, questionId: string) => void;
  onPlayFile: (subjectId: string, fileId: string) => void;
  selectedIds: Set<string>;
  onToggleSelect: (questionId: string) => void;
  selectMode: boolean;
}

function FileGroupCard({
  fileGroup,
  subjectId,
  isExpanded,
  onToggle,
  currentQuestionId,
  currentFileId,
  onSelectQuestion,
  onPlayFile,
  selectedIds,
  onToggleSelect,
  selectMode,
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
        <div className="px-4 py-2.5 flex items-center justify-between">
          <div
            className="flex-1 cursor-pointer flex items-center gap-2"
            onClick={onToggle}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onToggle()}
          >
            <span className="text-xs font-bold text-[#8b949e]">{fileGroup.name}</span>
            <span className="text-[10px] text-[#8b949e]/50">
              {fileGroup.questions.length}개 설문
              {isExpanded ? ` · ${totalDuration}` : ''}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            {/* 파일 전체 재생 버튼 */}
            <button
              className="w-7 h-7 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400 active:bg-blue-500/20 transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                onPlayFile(subjectId, fileGroup.id);
              }}
              aria-label={`${fileGroup.name} 전체 재생`}
              title="파일 전체 재생"
            >
              <PlayIcon className="w-3.5 h-3.5" />
            </button>
            {/* 펼침/접힘 화살표 */}
            <button
              className="w-7 h-7 flex items-center justify-center"
              onClick={onToggle}
              aria-label={isExpanded ? '접기' : '펼치기'}
            >
              <svg
                className={`w-3 h-3 text-[#8b949e]/40 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
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
            </button>
          </div>
        </div>

        {/* 설문 목록 (펼쳐진 경우) */}
        {isExpanded && (
          <div className="divide-y divide-[#21262d] border-t border-[#21262d]">
            {fileGroup.questions.map((question, idx) => {
              const isNowPlaying =
                isCurrentFile && currentQuestionId === question.id;
              const isSelected = selectedIds.has(question.id);

              return (
                <div
                  key={question.id}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors active:bg-white/[0.06] ${
                    isNowPlaying
                      ? 'bg-[rgba(56,139,253,0.08)] border-l-[3px] border-[#388bfd]'
                      : ''
                  }`}
                  onClick={() => {
                    if (selectMode) {
                      onToggleSelect(question.id);
                    } else {
                      onSelectQuestion(subjectId, fileGroup.id, question.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      if (selectMode) {
                        onToggleSelect(question.id);
                      } else {
                        onSelectQuestion(subjectId, fileGroup.id, question.id);
                      }
                    }
                  }}
                >
                  {/* 선택모드: 체크박스 / 일반모드: 번호 */}
                  {selectMode ? (
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border transition-colors ${
                        isSelected
                          ? 'bg-blue-500/20 border-blue-500/40 text-blue-400'
                          : 'border-[#21262d] text-[#8b949e]/40'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleSelect(question.id);
                      }}
                    >
                      {isSelected && (
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
                        </svg>
                      )}
                    </div>
                  ) : (
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${
                        isNowPlaying
                          ? 'bg-blue-600/20 text-blue-400'
                          : 'bg-white/5 text-[#8b949e]'
                      }`}
                    >
                      {idx + 1}
                    </div>
                  )}

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

export function ListScreen({ subjectId, onBack, onSelectQuestion, onOpenFavorites }: ListScreenProps) {
  const subject = subjects.find((s) => s.id === subjectId);
  const { state, setLevel, playSubject, playFile, playSelected } = usePlayer();
  const { level, currentFileId, currentQuestionId } = state;
  const [expandedFileIds, setExpandedFileIds] = useState<Set<string>>(
    () => new Set(subject?.files[0] ? [subject.files[0].id] : [])
  );

  // 선택 모드
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  if (!subject) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]">
        <p className="text-[#8b949e]">과목을 찾을 수 없습니다.</p>
      </div>
    );
  }

  const toggleFile = (fileId: string) => {
    setExpandedFileIds((prev) => {
      log.ui('list_toggle_file', {fileId, expanded: !prev.has(fileId)});
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        next.add(fileId);
      }
      return next;
    });
  };

  const toggleSelectQuestion = (questionId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  };

  const handlePlaySelected = () => {
    if (selectedIds.size === 0) return;
    log.ui('list_play_selected', {count: selectedIds.size});
    // 선택된 항목들을 파일 순서 유지하여 플레이리스트 생성
    const items: PlaylistItem[] = [];
    const added = new Set<string>();
    for (const file of subject.files) {
      for (const q of file.questions) {
        if (selectedIds.has(q.id) && !added.has(q.id)) {
          items.push({ subjectId, fileId: file.id, questionId: q.id });
          added.add(q.id);
        }
      }
    }
    playSelected(items);
    // 선택재생 시 첫 곡의 PlayerScreen으로 자동 진입
    onSelectQuestion(items[0].subjectId, items[0].fileId, items[0].questionId);
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const handleToggleSelectMode = () => {
    if (selectMode) {
      // 선택 모드 해제
      setSelectMode(false);
      setSelectedIds(new Set());
    } else {
      setSelectMode(true);
    }
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

      {/* 레벨 토글 + 과목 전체 재생 + 선택 모드 */}
      <div className="px-4 pb-3 space-y-2.5 shrink-0">
        {/* 레벨 토글 */}
        <div className="flex gap-2">
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

        {/* 액션 버튼들 */}
        <div className="flex gap-2">
          {/* 과목 전체 재생 */}
          <button
            className="flex-1 py-2.5 rounded-xl bg-blue-500/15 border border-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center gap-1.5 active:bg-blue-500/25 transition-colors"
            onClick={() => { log.ui('list_play_subject', {subjectId}); playSubject(subjectId); }}
          >
            <PlayIcon className="w-3.5 h-3.5" />
            전체 재생
          </button>

          {/* 선택 재생 모드 토글 */}
          <button
            className={`flex-1 py-2.5 rounded-xl border text-xs font-bold flex items-center justify-center gap-1.5 transition-colors ${
              selectMode
                ? 'bg-amber-500/15 border-amber-500/20 text-amber-400 active:bg-amber-500/25'
                : 'bg-white/5 border-[#21262d] text-[#8b949e] active:bg-white/10'
            }`}
            onClick={handleToggleSelectMode}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            {selectMode ? '취소' : '선택 재생'}
          </button>

          {/* 즐겨찾기 */}
          <button
            className="flex-1 py-2.5 rounded-xl border border-[#21262d] bg-white/5 text-[#8b949e] text-xs font-bold flex items-center justify-center gap-1.5 active:bg-white/10 transition-colors"
            onClick={() => { log.ui('list_open_favorites', {subjectId}); onOpenFavorites?.(); }}
          >
            <span className="text-amber-400">★</span>
            즐겨찾기
          </button>
        </div>
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
            onSelectQuestion={(sid, fid, qid) => {
              log.ui('list_select_case', { subjectId: sid, fileId: fid, questionId: qid });
              onSelectQuestion(sid, fid, qid);
            }}
            onPlayFile={(sid, fid) => { log.ui('list_play_file', {subjectId: sid, fileId: fid}); playFile(sid, fid); }}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelectQuestion}
            selectMode={selectMode}
          />
        ))}
        {subject.files.length === 0 && (
          <div className="flex items-center justify-center h-40">
            <p className="text-[#8b949e] text-sm">아직 콘텐츠가 없습니다.</p>
          </div>
        )}
      </div>

      {/* 선택 모드 하단 바 */}
      {selectMode && selectedIds.size > 0 && (
        <div
          className="fixed bottom-36 left-0 right-0 max-w-md mx-auto z-[55] px-4 pb-3"
        >
          <button
            className="w-full py-3.5 rounded-xl bg-blue-500 text-white font-bold text-sm flex items-center justify-center gap-2 active:bg-blue-600 transition-colors shadow-lg shadow-blue-500/30"
            onClick={handlePlaySelected}
          >
            <PlayIcon className="w-4 h-4" />
            {selectedIds.size}개 선택 재생
          </button>
        </div>
      )}

    </div>
  );
}
