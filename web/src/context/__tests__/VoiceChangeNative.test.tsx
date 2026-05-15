/**
 * TC-08: 네이티브 실기기 경로 — 음성 변경이 TTSFile.speakSequence 호출에 전달되는지 검증
 *
 * 버그:
 *   실기기에서는 speakCurrentSentence → startNativeSequence → TTSFile.speakSequence
 *   호출 경로인데, TTSFile.speakSequence에 voice 파라미터가 전달되지 않아서
 *   음성 변경 후 재개해도 기본 음성으로 재생됨.
 *
 * 수정:
 *   1. TTSFile.speakSequence가 voiceName을 받도록 인터페이스 확장
 *   2. startNativeSequence에서 state.selectedVoiceURI를 voiceName으로 전달
 *   3. setVoice 재생 중 호출 시 TTSFile.setSequenceVoice + stop/restart
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ── localStorage + SpeechSynthesisUtterance polyfill ─────────────────────
vi.hoisted(() => {
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

  if (typeof globalThis.SpeechSynthesisUtterance === 'undefined') {
    (globalThis as any).SpeechSynthesisUtterance = class {
      text: string;
      lang = '';
      rate = 1;
      pitch = 1;
      volume = 1;
      voice: any = null;
      onstart: any = null;
      onend: any = null;
      onerror: any = null;
      onboundary: any = null;
      constructor(text = '') { this.text = text; }
    };
  }

  (globalThis as any).Audio = class {
    src = ''; loop = false; volume = 1; playbackRate = 1; paused = true;
    onplay: any = null; onended: any = null; onerror: any = null;
    constructor(src?: string) { if (src) this.src = src; }
    play() { this.paused = false; return Promise.resolve(); }
    pause() { this.paused = true; }
    load() {}
    removeAttribute() {}
  };
});

import { render, act } from '@testing-library/react';
import React, { useEffect } from 'react';

// ── Mock: @capacitor/core — 네이티브 플랫폼으로 간주 ────────────────────
// vi.hoisted로 mock이 평가되는 시점에 이미 존재하도록 보장
const {
  mockSpeakSequence,
  mockStopSequence,
  mockSetSequenceVoice,
  mockJumpSequence,
  mockUpdateSequenceRate,
  mockAddListener,
  mockTTSFileListeners,
  mockTTSFilePlugin,
} = vi.hoisted(() => {
  // vi.hoisted 안에서는 vi가 전역으로 이미 제공됨
  const sSeq = vi.fn((_opts: any) => Promise.resolve());
  const stSeq = vi.fn(() => Promise.resolve());
  const svSeq = vi.fn((_opts: any) => Promise.resolve());
  const jpSeq = vi.fn(() => Promise.resolve());
  const urSeq = vi.fn(() => Promise.resolve());
  const listeners: Array<(ev: { event: string; index: number }) => void> = [];
  const addL = vi.fn((_name: string, handler: any) => {
    listeners.push(handler);
    return Promise.resolve({ remove: vi.fn() });
  });
  const plugin = {
    speakSequence: sSeq,
    stopSequence: stSeq,
    setSequenceVoice: svSeq,
    jumpSequence: jpSeq,
    updateSequenceRate: urSeq,
    addListener: addL,
    getBatteryStatus: () => Promise.resolve({ isExcluded: true }),
    setBatteryOptimization: () => Promise.resolve(),
  };
  return {
    mockSpeakSequence: sSeq,
    mockStopSequence: stSeq,
    mockSetSequenceVoice: svSeq,
    mockJumpSequence: jpSeq,
    mockUpdateSequenceRate: urSeq,
    mockAddListener: addL,
    mockTTSFileListeners: listeners,
    mockTTSFilePlugin: plugin,
  };
});
// TS 경고 회피: 일부 mock은 테스트에서 직접 참조하지 않지만 beforeEach에서 사용
void mockJumpSequence;
void mockUpdateSequenceRate;
void mockAddListener;

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => true },
  registerPlugin: () => mockTTSFilePlugin,
}));

// ── Mock: @capacitor-community/text-to-speech ───────────────────────────
vi.mock('@capacitor-community/text-to-speech', () => ({
  TextToSpeech: {
    getSupportedVoices: () => Promise.resolve({
      voices: [
        { voiceURI: 'ko-kr-x-koc-network', name: 'ko-kr-x-koc-network', lang: 'ko-KR' },
        { voiceURI: 'ko-kr-x-kod-local', name: 'ko-kr-x-kod-local', lang: 'ko-KR' },
        { voiceURI: 'ko-kr-x-lvariant-g01', name: 'ko-kr-x-lvariant-g01', lang: 'ko-KR' },
      ],
    }),
    speak: () => Promise.resolve(),
    stop: () => Promise.resolve(),
  },
}));

// ── Mock: data/tts ─────────────────────────────────────────────────────────
vi.mock('../../data/tts', () => ({
  subjects: [{
    id: 'test-subject',
    name: 'Test',
    files: [{
      id: 'test-file',
      name: 'Test File',
      questions: [{
        id: 'test-q1',
        label: 'Q1',
        subtitle: 'sub',
        content: { problem: ['문제입니다.'], toc: [], answer: ['답안입니다.'] },
      }],
    }],
  }],
}));

vi.mock('../../services/mediaSession', () => ({
  initMediaSession: vi.fn(),
  updateMediaTrack: vi.fn(),
  updateMediaPlaybackState: vi.fn(),
  destroyMediaSession: vi.fn(),
  cleanupMediaSession: vi.fn(),
}));

vi.mock('../../services/logger', () => ({
  log: {
    player: vi.fn(), tts: vi.fn(), life: vi.fn(), error: vi.fn(), warn: vi.fn(), ui: vi.fn(),
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

// PlayerContext를 import — 네이티브 플랫폼 mock이 적용된 상태
// eslint-disable-next-line import/first
import { PlayerProvider, usePlayer } from '../PlayerContext';

beforeEach(() => {
  mockSpeakSequence.mockClear();
  mockStopSequence.mockClear();
  mockSetSequenceVoice.mockClear();
  mockJumpSequence.mockClear();
  mockAddListener.mockClear();
  mockTTSFileListeners.length = 0;

  Object.defineProperty(navigator, 'wakeLock', {
    value: undefined, writable: true, configurable: true,
  });

  // 네이티브 모드에서도 initial voices load를 위한 speechSynthesis stub
  Object.defineProperty(window, 'speechSynthesis', {
    value: {
      speak: vi.fn(), cancel: vi.fn(), pause: vi.fn(), resume: vi.fn(),
      getVoices: () => [],
      paused: false, speaking: false, pending: false,
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
    },
    writable: true, configurable: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

interface Ctx {
  play: ReturnType<typeof usePlayer>['play'];
  togglePlay: ReturnType<typeof usePlayer>['togglePlay'];
  setVoice: ReturnType<typeof usePlayer>['setVoice'];
  state: ReturnType<typeof usePlayer>['state'];
}

function TestConsumer({ ctxRef }: { ctxRef: React.MutableRefObject<Ctx | null> }) {
  const ctx = usePlayer();
  useEffect(() => {
    ctxRef.current = {
      play: ctx.play, togglePlay: ctx.togglePlay, setVoice: ctx.setVoice, state: ctx.state,
    };
  });
  return null;
}

describe('TC-08: 네이티브 실기기 경로 — TTSFile.speakSequence에 voice 전달', () => {
  it('첫 재생 시 selectedVoiceURI가 speakSequence의 voiceName으로 전달된다', async () => {
    const ctxRef: React.MutableRefObject<Ctx | null> = { current: null };

    render(
      <PlayerProvider>
        <TestConsumer ctxRef={ctxRef} />
      </PlayerProvider>,
    );

    // 음성 선택 (재생 전)
    await act(async () => {
      ctxRef.current!.setVoice('ko-kr-x-lvariant-g01');
    });

    // 재생 시작
    await act(async () => {
      ctxRef.current!.play('test-subject', 'test-file', 'test-q1');
    });

    // speakSequence가 호출되었고 voiceName 파라미터가 포함되어야 함
    expect(mockSpeakSequence).toHaveBeenCalled();
    const callArgs = (mockSpeakSequence.mock.calls[0] as any[])[0] as any;
    expect(callArgs.voiceName).toBe('ko-kr-x-lvariant-g01');
    expect(callArgs.texts).toBeDefined();
    expect(callArgs.rate).toBeDefined();
  });

  it('재생 중 음성 변경 → stopSequence + 새 speakSequence 호출 + 새 voiceName 전달', async () => {
    const ctxRef: React.MutableRefObject<Ctx | null> = { current: null };

    render(
      <PlayerProvider>
        <TestConsumer ctxRef={ctxRef} />
      </PlayerProvider>,
    );

    // 기본 재생 + 첫 speakSequence 대기 (startNativeSequence 내부 await 완료까지)
    await act(async () => {
      ctxRef.current!.play('test-subject', 'test-file', 'test-q1');
      await new Promise((r) => setTimeout(r, 10));
    });

    // 네이티브 sequence start 이벤트 시뮬레이션 (isPlaying=true 유지)
    await act(async () => {
      for (const h of mockTTSFileListeners) {
        h({ event: 'start', index: 0 });
      }
    });

    expect(ctxRef.current!.state.isPlaying).toBe(true);

    mockSpeakSequence.mockClear();
    mockStopSequence.mockClear();

    // 음성 변경 (재생 중) — 두 번째 startNativeSequence의 await 완료까지 대기
    await act(async () => {
      ctxRef.current!.setVoice('ko-kr-x-lvariant-g01');
      await new Promise((r) => setTimeout(r, 20));
    });

    // state 반영
    expect(ctxRef.current!.state.selectedVoiceURI).toBe('ko-kr-x-lvariant-g01');

    // setSequenceVoice가 호출되어야 함 (즉시 반영 시도)
    expect(mockSetSequenceVoice).toHaveBeenCalledWith({ voiceName: 'ko-kr-x-lvariant-g01' });

    // 기존 sequence 중단
    expect(mockStopSequence).toHaveBeenCalled();

    // 새 speakSequence가 새 voiceName으로 호출
    expect(mockSpeakSequence).toHaveBeenCalled();
    const callArgs = (mockSpeakSequence.mock.calls[0] as any[])[0] as any;
    expect(callArgs.voiceName).toBe('ko-kr-x-lvariant-g01');
  });

  it('일시정지 → 음성 변경 → 재개 시 새 voiceName으로 speakSequence 호출', async () => {
    const ctxRef: React.MutableRefObject<Ctx | null> = { current: null };

    render(
      <PlayerProvider>
        <TestConsumer ctxRef={ctxRef} />
      </PlayerProvider>,
    );

    // 기본 재생 시작
    await act(async () => {
      ctxRef.current!.play('test-subject', 'test-file', 'test-q1');
    });

    // start 이벤트로 isPlaying 확정
    await act(async () => {
      for (const h of mockTTSFileListeners) {
        h({ event: 'start', index: 0 });
      }
    });

    // 일시정지
    await act(async () => {
      ctxRef.current!.togglePlay();
    });
    expect(ctxRef.current!.state.isPlaying).toBe(false);

    // 음성 변경 (일시정지 상태)
    await act(async () => {
      ctxRef.current!.setVoice('ko-kr-x-lvariant-g01');
    });
    expect(ctxRef.current!.state.selectedVoiceURI).toBe('ko-kr-x-lvariant-g01');

    mockSpeakSequence.mockClear();

    // 재개
    await act(async () => {
      ctxRef.current!.togglePlay();
    });

    // 새 speakSequence 호출에 voiceName이 전달되어야 함
    expect(mockSpeakSequence).toHaveBeenCalled();
    const callArgs = (mockSpeakSequence.mock.calls[0] as any[])[0] as any;
    expect(callArgs.voiceName).toBe('ko-kr-x-lvariant-g01');
  });

  it('selectedVoiceURI가 null이면 voiceName 파라미터 없이 speakSequence 호출', async () => {
    const ctxRef: React.MutableRefObject<Ctx | null> = { current: null };

    render(
      <PlayerProvider>
        <TestConsumer ctxRef={ctxRef} />
      </PlayerProvider>,
    );

    // voice를 null로 설정 (자동)
    await act(async () => {
      ctxRef.current!.setVoice(null);
    });

    // 재생
    await act(async () => {
      ctxRef.current!.play('test-subject', 'test-file', 'test-q1');
    });

    expect(mockSpeakSequence).toHaveBeenCalled();
    const callArgs = (mockSpeakSequence.mock.calls[0] as any[])[0] as any;
    // voiceName 프로퍼티 자체가 없어야 함
    expect('voiceName' in callArgs).toBe(false);
  });
});
