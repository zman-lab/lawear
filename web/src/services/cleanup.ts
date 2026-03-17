/**
 * 레거시 파일 정리 서비스
 * 앱 시작 시 1회 실행하여 이전 다운로드/캐시 찌꺼기 제거
 */
import { Filesystem, Directory } from '@capacitor/filesystem';
import { Capacitor } from '@capacitor/core';
import { log } from './logger';

/** 앱 외부 저장소(Downloads 등)에 남은 레거시 APK 파일 삭제 */
async function cleanLegacyApks(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;

  // 앱 외부 저장소에서 lawear 관련 파일 정리
  const dirs = [Directory.External, Directory.Documents];

  for (const dir of dirs) {
    try {
      const result = await Filesystem.readdir({ path: '', directory: dir });
      for (const file of result.files) {
        const name = file.name.toLowerCase();
        if (name.includes('lawear') && name.endsWith('.apk')) {
          await Filesystem.deleteFile({ path: file.name, directory: dir });
          log.life('legacy_apk_deleted', { file: file.name, dir: String(dir) });
        }
      }
    } catch {
      // 해당 디렉토리 접근 불가 시 무시
    }
  }
}

/** 앱 내부 저장소의 임시 파일 정리 */
async function cleanTempFiles(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;

  try {
    const result = await Filesystem.readdir({ path: '', directory: Directory.Cache });
    for (const file of result.files) {
      const name = file.name.toLowerCase();
      if (name.endsWith('.apk') || name.endsWith('.apk.bin')) {
        await Filesystem.deleteFile({ path: file.name, directory: Directory.Cache });
        log.life('temp_file_deleted', { file: file.name });
      }
    }
  } catch {
    // 무시
  }
}

/**
 * 앱 시작 시 1회 호출 — 레거시 파일 정리
 * 비동기, 실패해도 앱 동작에 영향 없음
 */
export async function runCleanup(): Promise<void> {
  try {
    await Promise.all([cleanLegacyApks(), cleanTempFiles()]);
  } catch {
    // 전체 실패 무시
  }
}
