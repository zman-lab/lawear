import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { PlayerState, Speed, Level, ViewMode, RepeatMode, SleepTimer } from '../types';
import { subjects } from '../data/ttsData';
import { useSpeechSynthesis } from '../hooks/useSpeechSynthesis';

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 현재 question의 전체 문장 배열 반환
// ──────────────────────────────────────────────────────────────────────────────
function getSentences(
  subjectId: string | null,
  fileId: string | null,
  questionId: string | null,
): string[] {
  if (!subjectId || !fileId || !questionId) return [];
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return [];
  const file = subject.files.find((f) => f.id === fileId);
  if (!file) return [];
  const question = file.questions.find((q) => q.id === questionId);
  if (!question) return [];
  const { problem, toc, answer } = question.content;
  const tocSentences = toc.map((t) => `${t.number} ${t.text}`);
  return [...problem, ...tocSentences, ...answer];
}

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 다음/이전 question id 찾기
// ──────────────────────────────────────────────────────────────────────────────
function getAdjacentQuestion(
  subjectId: string | null,
  fileId: string | null,
  questionId: string | null,
  direction: 1 | -1,
): { subjectId: string; fileId: string; questionId: string } | null {
  if (!subjectId || !fileId || !questionId) return null;
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return null;
  const file = subject.files.find((f) => f.id === fileId);
  if (!file) return null;
  const idx = file.questions.findIndex((q) => q.id === questionId);
  if (idx === -1) return null;
  const nextIdx = idx + direction;
  if (nextIdx < 0 || nextIdx >= file.questions.length) return null;
  return { subjectId, fileId, questionId: file.questions[nextIdx].id };
}

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 파일 내 첫 설문 찾기
// ──────────────────────────────────────────────────────────────────────────────
function getFirstQuestion(
  subjectId: string | null,
  fileId: string | null,
): { subjectId: string; fileId: string; questionId: string } | null {
  if (!subjectId || !fileId) return null;
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return null;
  const file = subject.files.find((f) => f.id === fileId);
  if (!file || file.questions.length === 0) return null;
  return { subjectId, fileId, questionId: file.questions[0].id };
}

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 파일 내 랜덤 설문 (현재 제외, 1개뿐이면 동일)
// ──────────────────────────────────────────────────────────────────────────────
function getRandomQuestion(
  subjectId: string | null,
  fileId: string | null,
  currentQuestionId: string | null,
): { subjectId: string; fileId: string; questionId: string } | null {
  if (!subjectId || !fileId) return null;
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return null;
  const file = subject.files.find((f) => f.id === fileId);
  if (!file || file.questions.length === 0) return null;
  const candidates = file.questions.filter((q) => q.id !== currentQuestionId);
  if (candidates.length === 0) {
    // 1개뿐 → 같은 설문
    return { subjectId, fileId, questionId: file.questions[0].id };
  }
  const picked = candidates[Math.floor(Math.random() * candidates.length)];
  return { subjectId, fileId, questionId: picked.id };
}

// ──────────────────────────────────────────────────────────────────────────────
// 초기 상태
// ──────────────────────────────────────────────────────────────────────────────
const initialState: PlayerState = {
  isPlaying: false,
  currentSubjectId: null,
  currentFileId: null,
  currentQuestionId: null,
  currentSentenceIndex: 0,
  speed: 1.0,
  repeatMode: 'stop-after-one',
  sleepTimer: null,
  selectedVoiceURI: null,
  level: 1,
  viewMode: 'reader',
};

// ──────────────────────────────────────────────────────────────────────────────
// Context 타입
// ──────────────────────────────────────────────────────────────────────────────
interface PlayerContextValue {
  state: PlayerState;
  sentences: string[];
  isTTSSupported: boolean;
  voices: SpeechSynthesisVoice[];
  play: (subjectId: string, fileId: string, questionId: string) => void;
  selectQuestion: (subjectId: string, fileId: string, questionId: string) => void;
  togglePlay: () => void;
  stop: () => void;
  setSpeed: (speed: Speed) => void;
  setLevel: (level: Level) => void;
  setViewMode: (mode: ViewMode) => void;
  setRepeatMode: (mode: RepeatMode) => void;
  setSleepTimer: (seconds: number | null) => void;
  sleepTimerRemaining: number | null;
  setVoice: (voiceURI: string | null) => void;
  nextSentence: () => void;
  prevSentence: () => void;
  setSentenceIndex: (idx: number) => void;
  nextQuestion: () => void;
  prevQuestion: () => void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

// ──────────────────────────────────────────────────────────────────────────────
// Provider
// ──────────────────────────────────────────────────────────────────────────────
export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<PlayerState>(initialState);
  const [sleepTimerRemaining, setSleepTimerRemaining] = useState<number | null>(null);
  const { isSupported, speak, pause, resume, cancel, setRate, voices } = useSpeechSynthesis();

  // 백그라운드 재생 허용 — visibilitychange 핸들러 제거됨

  // ── E-05: Wake Lock (화면 꺼짐 방지) ────────────────────────────────────
  useEffect(() => {
    let wakeLock: WakeLockSentinel | null = null;
    const requestWakeLock = async () => {
      if ('wakeLock' in navigator && state.isPlaying) {
        try {
          wakeLock = await navigator.wakeLock.request('screen');
        } catch {
          // Wake Lock 실패 시 무시 (브라우저 정책)
        }
      }
    };
    if (state.isPlaying) {
      requestWakeLock();
    }
    return () => { wakeLock?.release(); };
  }, [state.isPlaying]);

  // sentences는 state 변경 시 재계산
  const sentences = getSentences(
    state.currentSubjectId,
    state.currentFileId,
    state.currentQuestionId,
  );

  // 현재 문장 인덱스를 ref로도 유지 (콜백 클로저에서 최신값 참조)
  const sentenceIndexRef = useRef(state.currentSentenceIndex);
  const stateRef = useRef(state);
  useEffect(() => {
    sentenceIndexRef.current = state.currentSentenceIndex;
    stateRef.current = state;
  }, [state]);

  const sentencesRef = useRef(sentences);
  useEffect(() => {
    sentencesRef.current = sentences;
  }, [sentences]);

  // ── 문장 재생 ──────────────────────────────────────────────────────────────
  const speakCurrentSentence = useCallback(
    (idx: number, speed: Speed) => {
      const sents = sentencesRef.current;
      if (idx >= sents.length) {
        // 모든 문장 완료 → 정지
        setState((prev) => ({
          ...prev,
          isPlaying: false,
          currentSentenceIndex: 0,
        }));
        cancel();
        return;
      }

      speak(sents[idx], {
        rate: speed,
        voiceURI: stateRef.current.selectedVoiceURI ?? undefined,
        onEnd: () => {
          const nextIdx = sentenceIndexRef.current + 1;
          if (nextIdx < sentencesRef.current.length) {
            // 아직 문장 남음 → 다음 문장 재생
            setState((prev) => ({ ...prev, currentSentenceIndex: nextIdx }));
            sentenceIndexRef.current = nextIdx;
            speakCurrentSentence(nextIdx, stateRef.current.speed);
          } else {
            // 모든 문장 완료 → repeatMode에 따라 분기
            const mode = stateRef.current.repeatMode;

            if (mode === 'stop-after-one') {
              // 정지
              setState((prev) => ({ ...prev, isPlaying: false, currentSentenceIndex: 0 }));
            } else if (mode === 'repeat-one') {
              // 현재 설문 처음부터 재시작
              setState((prev) => ({ ...prev, currentSentenceIndex: 0 }));
              sentenceIndexRef.current = 0;
              speakCurrentSentence(0, stateRef.current.speed);
            } else if (mode === 'stop-after-all') {
              // 다음 설문으로 이동, 마지막이면 정지
              const current = stateRef.current;
              const next = getAdjacentQuestion(
                current.currentSubjectId,
                current.currentFileId,
                current.currentQuestionId,
                1,
              );
              if (next) {
                const newSents = getSentences(next.subjectId, next.fileId, next.questionId);
                sentencesRef.current = newSents;
                sentenceIndexRef.current = 0;
                setState((prev) => ({
                  ...prev,
                  currentSubjectId: next.subjectId,
                  currentFileId: next.fileId,
                  currentQuestionId: next.questionId,
                  currentSentenceIndex: 0,
                }));
                speakCurrentSentence(0, stateRef.current.speed);
              } else {
                // 마지막 설문 → 정지
                setState((prev) => ({ ...prev, isPlaying: false, currentSentenceIndex: 0 }));
              }
            } else if (mode === 'repeat-all') {
              // 다음 설문, 마지막이면 첫 설문으로 순환
              const current = stateRef.current;
              const next = getAdjacentQuestion(
                current.currentSubjectId,
                current.currentFileId,
                current.currentQuestionId,
                1,
              );
              if (next) {
                const newSents = getSentences(next.subjectId, next.fileId, next.questionId);
                sentencesRef.current = newSents;
                sentenceIndexRef.current = 0;
                setState((prev) => ({
                  ...prev,
                  currentSubjectId: next.subjectId,
                  currentFileId: next.fileId,
                  currentQuestionId: next.questionId,
                  currentSentenceIndex: 0,
                }));
                speakCurrentSentence(0, stateRef.current.speed);
              } else {
                // 마지막 → 첫 설문으로 돌아감
                const firstQ = getFirstQuestion(current.currentSubjectId, current.currentFileId);
                if (firstQ) {
                  const newSents = getSentences(firstQ.subjectId, firstQ.fileId, firstQ.questionId);
                  sentencesRef.current = newSents;
                  sentenceIndexRef.current = 0;
                  setState((prev) => ({
                    ...prev,
                    currentSubjectId: firstQ.subjectId,
                    currentFileId: firstQ.fileId,
                    currentQuestionId: firstQ.questionId,
                    currentSentenceIndex: 0,
                  }));
                  speakCurrentSentence(0, stateRef.current.speed);
                }
              }
            } else if (mode === 'shuffle') {
              // 파일 내 랜덤 설문 선택
              const current = stateRef.current;
              const randomQ = getRandomQuestion(
                current.currentSubjectId,
                current.currentFileId,
                current.currentQuestionId,
              );
              if (randomQ) {
                const newSents = getSentences(randomQ.subjectId, randomQ.fileId, randomQ.questionId);
                sentencesRef.current = newSents;
                sentenceIndexRef.current = 0;
                setState((prev) => ({
                  ...prev,
                  currentSubjectId: randomQ.subjectId,
                  currentFileId: randomQ.fileId,
                  currentQuestionId: randomQ.questionId,
                  currentSentenceIndex: 0,
                }));
                speakCurrentSentence(0, stateRef.current.speed);
              }
            }
          }
        },
      });
    },
    [speak, cancel],
  );

  // ── selectQuestion (재생 없이 문제 선택만) ────────────────────────────────
  const selectQuestion = useCallback(
    (subjectId: string, fileId: string, questionId: string) => {
      setState((prev) => ({
        ...prev,
        currentSubjectId: subjectId,
        currentFileId: fileId,
        currentQuestionId: questionId,
        currentSentenceIndex: 0,
      }));
      sentenceIndexRef.current = 0;
      const sents = getSentences(subjectId, fileId, questionId);
      sentencesRef.current = sents;
    },
    [],
  );

  // ── play ──────────────────────────────────────────────────────────────────
  const play = useCallback(
    (subjectId: string, fileId: string, questionId: string) => {
      setState((prev) => ({
        ...prev,
        isPlaying: true,
        currentSubjectId: subjectId,
        currentFileId: fileId,
        currentQuestionId: questionId,
        currentSentenceIndex: 0,
      }));
      sentenceIndexRef.current = 0;
      // sentences 갱신은 다음 render에서 반영되므로 직접 계산
      const sents = getSentences(subjectId, fileId, questionId);
      sentencesRef.current = sents;
      speakCurrentSentence(0, stateRef.current.speed);
    },
    [speakCurrentSentence],
  );

  // ── togglePlay ────────────────────────────────────────────────────────────
  const togglePlay = useCallback(() => {
    const current = stateRef.current;
    if (!current.currentQuestionId) return;

    if (current.isPlaying) {
      pause();
      setState((prev) => ({ ...prev, isPlaying: false }));
    } else {
      resume();
      setState((prev) => ({ ...prev, isPlaying: true }));
    }
  }, [pause, resume]);

  // ── stop ──────────────────────────────────────────────────────────────────
  const stop = useCallback(() => {
    cancel();
    setState((prev) => ({
      ...prev,
      isPlaying: false,
      currentSentenceIndex: 0,
    }));
    sentenceIndexRef.current = 0;
  }, [cancel]);

  // ── setSpeed ──────────────────────────────────────────────────────────────
  const setSpeed = useCallback(
    (speed: Speed) => {
      setRate(speed);
      setState((prev) => ({ ...prev, speed }));
    },
    [setRate],
  );

  // ── setLevel ──────────────────────────────────────────────────────────────
  const setLevel = useCallback((level: Level) => {
    setState((prev) => ({ ...prev, level }));
  }, []);

  // ── setViewMode ───────────────────────────────────────────────────────────
  const setViewMode = useCallback((viewMode: ViewMode) => {
    setState((prev) => ({ ...prev, viewMode }));
  }, []);

  // ── setRepeatMode ───────────────────────────────────────────────────────
  const setRepeatMode = useCallback((repeatMode: RepeatMode) => {
    setState((prev) => ({ ...prev, repeatMode }));
  }, []);

  // ── setSleepTimer ───────────────────────────────────────────────────────
  const setSleepTimer = useCallback((seconds: number | null) => {
    if (seconds === null) {
      setState((prev) => ({ ...prev, sleepTimer: null }));
    } else {
      const timer: SleepTimer = {
        endTime: Date.now() + seconds * 1000,
        totalSeconds: seconds,
      };
      setState((prev) => ({ ...prev, sleepTimer: timer }));
    }
  }, []);

  // ── setVoice ────────────────────────────────────────────────────────────
  const setVoice = useCallback((voiceURI: string | null) => {
    setState((prev) => ({ ...prev, selectedVoiceURI: voiceURI }));
  }, []);

  // ── 슬립 타이머 카운트다운 ──────────────────────────────────────────────
  useEffect(() => {
    if (!state.sleepTimer) {
      setSleepTimerRemaining(null);
      return;
    }

    const update = () => {
      const timer = stateRef.current.sleepTimer;
      if (!timer) return;
      const remaining = Math.max(0, Math.ceil((timer.endTime - Date.now()) / 1000));
      setSleepTimerRemaining(remaining);
      if (remaining <= 0) {
        cancel();
        setState((prev) => ({
          ...prev,
          isPlaying: false,
          currentSentenceIndex: 0,
          sleepTimer: null,
        }));
      }
    };

    update(); // 즉시 1회
    const intervalId = setInterval(update, 1000);
    return () => clearInterval(intervalId);
  }, [state.sleepTimer, cancel]);

  // ── nextSentence ──────────────────────────────────────────────────────────
  const nextSentence = useCallback(() => {
    const current = stateRef.current;
    const sents = sentencesRef.current;
    const nextIdx = current.currentSentenceIndex + 1;
    if (nextIdx >= sents.length) return;
    cancel();
    setState((prev) => ({ ...prev, currentSentenceIndex: nextIdx }));
    sentenceIndexRef.current = nextIdx;
    if (current.isPlaying) {
      speakCurrentSentence(nextIdx, current.speed);
    }
  }, [cancel, speakCurrentSentence]);

  // ── prevSentence ──────────────────────────────────────────────────────────
  const prevSentence = useCallback(() => {
    const current = stateRef.current;
    const prevIdx = Math.max(0, current.currentSentenceIndex - 1);
    cancel();
    setState((prev) => ({ ...prev, currentSentenceIndex: prevIdx }));
    sentenceIndexRef.current = prevIdx;
    if (current.isPlaying) {
      speakCurrentSentence(prevIdx, current.speed);
    }
  }, [cancel, speakCurrentSentence]);

  // ── setSentenceIndex ──────────────────────────────────────────────────────
  const setSentenceIndex = useCallback(
    (idx: number) => {
      const current = stateRef.current;
      const sents = sentencesRef.current;
      const clampedIdx = Math.max(0, Math.min(idx, sents.length - 1));
      cancel();
      setState((prev) => ({ ...prev, currentSentenceIndex: clampedIdx }));
      sentenceIndexRef.current = clampedIdx;
      if (current.isPlaying) {
        speakCurrentSentence(clampedIdx, current.speed);
      }
    },
    [cancel, speakCurrentSentence],
  );

  // ── nextQuestion ──────────────────────────────────────────────────────────
  const nextQuestion = useCallback(() => {
    const current = stateRef.current;
    const adjacent = getAdjacentQuestion(
      current.currentSubjectId,
      current.currentFileId,
      current.currentQuestionId,
      1,
    );
    if (!adjacent) return;
    cancel();
    if (current.isPlaying) {
      play(adjacent.subjectId, adjacent.fileId, adjacent.questionId);
    } else {
      setState((prev) => ({
        ...prev,
        currentSubjectId: adjacent.subjectId,
        currentFileId: adjacent.fileId,
        currentQuestionId: adjacent.questionId,
        currentSentenceIndex: 0,
      }));
    }
  }, [cancel, play]);

  // ── prevQuestion ──────────────────────────────────────────────────────────
  const prevQuestion = useCallback(() => {
    const current = stateRef.current;
    const adjacent = getAdjacentQuestion(
      current.currentSubjectId,
      current.currentFileId,
      current.currentQuestionId,
      -1,
    );
    if (!adjacent) return;
    cancel();
    if (current.isPlaying) {
      play(adjacent.subjectId, adjacent.fileId, adjacent.questionId);
    } else {
      setState((prev) => ({
        ...prev,
        currentSubjectId: adjacent.subjectId,
        currentFileId: adjacent.fileId,
        currentQuestionId: adjacent.questionId,
        currentSentenceIndex: 0,
      }));
    }
  }, [cancel, play]);

  const value: PlayerContextValue = {
    state,
    sentences,
    isTTSSupported: isSupported,
    voices,
    play,
    selectQuestion,
    togglePlay,
    stop,
    setSpeed,
    setLevel,
    setViewMode,
    setRepeatMode,
    setSleepTimer,
    sleepTimerRemaining,
    setVoice,
    nextSentence,
    prevSentence,
    setSentenceIndex,
    nextQuestion,
    prevQuestion,
  };

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

// ──────────────────────────────────────────────────────────────────────────────
// 소비 훅
// ──────────────────────────────────────────────────────────────────────────────
export function usePlayer(): PlayerContextValue {
  const ctx = useContext(PlayerContext);
  if (!ctx) {
    throw new Error('usePlayer must be used within a PlayerProvider');
  }
  return ctx;
}
