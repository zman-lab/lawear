import { useState, useEffect, useRef, useCallback } from 'react';
import { Capacitor } from '@capacitor/core';
import { TextToSpeech } from '@capacitor-community/text-to-speech';
import { TTSVoice } from '../types';
import { getCachedAudioUri } from '../services/audioCache';
import { log } from '../services/logger';

const isNative = Capacitor.isNativePlatform();

interface SpeakOptions {
  rate?: number;
  voiceURI?: string;
  onEnd?: () => void;
  onBoundary?: (event: SpeechSynthesisEvent) => void;
  /** 캐시 조회용: 과목 ID */
  subjectId?: string;
  /** 캐시 조회용: 파일 ID */
  fileId?: string;
  /** 캐시 조회용: 문제 ID */
  questionId?: string;
}

export function useSpeechSynthesis() {
  const [isSupported] = useState(() => isNative || 'speechSynthesis' in window);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [voices, setVoices] = useState<TTSVoice[]>([]);
  /** 현재 캐시된 MP3로 재생 중인지 */
  const [isPlayingCached, setIsPlayingCached] = useState(false);
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const rateRef = useRef<number>(1.0);
  // 캐시된 오디오 재생용 Audio 객체
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const audioObjectUrlRef = useRef<string | null>(null);
  // 네이티브 TTS는 pause를 지원하지 않으므로 중단 시 현재 텍스트를 저장
  const nativeSpeakingRef = useRef(false);
  const nativeOnEndRef = useRef<(() => void) | null>(null);
  // 각 speak 호출에 고유 ID 부여 — cancel/stop 후 지연된 .then/.catch가 새 speak을 방해하지 않도록
  const speakIdRef = useRef(0);
  // setRate에 의한 중단인지 여부 (interrupted 에러와 구분)
  const isRateChangingRef = useRef(false);
  // 웹 TTS onEnd 콜백 저장 (setRate에서 재사용)
  const onEndCallbackRef = useRef<(() => void) | undefined>(undefined);

  // 음성 목록 로드
  useEffect(() => {
    if (!isSupported) return;

    if (isNative) {
      TextToSpeech.getSupportedVoices()
        .then((result) => {
          const mapped: TTSVoice[] = result.voices.map((v) => ({
            voiceURI: v.voiceURI,
            name: v.name,
            lang: v.lang,
          }));
          setVoices(mapped);
        })
        .catch(() => {
          // 네이티브 음성 목록 실패 시 빈 배열 유지
        });
    } else {
      const loadVoices = () => {
        const allVoices = window.speechSynthesis.getVoices();
        const mapped: TTSVoice[] = allVoices.map((v) => ({
          voiceURI: v.voiceURI,
          name: v.name,
          lang: v.lang,
        }));
        setVoices(mapped);
      };

      loadVoices();
      window.speechSynthesis.addEventListener('voiceschanged', loadVoices);
      return () => {
        window.speechSynthesis.removeEventListener('voiceschanged', loadVoices);
      };
    }
  }, [isSupported]);

  // 한국어 음성 선택 (Google TTS 우선) — 웹 전용
  const getKoreanVoice = useCallback((): SpeechSynthesisVoice | null => {
    if (isNative) return null;
    const allVoices = window.speechSynthesis.getVoices();
    const koVoices = allVoices.filter((v) => v.lang === 'ko-KR' || v.lang.startsWith('ko'));
    if (koVoices.length === 0) return null;
    const googleVoice = koVoices.find((v) => v.name.toLowerCase().includes('google'));
    return googleVoice ?? koVoices[0];
  }, []);

  // ── 캐시된 오디오 정리 헬퍼 ─────────────────────────────────────────────
  const cleanupAudioElement = useCallback(() => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.removeAttribute('src');
      audioElementRef.current.load();
      audioElementRef.current = null;
    }
    if (audioObjectUrlRef.current) {
      URL.revokeObjectURL(audioObjectUrlRef.current);
      audioObjectUrlRef.current = null;
    }
    setIsPlayingCached(false);
  }, []);

  const speak = useCallback(
    (text: string, options: SpeakOptions = {}) => {
      log.tts('speak', { text: text.slice(0, 60), hasCacheOpts: !!(options.subjectId) });
      if (!isSupported) return;

      const rate = Math.min(10, Math.max(0.1, options.rate ?? rateRef.current));

      // ── 캐시된 MP3 우선 재생 ──────────────────────────────────────────
      // subjectId/fileId/questionId가 제공되면 캐시를 확인한다.
      // 캐시가 있으면 HTML5 Audio로 재생하고 TTS를 사용하지 않는다.
      if (options.subjectId && options.fileId && options.questionId) {
        // 비동기 캐시 확인 → 있으면 Audio 재생, 없으면 TTS 폴백
        getCachedAudioUri(options.subjectId, options.fileId, options.questionId)
          .then((uri) => {
            if (uri) {
              playCachedAudio(uri, rate, options.onEnd ?? null);
            } else {
              speakWithTts(text, rate, options);
            }
          })
          .catch(() => {
            speakWithTts(text, rate, options);
          });
        return;
      }

      // 캐시 정보 없으면 바로 TTS로 재생
      speakWithTts(text, rate, options);
    },
    [isSupported, getKoreanVoice, cleanupAudioElement],
  );

  // ── 캐시된 오디오 재생 (HTML5 Audio) ──────────────────────────────────
  const playCachedAudio = useCallback(
    (uri: string, rate: number, onEnd: (() => void) | null) => {
      log.tts('play_cached', { uri: uri.slice(0, 80) });
      // 기존 재생 중단
      cleanupAudioElement();
      if (isNative) {
        TextToSpeech.stop().catch(() => {});
        nativeSpeakingRef.current = false;
      } else {
        window.speechSynthesis.cancel();
        currentUtteranceRef.current = null;
      }

      const audio = new Audio(uri);
      audio.playbackRate = rate;
      audioElementRef.current = audio;
      // Object URL이면 나중에 revoke 해야 하므로 저장
      if (uri.startsWith('blob:')) {
        audioObjectUrlRef.current = uri;
      }

      audio.onplay = () => {
        setIsSpeaking(true);
        setIsPaused(false);
        setIsPlayingCached(true);
      };

      audio.onended = () => {
        setIsSpeaking(false);
        setIsPaused(false);
        setIsPlayingCached(false);
        cleanupAudioElement();
        onEnd?.();
      };

      audio.onerror = () => {
        log.error('tts', 'cached_audio_error');
        setIsSpeaking(false);
        setIsPaused(false);
        setIsPlayingCached(false);
        cleanupAudioElement();
        // 캐시 재생 실패 시 조용히 종료 (TTS 폴백은 하지 않음 — 이미 문장이 진행됨)
      };

      audio.play().catch(() => {
        setIsSpeaking(false);
        setIsPlayingCached(false);
        cleanupAudioElement();
      });
    },
    [cleanupAudioElement],
  );

  // ── TTS 엔진으로 재생 (기존 로직) ────────────────────────────────────
  const speakWithTts = useCallback(
    (text: string, rate: number, options: SpeakOptions) => {
      log.tts('speak_tts', { isNative, voiceURI: options.voiceURI ?? 'auto' });
      // 캐시 오디오가 재생 중이면 중단
      cleanupAudioElement();

      if (isNative) {
        // 기존 재생 중단
        TextToSpeech.stop().catch(() => {});
        // 새 speak에 고유 ID 부여 — 이전 speak의 지연된 .then/.catch가 이 speak을 방해하지 않도록
        const thisId = ++speakIdRef.current;
        nativeSpeakingRef.current = true;
        nativeOnEndRef.current = options.onEnd ?? null;
        isRateChangingRef.current = false;

        setIsSpeaking(true);
        setIsPaused(false);

        // 네이티브 voice는 인덱스(number) — voiceURI로 인덱스 검색
        const nativeVoiceIdx = options.voiceURI
          ? voices.findIndex((v) => v.voiceURI === options.voiceURI)
          : -1;

        TextToSpeech.speak({
          text,
          lang: 'ko-KR',
          rate,
          pitch: 1.0,
          volume: 1.0,
          category: 'playback',
          ...(nativeVoiceIdx >= 0 ? { voice: nativeVoiceIdx } : {}),
        })
          .then(() => {
            // ID가 다르면 이미 cancel/새 speak이 시작된 것 — 무시
            if (speakIdRef.current !== thisId) return;
            nativeSpeakingRef.current = false;
            setIsSpeaking(false);
            setIsPaused(false);
            // onEnd를 로컬에 저장 후 ref를 먼저 비움
            // (onEnd 안에서 다음 speak이 nativeOnEndRef를 덮어쓰므로, 뒤에서 null로 리셋하면 안 됨)
            const onEnd = nativeOnEndRef.current;
            nativeOnEndRef.current = null;
            onEnd?.();
          })
          .catch(() => {
            // ID가 다르면 이미 새 speak이 시작된 것 — 새 speak의 flag 건드리지 않음
            if (speakIdRef.current !== thisId) return;
            log.warn('tts', 'native_speak_interrupted');
            nativeSpeakingRef.current = false;
            setIsSpeaking(false);
            setIsPaused(false);
          });
      } else {
        // 기존 발화 취소
        window.speechSynthesis.cancel();
        const thisId = ++speakIdRef.current;

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'ko-KR';
        utterance.rate = rate;

        if (options.voiceURI) {
          const allVoices = window.speechSynthesis.getVoices();
          const selectedVoice = allVoices.find((v) => v.voiceURI === options.voiceURI);
          if (selectedVoice) utterance.voice = selectedVoice;
        } else {
          const korVoice = getKoreanVoice();
          if (korVoice) utterance.voice = korVoice;
        }

        utterance.onstart = () => {
          if (speakIdRef.current !== thisId) return;
          setIsSpeaking(true);
          setIsPaused(false);
        };

        onEndCallbackRef.current = options.onEnd;

        utterance.onend = () => {
          // ID가 다르면 이미 cancel/새 speak이 시작된 것 — 지연 onend 무시
          if (speakIdRef.current !== thisId) return;
          setIsSpeaking(false);
          setIsPaused(false);
          currentUtteranceRef.current = null;
          onEndCallbackRef.current?.();
        };

        utterance.onerror = (e) => {
          if (speakIdRef.current !== thisId) return;
          log.error('tts', 'web_speak_error', { error: e.error });
          if (e.error === 'interrupted' || e.error === 'canceled') {
            return;
          }
          setIsSpeaking(false);
          setIsPaused(false);
          currentUtteranceRef.current = null;
        };

        if (options.onBoundary) {
          utterance.onboundary = options.onBoundary;
        }

        currentUtteranceRef.current = utterance;
        requestAnimationFrame(() => {
          if (speakIdRef.current !== thisId) return;
          isRateChangingRef.current = false;
          window.speechSynthesis.speak(utterance);
        });
      }
    },
    [cleanupAudioElement, getKoreanVoice],
  );

  const pause = useCallback(() => {
    log.tts('pause', { isPlayingCached, isSpeaking, nativeSpeaking: nativeSpeakingRef.current });
    if (!isSupported) return;

    // 캐시된 오디오 재생 중이면 Audio 일시정지
    if (audioElementRef.current && isPlayingCached) {
      audioElementRef.current.pause();
      setIsPaused(true);
      setIsSpeaking(false);
      return;
    }

    if (isNative) {
      // 네이티브 TTS는 pause/resume 미지원 — stop으로 대체
      // nativeSpeakingRef로 체크 (isSpeaking state보다 실시간 정확)
      ++speakIdRef.current;
      TextToSpeech.stop().catch(() => {});
      nativeSpeakingRef.current = false;
      nativeOnEndRef.current = null;
      setIsPaused(true);
      setIsSpeaking(false);
    } else {
      if (!isSpeaking) return;
      window.speechSynthesis.pause();
      setIsPaused(true);
    }
  }, [isSupported, isSpeaking, isPlayingCached]);

  const resume = useCallback(() => {
    log.tts('resume', { isPlayingCached });
    if (!isSupported || !isPaused) return;

    // 캐시된 오디오 재생 중이면 Audio resume
    if (audioElementRef.current && isPlayingCached) {
      audioElementRef.current.play().catch(() => {});
      setIsPaused(false);
      setIsSpeaking(true);
      return;
    }

    if (isNative) {
      // 네이티브에서는 resume 불가 — PlayerContext에서 speakCurrentSentence 재호출
      setIsPaused(false);
    } else {
      window.speechSynthesis.resume();
      setIsPaused(false);
    }
  }, [isSupported, isPaused, isPlayingCached]);

  const cancel = useCallback(() => {
    log.tts('cancel');
    if (!isSupported) return;

    // speakId 증가 — 이전 speak의 지연된 .then/.catch 무효화
    ++speakIdRef.current;

    // 캐시된 오디오 정리
    cleanupAudioElement();

    if (isNative) {
      TextToSpeech.stop().catch(() => {});
      nativeSpeakingRef.current = false;
      nativeOnEndRef.current = null;
    } else {
      window.speechSynthesis.cancel();
      currentUtteranceRef.current = null;
    }
    setIsSpeaking(false);
    setIsPaused(false);
  }, [isSupported, cleanupAudioElement]);

  const setRate = useCallback(
    (speed: number) => {
      rateRef.current = Math.min(10, Math.max(0.1, speed));

      // 캐시된 오디오는 즉시 변경 가능
      if (audioElementRef.current && isPlayingCached) {
        audioElementRef.current.playbackRate = rateRef.current;
      }
      // TTS 재생 중이면 현재 문장은 그대로 끝까지 읽고, 다음 문장부터 새 rate 적용
      // (rateRef + PlayerContext state.speed 업데이트만으로 충분)
    },
    [isPlayingCached],
  );

  // 네이티브에서 rate 변경 시 PlayerContext에 알림을 위한 콜백
  const onRateChangeRef = useRef<(() => void) | null>(null);
  const setOnRateChange = useCallback((cb: (() => void) | null) => {
    onRateChangeRef.current = cb;
  }, []);

  return {
    isSupported,
    isSpeaking,
    isPaused,
    isNative,
    isPlayingCached,
    currentUtterance: currentUtteranceRef.current,
    speak,
    pause,
    resume,
    cancel,
    setRate,
    setOnRateChange,
    voices,
  };
}
