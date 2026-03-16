/**
 * Render Queue Service
 *
 * TTS 텍스트를 백그라운드에서 MP3로 렌더링하는 큐 시스템.
 *
 * Web SpeechSynthesis + MediaRecorder로 오디오를 캡처하거나,
 * 네이티브 환경에서는 캡처가 불가능하므로 "렌더링 불가" 상태를 반환한다.
 * (네이티브 synthesizeToFile은 추후 커스텀 Capacitor 플러그인으로 구현)
 *
 * 렌더링 중에도 TTS 실시간 재생은 정상 동작한다. (별도 utterance 사용)
 */
import { Capacitor } from '@capacitor/core';
import { saveCachedAudio } from './audioCache';

const isNative = Capacitor.isNativePlatform();

// ── 타입 ────────────────────────────────────────────────────────────────────

export interface RenderItem {
  subjectId: string;
  fileId: string;
  questionId: string;
  /** 렌더링할 전체 텍스트 (문장 배열 join) */
  text: string;
}

export type RenderItemStatus = 'pending' | 'rendering' | 'done' | 'error' | 'skipped';

export interface RenderProgress {
  /** 전체 큐 항목 수 */
  total: number;
  /** 완료된 항목 수 */
  completed: number;
  /** 에러난 항목 수 */
  errors: number;
  /** 스킵된 항목 수 (이미 캐시됨) */
  skipped: number;
  /** 현재 렌더링 중인 항목 */
  current: RenderItem | null;
  /** 현재 항목 상태 */
  currentStatus: RenderItemStatus;
  /** 큐가 실행 중인지 */
  isRunning: boolean;
  /** 렌더링 지원 여부 */
  isSupported: boolean;
}

export type ProgressCallback = (progress: RenderProgress) => void;

// ── 내부 상태 ───────────────────────────────────────────────────────────────

let _queue: RenderItem[] = [];
let _isRunning = false;
let _isCancelled = false;
let _completed = 0;
let _errors = 0;
let _skipped = 0;
let _currentItem: RenderItem | null = null;
let _currentStatus: RenderItemStatus = 'pending';
let _progressCallback: ProgressCallback | null = null;
let _voiceURI: string | null = null;
let _rate: number = 1.0;

// ── Web SpeechSynthesis 렌더링 지원 여부 ────────────────────────────────────

/**
 * Web 환경에서 MediaRecorder + SpeechSynthesis 조합이 가능한지 확인한다.
 * Android WebView에서는 거의 불가능하므로, 데스크탑 Chrome 등에서만 동작.
 */
function isWebRenderingSupported(): boolean {
  if (isNative) return false;
  // Web SpeechSynthesis + MediaRecorder가 모두 있어야 함
  // 실제로는 SpeechSynthesis의 오디오 스트림을 캡처할 수 없으므로,
  // OfflineAudioContext + decodeAudioData 등의 우회가 필요하지만
  // 현 단계에서는 "지원 안 함"으로 처리하고, 추후 확장 가능하도록 구조만 잡는다.
  return false;
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * 렌더링이 지원되는 환경인지 반환한다.
 * 현재: Web SpeechSynthesis + MediaRecorder 조합이 가능한 환경만.
 * 추후: Android 네이티브 synthesizeToFile 플러그인 추가 시 true 확장.
 */
export function isRenderingSupported(): boolean {
  return isWebRenderingSupported();
}

/**
 * 큐에 렌더링 항목들을 추가한다.
 */
export function enqueue(items: RenderItem[]): void {
  _queue.push(...items);
}

/**
 * 큐를 비운다.
 */
export function clearQueue(): void {
  _queue = [];
  _completed = 0;
  _errors = 0;
  _skipped = 0;
  _currentItem = null;
  _currentStatus = 'pending';
}

/**
 * 진행률 콜백을 등록한다.
 */
export function onProgress(callback: ProgressCallback | null): void {
  _progressCallback = callback;
}

/**
 * 렌더링에 사용할 음성과 속도를 설정한다.
 */
export function setRenderOptions(voiceURI: string | null, rate: number): void {
  _voiceURI = voiceURI;
  _rate = rate;
}

/**
 * 현재 진행 상태를 반환한다.
 */
export function getProgress(): RenderProgress {
  return {
    total: _queue.length + _completed + _errors + _skipped,
    completed: _completed,
    errors: _errors,
    skipped: _skipped,
    current: _currentItem,
    currentStatus: _currentStatus,
    isRunning: _isRunning,
    isSupported: isRenderingSupported(),
  };
}

/**
 * 큐를 순차적으로 처리한다.
 * 이미 캐시된 항목은 스킵한다.
 */
export async function startQueue(): Promise<void> {
  if (_isRunning) return;
  if (!isRenderingSupported()) {
    // 렌더링 미지원 환경: 큐 항목을 모두 skipped로 처리
    _skipped += _queue.length;
    _queue = [];
    notifyProgress();
    return;
  }

  _isRunning = true;
  _isCancelled = false;
  notifyProgress();

  while (_queue.length > 0 && !_isCancelled) {
    const item = _queue.shift()!;
    _currentItem = item;
    _currentStatus = 'rendering';
    notifyProgress();

    try {
      // 실제 렌더링은 추후 구현 (현재 isRenderingSupported()가 false이므로 여기 도달 안 함)
      const audioBlob = await renderSingleItem(item);
      if (audioBlob) {
        await saveCachedAudio(
          item.subjectId,
          item.fileId,
          item.questionId,
          audioBlob,
          _voiceURI,
        );
        _currentStatus = 'done';
        _completed++;
      } else {
        _currentStatus = 'skipped';
        _skipped++;
      }
    } catch {
      _currentStatus = 'error';
      _errors++;
    }

    notifyProgress();
  }

  _currentItem = null;
  _isRunning = false;
  notifyProgress();
}

/**
 * 큐 처리를 중단한다.
 * 현재 렌더링 중인 항목은 완료 후 중단된다.
 */
export function stopQueue(): void {
  _isCancelled = true;
}

/**
 * 큐가 실행 중인지 반환한다.
 */
export function isQueueRunning(): boolean {
  return _isRunning;
}

// ── 내부: 단일 항목 렌더링 ──────────────────────────────────────────────────

/**
 * 단일 텍스트를 오디오 Blob으로 렌더링한다.
 * 현재 Web SpeechSynthesis에서 오디오 스트림 캡처가 불가능하므로,
 * 추후 아래 방법 중 하나로 확장:
 *   1. Android 네이티브 synthesizeToFile() → Capacitor 플러그인
 *   2. Web Audio API + OfflineAudioContext (실험적)
 *   3. 서버 사이드 TTS API 호출 (Cloud TTS)
 *
 * 현재는 placeholder로 null을 반환한다.
 */
async function renderSingleItem(_item: RenderItem): Promise<Blob | null> {
  // TODO: 실제 렌더링 구현
  // 참고: _voiceURI, _rate를 사용
  void _voiceURI;
  void _rate;
  return null;
}

// ── 내부: 진행률 알림 ───────────────────────────────────────────────────────

function notifyProgress(): void {
  _progressCallback?.(getProgress());
}
