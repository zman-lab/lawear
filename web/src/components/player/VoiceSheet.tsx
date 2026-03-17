import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { Capacitor } from '@capacitor/core';
import { TextToSpeech } from '@capacitor-community/text-to-speech';
import { usePlayer } from '../../context/PlayerContext';
import { TTSFile } from '../../plugins/ttsFile';
import type { TTSVoice, TTSEngine } from '../../types';

const isNative = Capacitor.isNativePlatform();
const PREVIEW_TEXT = '법무사 시험 학습을 시작합니다.';

interface VoiceSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

function PreviewButton({ voiceURI, previewingURI, onPreview }: {
  voiceURI: string | null;
  previewingURI: string | null;
  onPreview: (uri: string | null) => void;
}) {
  const isPreviewing = previewingURI === (voiceURI ?? '__auto__');
  return (
    <button
      className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
        isPreviewing
          ? 'bg-blue-500/20 text-blue-400'
          : 'bg-white/5 text-[#8b949e] active:bg-white/10'
      }`}
      onClick={(e) => {
        e.stopPropagation();
        onPreview(voiceURI);
      }}
      aria-label="미리듣기"
    >
      {isPreviewing ? (
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
          <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
        </svg>
      )}
    </button>
  );
}

function VoiceItem({ voice, isSelected, onSelect, previewingURI, onPreview }: {
  voice: TTSVoice;
  isSelected: boolean;
  onSelect: () => void;
  previewingURI: string | null;
  onPreview: (uri: string | null) => void;
}) {
  return (
    <div
      className={`w-full text-left py-3 px-3 rounded-xl mb-1 flex items-center gap-2 ${
        isSelected ? 'bg-blue-500/10 border border-blue-500/20' : 'bg-white/5'
      }`}
    >
      <button
        className="flex-1 text-left min-w-0"
        onClick={onSelect}
      >
        <p className={`text-sm truncate ${isSelected ? 'text-blue-400 font-medium' : 'text-white'}`}>
          {voice.name}
        </p>
        <p className="text-[10px] text-[#8b949e]">{voice.lang}</p>
      </button>
      <PreviewButton voiceURI={voice.voiceURI} previewingURI={previewingURI} onPreview={onPreview} />
      {isSelected && (
        <svg className="w-4 h-4 text-blue-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
        </svg>
      )}
    </div>
  );
}

/** 엔진 패키지명 → 짧은 표시명 */
function getEngineDisplayName(engine: TTSEngine): string {
  const { name, label } = engine;
  if (label && label.length < 30) return label;
  if (name.includes('google')) return 'Google TTS';
  if (name.includes('samsung') || name.includes('SMT')) return 'Samsung TTS';
  if (name.includes('naver')) return 'NAVER TTS';
  if (name.includes('kakao')) return 'Kakao TTS';
  return label || name.split('.').pop() || name;
}

export function VoiceSheet({ isOpen, onClose }: VoiceSheetProps) {
  const { state, voices, setVoice } = usePlayer();
  const { selectedVoiceURI } = state;
  const [previewingURI, setPreviewingURI] = useState<string | null>(null);
  const previewUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  // 엔진 정보 (네이티브 전용)
  const [engines, setEngines] = useState<TTSEngine[]>([]);
  const [defaultEngine, setDefaultEngine] = useState<string>('');

  useEffect(() => {
    if (!isNative || !isOpen) return;
    TTSFile.getEngines()
      .then((result) => {
        setEngines(result.engines);
        setDefaultEngine(result.defaultEngine);
      })
      .catch(() => {});
  }, [isOpen]);

  // voiceURI -> 인덱스 맵 (네이티브에서 voice는 number 인덱스)
  const voiceIndexMap = useMemo(() => {
    const m = new Map<string, number>();
    voices.forEach((v, i) => m.set(v.voiceURI, i));
    return m;
  }, [voices]);

  // 현재 엔진 표시명
  const currentEngineName = useMemo(() => {
    const engine = engines.find((e) => e.name === defaultEngine);
    return engine ? getEngineDisplayName(engine) : null;
  }, [engines, defaultEngine]);

  const stopPreview = useCallback(() => {
    if (isNative) {
      TextToSpeech.stop().catch(() => {});
    } else {
      window.speechSynthesis.cancel();
      previewUtteranceRef.current = null;
    }
    setPreviewingURI(null);
  }, []);

  const handlePreview = useCallback((voiceURI: string | null) => {
    const previewKey = voiceURI ?? '__auto__';

    if (previewingURI === previewKey) {
      stopPreview();
      return;
    }

    stopPreview();
    setPreviewingURI(previewKey);

    if (isNative) {
      const nativeVoiceIdx = voiceURI ? (voiceIndexMap.get(voiceURI) ?? -1) : -1;
      TextToSpeech.speak({
        text: PREVIEW_TEXT,
        lang: 'ko-KR',
        rate: 1.0,
        pitch: 1.0,
        volume: 1.0,
        category: 'playback',
        ...(nativeVoiceIdx >= 0 ? { voice: nativeVoiceIdx } : {}),
      })
        .then(() => setPreviewingURI(null))
        .catch(() => setPreviewingURI(null));
    } else {
      const utterance = new SpeechSynthesisUtterance(PREVIEW_TEXT);
      utterance.lang = 'ko-KR';
      utterance.rate = 1.0;

      if (voiceURI) {
        const allVoices = window.speechSynthesis.getVoices();
        const found = allVoices.find((v) => v.voiceURI === voiceURI);
        if (found) utterance.voice = found;
      } else {
        const allVoices = window.speechSynthesis.getVoices();
        const koVoices = allVoices.filter((v) => v.lang === 'ko-KR' || v.lang.startsWith('ko'));
        const googleVoice = koVoices.find((v) => v.name.toLowerCase().includes('google'));
        const picked = googleVoice ?? koVoices[0];
        if (picked) utterance.voice = picked;
      }

      utterance.onend = () => {
        setPreviewingURI(null);
        previewUtteranceRef.current = null;
      };
      utterance.onerror = () => {
        setPreviewingURI(null);
        previewUtteranceRef.current = null;
      };

      previewUtteranceRef.current = utterance;
      window.speechSynthesis.cancel();
      requestAnimationFrame(() => {
        window.speechSynthesis.speak(utterance);
      });
    }
  }, [previewingURI, stopPreview, voiceIndexMap]);

  const handleSelect = (voiceURI: string | null) => {
    stopPreview();
    setVoice(voiceURI);
    onClose();
  };

  const handleClose = () => {
    stopPreview();
    onClose();
  };

  const handleOpenTTSSettings = () => {
    if (isNative) {
      TTSFile.openTTSSettings().catch(() => {});
    }
  };

  if (!isOpen) return null;

  // 한국어 음성 우선, Google TTS 음성 상위 정렬
  const koreanVoices = voices
    .filter((v) => v.lang.startsWith('ko'))
    .sort((a, b) => {
      const aGoogle = a.name.toLowerCase().includes('google') ? 0 : 1;
      const bGoogle = b.name.toLowerCase().includes('google') ? 0 : 1;
      return aGoogle - bGoogle;
    });
  const otherVoices = voices.filter((v) => !v.lang.startsWith('ko'));

  return (
    <>
      {/* 백드롭 */}
      <div className="fixed inset-0 bg-black/40 z-[60]" onClick={handleClose} />
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
              onClick={handleClose}
              aria-label="닫기"
            >
              닫기
            </button>
          </div>

          {/* 현재 엔진 정보 (네이티브) */}
          {isNative && currentEngineName && (
            <div className="mt-2 flex items-center justify-between bg-white/5 rounded-lg px-3 py-2">
              <div className="min-w-0">
                <p className="text-[10px] text-[#8b949e]/60 uppercase tracking-wider">현재 엔진</p>
                <p className="text-xs text-white/80 truncate">{currentEngineName}</p>
              </div>
              <button
                className="text-[10px] text-blue-400 px-2 py-1 bg-blue-500/10 rounded-md shrink-0"
                onClick={handleOpenTTSSettings}
              >
                변경
              </button>
            </div>
          )}

          {/* 설치된 엔진 목록 (2개 이상일 때) */}
          {isNative && engines.length > 1 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {engines.map((engine) => (
                <span
                  key={engine.name}
                  className={`text-[10px] px-2 py-0.5 rounded-full ${
                    engine.name === defaultEngine
                      ? 'bg-blue-500/15 text-blue-400'
                      : 'bg-white/5 text-[#8b949e]/60'
                  }`}
                >
                  {getEngineDisplayName(engine)}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-5 pb-6">
          {/* 자동 선택 (기본) */}
          <div
            className={`w-full text-left py-3 px-3 rounded-xl mb-1 flex items-center gap-2 ${
              !selectedVoiceURI ? 'bg-blue-500/10 border border-blue-500/20' : 'bg-white/5'
            }`}
          >
            <button
              className="flex-1 text-left min-w-0"
              onClick={() => handleSelect(null)}
            >
              <p className={`text-sm ${!selectedVoiceURI ? 'text-blue-400 font-medium' : 'text-white'}`}>
                자동 (한국어 기본)
              </p>
              <p className="text-[10px] text-[#8b949e]">시스템 기본 한국어 음성</p>
            </button>
            <PreviewButton voiceURI={null} previewingURI={previewingURI} onPreview={handlePreview} />
            {!selectedVoiceURI && (
              <svg className="w-4 h-4 text-blue-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
              </svg>
            )}
          </div>

          {/* 한국어 음성 */}
          {koreanVoices.length > 0 && (
            <>
              <p className="text-[10px] text-[#8b949e]/60 uppercase tracking-widest pt-3 pb-2">한국어</p>
              {koreanVoices.map((voice) => (
                <VoiceItem
                  key={voice.voiceURI}
                  voice={voice}
                  isSelected={selectedVoiceURI === voice.voiceURI}
                  onSelect={() => handleSelect(voice.voiceURI)}
                  previewingURI={previewingURI}
                  onPreview={handlePreview}
                />
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
                <VoiceItem
                  key={voice.voiceURI}
                  voice={voice}
                  isSelected={selectedVoiceURI === voice.voiceURI}
                  onSelect={() => handleSelect(voice.voiceURI)}
                  previewingURI={previewingURI}
                  onPreview={handlePreview}
                />
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
