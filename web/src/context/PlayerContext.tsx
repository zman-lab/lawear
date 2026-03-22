import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { Capacitor, registerPlugin, PluginListenerHandle } from '@capacitor/core';
import { PlayerState, PlaylistItem, Speed, Level, ViewMode, RepeatMode, SleepTimer, TTSVoice } from '../types';
import { subjects } from '../data/ttsData';
import { insertArticleTitles } from '../utils/lawArticleHelper';
import { useSpeechSynthesis } from '../hooks/useSpeechSynthesis';

// ── 네이티브 TTS 순차 재생 플러그인 (백그라운드 안전) ───────────────────────
interface TTSFilePlugin {
  speakSequence(opts: { texts: string[]; startIndex: number; rate: number; trackTitle?: string }): Promise<void>;
  stopSequence(): Promise<void>;
  updateSequenceRate(opts: { rate: number }): Promise<void>;
  jumpSequence(opts: { index: number }): Promise<void>;
  addListener(eventName: 'sequenceEvent', handler: (ev: { event: string; index: number }) => void): Promise<PluginListenerHandle>;
  setBatteryOptimization(opts: { enabled: boolean }): Promise<void>;
  getBatteryStatus(): Promise<{ isExcluded: boolean }>;
}
const TTSFile = Capacitor.isNativePlatform()
  ? registerPlugin<TTSFilePlugin>('TTSFile')
  : null;
import {
  initMediaSession,
  updateMediaTrack,
  updateMediaPlaybackState,
  destroyMediaSession,
  cleanupMediaSession,
  MediaTrackInfo,
} from '../services/mediaSession';
import { log } from '../services/logger';
import { recordCompletion, recordReview, loadProgress } from '../services/learningProgress';

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 현재 question의 전체 문장 배열 반환
// ──────────────────────────────────────────────────────────────────────────────
// 슈퍼심플 키워드 (의의/취지/요건/효과 등 기본 개념)
const SUPERSIMPLE_KEYWORDS = ['의의', '취지', '요건', '효과', '성질', '종류', '개념', '정의', '원칙', '예외', '구별', '차이', '유사', '적용범위'];

const TTS_PIPELINE_DEBUG =
  typeof localStorage !== 'undefined' && localStorage.getItem('lawear-debug-law') !== 'false';

function getSentences(
  subjectId: string | null,
  fileId: string | null,
  questionId: string | null,
  level: Level = 1,
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

  if (TTS_PIPELINE_DEBUG) {
    console.log(`[TTS Pipeline] getSentences — subject: ${subjectId}, level: ${level}`);
  }

  // R-16 조문 제목 삽입. subject.name을 기본 법령명으로 사용.
  // Lv.3이면 내부에서 삽입을 건너뛴다.
  const ins = (s: string) => insertArticleTitles(s, subject.name, level);

  let raw: string[];
  if (level === 2) {
    // 핵심요약: 문제 제거, 목차 + 답안만
    raw = [...tocSentences, ...answer];
  } else if (level === 3) {
    // 슈퍼심플: 목차 + 답안에서 키워드 포함 문장만
    const keyAnswer = answer.filter((s) =>
      SUPERSIMPLE_KEYWORDS.some((kw) => s.includes(kw)) || s === answer[0]
    );
    raw = [...tocSentences, ...(keyAnswer.length > 0 ? keyAnswer : [answer[0] ?? ''])];
  } else {
    // Lv.1 빠른복습: 전체
    raw = [...problem, ...tocSentences, ...answer];
  }

  const processed = raw.map(ins);

  if (TTS_PIPELINE_DEBUG) {
    const changedCount = raw.filter((s, i) => s !== processed[i]).length;
    console.log(
      `[TTS Pipeline] 총 ${processed.length}문장 처리, 조문 삽입 ${changedCount}문장 변경됨`,
    );
  }

  return processed;
}

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 현재 트랙의 미디어 세션 메타데이터 생성
// ──────────────────────────────────────────────────────────────────────────────
function getTrackInfo(
  subjectId: string | null,
  fileId: string | null,
  questionId: string | null,
): MediaTrackInfo | null {
  if (!subjectId || !fileId || !questionId) return null;
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return null;
  const file = subject.files.find((f) => f.id === fileId);
  if (!file) return null;
  const question = file.questions.find((q) => q.id === questionId);
  if (!question) return null;
  return {
    subject: subject.name,
    file: file.name,
    label: question.label,
    subtitle: question.subtitle,
  };
}

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 과목의 모든 question을 PlaylistItem[]로 변환
// ──────────────────────────────────────────────────────────────────────────────
function getSubjectPlaylist(subjectId: string): PlaylistItem[] {
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return [];
  const items: PlaylistItem[] = [];
  for (const file of subject.files) {
    for (const q of file.questions) {
      items.push({ subjectId, fileId: file.id, questionId: q.id });
    }
  }
  return items;
}

// ──────────────────────────────────────────────────────────────────────────────
// 헬퍼: 파일의 모든 question을 PlaylistItem[]로 변환
// ──────────────────────────────────────────────────────────────────────────────
function getFilePlaylist(subjectId: string, fileId: string): PlaylistItem[] {
  const subject = subjects.find((s) => s.id === subjectId);
  if (!subject) return [];
  const file = subject.files.find((f) => f.id === fileId);
  if (!file) return [];
  return file.questions.map((q) => ({ subjectId, fileId, questionId: q.id }));
}

// ──────────────────────────────────────────────────────────────────────────────
// localStorage 키
// ──────────────────────────────────────────────────────────────────────────────
const STORAGE_KEY_VOICE = 'lawear-selected-voice-uri';

function loadSavedVoiceURI(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY_VOICE);
  } catch {
    return null;
  }
}

function saveVoiceURI(voiceURI: string | null): void {
  try {
    if (voiceURI) {
      localStorage.setItem(STORAGE_KEY_VOICE, voiceURI);
    } else {
      localStorage.removeItem(STORAGE_KEY_VOICE);
    }
  } catch {
    // localStorage 사용 불가 시 무시
  }
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
  speed: 5.0,
  repeatMode: 'stop-after-one',
  sleepTimer: null,
  selectedVoiceURI: loadSavedVoiceURI(),
  level: 1,
  viewMode: 'reader',
  playlist: [],
  playlistIndex: -1,
  repeatSectionStart: null,
  repeatSectionEnd: null,
  isRepeatingSectionActive: false,
};

// ──────────────────────────────────────────────────────────────────────────────
// Context 타입
// ──────────────────────────────────────────────────────────────────────────────
interface PlayerContextValue {
  state: PlayerState;
  sentences: string[];
  isTTSSupported: boolean;
  voices: TTSVoice[];
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
  playSubject: (subjectId: string) => void;
  playFile: (subjectId: string, fileId: string) => void;
  playSelected: (items: PlaylistItem[], startIndex?: number, startSentenceIndex?: number) => void;
  jumpToPlaylistIndex: (idx: number) => void;
  toggleRepeatSection: () => void;
  clearRepeatSection: () => void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

// ──────────────────────────────────────────────────────────────────────────────
// Provider
// ──────────────────────────────────────────────────────────────────────────────
export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<PlayerState>(initialState);
  const [sleepTimerRemaining, setSleepTimerRemaining] = useState<number | null>(null);

  // 현재 문장 인덱스를 ref로도 유지 (콜백 클로저에서 최신값 참조)
  const sentenceIndexRef = useRef(state.currentSentenceIndex);
  const stateRef = useRef(state);
  // fallback sync: updateState를 거치지 않는 setState 호출도 stateRef에 반영
  useEffect(() => {
    sentenceIndexRef.current = state.currentSentenceIndex;
    stateRef.current = state;
  }, [state]);

  // ── updateState: setState + stateRef 자동 동기화 ──────────────────────────
  const updateState = useCallback((updater: Partial<PlayerState> | ((prev: PlayerState) => Partial<PlayerState>)) => {
    setState((prev) => {
      const updates = typeof updater === 'function' ? updater(prev) : updater;
      const next = { ...prev, ...updates };
      stateRef.current = next;
      return next;
    });
  }, []);

  // ── CDP 자동 QA용: window.__debug__에 state 노출 (dev 빌드 전용) ──
  useEffect(() => {
    if (typeof window !== 'undefined' && import.meta.env.DEV) {
      (window as any).__debug__ = { state, setState };
    }
  }, [state]);
  const { isSupported, isNative, speak, pause, resume, cancel, setRate, setOnRateChange, voices } = useSpeechSynthesis();

  // ── 백그라운드 WebView 활성 유지 ────────────────────────────────────────
  // 무음 Audio를 loop 재생하여 시스템이 "미디어 재생 중"으로 인식 → WebView JS suspend 방지
  const silenceRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    if (state.isPlaying && !silenceRef.current) {
      // 0.1초 무음 WAV (base64)
      const wav = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
      const audio = new Audio(wav);
      audio.loop = true;
      audio.volume = 0.01; // 거의 무음
      audio.play().catch(() => {});
      silenceRef.current = audio;
    } else if (!state.isPlaying && silenceRef.current) {
      silenceRef.current.pause();
      silenceRef.current = null;
    }
    return () => {
      if (silenceRef.current) {
        silenceRef.current.pause();
        silenceRef.current = null;
      }
    };
  }, [state.isPlaying]);

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

  // ── 배터리 최적화 상태 로그 (앱 시작 시 1회) ──────────────────────────
  useEffect(() => {
    if (TTSFile) {
      TTSFile.getBatteryStatus().then((status) => {
        console.log('[Battery] 현재 상태:', status.isExcluded ? '최적화 제외' : '최적화 적용');
      }).catch(() => {});
    }
  }, []);

  // ── MediaSession 초기화 (알림바/잠금화면 미니플레이어) ──────────────────
  const mediaSessionInitRef = useRef(false);
  useEffect(() => {
    if (mediaSessionInitRef.current) return;
    mediaSessionInitRef.current = true;

    initMediaSession({
      onPlay: () => {
        // 알림바에서 재생 버튼 탭 → togglePlay와 동일
        const current = stateRef.current;
        if (!current.currentQuestionId) return;
        if (!current.isPlaying) {
          console.log('[Player] isPlaying changed to', true, 'reason: MediaSession onPlay');
          stateRef.current = { ...stateRef.current, isPlaying: true };
          setState((prev) => ({ ...prev, isPlaying: true }));
          // speakCurrentSentence는 아래 effect에서 호출됨
          mediaSessionResumeRef.current = true;
        }
      },
      onPause: () => {
        const current = stateRef.current;
        if (current.isPlaying) {
          pause();
          console.log('[Player] isPlaying changed to', false, 'reason: MediaSession onPause');
          stateRef.current = { ...stateRef.current, isPlaying: false };
          setState((prev) => ({ ...prev, isPlaying: false }));
          updateMediaPlaybackState(false);
        }
      },
      onNext: () => {
        nextQuestionRef.current?.();
      },
      onPrev: () => {
        prevQuestionRef.current?.();
      },
    });
    log.life('media_session_init');

    return () => {
      cleanupMediaSession();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 알림바 재생 버튼으로 resume 시 speakCurrentSentence 호출을 위한 ref
  const mediaSessionResumeRef = useRef(false);

  // nextQuestion/prevQuestion을 콜백에서 호출하기 위한 ref
  const nextQuestionRef = useRef<(() => void) | null>(null);
  const prevQuestionRef = useRef<(() => void) | null>(null);

  // ── MediaSession: 트랙/상태 동기화 ─────────────────────────────────────
  useEffect(() => {
    const { isPlaying, currentSubjectId, currentFileId, currentQuestionId, playlistIndex } = state;
    // playlist는 deps에 포함되지 않으므로 stateRef.current로 최신값 참조
    const playlist = stateRef.current.playlist;
    const trackInfo = getTrackInfo(currentSubjectId, currentFileId, currentQuestionId);

    if (trackInfo && currentQuestionId) {
      const hasPrev = playlist.length > 0 ? playlistIndex > 0 : false;
      const hasNext = playlist.length > 0 ? playlistIndex < playlist.length - 1 : false;
      updateMediaTrack(trackInfo, isPlaying, hasPrev, hasNext);
    }

    updateMediaPlaybackState(isPlaying);

    if (!isPlaying && !currentQuestionId) {
      destroyMediaSession();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.isPlaying, state.currentSubjectId, state.currentFileId, state.currentQuestionId, state.playlistIndex]);

  // sentences는 state 변경 시 재계산 (레벨 반영)
  const sentences = getSentences(
    state.currentSubjectId,
    state.currentFileId,
    state.currentQuestionId,
    state.level,
  );

  const sentencesRef = useRef(sentences);
  useEffect(() => {
    sentencesRef.current = sentences;
  }, [sentences]);

  // ── 네이티브 순차 재생 (백그라운드 안전) ─────────────────────────────────
  const nativeSequenceActiveRef = useRef(false);
  const isJumpingRef = useRef(false); // 구간 반복 jumpSequence 중복 방지
  const sequenceListenerRef = useRef<PluginListenerHandle | null>(null);

  // playlist 전체 문장을 합쳐서 네이티브에 넘김 — 트랙 전환도 JS 없이 네이티브가 처리
  const buildAllSentences = useCallback(() => {
    const current = stateRef.current;
    const { playlist } = current;
    if (playlist.length === 0) {
      return { allSents: sentencesRef.current, trackOffsets: [0] };
    }
    const allSents: string[] = [];
    const trackOffsets: number[] = []; // 각 트랙의 시작 인덱스
    for (const item of playlist) {
      trackOffsets.push(allSents.length);
      const s = getSentences(item.subjectId, item.fileId, item.questionId, current.level);
      allSents.push(...s);
    }
    return { allSents, trackOffsets };
  }, []);

  const startNativeSequence = useCallback(
    async (idx: number, speed: Speed) => {
      if (!TTSFile) return;

      const { allSents, trackOffsets } = buildAllSentences();
      if (allSents.length === 0) return;

      // 현재 트랙 내 idx를 전체 배열에서의 절대 인덱스로 변환
      const current = stateRef.current;
      const playlistIdx = current.playlistIndex >= 0 ? current.playlistIndex : 0;
      const absoluteIdx = (trackOffsets[playlistIdx] ?? 0) + idx;

      nativeSequenceActiveRef.current = true;
      log.tts('native_sequence_start', { idx, absoluteIdx, totalAll: allSents.length });

      // 현재 트랙 정보를 안드로이드 알림 제목에 표시하기 위해 trackTitle 구성
      const trackInfo = getTrackInfo(
        current.currentSubjectId,
        current.currentFileId,
        current.currentQuestionId,
      );
      const nativeTrackTitle = trackInfo
        ? `${trackInfo.subject} · ${trackInfo.label}`
        : undefined;

      // 기존 리스너 제거
      if (sequenceListenerRef.current) {
        sequenceListenerRef.current.remove();
        sequenceListenerRef.current = null;
      }

      // 이벤트 리스너 등록 (notifyListeners 방식)
      sequenceListenerRef.current = await TTSFile.addListener('sequenceEvent', (ev) => {
        if (!nativeSequenceActiveRef.current) return;

        console.log('[AB Debug] sequenceEvent', {
          event: ev.event,
          index: ev.index,
          isActive: stateRef.current.isRepeatingSectionActive,
          start: stateRef.current.repeatSectionStart,
          end: stateRef.current.repeatSectionEnd,
        });

        if (ev.event === 'start') {
          // 네이티브가 실제로 재생 시작 → isPlaying 보장
          if (!stateRef.current.isPlaying) {
            console.log('[Player] isPlaying changed to', true, 'reason: native sequenceEvent start');
            stateRef.current = { ...stateRef.current, isPlaying: true };
            setState((prev) => ({ ...prev, isPlaying: true }));
          }

          // 절대 인덱스 → 어떤 트랙의 몇 번째 문장인지 계산
          let trackIdx = 0;
          let localIdx = ev.index;
          for (let i = trackOffsets.length - 1; i >= 0; i--) {
            if (ev.index >= trackOffsets[i]) {
              trackIdx = i;
              localIdx = ev.index - trackOffsets[i];
              break;
            }
          }

          // 구간 반복 체크 (네이티브 모드)
          const rsNative = stateRef.current;
          if (
            rsNative.isRepeatingSectionActive &&
            rsNative.repeatSectionStart !== null &&
            rsNative.repeatSectionEnd !== null &&
            localIdx > rsNative.repeatSectionEnd &&
            !isJumpingRef.current
          ) {
            isJumpingRef.current = true;
            const currentTrackIdx = stateRef.current.playlistIndex >= 0 ? stateRef.current.playlistIndex : 0;
            const absoluteStartIdx = (trackOffsets[currentTrackIdx] ?? 0) + rsNative.repeatSectionStart;
            console.log('[AB Debug] jumping to A', { jumpTarget: absoluteStartIdx });
            TTSFile.jumpSequence({ index: absoluteStartIdx }).then(() => {
              isJumpingRef.current = false;
              setState((prev) => ({ ...prev, currentSentenceIndex: rsNative.repeatSectionStart! }));
              sentenceIndexRef.current = rsNative.repeatSectionStart!;
            }).catch(() => {
              isJumpingRef.current = false;
            });
            return;
          } else if (rsNative.isRepeatingSectionActive) {
            console.log('[AB Debug] no jump (condition not met)', { localIdx, end: stateRef.current.repeatSectionEnd });
          }

          // 트랙 전환 감지 → handleTrackEnd로 통합 처리
          const prevTrackIdx = stateRef.current.playlistIndex;
          if (trackIdx !== prevTrackIdx && stateRef.current.playlist.length > 0) {
            const mode = stateRef.current.repeatMode;

            // repeat-all / stop-after-all: 순차 진행이므로 트랙 전환을 허용
            if (mode === 'repeat-all' || mode === 'stop-after-all') {
              const item = stateRef.current.playlist[trackIdx];
              if (item) {
                const newSents = getSentences(item.subjectId, item.fileId, item.questionId, stateRef.current.level);
                sentencesRef.current = newSents;
                updateState({
                  currentSubjectId: item.subjectId,
                  currentFileId: item.fileId,
                  currentQuestionId: item.questionId,
                  currentSentenceIndex: localIdx,
                  playlistIndex: trackIdx,
                });
              }
            } else {
              // repeat-one, stop-after-one, shuffle: handleTrackEnd가 처리
              handleTrackEndRef.current(mode, true, trackOffsets);
              return;
            }
          } else {
            setState((prev) => ({ ...prev, currentSentenceIndex: localIdx }));
          }
          sentenceIndexRef.current = localIdx;
        } else if (ev.event === 'complete') {
          // 전체 playlist 완료 → handleTrackEnd로 통합 처리
          // complete에서는 trackOffsets를 넘기지 않음 (새 시퀀스를 시작해야 하므로)
          nativeSequenceActiveRef.current = false;
          handleTrackEndRef.current(stateRef.current.repeatMode, true);
        }
      });

      // 시퀀스 시작 (Promise는 즉시 resolve)
      await TTSFile.speakSequence({ texts: allSents, startIndex: absoluteIdx, rate: speed, trackTitle: nativeTrackTitle });
    },
    [buildAllSentences],
  );

  const stopNativeSequence = useCallback(() => {
    nativeSequenceActiveRef.current = false;
    if (sequenceListenerRef.current) {
      sequenceListenerRef.current.remove();
      sequenceListenerRef.current = null;
    }
    TTSFile?.stopSequence().catch(() => {});
  }, []);

  // ── 문장 재생 ──────────────────────────────────────────────────────────────
  const speakCurrentSentence = useCallback(
    (idx: number, speed: Speed) => {
      log.tts('speak_sentence', { idx, total: sentencesRef.current.length });
      const sents = sentencesRef.current;
      if (idx >= sents.length) {
        // 모든 문장 완료 → 정지
        console.log('[Player] isPlaying changed to', false, 'reason: all sentences complete (web)');
        updateState({ isPlaying: false, currentSentenceIndex: 0 });
        cancel();
        return;
      }

      // 네이티브 모드: speakSequence 사용 (백그라운드 안전)
      if (TTSFile && Capacitor.isNativePlatform()) {
        stopNativeSequence();
        startNativeSequence(idx, speed);
        return;
      }

      // 첫 문장(idx===0)일 때만 캐시 정보를 전달하여 MP3 캐시 재생을 시도한다.
      // 캐시된 MP3는 문제 전체를 하나의 파일로 담고 있으므로, 문장 단위가 아닌 트랙 단위로 재생.
      // idx > 0이면 중간부터 재생하는 것이므로 캐시를 사용하지 않고 TTS로 재생.
      const currentState = stateRef.current;
      const cacheOpts = idx === 0 && currentState.currentSubjectId && currentState.currentFileId && currentState.currentQuestionId
        ? {
            subjectId: currentState.currentSubjectId,
            fileId: currentState.currentFileId,
            questionId: currentState.currentQuestionId,
          }
        : {};

      speak(sents[idx], {
        rate: speed,
        voiceURI: currentState.selectedVoiceURI ?? undefined,
        ...cacheOpts,
        onEnd: () => {
          const nextIdx = sentenceIndexRef.current + 1;
          console.log('[AB Debug] onEnd', {
            nextIdx,
            isActive: stateRef.current.isRepeatingSectionActive,
            start: stateRef.current.repeatSectionStart,
            end: stateRef.current.repeatSectionEnd,
          });

          // 구간 반복 체크: 다음 인덱스가 구간 종료를 넘으면 시작점으로 점프
          const rs = stateRef.current;
          if (
            rs.isRepeatingSectionActive &&
            rs.repeatSectionStart !== null &&
            rs.repeatSectionEnd !== null &&
            nextIdx > rs.repeatSectionEnd
          ) {
            setState((prev) => ({ ...prev, currentSentenceIndex: rs.repeatSectionStart! }));
            sentenceIndexRef.current = rs.repeatSectionStart!;
            speakCurrentSentence(rs.repeatSectionStart!, stateRef.current.speed);
            return;
          }

          if (nextIdx < sentencesRef.current.length) {
            // 아직 문장 남음 → 다음 문장 재생
            setState((prev) => ({ ...prev, currentSentenceIndex: nextIdx }));
            sentenceIndexRef.current = nextIdx;
            speakCurrentSentence(nextIdx, stateRef.current.speed);
          } else {
            // 모든 문장 완료 → 진도 기록 + handleTrackEnd로 통합 처리
            log.player('track_complete');
            // 학습 진도 기록 + 복습 스케줄 처리
            const completedQuestionId = stateRef.current.currentQuestionId;
            if (completedQuestionId) {
              const prog = loadProgress();
              const entry = prog[completedQuestionId];
              if (entry?.reviewSchedule && Date.now() >= entry.reviewSchedule.nextReviewAt) {
                recordReview(completedQuestionId);
              } else {
                recordCompletion(completedQuestionId);
              }
            }
            handleTrackEndRef.current(stateRef.current.repeatMode, false);
          }
        },
      });
    },
    [speak, cancel],
  );

  // ── playTrackAt: 트랙 전환 공통 로직 ─────────────────────────────────────
  const playTrackAt = useCallback((
    trackIdx: number,
    item: PlaylistItem,
    isNativeMode: boolean,
    trackOffsets?: number[],
  ) => {
    const startSent = item.sentenceIndex ?? 0;
    const newSents = getSentences(item.subjectId, item.fileId, item.questionId, stateRef.current.level);
    const clampedStart = Math.max(0, Math.min(startSent, newSents.length - 1));

    sentencesRef.current = newSents;
    sentenceIndexRef.current = clampedStart;

    updateState({
      isPlaying: true,
      currentSubjectId: item.subjectId,
      currentFileId: item.fileId,
      currentQuestionId: item.questionId,
      currentSentenceIndex: clampedStart,
      playlistIndex: trackIdx,
    });

    if (isNativeMode && trackOffsets && TTSFile) {
      const jumpAbsolute = (trackOffsets[trackIdx] ?? 0) + clampedStart;
      TTSFile.jumpSequence({ index: jumpAbsolute }).catch(() => {});
    } else if (!isNativeMode) {
      speakCurrentSentence(clampedStart, stateRef.current.speed);
    }
  }, [speakCurrentSentence, updateState]);

  // ── handleNoPlaylistTrackEnd: playlist 없는 경우 ────────────────────────
  const handleNoPlaylistTrackEnd = useCallback((
    mode: RepeatMode,
    isNativeMode: boolean,
  ) => {
    const current = stateRef.current;

    if (mode === 'repeat-one') {
      sentenceIndexRef.current = 0;
      updateState({ currentSentenceIndex: 0 });
      if (isNativeMode) {
        startNativeSequence(0, current.speed);
      } else {
        speakCurrentSentence(0, current.speed);
      }
    } else if (mode === 'stop-after-one') {
      console.log('[Player] isPlaying changed to', false, 'reason: stop-after-one no-playlist');
      if (isNativeMode) nativeSequenceActiveRef.current = false;
      updateState({ isPlaying: false, currentSentenceIndex: 0 });
      sentenceIndexRef.current = 0;
    } else if (mode === 'stop-after-all') {
      const nextQ = getAdjacentQuestionInFile(current.currentSubjectId, current.currentFileId, current.currentQuestionId, 1);
      if (nextQ) {
        const newSents = getSentences(nextQ.subjectId, nextQ.fileId, nextQ.questionId, current.level);
        sentencesRef.current = newSents;
        sentenceIndexRef.current = 0;
        updateState({
          currentSubjectId: nextQ.subjectId,
          currentFileId: nextQ.fileId,
          currentQuestionId: nextQ.questionId,
          currentSentenceIndex: 0,
        });
        if (isNativeMode) {
          startNativeSequence(0, current.speed);
        } else {
          speakCurrentSentence(0, current.speed);
        }
      } else {
        console.log('[Player] isPlaying changed to', false, 'reason: stop-after-all no-playlist end');
        if (isNativeMode) nativeSequenceActiveRef.current = false;
        updateState({ isPlaying: false, currentSentenceIndex: 0 });
        sentenceIndexRef.current = 0;
      }
    } else if (mode === 'repeat-all') {
      const nextQ = getAdjacentQuestionInFile(current.currentSubjectId, current.currentFileId, current.currentQuestionId, 1);
      if (nextQ) {
        const newSents = getSentences(nextQ.subjectId, nextQ.fileId, nextQ.questionId, current.level);
        sentencesRef.current = newSents;
        sentenceIndexRef.current = 0;
        updateState({
          currentSubjectId: nextQ.subjectId,
          currentFileId: nextQ.fileId,
          currentQuestionId: nextQ.questionId,
          currentSentenceIndex: 0,
        });
        if (isNativeMode) {
          startNativeSequence(0, current.speed);
        } else {
          speakCurrentSentence(0, current.speed);
        }
      } else {
        const firstQ = getFirstQuestionInFile(current.currentSubjectId, current.currentFileId);
        if (firstQ) {
          const newSents = getSentences(firstQ.subjectId, firstQ.fileId, firstQ.questionId, current.level);
          sentencesRef.current = newSents;
          sentenceIndexRef.current = 0;
          updateState({
            currentSubjectId: firstQ.subjectId,
            currentFileId: firstQ.fileId,
            currentQuestionId: firstQ.questionId,
            currentSentenceIndex: 0,
          });
          if (isNativeMode) {
            startNativeSequence(0, current.speed);
          } else {
            speakCurrentSentence(0, current.speed);
          }
        }
      }
    } else if (mode === 'shuffle') {
      const randomQ = getRandomQuestionInFile(current.currentSubjectId, current.currentFileId, current.currentQuestionId);
      if (randomQ) {
        const newSents = getSentences(randomQ.subjectId, randomQ.fileId, randomQ.questionId, current.level);
        sentencesRef.current = newSents;
        sentenceIndexRef.current = 0;
        updateState({
          currentSubjectId: randomQ.subjectId,
          currentFileId: randomQ.fileId,
          currentQuestionId: randomQ.questionId,
          currentSentenceIndex: 0,
        });
        if (isNativeMode) {
          startNativeSequence(0, current.speed);
        } else {
          speakCurrentSentence(0, current.speed);
        }
      }
    }
  }, [speakCurrentSentence, startNativeSequence, updateState]);

  // ── handleTrackEnd: 트랙 종료 시 반복모드에 따른 다음 동작 결정 ───────────
  // 네이티브/Web 양쪽에서 호출. 반복모드 로직을 한 곳에 통합.
  const handleTrackEnd = useCallback((
    mode: RepeatMode,
    isNativeMode: boolean,
    trackOffsets?: number[],
  ) => {
    const current = stateRef.current;
    const { playlist, playlistIndex } = current;

    // === 1. repeat-one: 현재 트랙 반복 ===
    if (mode === 'repeat-one') {
      if (playlist.length > 0) {
        const currentItem = playlist[playlistIndex];
        const repeatStart = currentItem?.sentenceIndex ?? 0;
        if (isNativeMode && trackOffsets && TTSFile) {
          if (isJumpingRef.current) return;
          isJumpingRef.current = true;
          const currentTrackIdx = playlistIndex >= 0 ? playlistIndex : 0;
          const jumpAbsolute = (trackOffsets[currentTrackIdx] ?? 0) + repeatStart;
          console.log('[Player] repeat-one: jumping back to track start', { currentTrackIdx, repeatStart, jumpAbsolute });
          TTSFile.jumpSequence({ index: jumpAbsolute }).then(() => {
            isJumpingRef.current = false;
          }).catch(() => {
            isJumpingRef.current = false;
          });
        } else if (!isNativeMode) {
          speakCurrentSentence(repeatStart, current.speed);
        }
        updateState({ currentSentenceIndex: repeatStart });
        sentenceIndexRef.current = repeatStart;
      } else {
        // playlist 없으면 no-playlist 핸들러로
        handleNoPlaylistTrackEnd(mode, isNativeMode);
      }
      return;
    }

    // === 2. stop-after-one: 현재 트랙 끝나면 정지 ===
    if (mode === 'stop-after-one') {
      if (playlist.length > 0) {
        console.log('[Player] stop-after-one: stopping at track boundary');
        if (isNativeMode) {
          nativeSequenceActiveRef.current = false;
          TTSFile?.stopSequence().catch(() => {});
        }
        console.log('[Player] isPlaying changed to', false, 'reason: stop-after-one');
        updateState({ isPlaying: false, currentSentenceIndex: 0 });
        sentenceIndexRef.current = 0;
      } else {
        handleNoPlaylistTrackEnd(mode, isNativeMode);
      }
      return;
    }

    // === 3. shuffle: 랜덤 트랙 ===
    if (mode === 'shuffle') {
      if (playlist.length > 0) {
        const indexed = playlist.map((item, i) => ({ item, i })).filter(({ i }) => i !== playlistIndex);
        if (indexed.length > 0) {
          const chosen = indexed[Math.floor(Math.random() * indexed.length)];
          if (isNativeMode) {
            // 네이티브: complete 이벤트에서는 startNativeSequence로 새로 시작
            // start 이벤트(트랙 전환)에서는 jumpSequence 사용
            if (trackOffsets) {
              playTrackAt(chosen.i, chosen.item, true, trackOffsets);
            } else {
              // complete에서 호출됨 — nativeSequenceActiveRef가 false, 새로 시작 필요
              const newSents = getSentences(chosen.item.subjectId, chosen.item.fileId, chosen.item.questionId, current.level);
              const chosenStart = chosen.item.sentenceIndex ?? 0;
              const clampedChosenStart = Math.max(0, Math.min(chosenStart, newSents.length - 1));
              sentencesRef.current = newSents;
              sentenceIndexRef.current = clampedChosenStart;
              updateState({
                isPlaying: true,
                currentSubjectId: chosen.item.subjectId,
                currentFileId: chosen.item.fileId,
                currentQuestionId: chosen.item.questionId,
                currentSentenceIndex: clampedChosenStart,
                playlistIndex: chosen.i,
              });
              console.log('[Player] isPlaying changed to', true, 'reason: shuffle restart (native)');
              startNativeSequence(clampedChosenStart, current.speed);
            }
          } else {
            playTrackAt(chosen.i, chosen.item, false);
          }
        } else {
          // 1곡짜리 playlist: 자기 자신 반복
          const selfItem = playlist[playlistIndex];
          const selfStart = selfItem?.sentenceIndex ?? 0;
          sentenceIndexRef.current = selfStart;
          updateState({ currentSentenceIndex: selfStart });
          if (!isNativeMode) {
            speakCurrentSentence(selfStart, current.speed);
          } else if (trackOffsets && TTSFile) {
            const jumpAbs = (trackOffsets[playlistIndex] ?? 0) + selfStart;
            TTSFile.jumpSequence({ index: jumpAbs }).catch(() => {});
          } else {
            startNativeSequence(selfStart, current.speed);
          }
        }
      } else {
        handleNoPlaylistTrackEnd(mode, isNativeMode);
      }
      return;
    }

    // === 4. stop-after-all / repeat-all: 순차 진행 ===
    if (playlist.length > 0) {
      const nextTrackIdx = playlistIndex + 1;

      if (nextTrackIdx < playlist.length) {
        // 다음 트랙
        if (isNativeMode && trackOffsets) {
          playTrackAt(nextTrackIdx, playlist[nextTrackIdx], true, trackOffsets);
        } else if (isNativeMode) {
          // complete에서 호출 — 새로 startNativeSequence
          const nextItem = playlist[nextTrackIdx];
          const newSents = getSentences(nextItem.subjectId, nextItem.fileId, nextItem.questionId, current.level);
          const nextStart = nextItem.sentenceIndex ?? 0;
          const clampedNext = Math.max(0, Math.min(nextStart, newSents.length - 1));
          sentencesRef.current = newSents;
          sentenceIndexRef.current = clampedNext;
          updateState({
            isPlaying: true,
            currentSubjectId: nextItem.subjectId,
            currentFileId: nextItem.fileId,
            currentQuestionId: nextItem.questionId,
            currentSentenceIndex: clampedNext,
            playlistIndex: nextTrackIdx,
          });
          startNativeSequence(clampedNext, current.speed);
        } else {
          playTrackAt(nextTrackIdx, playlist[nextTrackIdx], false);
        }
      } else if (mode === 'repeat-all') {
        // 처음으로 돌아가기
        if (isNativeMode) {
          // 네이티브 complete → 새 시퀀스 시작
          const first = playlist[0];
          const firstStart = first.sentenceIndex ?? 0;
          const newSents = getSentences(first.subjectId, first.fileId, first.questionId, current.level);
          const clampedFirst = Math.max(0, Math.min(firstStart, newSents.length - 1));
          sentencesRef.current = newSents;
          sentenceIndexRef.current = clampedFirst;
          updateState({
            isPlaying: true,
            currentSubjectId: first.subjectId,
            currentFileId: first.fileId,
            currentQuestionId: first.questionId,
            currentSentenceIndex: clampedFirst,
            playlistIndex: 0,
          });
          console.log('[Player] isPlaying changed to', true, 'reason: repeat-all restart');
          startNativeSequence(clampedFirst, current.speed);
        } else {
          playTrackAt(0, playlist[0], false);
        }
      } else {
        // stop-after-all: 전곡 끝 → 정지
        console.log('[Player] isPlaying changed to', false, 'reason: stop-after-all playlist end');
        if (isNativeMode) nativeSequenceActiveRef.current = false;
        updateState({ isPlaying: false, currentSentenceIndex: 0 });
        sentenceIndexRef.current = 0;
      }
      return;
    }

    // === 5. playlist 없으면 파일 내 다음 question으로 ===
    handleNoPlaylistTrackEnd(mode, isNativeMode);
  }, [playTrackAt, handleNoPlaylistTrackEnd, speakCurrentSentence, startNativeSequence, updateState]);

  // handleTrackEnd ref — onEnd 콜백에서 최신 함수 참조
  const handleTrackEndRef = useRef(handleTrackEnd);
  useEffect(() => {
    handleTrackEndRef.current = handleTrackEnd;
  }, [handleTrackEnd]);

  // ── 네이티브 rate 변경 시 현재 문장 재시작 콜백 등록 ─────────────────────
  useEffect(() => {
    setOnRateChange(() => {
      const current = stateRef.current;
      if (current.isPlaying) {
        setState((prev) => ({ ...prev, isPlaying: true }));
        speakCurrentSentence(sentenceIndexRef.current, current.speed);
      }
    });
    return () => setOnRateChange(null);
  }, [setOnRateChange, speakCurrentSentence]);

  // ── selectQuestion (재생 없이 문제 선택만) ────────────────────────────────
  const selectQuestion = useCallback(
    (subjectId: string, fileId: string, questionId: string) => {
      log.player('select_question', { subjectId, fileId, questionId });
      // 케이스 전환 시 진행 중인 TTS를 먼저 완전히 중단
      stopNativeSequence();
      cancel();
      const sents = getSentences(subjectId, fileId, questionId, stateRef.current.level);
      sentencesRef.current = sents;
      sentenceIndexRef.current = 0;
      updateState({
        currentSubjectId: subjectId,
        currentFileId: fileId,
        currentQuestionId: questionId,
        currentSentenceIndex: 0,
        isPlaying: false,
        // 구간 반복 자동 해제
        repeatSectionStart: null,
        repeatSectionEnd: null,
        isRepeatingSectionActive: false,
      });
    },
    [cancel, stopNativeSequence, updateState],
  );

  // ── play (단일 문제 재생 — 플레이리스트 1개짜리로 설정) ─────────────────
  const play = useCallback(
    (subjectId: string, fileId: string, questionId: string) => {
      log.player('play', { subjectId, fileId, questionId });
      // 같은 파일의 전체 케이스를 playlist에 넣어서 전곡반복/다음트랙이 자연스럽게 동작
      const filePlaylist = getFilePlaylist(subjectId, fileId);
      const idx = filePlaylist.findIndex((i) => i.questionId === questionId);
      console.log('[Player] isPlaying changed to', true, 'reason: play');
      updateState({
        isPlaying: true,
        currentSubjectId: subjectId,
        currentFileId: fileId,
        currentQuestionId: questionId,
        currentSentenceIndex: 0,
        playlist: filePlaylist,
        playlistIndex: idx >= 0 ? idx : 0,
        repeatSectionStart: null,
        repeatSectionEnd: null,
        isRepeatingSectionActive: false,
      });
      sentenceIndexRef.current = 0;
      const sents = getSentences(subjectId, fileId, questionId);
      sentencesRef.current = sents;
      speakCurrentSentence(0, stateRef.current.speed);
    },
    [speakCurrentSentence, updateState],
  );

  // ── playSubject (과목 전체 재생) ──────────────────────────────────────────
  const playSubject = useCallback(
    (subjectId: string) => {
      log.player('play_subject', { subjectId });
      const playlist = getSubjectPlaylist(subjectId);
      if (playlist.length === 0) return;
      const first = playlist[0];
      console.log('[Player] isPlaying changed to', true, 'reason: playSubject');
      updateState({
        isPlaying: true,
        currentSubjectId: first.subjectId,
        currentFileId: first.fileId,
        currentQuestionId: first.questionId,
        currentSentenceIndex: 0,
        playlist,
        playlistIndex: 0,
        repeatSectionStart: null,
        repeatSectionEnd: null,
        isRepeatingSectionActive: false,
      });
      sentenceIndexRef.current = 0;
      const sents = getSentences(first.subjectId, first.fileId, first.questionId);
      sentencesRef.current = sents;
      speakCurrentSentence(0, stateRef.current.speed);
    },
    [speakCurrentSentence, updateState],
  );

  // ── playFile (파일 전체 재생) ─────────────────────────────────────────────
  const playFile = useCallback(
    (subjectId: string, fileId: string) => {
      log.player('play_file', { subjectId, fileId });
      const playlist = getFilePlaylist(subjectId, fileId);
      if (playlist.length === 0) return;
      const first = playlist[0];
      console.log('[Player] isPlaying changed to', true, 'reason: playFile');
      updateState({
        isPlaying: true,
        currentSubjectId: first.subjectId,
        currentFileId: first.fileId,
        currentQuestionId: first.questionId,
        currentSentenceIndex: 0,
        playlist,
        playlistIndex: 0,
        repeatSectionStart: null,
        repeatSectionEnd: null,
        isRepeatingSectionActive: false,
      });
      sentenceIndexRef.current = 0;
      const sents = getSentences(first.subjectId, first.fileId, first.questionId);
      sentencesRef.current = sents;
      speakCurrentSentence(0, stateRef.current.speed);
    },
    [speakCurrentSentence, updateState],
  );

  // ── playSelected (선택된 항목들 재생) ─────────────────────────────────────
  const playSelected = useCallback(
    (items: PlaylistItem[], startIndex: number = 0, startSentenceIndex: number = 0) => {
      log.player('play_selected', { count: items.length, startIndex, startSentenceIndex });
      if (items.length === 0) return;
      const idx = Math.max(0, Math.min(startIndex, items.length - 1));
      const target = items[idx];
      const sents = getSentences(target.subjectId, target.fileId, target.questionId);
      const clampedSentIdx = Math.max(0, Math.min(startSentenceIndex, sents.length - 1));
      console.log('[Player] isPlaying changed to', true, 'reason: playSelected');
      updateState((prev) => ({
        isPlaying: true,
        currentSubjectId: target.subjectId,
        currentFileId: target.fileId,
        currentQuestionId: target.questionId,
        currentSentenceIndex: clampedSentIdx,
        playlist: items,
        playlistIndex: idx,
        // 선택 재생은 선택한 곡을 다 듣는 게 자연스러우므로 stop-after-all로 전환
        repeatMode: prev.repeatMode === 'stop-after-one' ? 'stop-after-all' : prev.repeatMode,
        repeatSectionStart: null,
        repeatSectionEnd: null,
        isRepeatingSectionActive: false,
      }));
      sentenceIndexRef.current = clampedSentIdx;
      sentencesRef.current = sents;
      speakCurrentSentence(clampedSentIdx, stateRef.current.speed);
    },
    [speakCurrentSentence, updateState],
  );

  // ── togglePlay ────────────────────────────────────────────────────────────
  const togglePlay = useCallback(() => {
    log.player('toggle_play', { wasPlaying: stateRef.current.isPlaying });
    const current = stateRef.current;
    if (!current.currentQuestionId) return;

    if (current.isPlaying) {
      // 일시정지: 네이티브 Service도 중단
      stopNativeSequence();
      pause();
      console.log('[Player] isPlaying changed to', false, 'reason: togglePlay pause');
      updateState({ isPlaying: false });
    } else {
      // 케이스가 변경된 경우(selectQuestion 후 재생): playlist를 새 케이스 기준으로 재설정
      // 또는 playlist가 비어있으면 현재 파일의 전체 케이스로 자동 설정
      const playlistMismatch =
        current.playlist.length > 0 &&
        current.playlist[current.playlistIndex >= 0 ? current.playlistIndex : 0]?.questionId !== current.currentQuestionId;
      if (current.playlist.length === 0 || playlistMismatch) {
        if (current.currentSubjectId && current.currentFileId && current.currentQuestionId) {
          const filePlaylist = getFilePlaylist(current.currentSubjectId, current.currentFileId);
          const idx = filePlaylist.findIndex((i) => i.questionId === current.currentQuestionId);
          const newPlaylistIndex = idx >= 0 ? idx : 0;
          updateState({ isPlaying: true, playlist: filePlaylist, playlistIndex: newPlaylistIndex });
        } else {
          updateState({ isPlaying: true });
        }
      } else {
        updateState({ isPlaying: true });
      }

      console.log('[Player] isPlaying changed to', true, 'reason: togglePlay resume');
      // 재개: 현재 문장부터 다시 시작
      speakCurrentSentence(current.currentSentenceIndex, current.speed);
    }
  }, [pause, speakCurrentSentence, stopNativeSequence, updateState]);

  // ── stop ──────────────────────────────────────────────────────────────────
  const stop = useCallback(() => {
    log.player('stop');
    stopNativeSequence();
    cancel();
    console.log('[Player] isPlaying changed to', false, 'reason: stop');
    updateState({ isPlaying: false, currentSentenceIndex: 0 });
    sentenceIndexRef.current = 0;
  }, [cancel, stopNativeSequence, updateState]);

  // ── setSpeed ──────────────────────────────────────────────────────────────
  const setSpeed = useCallback(
    (speed: Speed) => {
      log.player('speed_change', { speed });
      setState((prev) => ({ ...prev, speed }));
      setRate(speed);
    },
    [setRate],
  );

  // ── setLevel ──────────────────────────────────────────────────────────────
  const setLevel = useCallback((level: Level) => {
    setState((prev) => ({
      ...prev,
      level,
      // 레벨 변경 시 문장 배열이 바뀌므로 구간 반복 해제
      repeatSectionStart: null,
      repeatSectionEnd: null,
      isRepeatingSectionActive: false,
    }));
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
    log.player('voice_change', { voiceURI });
    setState((prev) => ({ ...prev, selectedVoiceURI: voiceURI }));
    saveVoiceURI(voiceURI);
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
        console.log('[Player] isPlaying changed to', false, 'reason: sleepTimer expired');
        updateState({ isPlaying: false, currentSentenceIndex: 0, sleepTimer: null });
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

  // ── nextQuestion (플레이리스트 기반) ──────────────────────────────────────
  const nextQuestion = useCallback(() => {
    log.player('next_question', { playlistIndex: stateRef.current.playlistIndex });
    const current = stateRef.current;
    const { playlist, playlistIndex } = current;

    if (playlist.length > 0) {
      // 플레이리스트 모드
      const nextIdx = playlistIndex + 1;
      if (nextIdx >= playlist.length) return;
      cancel();
      const item = playlist[nextIdx];
      const sents = getSentences(item.subjectId, item.fileId, item.questionId);
      sentencesRef.current = sents;
      sentenceIndexRef.current = 0;
      if (current.isPlaying) {
        setState((prev) => ({
          ...prev,
          currentSubjectId: item.subjectId,
          currentFileId: item.fileId,
          currentQuestionId: item.questionId,
          currentSentenceIndex: 0,
          playlistIndex: nextIdx,
        }));
        speakCurrentSentence(0, current.speed);
      } else {
        setState((prev) => ({
          ...prev,
          currentSubjectId: item.subjectId,
          currentFileId: item.fileId,
          currentQuestionId: item.questionId,
          currentSentenceIndex: 0,
          playlistIndex: nextIdx,
        }));
      }
    } else {
      // 레거시: 파일 내 다음 문제
      const adjacent = getAdjacentQuestionInFile(
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
    }
  }, [cancel, play, speakCurrentSentence]);

  // ── prevQuestion (플레이리스트 기반) ──────────────────────────────────────
  const prevQuestion = useCallback(() => {
    log.player('prev_question', { playlistIndex: stateRef.current.playlistIndex });
    const current = stateRef.current;
    const { playlist, playlistIndex } = current;

    if (playlist.length > 0) {
      // 플레이리스트 모드
      const prevIdx = playlistIndex - 1;
      if (prevIdx < 0) return;
      cancel();
      const item = playlist[prevIdx];
      const sents = getSentences(item.subjectId, item.fileId, item.questionId);
      sentencesRef.current = sents;
      sentenceIndexRef.current = 0;
      if (current.isPlaying) {
        setState((prev) => ({
          ...prev,
          currentSubjectId: item.subjectId,
          currentFileId: item.fileId,
          currentQuestionId: item.questionId,
          currentSentenceIndex: 0,
          playlistIndex: prevIdx,
        }));
        speakCurrentSentence(0, current.speed);
      } else {
        setState((prev) => ({
          ...prev,
          currentSubjectId: item.subjectId,
          currentFileId: item.fileId,
          currentQuestionId: item.questionId,
          currentSentenceIndex: 0,
          playlistIndex: prevIdx,
        }));
      }
    } else {
      // 레거시: 파일 내 이전 문제
      const adjacent = getAdjacentQuestionInFile(
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
    }
  }, [cancel, play, speakCurrentSentence]);

  // ── jumpToPlaylistIndex (playlist 내 특정 곡으로 점프) ────────────────────
  const jumpToPlaylistIndex = useCallback((idx: number) => {
    const current = stateRef.current;
    const { playlist } = current;
    if (idx < 0 || idx >= playlist.length) return;
    cancel();
    const item = playlist[idx];
    const sents = getSentences(item.subjectId, item.fileId, item.questionId);
    sentencesRef.current = sents;
    sentenceIndexRef.current = 0;
    console.log('[Player] isPlaying changed to', true, 'reason: jumpToPlaylistIndex');
    updateState({
      isPlaying: true,
      currentSubjectId: item.subjectId,
      currentFileId: item.fileId,
      currentQuestionId: item.questionId,
      currentSentenceIndex: 0,
      playlistIndex: idx,
    });
    speakCurrentSentence(0, stateRef.current.speed);
  }, [cancel, speakCurrentSentence, updateState]);

  // ── toggleRepeatSection (A-B 구간 반복 토글) ─────────────────────────────
  const toggleRepeatSection = useCallback(() => {
    const current = stateRef.current;
    if (current.isRepeatingSectionActive) {
      // 3번째 탭: 구간 반복 해제
      setState((prev) => ({
        ...prev,
        repeatSectionStart: null,
        repeatSectionEnd: null,
        isRepeatingSectionActive: false,
      }));
    } else if (current.repeatSectionStart !== null && current.repeatSectionEnd === null) {
      // 2번째 탭: 종료점(B) 설정 → 구간 반복 시작
      const endIdx = current.currentSentenceIndex;
      const startIdx = current.repeatSectionStart;
      // 종료점이 시작점보다 앞이면 스왑
      const actualStart = Math.min(startIdx, endIdx);
      const actualEnd = Math.max(startIdx, endIdx);
      updateState({
        repeatSectionStart: actualStart,
        repeatSectionEnd: actualEnd,
        isRepeatingSectionActive: true,
      });
    } else {
      // 1번째 탭: 시작점(A) 설정
      updateState({
        repeatSectionStart: current.currentSentenceIndex,
        repeatSectionEnd: null,
        isRepeatingSectionActive: false,
      });
    }
  }, [updateState]);

  // ── clearRepeatSection ──────────────────────────────────────────────────
  const clearRepeatSection = useCallback(() => {
    setState((prev) => ({
      ...prev,
      repeatSectionStart: null,
      repeatSectionEnd: null,
      isRepeatingSectionActive: false,
    }));
  }, []);

  // ── MediaSession: nextQuestion/prevQuestion ref 연결 ────────────────────
  useEffect(() => {
    nextQuestionRef.current = nextQuestion;
    prevQuestionRef.current = prevQuestion;
  }, [nextQuestion, prevQuestion]);

  // ── MediaSession: 알림바 재생 버튼으로 resume 시 speak 호출 ─────────────
  useEffect(() => {
    if (mediaSessionResumeRef.current && state.isPlaying) {
      mediaSessionResumeRef.current = false;
      const current = stateRef.current;
      if (isNative) {
        speakCurrentSentence(current.currentSentenceIndex, current.speed);
      } else {
        const synth = window.speechSynthesis;
        if (synth.paused) {
          resume();
        } else {
          speakCurrentSentence(current.currentSentenceIndex, current.speed);
        }
      }
    }
  }, [state.isPlaying, isNative, resume, speakCurrentSentence]);

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
    playSubject,
    playFile,
    playSelected,
    jumpToPlaylistIndex,
    toggleRepeatSection,
    clearRepeatSection,
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

// ──────────────────────────────────────────────────────────────────────────────
// 내부 헬퍼 (파일 내 인접 문제 찾기 — 기존 getAdjacentQuestion 이름 변경)
// ──────────────────────────────────────────────────────────────────────────────
function getAdjacentQuestionInFile(
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

function getFirstQuestionInFile(
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

function getRandomQuestionInFile(
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
    return { subjectId, fileId, questionId: file.questions[0].id };
  }
  const picked = candidates[Math.floor(Math.random() * candidates.length)];
  return { subjectId, fileId, questionId: picked.id };
}
