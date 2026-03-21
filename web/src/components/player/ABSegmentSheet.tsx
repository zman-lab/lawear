import { useState, useEffect, useCallback, useRef } from 'react';
import { usePlayer } from '../../context/PlayerContext';
import { subjects } from '../../data/ttsData';
import {
  loadABSegments,
  addABSegment,
  deleteABSegment,
  type SavedABSegment,
} from '../../services/abSegment';

interface ABSegmentSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ABSegmentSheet({ isOpen, onClose }: ABSegmentSheetProps) {
  const { state, playSelected } = usePlayer();
  const {
    currentSubjectId,
    currentFileId,
    currentQuestionId,
    repeatSectionStart,
    repeatSectionEnd,
    isRepeatingSectionActive,
  } = state;

  const [segments, setSegments] = useState<SavedABSegment[]>([]);
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [saveTitle, setSaveTitle] = useState('');
  const titleInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    setSegments(loadABSegments());
  }, []);

  useEffect(() => {
    if (isOpen) refresh();
  }, [isOpen, refresh]);

  // A-B 구간이 활성 상태인지
  const canSave = isRepeatingSectionActive && repeatSectionStart !== null && repeatSectionEnd !== null;

  const handleSave = useCallback(() => {
    if (!canSave || !currentSubjectId || !currentFileId || !currentQuestionId) return;
    const trimmed = saveTitle.trim();
    if (!trimmed) return;

    addABSegment({
      title: trimmed,
      subjectId: currentSubjectId,
      fileId: currentFileId,
      questionId: currentQuestionId,
      startIndex: repeatSectionStart!,
      endIndex: repeatSectionEnd!,
    });
    setSaveTitle('');
    setShowSaveForm(false);
    refresh();
  }, [canSave, currentSubjectId, currentFileId, currentQuestionId, repeatSectionStart, repeatSectionEnd, saveTitle, refresh]);

  // 구간 클릭 -> 해당 문제로 이동 + A-B 구간 로드 + 재생
  const handlePlaySegment = useCallback(
    (seg: SavedABSegment) => {
      // 해당 문제를 playlist에 넣고 재생 시작 (startSentenceIndex = seg.startIndex)
      const item = { subjectId: seg.subjectId, fileId: seg.fileId, questionId: seg.questionId };
      playSelected([item], 0, seg.startIndex);
      onClose();
    },
    [playSelected, onClose],
  );

  const handleDelete = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      deleteABSegment(id);
      refresh();
    },
    [refresh],
  );

  if (!isOpen) return null;

  // 구간 라벨 생성 헬퍼
  const getQuestionLabel = (seg: SavedABSegment): string => {
    const sub = subjects.find((s) => s.id === seg.subjectId);
    const file = sub?.files.find((f) => f.id === seg.fileId);
    const q = file?.questions.find((qq) => qq.id === seg.questionId);
    return q?.label ?? seg.questionId;
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
            A-B 구간 저장
            <span className="text-[#8b949e] font-normal ml-2">{segments.length}개</span>
          </h3>
          <div className="flex items-center gap-2">
            {/* A-B 활성 시 저장 버튼 */}
            {canSave && !showSaveForm && (
              <button
                className="text-xs px-2.5 py-1 rounded-lg bg-green-500/10 text-green-400 border border-green-500/20 flex items-center gap-1 active:bg-green-500/20 transition-colors"
                onClick={() => {
                  setShowSaveForm(true);
                  setTimeout(() => titleInputRef.current?.focus(), 50);
                }}
                aria-label="현재 A-B 구간 저장"
              >
                + 현재 구간 저장
              </button>
            )}
            <button className="text-xs text-[#8b949e] px-2 py-1" onClick={onClose}>
              닫기
            </button>
          </div>
        </div>

        {/* 저장 폼 */}
        {showSaveForm && (
          <div className="px-4 pb-3 shrink-0">
            <div className="px-3 py-3 rounded-lg border border-green-500/30 bg-green-500/5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] text-green-400/70 font-mono">
                  A:{(repeatSectionStart ?? 0) + 1} ~ B:{(repeatSectionEnd ?? 0) + 1}
                </span>
              </div>
              <input
                ref={titleInputRef}
                type="text"
                value={saveTitle}
                onChange={(e) => setSaveTitle(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && saveTitle.trim()) handleSave(); }}
                placeholder="구간 제목 입력"
                className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2.5 text-sm text-white placeholder-[#8b949e]/50 outline-none focus:border-green-500/50 transition-colors"
                autoComplete="off"
                maxLength={50}
              />
              <div className="flex gap-2 mt-2.5">
                <button
                  className="flex-1 py-2 rounded-lg text-xs font-bold text-[#8b949e] bg-white/5 active:bg-white/10 transition-colors"
                  onClick={() => { setShowSaveForm(false); setSaveTitle(''); }}
                >
                  취소
                </button>
                <button
                  className={`flex-1 py-2 rounded-lg text-xs font-bold transition-colors ${
                    saveTitle.trim()
                      ? 'bg-green-500 text-white active:bg-green-600'
                      : 'bg-green-500/20 text-green-400/40 cursor-not-allowed'
                  }`}
                  onClick={handleSave}
                  disabled={!saveTitle.trim()}
                >
                  저장
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 구간 목록 */}
        <div className="flex-1 overflow-y-auto px-3 pb-6">
          {segments.length === 0 ? (
            <div className="text-center py-10">
              <p className="text-[#8b949e] text-sm">저장된 구간이 없습니다</p>
              <p className="text-[#8b949e]/50 text-[11px] mt-1.5">
                A-B 구간을 설정한 뒤 여기서 저장하세요
              </p>
            </div>
          ) : (
            (() => {
              // 과목별 그룹화
              const grouped: { subjectId: string; subjectName: string; items: SavedABSegment[] }[] = [];
              const subjectOrder: string[] = [];
              const subjectMap = new Map<string, SavedABSegment[]>();
              for (const seg of segments) {
                if (!subjectMap.has(seg.subjectId)) {
                  subjectMap.set(seg.subjectId, []);
                  subjectOrder.push(seg.subjectId);
                }
                subjectMap.get(seg.subjectId)!.push(seg);
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
                  {group.items.map((seg) => {
                    const isCurrent = seg.questionId === currentQuestionId;
                    return (
                      <button
                        key={seg.id}
                        className="w-full text-left px-3 py-2.5 rounded-lg mb-1 flex items-center gap-3 active:bg-white/5 transition-colors"
                        onClick={() => handlePlaySegment(seg)}
                      >
                        {/* A-B 아이콘 */}
                        <span
                          className={`text-[11px] font-bold shrink-0 px-1.5 py-0.5 rounded ${
                            isCurrent ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-[#8b949e]/50'
                          }`}
                        >
                          A-B
                        </span>

                        {/* 정보 */}
                        <div className="flex-1 min-w-0">
                          <p
                            className={`text-sm truncate ${
                              isCurrent ? 'text-green-400 font-semibold' : 'text-white'
                            }`}
                          >
                            {seg.title}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-[#8b949e]/40">
                              {getQuestionLabel(seg)}
                            </span>
                            <span className="text-[10px] text-[#8b949e]/30 font-mono">
                              {seg.startIndex + 1}~{seg.endIndex + 1}
                            </span>
                          </div>
                        </div>

                        {/* 재생 아이콘 */}
                        <span className={`shrink-0 ${isCurrent ? 'text-green-400' : 'text-[#8b949e]/30'}`}>
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M8 5v14l11-7z" />
                          </svg>
                        </span>

                        {/* 삭제 버튼 */}
                        <button
                          className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full text-[#8b949e]/40 active:text-red-400 active:bg-red-500/10 transition-colors"
                          onClick={(e) => handleDelete(seg.id, e)}
                          aria-label="구간 삭제"
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
