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
        nativeSpeakingRef.current = true;
        nativeOnEndRef.current = options.onEnd ?? null;

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
            // speak이 resolve되면 재생 완료
            if (nativeSpeakingRef.current) {
              nativeSpeakingRef.current = false;
              setIsSpeaking(false);
              setIsPaused(false);
              nativeOnEndRef.current?.();
              nativeOnEndRef.current = null;
            }
          })
          .catch(() => {
            log.warn('tts', 'native_speak_interrupted');
            // 중단(stop)에 의한 에러는 정상 동작
            nativeSpeakingRef.current = false;
            setIsSpeaking(false);
            setIsPaused(false);
          });
      } else {
        // 기존 발화 취소
        window.speechSynthesis.cancel();

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
          setIsSpeaking(true);
          setIsPaused(false);
        };

        utterance.onend = () => {
          setIsSpeaking(false);
          setIsPaused(false);
          currentUtteranceRef.current = null;
          options.onEnd?.();
        };

        utterance.onerror = (e) => {
          log.error('tts', 'web_speak_error', { error: e.error });
          if (e.error === 'interrupted' || e.error === 'canceled') return;
          setIsSpeaking(false);
          setIsPaused(false);
          currentUtteranceRef.current = null;
        };

        if (options.onBoundary) {
          utterance.onboundary = options.onBoundary;
        }

        currentUtteranceRef.current = utterance;
        requestAnimationFrame(() => {
          window.speechSynthesis.speak(utterance);
        });
      }
    },
    [cleanupAudioElement, getKoreanVoice],
  );

  const pause = useCallback(() => {
    log.tts('pause', { isPlayingCached });
    if (!isSupported || !isSpeaking) return;

    // 캐시된 오디오 재생 중이면 Audio 일시정지
    if (audioElementRef.current && isPlayingCached) {
      audioElementRef.current.pause();
      setIsPaused(true);
      setIsSpeaking(false);
      return;
    }

    if (isNative) {
      // 네이티브 TTS는 pause/resume 미지원 — stop으로 대체
      // PlayerContext에서 togglePlay 시 현재 문장부터 다시 speak
      TextToSpeech.stop().catch(() => {});
      nativeSpeakingRef.current = false;
      nativeOnEndRef.current = null;
      setIsPaused(true);
      setIsSpeaking(false);
    } else {
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

      // 캐시된 오디오 재생 중이면 playbackRate만 변경
      if (audioElementRef.current && isPlayingCached) {
        audioElementRef.current.playbackRate = rateRef.current;
        return;
      }

      if (isSpeaking) {
        if (isNative) {
          // 네이티브: 현재 재생을 중단하고 onRateChange 콜백 호출
          // PlayerContext에서 현재 문장을 새 rate로 다시 speak
          TextToSpeech.stop().catch(() => {});
          nativeSpeakingRef.current = false;
          nativeOnEndRef.current = null;
          setIsSpeaking(false);
          onRateChangeRef.current?.();
        } else if (currentUtteranceRef.current) {
          const text = currentUtteranceRef.current.text;
          const onEnd = currentUtteranceRef.current.onend as (() => void) | null;
          speak(text, { rate: rateRef.current, onEnd: onEnd ?? undefined });
        }
      }
    },
    [isSpeaking, isPlayingCached, speak],
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
