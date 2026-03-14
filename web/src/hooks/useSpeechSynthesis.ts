import { useState, useEffect, useRef, useCallback } from 'react';

interface SpeakOptions {
  rate?: number;
  voiceURI?: string;
  onEnd?: () => void;
  onBoundary?: (event: SpeechSynthesisEvent) => void;
}

export function useSpeechSynthesis() {
  const [isSupported] = useState(() => 'speechSynthesis' in window);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const rateRef = useRef<number>(1.0);

  // 음성 목록 로드
  useEffect(() => {
    if (!isSupported) return;

    const loadVoices = () => {
      const allVoices = window.speechSynthesis.getVoices();
      setVoices(allVoices);
    };

    loadVoices();
    window.speechSynthesis.addEventListener('voiceschanged', loadVoices);
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', loadVoices);
    };
  }, [isSupported]);

  // 한국어 음성 선택 (Google TTS 우선)
  const getKoreanVoice = useCallback((): SpeechSynthesisVoice | null => {
    const allVoices = window.speechSynthesis.getVoices();
    const koVoices = allVoices.filter((v) => v.lang === 'ko-KR' || v.lang.startsWith('ko'));
    if (koVoices.length === 0) return null;
    // Google TTS 음성 우선
    const googleVoice = koVoices.find((v) => v.name.toLowerCase().includes('google'));
    return googleVoice ?? koVoices[0];
  }, []);

  const speak = useCallback(
    (text: string, options: SpeakOptions = {}) => {
      if (!isSupported) return;

      // 기존 발화 취소
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'ko-KR';
      utterance.rate = Math.min(10, Math.max(0.1, options.rate ?? rateRef.current));

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
        // cancel()에 의한 interrupted는 정상 동작이므로 무시
        if (e.error === 'interrupted' || e.error === 'canceled') return;
        setIsSpeaking(false);
        setIsPaused(false);
        currentUtteranceRef.current = null;
      };

      if (options.onBoundary) {
        utterance.onboundary = options.onBoundary;
      }

      currentUtteranceRef.current = utterance;
      // Android Chrome에서 cancel 직후 speak이 씹히는 버그 방지
      // requestAnimationFrame으로 다음 프레임에서 speak 호출
      requestAnimationFrame(() => {
        window.speechSynthesis.speak(utterance);
      });
    },
    [isSupported, getKoreanVoice],
  );

  const pause = useCallback(() => {
    if (!isSupported || !isSpeaking) return;
    window.speechSynthesis.pause();
    setIsPaused(true);
  }, [isSupported, isSpeaking]);

  const resume = useCallback(() => {
    if (!isSupported || !isPaused) return;
    window.speechSynthesis.resume();
    setIsPaused(false);
  }, [isSupported, isPaused]);

  const cancel = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setIsPaused(false);
    currentUtteranceRef.current = null;
  }, [isSupported]);

  const setRate = useCallback(
    (speed: number) => {
      rateRef.current = Math.min(10, Math.max(0.1, speed));
      // 현재 발화 중이면 재시작
      if (currentUtteranceRef.current && isSpeaking) {
        const text = currentUtteranceRef.current.text;
        const onEnd = currentUtteranceRef.current.onend as (() => void) | null;
        speak(text, { rate: rateRef.current, onEnd: onEnd ?? undefined });
      }
    },
    [isSpeaking, speak],
  );

  return {
    isSupported,
    isSpeaking,
    isPaused,
    currentUtterance: currentUtteranceRef.current,
    speak,
    pause,
    resume,
    cancel,
    setRate,
    voices,
  };
}
