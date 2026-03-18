import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';

interface PlaylistSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PlaylistSheet({ isOpen, onClose }: PlaylistSheetProps) {
  const { state, jumpToPlaylistIndex } = usePlayer();
  const { playlist, playlistIndex } = state;

  if (!isOpen) return null;

  const handleItemClick = (idx: number) => {
    jumpToPlaylistIndex(idx);
    onClose();
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
            플레이리스트
            <span className="text-[#8b949e] font-normal ml-2">{playlist.length}곡</span>
          </h3>
          <button className="text-xs text-[#8b949e] px-2 py-1" onClick={onClose}>
            닫기
          </button>
        </div>

        {/* 곡 목록 */}
        <div className="flex-1 overflow-y-auto px-3 pb-6">
          {playlist.length === 0 ? (
            <p className="text-center text-[#8b949e] text-sm py-8">플레이리스트가 비어있습니다</p>
          ) : (
            playlist.map((item, idx) => {
              const isActive = idx === playlistIndex;
              const sub = subjects.find((s) => s.id === item.subjectId);
              const file = sub?.files.find((f) => f.id === item.fileId);
              const q = file?.questions.find((qq) => qq.id === item.questionId);
              const label = q?.label ?? item.questionId;
              const subtitle = q?.subtitle ?? '';

              return (
                <button
                  key={`${item.questionId}-${idx}`}
                  className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 flex items-center gap-3 transition-colors ${
                    isActive
                      ? 'bg-blue-500/15 border border-blue-500/30'
                      : 'active:bg-white/5'
                  }`}
                  onClick={() => handleItemClick(idx)}
                >
                  {/* 번호 */}
                  <span className={`text-xs font-mono w-5 text-center shrink-0 ${
                    isActive ? 'text-blue-400' : 'text-[#8b949e]/50'
                  }`}>
                    {idx + 1}
                  </span>

                  {/* 재생 인디케이터 */}
                  {isActive && (
                    <div className="flex items-end gap-[1px] h-3 shrink-0">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className="inline-block w-[2px] rounded-sm bg-blue-400"
                          style={{
                            animation: state.isPlaying ? 'lawear-wave 1s ease-in-out infinite' : undefined,
                            animationDelay: `${i * 0.15}s`,
                            height: state.isPlaying ? undefined : '3px',
                          }}
                        />
                      ))}
                    </div>
                  )}

                  {/* 곡 정보 */}
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm truncate ${isActive ? 'text-blue-400 font-semibold' : 'text-white'}`}>
                      {label}
                    </p>
                    {subtitle && (
                      <p className="text-[10px] text-[#8b949e] truncate mt-0.5">{subtitle}</p>
                    )}
                  </div>

                  {/* 시간 */}
                  <span className="text-[10px] text-[#8b949e]/50 shrink-0">
                    {q?.duration ?? ''}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
