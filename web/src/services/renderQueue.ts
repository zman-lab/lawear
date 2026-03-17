/**
 * Render Queue Service
 *
 * TTS 텍스트를 백그라운드에서 WAV 파일로 렌더링하는 큐 시스템.
 *
 * 네이티브(Android): TTSFile 플러그인의 synthesizeToFile() 사용.
 * 웹: 지원하지 않음 (SpeechSynthesis 오디오 캡처 불가).
 */
import { Capacitor } from '@capacitor/core';
import { TTSFile } from '../plugins/ttsFile';
import { hasCachedAudio, markAsCached } from './audioCache';

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

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * 렌더링이 지원되는 환경인지 반환한다.
 * Android 네이티브에서만 동작 (TextToSpeech.synthesizeToFile).
 */
export function isRenderingSupported(): boolean {
  return isNative;
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

    try {
      // 이미 캐시된 항목은 스킵
      const cached = await hasCachedAudio(item.subjectId, item.fileId, item.questionId);
      if (cached) {
        _currentStatus = 'skipped';
        _skipped++;
        notifyProgress();
        continue;
      }

      _currentStatus = 'rendering';
      notifyProgress();

      // 네이티브 synthesizeToFile 호출
      const fileName = `lawear-audio/${item.subjectId}/${item.fileId}/${item.questionId}.wav`;

      const result = await TTSFile.synthesizeToFile({
        text: item.text,
        fileName,
        rate: _rate,
        voiceName: _voiceURI ?? undefined,
      });

      // 매니페스트 업데이트 (파일은 네이티브에서 직접 기록됨)
      await markAsCached(
        item.subjectId,
        item.fileId,
        item.questionId,
        result.size,
        _voiceURI,
      );

      _currentStatus = 'done';
      _completed++;
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

// ── 내부: 진행률 알림 ───────────────────────────────────────────────────────

function notifyProgress(): void {
  _progressCallback?.(getProgress());
}
