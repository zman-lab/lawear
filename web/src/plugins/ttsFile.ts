/**
 * TTSFile Capacitor Plugin — TypeScript 인터페이스
 *
 * Android TextToSpeech.synthesizeToFile() 래핑.
 * 네이티브 환경에서만 동작하며, 웹에서는 미지원.
 */
import { registerPlugin } from '@capacitor/core';

export interface TTSEngine {
  /** 패키지명 (예: com.google.android.tts) */
  name: string;
  /** 표시명 (예: Google 텍스트 음성 변환 엔진) */
  label: string;
}

export interface SynthesizeResult {
  /** 저장된 파일 상대경로 (Directory.Data 기준) */
  filePath: string;
  /** 파일 크기 (bytes) */
  size: number;
}

export interface TTSFilePlugin {
  /**
   * TTS 텍스트를 WAV 파일로 합성하여 저장한다.
   * 긴 텍스트는 자동으로 청크 분할 + WAV 결합.
   */
  synthesizeToFile(options: {
    /** 합성할 텍스트 */
    text: string;
    /** 저장 파일명 (앱 내부 저장소 기준 상대경로) */
    fileName: string;
    /** 재생 속도 (기본 1.0) */
    rate?: number;
    /** 음성 이름 (Android Voice.getName() 값) */
    voiceName?: string;
  }): Promise<SynthesizeResult>;

  /**
   * 설치된 TTS 엔진 목록을 반환한다.
   */
  getEngines(): Promise<{
    engines: TTSEngine[];
    defaultEngine: string;
  }>;

  /**
   * Android TTS 설정 화면을 연다.
   */
  openTTSSettings(): Promise<void>;

  /**
   * 배터리 최적화 제외를 요청하거나, 비활성 시 안내 로그를 남긴다.
   * enabled=false 시 시스템 설정에서 직접 해제해야 함.
   */
  setBatteryOptimization(opts: { enabled: boolean }): Promise<void>;

  /**
   * 현재 배터리 최적화 제외 상태를 반환한다.
   */
  getBatteryStatus(): Promise<{ isExcluded: boolean }>;
}

export const TTSFile = registerPlugin<TTSFilePlugin>('TTSFile');
