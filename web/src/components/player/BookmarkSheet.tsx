import { useState, useEffect, useCallback } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';
import {
  loadBookmarks,
  addBookmark,
  deleteBookmark,
  type Bookmark,
} from '../../services/bookmark';

interface BookmarkSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

export function BookmarkSheet({ isOpen, onClose }: BookmarkSheetProps) {
  const { state, setSentenceIndex, jumpToPlaylistIndex, playSelected } = usePlayer();
  const {
    currentSubjectId,
    currentFileId,
    currentQuestionId,
    currentSentenceIndex,
    playlist,
  } = state;

  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [savedId, setSavedId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setBookmarks(loadBookmarks());
  }, []);

  useEffect(() => {
    if (isOpen) refresh();
  }, [isOpen, refresh]);

  // 현재 재생 위치 북마크 추가
  const handleAdd = useCallback(() => {
    if (!currentSubjectId || !currentFileId || !currentQuestionId) return;

    const sub = subjects.find((s) => s.id === currentSubjectId);
    const file = sub?.files.find((f) => f.id === currentFileId);
    const q = file?.questions.find((qq) => qq.id === currentQuestionId);
    if (!q) return;

    const newBm = addBookmark({
      questionId: currentQuestionId,
      subjectId: currentSubjectId,
      fileId: currentFileId,
      sentenceIndex: currentSentenceIndex,
      label: q.label,
    });
    setSavedId(newBm.id);
    setTimeout(() => setSavedId(null), 1500);
    refresh();
  }, [currentSubjectId, currentFileId, currentQuestionId, currentSentenceIndex, refresh]);

  // 북마크 위치로 이동
  const handleJump = useCallback(
    (bm: Bookmark) => {
      // 플레이리스트에서 해당 문제 찾기
      const idx = playlist.findIndex(
        (item) =>
          item.subjectId === bm.subjectId &&
          item.fileId === bm.fileId &&
          item.questionId === bm.questionId,
      );
      if (idx >= 0) {
        jumpToPlaylistIndex(idx);
        // 문장 이동은 약간 딜레이 후 (트랙 전환 완료 대기)
        setTimeout(() => setSentenceIndex(bm.sentenceIndex), 100);
      } else if (
        bm.questionId === currentQuestionId
      ) {
        // 이미 같은 문제 재생 중이면 문장만 이동
        setSentenceIndex(bm.sentenceIndex);
      }
      onClose();
    },
    [playlist, jumpToPlaylistIndex, setSentenceIndex, currentQuestionId, onClose],
  );

  // 전체 북마크 순차 재생 (중복 문제 제거, 북마크 순서 유지)
  const handlePlayAll = useCallback(() => {
    if (bookmarks.length === 0) return;
    const seen = new Set<string>();
    const items = bookmarks
      .filter((bm) => {
        const key = `${bm.subjectId}|${bm.fileId}|${bm.questionId}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .map((bm) => ({
        subjectId: bm.subjectId,
        fileId: bm.fileId,
        questionId: bm.questionId,
      }));
    if (items.length === 0) return;
    playSelected(items);
    // 첫 번째 북마크 문장으로 이동 (약간 딜레이)
    const first = bookmarks[0];
    setTimeout(() => setSentenceIndex(first.sentenceIndex), 100);
    onClose();
  }, [bookmarks, playSelected, setSentenceIndex, onClose]);

  const handleDelete = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      deleteBookmark(id);
      refresh();
    },
    [refresh],
  );

  if (!isOpen) return null;

  const hasContent = !!currentQuestionId;

  return (
    <>
      {/* backdrop */}
      <div className="fixed inset-0 bg-black/40 z-[60]" onClick={onClose} />
      {/* sheet */}
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d] max-h-[70vh] flex flex-col">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3 shrink-0" />
        <div className="px-5 pt-3 pb-2 flex items-center justify-between shrink-0">
          <h3 className="text-sm font-bold text-white">
            북마크
            <span className="text-[#8b949e] font-normal ml-2">{bookmarks.length}개</span>
          </h3>
          <div className="flex items-center gap-2">
            {/* 전체 재생 버튼 */}
            {bookmarks.length > 0 && (
              <button
                className="text-xs px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1 active:bg-amber-500/20 transition-colors"
                onClick={handlePlayAll}
                aria-label="전체 북마크 순차 재생"
              >
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
                전체 재생
              </button>
            )}
            {/* 현재 위치 북마크 추가 버튼 */}
            <button
              className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
                savedId
                  ? 'bg-amber-500/20 text-amber-400'
                  : hasContent
                  ? 'bg-white/5 text-[#8b949e] active:bg-white/10'
                  : 'text-[#8b949e]/30'
              }`}
              onClick={handleAdd}
              disabled={!hasContent}
              aria-label="현재 위치 북마크 추가"
            >
              {savedId ? '저장됨' : '+ 현재 위치'}
            </button>
            <button className="text-xs text-[#8b949e] px-2 py-1" onClick={onClose}>
              닫기
            </button>
          </div>
        </div>

        {/* 북마크 목록 */}
        <div className="flex-1 overflow-y-auto px-3 pb-6">
          {bookmarks.length === 0 ? (
            <div className="text-center py-10">
              <p className="text-[#8b949e] text-sm">저장된 북마크가 없습니다</p>
              <p className="text-[#8b949e]/50 text-[11px] mt-1.5">
                재생 중 🔖 버튼으로 현재 문장을 저장하세요
              </p>
            </div>
          ) : (
            (() => {
              // 과목별 그룹화
              const grouped: { subjectId: string; subjectName: string; items: typeof bookmarks }[] = [];
              const subjectOrder: string[] = [];
              const subjectMap = new Map<string, typeof bookmarks>();
              for (const bm of bookmarks) {
                if (!subjectMap.has(bm.subjectId)) {
                  subjectMap.set(bm.subjectId, []);
                  subjectOrder.push(bm.subjectId);
                }
                subjectMap.get(bm.subjectId)!.push(bm);
              }
              for (const sid of subjectOrder) {
                const sub = subjects.find((s) => s.id === sid);
                grouped.push({
                  subjectId: sid,
                  subjectName: sub ? sub.name : sid,
                  items: subjectMap.get(sid)!,
                });
              }

              return grouped.map((group) => (
                <div key={group.subjectId} className="mb-3">
                  {/* 과목 헤더 */}
                  <div className="px-3 py-1.5 mb-1">
                    <span className="text-[10px] font-bold text-[#8b949e]/60 uppercase tracking-wider">
                      {group.subjectName}
                    </span>
                  </div>
                  {group.items.map((bm) => {
                    const isCurrentQuestion = bm.questionId === currentQuestionId;
                    return (
                      <button
                        key={bm.id}
                        className="w-full text-left px-3 py-2.5 rounded-lg mb-1 flex items-center gap-3 active:bg-white/5 transition-colors"
                        onClick={() => handleJump(bm)}
                      >
                        {/* 북마크 아이콘 */}
                        <span
                          className={`text-sm shrink-0 ${
                            isCurrentQuestion ? 'text-amber-400' : 'text-[#8b949e]/50'
                          }`}
                        >
                          🔖
                        </span>

                        {/* 정보 */}
                        <div className="flex-1 min-w-0">
                          <p
                            className={`text-sm truncate ${
                              isCurrentQuestion ? 'text-amber-400 font-semibold' : 'text-white'
                            }`}
                          >
                            {bm.label}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-[#8b949e]/40">
                              {bm.sentenceIndex + 1}번째 문장
                            </span>
                            <span className="text-[10px] text-[#8b949e]/30">
                              {formatBookmarkDate(bm.createdAt)}
                            </span>
                          </div>
                        </div>

                        {/* ▶ 재생 힌트 아이콘 */}
                        <span className={`shrink-0 ${isCurrentQuestion ? 'text-amber-400' : 'text-[#8b949e]/30'}`}>
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M8 5v14l11-7z" />
                          </svg>
                        </span>

                        {/* 삭제 버튼 (항상 표시) */}
                        <button
                          className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full text-[#8b949e]/40 active:text-red-400 active:bg-red-500/10 transition-colors"
                          onClick={(e) => handleDelete(bm.id, e)}
                          aria-label="북마크 삭제"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </button>
                    );
                  })}
                </div>
              ));
            })()
          )}
        </div>
      </div>
    </>
  );
}

function formatBookmarkDate(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '방금';
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}시간 전`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD}일 전`;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
