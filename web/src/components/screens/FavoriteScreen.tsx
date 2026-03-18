import { useState, useEffect, useRef } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';
import {
  loadFavorites,
  deleteFavorite,
  updateFavoriteName,
  removeItemFromFavorite,
} from '../../services/favoritePlaylist';
import type { FavoritePlaylist } from '../../services/favoritePlaylist';
import type { PlaylistItem } from '../../types';

interface FavoriteScreenProps {
  onBack: () => void;
}

// ── 날짜 포매팅 ──────────────────────────────────────────────────────────────
function formatDate(ts: number): string {
  const d = new Date(ts);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}.${mm}.${dd}`;
}

// ── 곡 정보 조회 헬퍼 ────────────────────────────────────────────────────────
function getQuestionInfo(item: PlaylistItem): { label: string; subtitle: string; duration: string } | null {
  const sub = subjects.find((s) => s.id === item.subjectId);
  if (!sub) return null;
  const file = sub.files.find((f) => f.id === item.fileId);
  if (!file) return null;
  const q = file.questions.find((qq) => qq.id === item.questionId);
  if (!q) return null;
  return { label: q.label, subtitle: q.subtitle, duration: q.duration };
}

// ── 아이콘 컴포넌트들 ─────────────────────────────────────────────────────────
function BackIcon() {
  return (
    <svg className="w-4 h-4 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className ?? 'w-4 h-4'} fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="5" r="1.5" />
      <circle cx="12" cy="12" r="1.5" />
      <circle cx="12" cy="19" r="1.5" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
    </svg>
  );
}

// ── 액션 시트 (⋯ 메뉴 — 바텀시트로 표시하여 짤림 방지) ──────────────────────
interface ActionSheetProps {
  onRename: () => void;
  onDelete: () => void;
  onClose: () => void;
}

function ActionSheet({ onRename, onDelete, onClose }: ActionSheetProps) {
  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-[60]" onClick={onClose} />
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d] pb-8">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3" />
        <button
          className="w-full px-5 py-4 flex items-center gap-3 text-sm text-white active:bg-white/5 transition-colors"
          onClick={() => { onRename(); onClose(); }}
        >
          <span className="text-blue-400"><PencilIcon /></span>
          이름 변경
        </button>
        <div className="h-px bg-[#21262d] mx-4" />
        <button
          className="w-full px-5 py-4 flex items-center gap-3 text-sm text-red-400 active:bg-red-500/10 transition-colors"
          onClick={() => { onDelete(); onClose(); }}
        >
          <TrashIcon />
          삭제
        </button>
      </div>
    </>
  );
}

// ── 이름 변경 모달 ─────────────────────────────────────────────────────────────
interface RenameModalProps {
  initialName: string;
  onConfirm: (name: string) => void;
  onCancel: () => void;
}

function RenameModal({ initialName, onConfirm, onCancel }: RenameModalProps) {
  const [value, setValue] = useState(initialName);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 px-6">
      <div className="w-full max-w-sm bg-[#161b22] border border-[#21262d] rounded-2xl overflow-hidden">
        <div className="px-5 pt-5 pb-3">
          <p className="text-white font-bold text-base mb-3">이름 변경</p>
          <input
            ref={inputRef}
            className="w-full bg-[#0d1117] border border-[#21262d] rounded-xl px-4 py-2.5 text-sm text-white placeholder-[#8b949e] focus:outline-none focus:border-blue-500/50"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && value.trim()) onConfirm(value.trim());
              if (e.key === 'Escape') onCancel();
            }}
            placeholder="플레이리스트 이름"
          />
        </div>
        <div className="flex border-t border-[#21262d]">
          <button
            className="flex-1 py-3.5 text-sm text-[#8b949e] active:bg-white/5 transition-colors"
            onClick={onCancel}
          >
            취소
          </button>
          <div className="w-px bg-[#21262d]" />
          <button
            className="flex-1 py-3.5 text-sm text-blue-400 font-medium active:bg-white/5 transition-colors disabled:opacity-40"
            onClick={() => value.trim() && onConfirm(value.trim())}
            disabled={!value.trim()}
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 삭제 확인 모달 ─────────────────────────────────────────────────────────────
interface DeleteModalProps {
  name: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function DeleteModal({ name, onConfirm, onCancel }: DeleteModalProps) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 px-6">
      <div className="w-full max-w-sm bg-[#161b22] border border-[#21262d] rounded-2xl overflow-hidden">
        <div className="px-5 pt-5 pb-3 space-y-1.5">
          <p className="text-white font-bold text-base">플레이리스트 삭제</p>
          <p className="text-[#8b949e] text-sm">
            <span className="text-white">"{name}"</span>을 삭제하시겠습니까?
          </p>
        </div>
        <div className="flex border-t border-[#21262d]">
          <button
            className="flex-1 py-3.5 text-sm text-[#8b949e] active:bg-white/5 transition-colors"
            onClick={onCancel}
          >
            취소
          </button>
          <div className="w-px bg-[#21262d]" />
          <button
            className="flex-1 py-3.5 text-sm text-red-400 font-medium active:bg-red-500/10 transition-colors"
            onClick={onConfirm}
          >
            삭제
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 목록 뷰 ───────────────────────────────────────────────────────────────────
interface ListViewProps {
  favorites: FavoritePlaylist[];
  onSelect: (fav: FavoritePlaylist) => void;
  onPlay: (fav: FavoritePlaylist, e: React.MouseEvent) => void;
  onRename: (fav: FavoritePlaylist) => void;
  onDelete: (fav: FavoritePlaylist) => void;
}

function ListView({ favorites, onSelect, onPlay, onRename, onDelete }: ListViewProps) {
  const [menuTarget, setMenuTarget] = useState<FavoritePlaylist | null>(null);

  return (
    <>
      <div className="flex-1 overflow-y-auto pb-44 px-4 pt-2 space-y-3">
        {favorites.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <div className="w-14 h-14 rounded-2xl bg-amber-500/10 flex items-center justify-center">
              <span className="text-2xl text-amber-400/50">★</span>
            </div>
            <div className="text-center">
              <p className="text-[#8b949e] text-sm">아직 저장된 플레이리스트가 없습니다</p>
              <p className="text-[#8b949e]/50 text-xs mt-1">선택 재생 후 ★ 버튼으로 저장하세요</p>
            </div>
          </div>
        ) : (
          favorites.map((fav) => (
            <div
              key={fav.id}
              className="relative bg-gradient-to-br from-amber-900/8 to-[#161b22]/90 border border-[#21262d] rounded-xl overflow-hidden active:bg-white/5 transition-colors cursor-pointer"
              onClick={() => onSelect(fav)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSelect(fav)}
            >
              <div className="flex items-center gap-3 px-4 py-3.5">
                <div className="w-10 h-10 rounded-xl bg-amber-500/15 flex items-center justify-center shrink-0">
                  <span className="text-amber-400 text-lg">★</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-bold text-sm truncate">{fav.name}</p>
                  <p className="text-[11px] text-[#8b949e] mt-0.5">
                    {fav.items.length}곡 · {formatDate(fav.createdAt)}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400 active:bg-blue-500/20 transition-colors"
                    onClick={(e) => onPlay(fav, e)}
                    aria-label="전체 재생"
                  >
                    <PlayIcon className="w-3.5 h-3.5" />
                  </button>
                  <button
                    className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-[#8b949e] active:bg-white/10 transition-colors"
                    onClick={(e) => { e.stopPropagation(); setMenuTarget(fav); }}
                    aria-label="메뉴"
                  >
                    <DotsIcon />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* 액션 시트 (바텀시트로 표시 — 짤림 방지) */}
      {menuTarget && (
        <ActionSheet
          onRename={() => onRename(menuTarget)}
          onDelete={() => onDelete(menuTarget)}
          onClose={() => setMenuTarget(null)}
        />
      )}
    </>
  );
}

// ── 상세 뷰 ───────────────────────────────────────────────────────────────────
interface DetailViewProps {
  fav: FavoritePlaylist;
  onBack: () => void;
  onPlayAll: () => void;
  onPlayItem: (idx: number) => void;
  onRemoveItem: (questionId: string) => void;
  onRenameConfirm: (name: string) => void;
  currentQuestionId: string | null;
}

function DetailView({
  fav,
  onBack,
  onPlayAll,
  onPlayItem,
  onRemoveItem,
  onRenameConfirm,
  currentQuestionId,
}: DetailViewProps) {
  const [editMode, setEditMode] = useState(false);
  const [renamingInline, setRenamingInline] = useState(false);
  const [inlineValue, setInlineValue] = useState(fav.name);
  const inlineRef = useRef<HTMLInputElement>(null);

  // fav.name 변경 시 인라인 값 동기화
  useEffect(() => {
    setInlineValue(fav.name);
  }, [fav.name]);

  const handleInlineRenameStart = () => {
    setRenamingInline(true);
    setTimeout(() => {
      inlineRef.current?.focus();
      inlineRef.current?.select();
    }, 50);
  };

  const handleInlineRenameConfirm = () => {
    const trimmed = inlineValue.trim();
    if (trimmed && trimmed !== fav.name) {
      onRenameConfirm(trimmed);
    } else {
      setInlineValue(fav.name);
    }
    setRenamingInline(false);
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* 상세 헤더 */}
      <div className="px-4 pt-3 pb-2 shrink-0">
        {/* 제목 줄 */}
        <div className="flex items-center gap-2 mb-3">
          <button
            className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center shrink-0"
            onClick={onBack}
            aria-label="목록으로"
          >
            <BackIcon />
          </button>

          {renamingInline ? (
            <input
              ref={inlineRef}
              className="flex-1 bg-[#0d1117] border border-blue-500/50 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none"
              value={inlineValue}
              onChange={(e) => setInlineValue(e.target.value)}
              onBlur={handleInlineRenameConfirm}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleInlineRenameConfirm();
                if (e.key === 'Escape') { setInlineValue(fav.name); setRenamingInline(false); }
              }}
            />
          ) : (
            <button
              className="flex-1 text-left text-white font-bold text-[15px] truncate active:opacity-70"
              onClick={handleInlineRenameStart}
              title="탭해서 이름 변경"
            >
              {fav.name}
            </button>
          )}

          {/* 편집 모드 토글 */}
          <button
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors shrink-0 ${
              editMode
                ? 'bg-amber-500/15 border border-amber-500/20 text-amber-400'
                : 'bg-white/5 border border-[#21262d] text-[#8b949e]'
            }`}
            onClick={() => setEditMode(!editMode)}
          >
            {editMode ? '완료' : '편집'}
          </button>
        </div>

        {/* 메타 + 전체재생 */}
        <div className="flex items-center gap-2">
          <p className="text-[11px] text-[#8b949e] flex-1">
            {fav.items.length}곡 · {formatDate(fav.createdAt)}
          </p>
          <button
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-500/15 border border-blue-500/20 text-blue-400 text-xs font-bold active:bg-blue-500/25 transition-colors"
            onClick={onPlayAll}
            disabled={fav.items.length === 0}
          >
            <PlayIcon className="w-3.5 h-3.5" />
            전체 재생
          </button>
        </div>
      </div>

      {/* 곡 목록 */}
      <div className="flex-1 overflow-y-auto pb-44">
        {fav.items.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-[#8b949e] text-sm">곡이 없습니다</p>
          </div>
        ) : (
          <div className="divide-y divide-[#21262d] border-t border-[#21262d] mx-4 bg-[#161b22] rounded-xl overflow-hidden">
            {fav.items.map((item, idx) => {
              const info = getQuestionInfo(item);
              const isNowPlaying = currentQuestionId === item.questionId;
              return (
                <div
                  key={`${item.subjectId}-${item.fileId}-${item.questionId}`}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors active:bg-white/[0.06] ${
                    isNowPlaying
                      ? 'bg-[rgba(56,139,253,0.08)] border-l-[3px] border-[#388bfd]'
                      : ''
                  }`}
                  onClick={() => !editMode && onPlayItem(idx)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !editMode) onPlayItem(idx); }}
                >
                  {/* 번호 */}
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${
                      isNowPlaying ? 'bg-blue-600/20 text-blue-400' : 'bg-blue-500/10 text-[#8b949e]'
                    }`}
                  >
                    {idx + 1}
                  </div>

                  {/* 텍스트 */}
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${isNowPlaying ? 'text-white' : 'text-white/80'}`}>
                      {info?.label ?? item.questionId}
                    </p>
                    <p className="text-[11px] text-[#8b949e] truncate">{info?.subtitle ?? ''}</p>
                  </div>

                  {/* 시간 + 삭제 */}
                  <div className="flex items-center gap-2 shrink-0">
                    {info && <span className="text-[11px] text-[#8b949e]">{info.duration}</span>}
                    {isNowPlaying && !editMode && (
                      <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                      </div>
                    )}
                    {editMode && (
                      <button
                        className="w-7 h-7 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400 active:bg-red-500/20 transition-colors"
                        onClick={(e) => { e.stopPropagation(); onRemoveItem(item.questionId); }}
                        aria-label="곡 삭제"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 곡 추가 안내 */}
        <div className="px-4 pt-3 pb-2">
          <p className="text-[11px] text-[#8b949e]/50 text-center">
            선택 재생으로 곡을 추가하세요 (플레이리스트 저장 시 자동 추가)
          </p>
        </div>
      </div>
    </div>
  );
}

// ── 메인 FavoriteScreen ───────────────────────────────────────────────────────
export function FavoriteScreen({ onBack }: FavoriteScreenProps) {
  const { state, playSelected, jumpToPlaylistIndex } = usePlayer();
  const { currentQuestionId, playlist } = state;

  const [favorites, setFavorites] = useState<FavoritePlaylist[]>([]);
  const [selectedFav, setSelectedFav] = useState<FavoritePlaylist | null>(null);

  // 모달 상태
  const [renameTarget, setRenameTarget] = useState<FavoritePlaylist | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FavoritePlaylist | null>(null);

  // 목록 로드
  const reload = () => {
    const list = loadFavorites();
    setFavorites(list);
    // 상세 뷰 갱신
    if (selectedFav) {
      const updated = list.find((f) => f.id === selectedFav.id);
      setSelectedFav(updated ?? null);
    }
  };

  useEffect(() => {
    reload();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 핸들러: 목록 뷰 ──────────────────────────────────────────────────────
  const handlePlay = (fav: FavoritePlaylist, e: React.MouseEvent) => {
    e.stopPropagation();
    if (fav.items.length === 0) return;
    playSelected(fav.items);
  };

  const handleSelect = (fav: FavoritePlaylist) => {
    setSelectedFav(fav);
  };

  const handleRenameRequest = (fav: FavoritePlaylist) => {
    setRenameTarget(fav);
  };

  const handleDeleteRequest = (fav: FavoritePlaylist) => {
    setDeleteTarget(fav);
  };

  // ── 핸들러: 이름 변경 ─────────────────────────────────────────────────────
  const handleRenameConfirm = (name: string) => {
    if (!renameTarget) return;
    updateFavoriteName(renameTarget.id, name);
    setRenameTarget(null);
    reload();
  };

  // 상세 뷰 내 인라인 이름 변경
  const handleDetailRenameConfirm = (name: string) => {
    if (!selectedFav) return;
    updateFavoriteName(selectedFav.id, name);
    reload();
  };

  // ── 핸들러: 삭제 ────────────────────────────────────────────────────────
  const handleDeleteConfirm = () => {
    if (!deleteTarget) return;
    deleteFavorite(deleteTarget.id);
    if (selectedFav?.id === deleteTarget.id) {
      setSelectedFav(null);
    }
    setDeleteTarget(null);
    reload();
  };

  // ── 핸들러: 상세 뷰 ─────────────────────────────────────────────────────
  const handlePlayAll = () => {
    if (!selectedFav || selectedFav.items.length === 0) return;
    playSelected(selectedFav.items);
  };

  const handlePlayItem = (idx: number) => {
    if (!selectedFav) return;
    const items = selectedFav.items;
    // 현재 플레이리스트가 이 즐겨찾기와 동일하면 jumpToPlaylistIndex 사용
    const isSamePlaylist =
      playlist.length === items.length &&
      items.every(
        (item, i) =>
          item.subjectId === playlist[i]?.subjectId &&
          item.fileId === playlist[i]?.fileId &&
          item.questionId === playlist[i]?.questionId,
      );
    if (isSamePlaylist) {
      jumpToPlaylistIndex(idx);
    } else {
      playSelected(items);
      // playSelected는 첫 번째 곡부터 시작하므로, idx > 0이면 jumpToPlaylistIndex 호출
      if (idx > 0) {
        // 약간의 딜레이 없이 바로 jumpToPlaylistIndex 호출
        // playSelected가 상태 업데이트 후 jumpToPlaylistIndex가 실행되도록
        setTimeout(() => jumpToPlaylistIndex(idx), 50);
      }
    }
  };

  const handleRemoveItem = (questionId: string) => {
    if (!selectedFav) return;
    removeItemFromFavorite(selectedFav.id, questionId);
    reload();
    // 현재 재생 중인 playlist가 이 즐겨찾기와 동일하면 갱신
    const updated = loadFavorites().find((f) => f.id === selectedFav.id);
    if (updated && updated.items.length > 0) {
      const isSame = playlist.length === selectedFav.items.length &&
        selectedFav.items.every((item, i) => item.questionId === playlist[i]?.questionId);
      if (isSame) {
        playSelected(updated.items);
      }
    }
  };

  const handleDetailBack = () => {
    setSelectedFav(null);
    reload();
  };

  return (
    <div
      className="absolute inset-0 flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1e3a5f 0%, #0d1117 50%)' }}
    >
      {/* 공통 헤더 (목록 뷰에서만) */}
      {!selectedFav && (
        <header className="px-4 pt-4 pb-3 flex items-center gap-3 shrink-0">
          <button
            className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center min-w-[32px]"
            onClick={onBack}
            aria-label="뒤로가기"
          >
            <BackIcon />
          </button>
          <div className="flex-1 min-w-0">
            <h2 className="font-bold text-white">플레이리스트</h2>
            <p className="text-[11px] text-[#8b949e]">{favorites.length}개 저장됨</p>
          </div>
        </header>
      )}

      {/* 목록 뷰 */}
      {!selectedFav && (
        <ListView
          favorites={favorites}
          onSelect={handleSelect}
          onPlay={handlePlay}
          onRename={handleRenameRequest}
          onDelete={handleDeleteRequest}
        />
      )}

      {/* 상세 뷰 */}
      {selectedFav && (
        <>
          {/* 상세 뷰 헤더 영역은 DetailView 내부에서 처리 */}
          <header className="px-4 pt-4 shrink-0" />
          <DetailView
            fav={selectedFav}
            onBack={handleDetailBack}
            onPlayAll={handlePlayAll}
            onPlayItem={handlePlayItem}
            onRemoveItem={handleRemoveItem}
            onRenameConfirm={handleDetailRenameConfirm}
            currentQuestionId={currentQuestionId}
          />
        </>
      )}

      {/* 이름 변경 모달 */}
      {renameTarget && (
        <RenameModal
          initialName={renameTarget.name}
          onConfirm={handleRenameConfirm}
          onCancel={() => setRenameTarget(null)}
        />
      )}

      {/* 삭제 확인 모달 */}
      {deleteTarget && (
        <DeleteModal
          name={deleteTarget.name}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
