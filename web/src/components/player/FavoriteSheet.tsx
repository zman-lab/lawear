import { useState, useEffect } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';
import { loadFavorites, deleteFavorite } from '../../services/favoritePlaylist';
import type { FavoritePlaylist } from '../../services/favoritePlaylist';

interface FavoriteSheetProps {
  isOpen: boolean;
  onClose: () => void;
  onPlay: () => void;
}

function formatDate(ts: number): string {
  const d = new Date(ts);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${mm}/${dd}`;
}

export function FavoriteSheet({ isOpen, onClose, onPlay }: FavoriteSheetProps) {
  const { playSelected } = usePlayer();
  const [favorites, setFavorites] = useState<FavoritePlaylist[]>([]);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setFavorites(loadFavorites());
      setConfirmDeleteId(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handlePlay = (fav: FavoritePlaylist) => {
    if (fav.items.length === 0) return;
    playSelected(fav.items);
    onPlay();
    onClose();
  };

  const handleDeleteRequest = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(id);
  };

  const handleConfirmDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    deleteFavorite(id);
    setFavorites((prev) => prev.filter((f) => f.id !== id));
    setConfirmDeleteId(null);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(null);
  };

  const getFirstLabel = (fav: FavoritePlaylist): string => {
    const first = fav.items[0];
    if (!first) return '';
    const sub = subjects.find((s) => s.id === first.subjectId);
    const file = sub?.files.find((f) => f.id === first.fileId);
    const q = file?.questions.find((qq) => qq.id === first.questionId);
    return q?.subtitle ?? q?.label ?? first.questionId;
  };

  return (
    <>
      {/* backdrop */}
      <div className="fixed inset-0 bg-black/40 z-[60]" onClick={onClose} />
      {/* sheet */}
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d] max-h-[70vh] flex flex-col">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3 shrink-0" />
        <div className="px-5 pt-3 pb-2 flex items-center justify-between shrink-0">
          <h3 className="text-sm font-bold text-white">
            즐겨찾기
            <span className="text-[#8b949e] font-normal ml-2">{favorites.length}개</span>
          </h3>
          <button className="text-xs text-[#8b949e] px-2 py-1" onClick={onClose}>
            닫기
          </button>
        </div>

        {/* 즐겨찾기 목록 */}
        <div className="flex-1 overflow-y-auto px-3 pb-6">
          {favorites.length === 0 ? (
            <p className="text-center text-[#8b949e] text-sm py-8">
              저장된 즐겨찾기가 없습니다
            </p>
          ) : (
            favorites.map((fav) => {
              const isConfirming = confirmDeleteId === fav.id;
              return (
                <button
                  key={fav.id}
                  className="w-full text-left px-3 py-3 rounded-lg mb-1 flex items-center gap-3 active:bg-white/5 transition-colors"
                  onClick={() => !isConfirming && handlePlay(fav)}
                >
                  {/* 아이콘 */}
                  <div className="w-9 h-9 rounded-xl bg-amber-500/15 flex items-center justify-center shrink-0">
                    <span className="text-amber-400 text-base">★</span>
                  </div>

                  {/* 정보 */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium truncate">{fav.name}</p>
                    <p className="text-[10px] text-[#8b949e] mt-0.5 truncate">
                      {fav.items.length}곡 · {formatDate(fav.createdAt)} · {getFirstLabel(fav)}
                    </p>
                  </div>

                  {/* 삭제 버튼 / 확인 */}
                  {isConfirming ? (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        className="px-2 py-1 rounded-lg bg-red-500/20 text-red-400 text-[11px] font-bold active:bg-red-500/30"
                        onClick={(e) => handleConfirmDelete(fav.id, e)}
                      >
                        삭제
                      </button>
                      <button
                        className="px-2 py-1 rounded-lg bg-white/5 text-[#8b949e] text-[11px] active:bg-white/10"
                        onClick={handleCancelDelete}
                      >
                        취소
                      </button>
                    </div>
                  ) : (
                    <button
                      className="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center text-[#8b949e]/50 active:bg-white/10 shrink-0"
                      onClick={(e) => handleDeleteRequest(fav.id, e)}
                      aria-label="삭제"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
