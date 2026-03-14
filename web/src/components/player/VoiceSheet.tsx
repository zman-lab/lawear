import { usePlayer } from '../../context/PlayerContext';

interface VoiceSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

export function VoiceSheet({ isOpen, onClose }: VoiceSheetProps) {
  const { state, voices, setVoice } = usePlayer();
  const { selectedVoiceURI } = state;

  if (!isOpen) return null;

  // 한국어 음성 우선, Google TTS 음성 상위 정렬
  const koreanVoices = voices
    .filter((v) => v.lang.startsWith('ko'))
    .sort((a, b) => {
      // Google 음성 우선
      const aGoogle = a.name.toLowerCase().includes('google') ? 0 : 1;
      const bGoogle = b.name.toLowerCase().includes('google') ? 0 : 1;
      return aGoogle - bGoogle;
    });
  const otherVoices = voices.filter((v) => !v.lang.startsWith('ko'));

  const handleSelect = (voiceURI: string | null) => {
    setVoice(voiceURI);
    onClose();
  };

  return (
    <>
      {/* 백드롭 */}
      <div className="fixed inset-0 bg-black/40 z-[60]" onClick={onClose} />
      {/* 시트 */}
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto z-[70] bg-[#161b22] rounded-t-2xl border-t border-[#21262d] max-h-[70vh] flex flex-col">
        <div className="w-10 h-1 bg-white/10 rounded-full mx-auto mt-3 shrink-0" />
        <div className="px-5 pt-4 pb-2 shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white">음성 선택</h3>
              <p className="text-[10px] text-[#8b949e] mt-1">TTS 음성을 선택하세요</p>
            </div>
            <button
              className="text-xs text-[#8b949e] px-2 py-1"
              onClick={onClose}
              aria-label="닫기"
            >
              닫기
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 pb-6">
          {/* 자동 선택 (기본) */}
          <button
            className={`w-full text-left py-3 px-3 rounded-xl mb-1 flex items-center justify-between ${
              !selectedVoiceURI ? 'bg-blue-500/10 border border-blue-500/20' : 'bg-white/5'
            }`}
            onClick={() => handleSelect(null)}
          >
            <div>
              <p className={`text-sm ${!selectedVoiceURI ? 'text-blue-400 font-medium' : 'text-white'}`}>
                자동 (한국어 기본)
              </p>
              <p className="text-[10px] text-[#8b949e]">시스템 기본 한국어 음성</p>
            </div>
            {!selectedVoiceURI && (
              <svg className="w-4 h-4 text-blue-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
              </svg>
            )}
          </button>

          {/* 한국어 음성 */}
          {koreanVoices.length > 0 && (
            <>
              <p className="text-[10px] text-[#8b949e]/60 uppercase tracking-widest pt-3 pb-2">한국어</p>
              {koreanVoices.map((voice) => (
                <button
                  key={voice.voiceURI}
                  className={`w-full text-left py-3 px-3 rounded-xl mb-1 flex items-center justify-between ${
                    selectedVoiceURI === voice.voiceURI
                      ? 'bg-blue-500/10 border border-blue-500/20'
                      : 'bg-white/5'
                  }`}
                  onClick={() => handleSelect(voice.voiceURI)}
                >
                  <div>
                    <p
                      className={`text-sm ${selectedVoiceURI === voice.voiceURI ? 'text-blue-400 font-medium' : 'text-white'}`}
                    >
                      {voice.name}
                    </p>
                    <p className="text-[10px] text-[#8b949e]">{voice.lang}</p>
                  </div>
                  {selectedVoiceURI === voice.voiceURI && (
                    <svg className="w-4 h-4 text-blue-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                    </svg>
                  )}
                </button>
              ))}
            </>
          )}

          {/* 한국어 음성이 없을 때 기타 음성 표시 */}
          {koreanVoices.length === 0 && otherVoices.length > 0 && (
            <>
              <div className="py-3 px-3 bg-amber-400/10 rounded-xl mb-3">
                <p className="text-xs text-amber-400">한국어 음성이 없습니다. 다른 음성을 선택해 주세요.</p>
              </div>
              {otherVoices.slice(0, 20).map((voice) => (
                <button
                  key={voice.voiceURI}
                  className={`w-full text-left py-3 px-3 rounded-xl mb-1 flex items-center justify-between ${
                    selectedVoiceURI === voice.voiceURI
                      ? 'bg-blue-500/10 border border-blue-500/20'
                      : 'bg-white/5'
                  }`}
                  onClick={() => handleSelect(voice.voiceURI)}
                >
                  <div>
                    <p
                      className={`text-sm ${selectedVoiceURI === voice.voiceURI ? 'text-blue-400 font-medium' : 'text-white'}`}
                    >
                      {voice.name}
                    </p>
                    <p className="text-[10px] text-[#8b949e]">{voice.lang}</p>
                  </div>
                  {selectedVoiceURI === voice.voiceURI && (
                    <svg className="w-4 h-4 text-blue-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                    </svg>
                  )}
                </button>
              ))}
            </>
          )}

          {/* 한국어 있고 기타도 있을 때 — 기타는 숨김 */}
          {koreanVoices.length > 0 && otherVoices.length > 0 && (
            <p className="text-[10px] text-[#8b949e]/40 text-center pt-2">
              기타 {otherVoices.length}개 음성 사용 가능
            </p>
          )}
        </div>
      </div>
    </>
  );
}
