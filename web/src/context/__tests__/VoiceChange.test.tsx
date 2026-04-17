/**
 * TC-07: 재생 중 음성 변경 후 재개 시 새 음성 반영 테스트
 *
 * 버그: 재생 중 일시정지 → 음성 변경 → 재개 시 이전 음성 그대로 재생됨
 * 원인: setVoice가 setState만 사용하여 stateRef.current에 즉시 반영 안 됨
 * 수정: setVoice에서 updateState 사용하여 stateRef.current 즉시 동기화
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ── localStorage + SpeechSynthesis polyfill ──────────────────────────────
// vi.hoisted는 모든 vi.mock/import보다 먼저 실행되어 모듈 로딩 시점에 유효
vi.hoisted(() => {
  // localStorage (Node.js 내장 localStorage는 getItem 없음)
  const store: Record<string, string> = {};
  const ls = {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, val: string) => { store[key] = val; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
    get length() { return Object.keys(store).length; },
    key: (i: number) => Object.keys(store)[i] ?? null,
  };
  Object.defineProperty(globalThis, 'localStorage', {
    value: ls,
    writable: true,
    configurable: true,
  });

  // SpeechSynthesisUtterance (jsdom에 없음)
  if (typeof globalThis.SpeechSynthesisUtterance === 'undefined') {
    (globalThis as any).SpeechSynthesisUtterance = class SpeechSynthesisUtterance {
      text: string;
      lang: string = '';
      rate: number = 1;
      pitch: number = 1;
      volume: number = 1;
      voice: any = null;
      onstart: ((ev: any) => void) | null = null;
      onend: ((ev: any) => void) | null = null;
      onerror: ((ev: any) => void) | null = null;
      onboundary: ((ev: any) => void) | null = null;
      constructor(text: string = '') {
        this.text = text;
      }
    };
  }

  // HTMLMediaElement.play() polyfill (jsdom은 play 미구현)
  (globalThis as any).Audio = class MockAudio {
    src: string = '';
    loop: boolean = false;
    volume: number = 1;
    playbackRate: number = 1;
    paused: boolean = true;
    onplay: (() => void) | null = null;
    onended: (() => void) | null = null;
    onerror: (() => void) | null = null;
    constructor(src?: string) {
      if (src) this.src = src;
    }
    play() { this.paused = false; return Promise.resolve(); }
    pause() { this.paused = true; }
    load() {}
    removeAttribute() {}
  };
});

import { render, act } from '@testing-library/react';
import React, { useEffect } from 'react';
import { PlayerProvider, usePlayer } from '../PlayerContext';

// ── Mock: @capacitor/core ─────────────────────────────────────────────────
vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => false },
  registerPlugin: () => null,
}));

// ── Mock: @capacitor-community/text-to-speech ─────────────────────────────
vi.mock('@capacitor-community/text-to-speech', () => ({
  TextToSpeech: {
    getSupportedVoices: () => Promise.resolve({ voices: [] }),
    speak: () => Promise.resolve(),
    stop: () => Promise.resolve(),
  },
}));

// ── Mock: data/tts ─────────────────────────────────────────────────────────
vi.mock('../../data/tts', () => ({
  subjects: [
    {
      id: 'test-subject',
      name: 'Test Subject',
      files: [
        {
          id: 'test-file',
          name: 'Test File',
          questions: [
            {
              id: 'test-q1',
              label: 'Test Q1',
              subtitle: 'sub',
              content: {
                problem: ['Test problem sentence.'],
                toc: [],
                answer: ['Test answer sentence.'],
              },
            },
          ],
        },
      ],
    },
  ],
}));

// ── Mock: services ─────────────────────────────────────────────────────────
vi.mock('../../services/mediaSession', () => ({
  initMediaSession: vi.fn(),
  updateMediaTrack: vi.fn(),
  updateMediaPlaybackState: vi.fn(),
  destroyMediaSession: vi.fn(),
  cleanupMediaSession: vi.fn(),
}));

vi.mock('../../services/logger', () => ({
  log: {
    player: vi.fn(),
    tts: vi.fn(),
    life: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
  },
}));

vi.mock('../../services/learningProgress', () => ({
  recordCompletion: vi.fn(),
  recordReview: vi.fn(),
  loadProgress: () => ({}),
}));

vi.mock('../../services/audioCache', () => ({
  getCachedAudioUri: () => Promise.resolve(null),
}));

vi.mock('../../utils/lawArticleHelper', () => ({
  insertArticleTitles: (s: string) => s,
}));

// ── speechSynthesis 스텁 ──────────────────────────────────────────────────
let lastSpokenUtterance: SpeechSynthesisUtterance | null = null;
let mockVoices: SpeechSynthesisVoice[] = [];

function createMockVoice(name: string, voiceURI: string, lang: string): SpeechSynthesisVoice {
  return {
    name,
    voiceURI,
    lang,
    default: false,
    localService: true,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any as SpeechSynthesisVoice;
}

beforeEach(() => {
  lastSpokenUtterance = null;
  mockVoices = [
    createMockVoice('Korean Default', 'kor-default', 'ko-KR'),
    createMockVoice('Korean Variant G01', 'kor-x-lvariant-g01', 'ko-KR'),
    createMockVoice('Korean Variant G02', 'kor-x-lvariant-g02', 'ko-KR'),
  ];

  // speechSynthesis stub
  const synth = {
    speak: vi.fn((utt: SpeechSynthesisUtterance) => {
      lastSpokenUtterance = utt;
      // onend를 호출하지 않음 — 테스트에서 수동으로 제어
    }),
    cancel: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    getVoices: vi.fn(() => mockVoices),
    paused: false,
    speaking: false,
    pending: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
    onvoiceschanged: null,
  };

  Object.defineProperty(window, 'speechSynthesis', {
    value: synth,
    writable: true,
    configurable: true,
  });

  // navigator.wakeLock stub
  Object.defineProperty(navigator, 'wakeLock', {
    value: undefined,
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── 테스트용 컨슈머 컴포넌트 ──────────────────────────────────────────────
// PlayerContext의 기능을 외부로 노출하는 테스트 헬퍼
interface ExposedContextRef {
  play: ReturnType<typeof usePlayer>['play'];
  togglePlay: ReturnType<typeof usePlayer>['togglePlay'];
  setVoice: ReturnType<typeof usePlayer>['setVoice'];
  stop: ReturnType<typeof usePlayer>['stop'];
  state: ReturnType<typeof usePlayer>['state'];
}

function TestConsumer({ ctxRef }: { ctxRef: React.MutableRefObject<ExposedContextRef | null> }) {
  const ctx = usePlayer();
  useEffect(() => {
    ctxRef.current = {
      play: ctx.play,
      togglePlay: ctx.togglePlay,
      setVoice: ctx.setVoice,
      stop: ctx.stop,
      state: ctx.state,
    };
  });
  return null;
}

// ── TC-07 ──────────────────────────────────────────────────────────────────
describe('TC-07: 재생 중 음성 변경 후 재개 시 새 음성 반영', () => {
  it('일시정지 → 음성 변경 → 재개 시 새 음성(kor-x-lvariant-g01)으로 utterance 생성', async () => {
    const ctxRef: React.MutableRefObject<ExposedContextRef | null> = { current: null };

    render(
      <PlayerProvider>
        <TestConsumer ctxRef={ctxRef} />
      </PlayerProvider>,
    );

    // 1단계: 재생 시작 (기본 음성)
    await act(async () => {
      ctxRef.current!.play('test-subject', 'test-file', 'test-q1');
    });

    // requestAnimationFrame 대기
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(r));
    });

    // speak이 호출되었는지 확인
    expect(window.speechSynthesis.speak).toHaveBeenCalled();
    // 기본 음성이거나 voiceURI 미지정 (자동 선택)
    const firstUtterance = lastSpokenUtterance;
    expect(firstUtterance).not.toBeNull();

    // 2단계: 일시정지
    await act(async () => {
      ctxRef.current!.togglePlay();
    });

    // isPlaying이 false로 변경 확인
    expect(ctxRef.current!.state.isPlaying).toBe(false);

    // 3단계: 음성 변경 (새 음성 URI)
    const NEW_VOICE_URI = 'kor-x-lvariant-g01';
    await act(async () => {
      ctxRef.current!.setVoice(NEW_VOICE_URI);
    });

    // state에 새 음성이 반영되었는지 확인
    expect(ctxRef.current!.state.selectedVoiceURI).toBe(NEW_VOICE_URI);

    // speak 호출 횟수 리셋
    (window.speechSynthesis.speak as ReturnType<typeof vi.fn>).mockClear();
    lastSpokenUtterance = null;

    // 4단계: 재개 (togglePlay)
    await act(async () => {
      ctxRef.current!.togglePlay();
    });

    // requestAnimationFrame 대기
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(r));
    });

    // 5단계: 검증 — 새 utterance가 새 음성으로 생성되었는지 확인
    expect(window.speechSynthesis.speak).toHaveBeenCalled();
    expect(lastSpokenUtterance).not.toBeNull();
    expect(lastSpokenUtterance!.voice).not.toBeNull();
    expect(lastSpokenUtterance!.voice!.voiceURI).toBe(NEW_VOICE_URI);
    expect(lastSpokenUtterance!.voice!.name).toBe('Korean Variant G01');
  });

  it('음성을 두 번 변경 후 재개 시 최종 음성이 반영', async () => {
    const ctxRef: React.MutableRefObject<ExposedContextRef | null> = { current: null };

    render(
      <PlayerProvider>
        <TestConsumer ctxRef={ctxRef} />
      </PlayerProvider>,
    );

    // 재생
    await act(async () => {
      ctxRef.current!.play('test-subject', 'test-file', 'test-q1');
    });
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(r));
    });

    // 일시정지
    await act(async () => {
      ctxRef.current!.togglePlay();
    });

    // 음성 1차 변경
    await act(async () => {
      ctxRef.current!.setVoice('kor-x-lvariant-g01');
    });

    // 음성 2차 변경 (최종)
    const FINAL_VOICE_URI = 'kor-x-lvariant-g02';
    await act(async () => {
      ctxRef.current!.setVoice(FINAL_VOICE_URI);
    });

    expect(ctxRef.current!.state.selectedVoiceURI).toBe(FINAL_VOICE_URI);

    (window.speechSynthesis.speak as ReturnType<typeof vi.fn>).mockClear();
    lastSpokenUtterance = null;

    // 재개
    await act(async () => {
      ctxRef.current!.togglePlay();
    });
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(r));
    });

    expect(window.speechSynthesis.speak).toHaveBeenCalled();
    expect(lastSpokenUtterance).not.toBeNull();
    expect(lastSpokenUtterance!.voice).not.toBeNull();
    expect(lastSpokenUtterance!.voice!.voiceURI).toBe(FINAL_VOICE_URI);
  });

  it('음성을 null(자동)로 변경 후 재개 시 한국어 기본 음성 사용', async () => {
    const ctxRef: React.MutableRefObject<ExposedContextRef | null> = { current: null };

    render(
      <PlayerProvider>
        <TestConsumer ctxRef={ctxRef} />
      </PlayerProvider>,
    );

    // 특정 음성으로 시작
    await act(async () => {
      ctxRef.current!.setVoice('kor-x-lvariant-g01');
    });

    // 재생
    await act(async () => {
      ctxRef.current!.play('test-subject', 'test-file', 'test-q1');
    });
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(r));
    });

    // 일시정지
    await act(async () => {
      ctxRef.current!.togglePlay();
    });

    // 음성을 null(자동)로 변경
    await act(async () => {
      ctxRef.current!.setVoice(null);
    });

    expect(ctxRef.current!.state.selectedVoiceURI).toBeNull();

    (window.speechSynthesis.speak as ReturnType<typeof vi.fn>).mockClear();
    lastSpokenUtterance = null;

    // 재개
    await act(async () => {
      ctxRef.current!.togglePlay();
    });
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(r));
    });

    // 자동 선택 시 getKoreanVoice()가 호출되어 Korean Default가 선택됨
    expect(window.speechSynthesis.speak).toHaveBeenCalled();
    expect(lastSpokenUtterance).not.toBeNull();
    // voice가 null이 아닌 한국어 기본 음성
    expect(lastSpokenUtterance!.voice).not.toBeNull();
    expect(lastSpokenUtterance!.voice!.voiceURI).toBe('kor-default');
  });
});
