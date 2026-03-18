import { useState, useEffect, useRef, useMemo } from 'react';
import { subjects } from '../../data/ttsData';
import { usePlayer } from '../../context/PlayerContext';
import { log } from '../../services/logger';
import { loadFavorites, addItemToFavorite } from '../../services/favoritePlaylist';
import { loadProgress, formatDate } from '../../services/learningProgress';
import { loadWeakMarks, toggleWeakMark } from '../../services/weakMark';
import type { FavoritePlaylist } from '../../services/favoritePlaylist';
import type { ProgressMap } from '../../services/learningProgress';
import type { Level, FileGroup, Question, PlaylistItem } from '../../types';

interface ListScreenProps {
  subjectId: string;
  onBack: () => void;
  onSelectQuestion: (subjectId: string, fileId: string, questionId: string) => void;
  onOpenFavorites?: () => void;
}

const LEVEL_LABELS: Record<Level, { short: string; long: string; ready: boolean }> = {
  1: { short: 'Lv.1', long: '빠른복습', ready: true },
  2: { short: 'Lv.2', long: '핵심요약', ready: true },
  3: { short: 'Lv.3', long: '슈퍼심플', ready: true },
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
  progressMap: ProgressMap;
  weakMarks: Set<string>;
  onToggleWeak: (questionId: string) => void;
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
  progressMap,
  weakMarks,
  onToggleWeak,
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

                  {/* 재생 상태 / 시간 / 진도 / 취약 */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {/* 진도 표시 */}
                    {(() => {
                      const prog = progressMap[question.id];
                      if (!prog) return null;
                      return (
                        <span className="text-[10px] text-[#8b949e]/70 leading-none">
                          {prog.playCount}회
                          {prog.completedAt ? ` · ${formatDate(prog.completedAt)}` : ''}
                        </span>
                      );
                    })()}
                    {/* 취약 마킹 아이콘 */}
                    {weakMarks.has(question.id) && (
                      <span className="text-[11px] leading-none">🚩</span>
                    )}
                    <span className="text-[11px] text-[#8b949e]">{question.duration}</span>
                    {isNowPlaying && (
                      <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                      </div>
                    )}
                    {/* 취약 마킹 토글 버튼 (롱탭 대신 작은 버튼) */}
                    {!selectMode && (
                      <button
                        className="w-6 h-6 flex items-center justify-center opacity-30 active:opacity-100 transition-opacity"
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleWeak(question.id);
                        }}
                        aria-label="취약 마킹 토글"
                      >
                        <svg className="w-3.5 h-3.5 text-[#8b949e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21l1.9-5.7a8.5 8.5 0 113.8 3.8L3 21" />
                        </svg>
                      </button>
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
  const [showAddToSheet, setShowAddToSheet] = useState(false);

  // 진도 + 취약 마킹 (조회용)
  const [progressMap, setProgressMap] = useState<ProgressMap>(() => loadProgress());
  const [weakMarks, setWeakMarks] = useState<Set<string>>(() => loadWeakMarks());

  // 탭 포커스 시 최신 데이터 리로드
  useEffect(() => {
    const refresh = () => {
      setProgressMap(loadProgress());
      setWeakMarks(loadWeakMarks());
    };
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, []);

  const handleToggleWeak = (questionId: string) => {
    toggleWeakMark(questionId);
    setWeakMarks(loadWeakMarks());
  };

  // 검색 상태
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchQuery]);

  // 검색 결과
  interface SearchResult {
    subjectId: string;
    fileId: string;
    questionId: string;
    label: string;
    matchedText: string;
    matchStart: number;
    matchEnd: number;
  }

  const searchResults = useMemo<SearchResult[]>(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) return [];
    const query = debouncedQuery.toLowerCase();
    const results: SearchResult[] = [];
    for (const subj of subjects) {
      for (const file of subj.files) {
        for (const q of file.questions) {
          const { problem, toc, answer } = q.content;
          const allTexts = [
            ...problem,
            ...toc.map((t) => t.text),
            ...answer,
          ];
          for (const text of allTexts) {
            const idx = text.toLowerCase().indexOf(query);
            if (idx !== -1) {
              results.push({
                subjectId: subj.id,
                fileId: file.id,
                questionId: q.id,
                label: q.label,
                matchedText: text,
                matchStart: idx,
                matchEnd: idx + query.length,
              });
              break; // 케이스당 1개만
            }
          }
        }
      }
    }
    return results;
  }, [debouncedQuery]);

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
        {/* 검색 버튼 */}
        <button
          className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
            showSearch ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-white/60'
          }`}
          onClick={() => {
            setShowSearch((v) => !v);
            setSearchQuery('');
            setDebouncedQuery('');
            if (!showSearch) {
              setTimeout(() => searchInputRef.current?.focus(), 50);
            }
          }}
          aria-label="검색"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </button>
      </header>

      {/* 검색 입력 */}
      {showSearch && (
        <div className="px-4 pb-3 shrink-0">
          <div className="flex items-center gap-2 bg-[#161b22] border border-[#21262d] rounded-xl px-3 py-2">
            <svg className="w-3.5 h-3.5 text-[#8b949e] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="가사 검색..."
              className="flex-1 bg-transparent text-sm text-white placeholder-[#8b949e]/50 outline-none"
              autoComplete="off"
            />
            {searchQuery && (
              <button
                className="text-[#8b949e] text-xs"
                onClick={() => { setSearchQuery(''); setDebouncedQuery(''); }}
                aria-label="검색어 지우기"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      )}

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
              onClick={() => { if (LEVEL_LABELS[lv].ready) setLevel(lv); }}
              disabled={!LEVEL_LABELS[lv].ready}
            >
              <span className="block text-[13px] font-bold">{LEVEL_LABELS[lv].short}</span>
              <span className="block text-[10px] opacity-60 mt-0.5">
                {LEVEL_LABELS[lv].long}{!LEVEL_LABELS[lv].ready && ' (준비 중)'}
              </span>
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

      {/* 검색 결과 */}
      {showSearch && debouncedQuery.length >= 2 && (
        <div className="flex-1 overflow-y-auto pb-24">
          {searchResults.length === 0 ? (
            <div className="flex items-center justify-center h-32">
              <p className="text-[#8b949e] text-sm">"{debouncedQuery}" 검색 결과 없음</p>
            </div>
          ) : (
            <div className="px-4 space-y-1.5">
              <p className="text-[11px] text-[#8b949e] pb-1">{searchResults.length}개 결과</p>
              {searchResults.map((result) => (
                <button
                  key={`${result.questionId}-${result.matchStart}`}
                  className="w-full text-left bg-[#161b22] border border-[#21262d] rounded-xl px-4 py-3 active:bg-white/[0.06] transition-colors"
                  onClick={() => {
                    log.ui('list_search_select', { questionId: result.questionId });
                    onSelectQuestion(result.subjectId, result.fileId, result.questionId);
                  }}
                >
                  <p className="text-sm text-white font-medium mb-1">{result.label}</p>
                  <p className="text-[11px] text-[#8b949e] leading-relaxed">
                    {result.matchStart > 0 && (
                      <span>…{result.matchedText.slice(Math.max(0, result.matchStart - 20), result.matchStart)}</span>
                    )}
                    <span className="bg-yellow-400/20 text-yellow-300 rounded px-0.5">
                      {result.matchedText.slice(result.matchStart, result.matchEnd)}
                    </span>
                    {result.matchEnd < result.matchedText.length && (
                      <span>{result.matchedText.slice(result.matchEnd, result.matchEnd + 40)}…</span>
                    )}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 파일 그룹 목록 (검색 중이면 숨김) */}
      {!(showSearch && debouncedQuery.length >= 2) && (
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
              progressMap={progressMap}
              weakMarks={weakMarks}
              onToggleWeak={handleToggleWeak}
            />
          ))}
          {subject.files.length === 0 && (
            <div className="flex items-center justify-center h-40">
              <p className="text-[#8b949e] text-sm">아직 콘텐츠가 없습니다.</p>
            </div>
          )}
        </div>
      )}

      {/* 선택 모드 하단 바 */}
      {selectMode && selectedIds.size > 0 && (
        <div
          className="fixed bottom-36 left-0 right-0 max-w-md mx-auto z-[55] px-4 pb-3 flex gap-2"
        >
          <button
            className="flex-1 py-3.5 rounded-xl bg-blue-500 text-white font-bold text-sm flex items-center justify-center gap-2 active:bg-blue-600 transition-colors shadow-lg shadow-blue-500/30"
            onClick={handlePlaySelected}
          >
            <PlayIcon className="w-4 h-4" />
            {selectedIds.size}개 재생
          </button>
          <button
            className="py-3.5 px-4 rounded-xl bg-amber-500/15 border border-amber-500/20 text-amber-400 font-bold text-sm flex items-center justify-center gap-1.5 active:bg-amber-500/25 transition-colors"
            onClick={() => setShowAddToSheet(true)}
          >
            ★ 추가
          </button>
        </div>
      )}

      {/* 플레이리스트에 추가 바텀시트 */}
      {showAddToSheet && (
        <AddToPlaylistSheet
          subjectId={subjectId}
          selectedIds={selectedIds}
          onClose={() => setShowAddToSheet(false)}
          onDone={() => { setShowAddToSheet(false); setSelectMode(false); setSelectedIds(new Set()); }}
        />
      )}

    </div>
  );
}

// ── 플레이리스트에 추가 바텀시트 ────────────────────────────────────────────
interface AddToPlaylistSheetProps {
  subjectId: string;
  selectedIds: Set<string>;
  onClose: () => void;
  onDone: () => void;
}

function AddToPlaylistSheet({ subjectId, selectedIds, onClose, onDone }: AddToPlaylistSheetProps) {
  const favorites = loadFavorites();
  const subject = subjects.find((s) => s.id === subjectId);

  const handleAdd = (fav: FavoritePlaylist) => {
    if (!subject) return;
    let added = 0;
    for (const file of subject.files) {
      for (const q of file.questions) {
        if (selectedIds.has(q.id)) {
          addItemToFavorite(fav.id, { subjectId, fileId: file.id, questionId: q.id });
          added++;
        }
      }
    }
    log.ui('list_add_to_favorite', { favId: fav.id, added });
    onDone();
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-[60]" onClick={onClose} />
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d] max-h-[50vh] flex flex-col">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3 shrink-0" />
        <div className="px-5 pt-3 pb-2 flex items-center justify-between shrink-0">
          <h3 className="text-sm font-bold text-white">
            플레이리스트에 추가
            <span className="text-[#8b949e] font-normal ml-2">{selectedIds.size}곡</span>
          </h3>
          <button className="text-xs text-[#8b949e] px-2 py-1" onClick={onClose}>닫기</button>
        </div>
        <div className="flex-1 overflow-y-auto px-3 pb-6">
          {favorites.length === 0 ? (
            <p className="text-center text-[#8b949e] text-sm py-8">저장된 플레이리스트가 없습니다</p>
          ) : (
            favorites.map((fav) => (
              <button
                key={fav.id}
                className="w-full text-left px-4 py-3 rounded-lg mb-1 flex items-center gap-3 active:bg-white/5 transition-colors"
                onClick={() => handleAdd(fav)}
              >
                <span className="text-amber-400 text-lg">★</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium truncate">{fav.name}</p>
                  <p className="text-[10px] text-[#8b949e]">{fav.items.length}곡</p>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </>
  );
}
