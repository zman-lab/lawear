import { useState, useEffect, useRef, useCallback } from 'react';
import { Capacitor } from '@capacitor/core';
import { TextToSpeech } from '@capacitor-community/text-to-speech';
import { TTSVoice } from '../types';

const isNative = Capacitor.isNativePlatform();

interface SpeakOptions {
  rate?: number;
  voiceURI?: string;
  onEnd?: () => void;
  onBoundary?: (event: SpeechSynthesisEvent) => void;
}

export function useSpeechSynthesis() {
  const [isSupported] = useState(() => isNative || 'speechSynthesis' in window);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [voices, setVoices] = useState<TTSVoice[]>([]);
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const rateRef = useRef<number>(1.0);
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

  const speak = useCallback(
    (text: string, options: SpeakOptions = {}) => {
      if (!isSupported) return;

      const rate = Math.min(10, Math.max(0.1, options.rate ?? rateRef.current));

      if (isNative) {
        // 기존 재생 중단
        TextToSpeech.stop().catch(() => {});
        nativeSpeakingRef.current = true;
        nativeOnEndRef.current = options.onEnd ?? null;

        setIsSpeaking(true);
        setIsPaused(false);

        TextToSpeech.speak({
          text,
          lang: 'ko-KR',
          rate,
          pitch: 1.0,
          volume: 1.0,
          category: 'playback',
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
    [isSupported, getKoreanVoice],
  );

  const pause = useCallback(() => {
    if (!isSupported || !isSpeaking) return;
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
  }, [isSupported, isSpeaking]);

  const resume = useCallback(() => {
    if (!isSupported || !isPaused) return;
    if (isNative) {
      // 네이티브에서는 resume 불가 — PlayerContext에서 speakCurrentSentence 재호출
      setIsPaused(false);
    } else {
      window.speechSynthesis.resume();
      setIsPaused(false);
    }
  }, [isSupported, isPaused]);

  const cancel = useCallback(() => {
    if (!isSupported) return;
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
  }, [isSupported]);

  const setRate = useCallback(
    (speed: number) => {
      rateRef.current = Math.min(10, Math.max(0.1, speed));
      if (!isNative && currentUtteranceRef.current && isSpeaking) {
        const text = currentUtteranceRef.current.text;
        const onEnd = currentUtteranceRef.current.onend as (() => void) | null;
        speak(text, { rate: rateRef.current, onEnd: onEnd ?? undefined });
      }
      // 네이티브에서 속도 변경 시 현재 문장 재시작은 PlayerContext에서 처리
    },
    [isSpeaking, speak],
  );

  return {
    isSupported,
    isSpeaking,
    isPaused,
    isNative,
    currentUtterance: currentUtteranceRef.current,
    speak,
    pause,
    resume,
    cancel,
    setRate,
    voices,
  };
}
