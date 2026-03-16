/**
 * MediaSession Service
 *
 * Android 알림바/잠금화면 미니플레이어를 제어한다.
 * - 네이티브: capacitor-music-controls-plugin (Android MediaSession)
 * - 웹(개발용): Web MediaSession API (Chrome 등에서 동작)
 *
 * PlayerContext에서 재생 상태가 바뀔 때마다 호출하여 알림을 동기화한다.
 */
import { Capacitor } from '@capacitor/core';

const isNative = Capacitor.isNativePlatform();

// ── 타입 ────────────────────────────────────────────────────────────────────

export interface MediaTrackInfo {
  /** 과목명 (예: "민사소송법") */
  subject: string;
  /** 파일명 (예: "미케01") */
  file: string;
  /** 문제 라벨 (예: "Case 01") */
  label: string;
  /** 부제 (예: "상계항변 · 항소의 이익") */
  subtitle: string;
}

export interface MediaSessionCallbacks {
  onPlay: () => void;
  onPause: () => void;
  onNext: () => void;
  onPrev: () => void;
}

// ── 내부 상태 ───────────────────────────────────────────────────────────────

let _initialized = false;
let _callbacks: MediaSessionCallbacks | null = null;
let _nativePlugin: typeof import('capacitor-music-controls-plugin').CapacitorMusicControls | null = null;
let _androidListenerCleanup: (() => void) | null = null;

// ── 초기화 (앱 시작 시 1회) ─────────────────────────────────────────────────

export async function initMediaSession(callbacks: MediaSessionCallbacks): Promise<void> {
  if (_initialized) return;
  _callbacks = callbacks;

  if (isNative) {
    try {
      const mod = await import('capacitor-music-controls-plugin');
      _nativePlugin = mod.CapacitorMusicControls;

      // Android: document event listener (Capacitor 4+ 호환)
      const handler = (event: Event) => {
        const customEvent = event as CustomEvent;
        const message = customEvent.detail?.message ?? (customEvent as unknown as { message: string }).message;
        handleNativeEvent(message);
      };
      document.addEventListener('controlsNotification', handler);
      _androidListenerCleanup = () => document.removeEventListener('controlsNotification', handler);

      // iOS: addListener도 등록 (플랫폼에 따라 둘 중 하나가 동작)
      _nativePlugin.addListener('controlsNotification', (info: { message: string }) => {
        handleNativeEvent(info.message);
      });
    } catch {
      // 플러그인 미설치 시 조용히 실패
      console.warn('[MediaSession] capacitor-music-controls-plugin not available');
    }
  } else {
    // 웹: Web MediaSession API
    setupWebMediaSession(callbacks);
  }

  _initialized = true;
}

// ── 트랙 정보 업데이트 ─────────────────────────────────────────────────────

export async function updateMediaTrack(
  track: MediaTrackInfo,
  isPlaying: boolean,
  hasPrev: boolean,
  hasNext: boolean,
): Promise<void> {
  const title = `${track.subject} · ${track.file} ${track.label}`;
  const artist = track.subtitle || track.subject;

  if (isNative && _nativePlugin) {
    try {
      await _nativePlugin.create({
        track: title,
        artist,
        album: track.subject,
        hasPrev,
        hasNext,
        hasClose: true,
        isPlaying,
        dismissable: false,
        ticker: `${track.subject} - ${track.label}`,
        // iOS
        duration: 0,
        elapsed: 0,
        hasSkipForward: false,
        hasSkipBackward: false,
        hasScrubbing: false,
      });
    } catch {
      // 알림 생성 실패 시 조용히 무시
    }
  } else if ('mediaSession' in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title,
      artist,
      album: track.subject,
    });
  }
}

// ── 재생 상태 업데이트 ─────────────────────────────────────────────────────

export function updateMediaPlaybackState(isPlaying: boolean): void {
  if (isNative && _nativePlugin) {
    try {
      _nativePlugin.updateIsPlaying({ isPlaying });
    } catch {
      // 무시
    }
  } else if ('mediaSession' in navigator) {
    navigator.mediaSession.playbackState = isPlaying ? 'playing' : 'paused';
  }
}

// ── 알림 제거 ──────────────────────────────────────────────────────────────

export async function destroyMediaSession(): Promise<void> {
  if (isNative && _nativePlugin) {
    try {
      await _nativePlugin.destroy();
    } catch {
      // 무시
    }
  } else if ('mediaSession' in navigator) {
    navigator.mediaSession.metadata = null;
    navigator.mediaSession.playbackState = 'none';
  }
}

// ── 정리 (앱 종료 시) ──────────────────────────────────────────────────────

export function cleanupMediaSession(): void {
  _androidListenerCleanup?.();
  _androidListenerCleanup = null;
  _callbacks = null;
  _initialized = false;
}

// ── 내부: 네이티브 이벤트 처리 ─────────────────────────────────────────────

function handleNativeEvent(message: string): void {
  if (!_callbacks) return;
  switch (message) {
    case 'music-controls-play':
    case 'music-controls-toggle-play-pause':
      _callbacks.onPlay();
      break;
    case 'music-controls-pause':
      _callbacks.onPause();
      break;
    case 'music-controls-next':
      _callbacks.onNext();
      break;
    case 'music-controls-previous':
      _callbacks.onPrev();
      break;
    case 'music-controls-destroy':
      // 알림 닫기 → 정지
      _callbacks.onPause();
      break;
    // 헤드셋 이벤트
    case 'music-controls-headset-unplugged':
      _callbacks.onPause();
      break;
    case 'music-controls-headset-plugged':
    case 'music-controls-media-button':
      // 무시 또는 토글
      break;
  }
}

// ── 내부: Web MediaSession API 설정 ────────────────────────────────────────

function setupWebMediaSession(callbacks: MediaSessionCallbacks): void {
  if (!('mediaSession' in navigator)) return;

  navigator.mediaSession.setActionHandler('play', () => callbacks.onPlay());
  navigator.mediaSession.setActionHandler('pause', () => callbacks.onPause());
  navigator.mediaSession.setActionHandler('previoustrack', () => callbacks.onPrev());
  navigator.mediaSession.setActionHandler('nexttrack', () => callbacks.onNext());
}
