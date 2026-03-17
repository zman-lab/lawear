/**
 * Audio Cache Service
 *
 * Capacitor Filesystem API를 사용하여 TTS 렌더링된 MP3 파일을
 * Android 내부 저장소에 캐시한다.
 *
 * 캐시 키: {subjectId}_{fileId}_{questionId}
 * 저장 경로: lawear-audio/{subjectId}/{fileId}/{questionId}.mp3
 *
 * Web 환경에서는 IndexedDB를 fallback으로 사용한다.
 */
import { Capacitor } from '@capacitor/core';
import { Filesystem, Directory, Encoding } from '@capacitor/filesystem';
import { log } from './logger';

const isNative = Capacitor.isNativePlatform();

// ── 상수 ────────────────────────────────────────────────────────────────────

const CACHE_DIR = 'lawear-audio';
const MANIFEST_FILE = `${CACHE_DIR}/_manifest.json`;

// ── 타입 ────────────────────────────────────────────────────────────────────

export interface CacheEntry {
  /** 과목 ID */
  subjectId: string;
  /** 파일 ID */
  fileId: string;
  /** 문제 ID */
  questionId: string;
  /** 캐시된 파일 경로 (Filesystem 상대경로) */
  path: string;
  /** 파일 크기 (bytes) */
  size: number;
  /** 캐시된 시각 (ISO 8601) */
  cachedAt: string;
  /** 사용된 음성 URI */
  voiceURI: string | null;
}

export interface CacheManifest {
  version: number;
  entries: Record<string, CacheEntry>; // key: subjectId_fileId_questionId
}

export interface CacheSizeInfo {
  /** 과목별 캐시 항목 수 */
  count: number;
  /** 과목별 캐시 크기 (bytes) */
  totalBytes: number;
}

// ── 내부 상태 ───────────────────────────────────────────────────────────────

let _manifest: CacheManifest | null = null;

// Web fallback: IndexedDB
const IDB_NAME = 'lawear-audio-cache';
const IDB_STORE = 'audio-files';
const IDB_META_STORE = 'meta';

function openIdb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.createObjectStore(IDB_STORE);
      }
      if (!db.objectStoreNames.contains(IDB_META_STORE)) {
        db.createObjectStore(IDB_META_STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// ── 매니페스트 관리 ─────────────────────────────────────────────────────────

function cacheKey(subjectId: string, fileId: string, questionId: string): string {
  return `${subjectId}_${fileId}_${questionId}`;
}

function cachePath(subjectId: string, fileId: string, questionId: string): string {
  return `${CACHE_DIR}/${subjectId}/${fileId}/${questionId}.wav`;
}

async function loadManifest(): Promise<CacheManifest> {
  if (_manifest) return _manifest;

  if (isNative) {
    try {
      const result = await Filesystem.readFile({
        path: MANIFEST_FILE,
        directory: Directory.Data,
        encoding: Encoding.UTF8,
      });
      _manifest = JSON.parse(result.data as string) as CacheManifest;
    } catch {
      // 파일 없으면 새로 생성
      _manifest = { version: 1, entries: {} };
    }
  } else {
    // Web: IndexedDB에서 매니페스트 로드
    try {
      const db = await openIdb();
      const tx = db.transaction(IDB_META_STORE, 'readonly');
      const store = tx.objectStore(IDB_META_STORE);
      const req = store.get('manifest');
      const result = await new Promise<CacheManifest | undefined>((resolve, reject) => {
        req.onsuccess = () => resolve(req.result as CacheManifest | undefined);
        req.onerror = () => reject(req.error);
      });
      db.close();
      _manifest = result ?? { version: 1, entries: {} };
    } catch {
      _manifest = { version: 1, entries: {} };
    }
  }

  return _manifest;
}

async function saveManifest(): Promise<void> {
  if (!_manifest) return;

  if (isNative) {
    await Filesystem.writeFile({
      path: MANIFEST_FILE,
      data: JSON.stringify(_manifest),
      directory: Directory.Data,
      encoding: Encoding.UTF8,
      recursive: true,
    });
  } else {
    try {
      const db = await openIdb();
      const tx = db.transaction(IDB_META_STORE, 'readwrite');
      const store = tx.objectStore(IDB_META_STORE);
      store.put(_manifest, 'manifest');
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
      db.close();
    } catch {
      // Web 환경에서 실패 시 조용히 무시
    }
  }
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * 캐시에 해당 케이스의 MP3 파일이 있는지 확인한다.
 */
export async function hasCachedAudio(
  subjectId: string,
  fileId: string,
  questionId: string,
): Promise<boolean> {
  const manifest = await loadManifest();
  return cacheKey(subjectId, fileId, questionId) in manifest.entries;
}

/**
 * 캐시된 MP3의 재생 가능한 URI를 반환한다.
 * 캐시가 없으면 null.
 */
export async function getCachedAudioUri(
  subjectId: string,
  fileId: string,
  questionId: string,
): Promise<string | null> {
  const manifest = await loadManifest();
  const key = cacheKey(subjectId, fileId, questionId);
  const entry = manifest.entries[key];
  if (!entry) return null;

  if (isNative) {
    try {
      const result = await Filesystem.getUri({
        path: entry.path,
        directory: Directory.Data,
      });
      log.cache('get_uri', { key, hit: true });
      return Capacitor.convertFileSrc(result.uri);
    } catch {
      // 파일이 사라졌으면 매니페스트에서도 제거
      delete manifest.entries[key];
      await saveManifest();
      log.cache('get_uri', { key, hit: false });
      return null;
    }
  } else {
    // Web: IndexedDB에서 Blob 가져와서 Object URL 생성
    try {
      const db = await openIdb();
      const tx = db.transaction(IDB_STORE, 'readonly');
      const store = tx.objectStore(IDB_STORE);
      const req = store.get(key);
      const blob = await new Promise<Blob | undefined>((resolve, reject) => {
        req.onsuccess = () => resolve(req.result as Blob | undefined);
        req.onerror = () => reject(req.error);
      });
      db.close();
      if (!blob) {
        delete manifest.entries[key];
        await saveManifest();
        log.cache('get_uri', { key, hit: false });
        return null;
      }
      log.cache('get_uri', { key, hit: true });
      return URL.createObjectURL(blob);
    } catch {
      log.cache('get_uri', { key, hit: false });
      return null;
    }
  }
}

/**
 * MP3 Blob을 캐시에 저장한다.
 */
export async function saveCachedAudio(
  subjectId: string,
  fileId: string,
  questionId: string,
  audioBlob: Blob,
  voiceURI: string | null,
): Promise<void> {
  const manifest = await loadManifest();
  const key = cacheKey(subjectId, fileId, questionId);
  const path = cachePath(subjectId, fileId, questionId);

  if (isNative) {
    // Blob -> base64
    const base64 = await blobToBase64(audioBlob);

    await Filesystem.writeFile({
      path,
      data: base64,
      directory: Directory.Data,
      recursive: true,
    });
  } else {
    // Web: IndexedDB에 Blob 저장
    try {
      const db = await openIdb();
      const tx = db.transaction(IDB_STORE, 'readwrite');
      const store = tx.objectStore(IDB_STORE);
      store.put(audioBlob, key);
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
      db.close();
    } catch {
      return; // Web에서 저장 실패 시 조용히 무시
    }
  }

  manifest.entries[key] = {
    subjectId,
    fileId,
    questionId,
    path,
    size: audioBlob.size,
    cachedAt: new Date().toISOString(),
    voiceURI,
  };

  await saveManifest();
  log.cache('save', { key, size: audioBlob.size });
}

/**
 * 개별 케이스의 캐시를 삭제한다.
 */
export async function removeCachedAudio(
  subjectId: string,
  fileId: string,
  questionId: string,
): Promise<void> {
  const manifest = await loadManifest();
  const key = cacheKey(subjectId, fileId, questionId);
  const entry = manifest.entries[key];
  if (!entry) return;

  if (isNative) {
    try {
      await Filesystem.deleteFile({
        path: entry.path,
        directory: Directory.Data,
      });
    } catch {
      // 파일 없으면 무시
    }
  } else {
    try {
      const db = await openIdb();
      const tx = db.transaction(IDB_STORE, 'readwrite');
      const store = tx.objectStore(IDB_STORE);
      store.delete(key);
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
      db.close();
    } catch {
      // 무시
    }
  }

  delete manifest.entries[key];
  await saveManifest();
  log.cache('remove', { key });
}

/**
 * 과목 전체 캐시를 삭제한다.
 */
export async function removeSubjectCache(subjectId: string): Promise<void> {
  const manifest = await loadManifest();
  const keysToRemove = Object.keys(manifest.entries).filter(
    (k) => manifest.entries[k].subjectId === subjectId,
  );

  for (const key of keysToRemove) {
    const entry = manifest.entries[key];
    if (isNative) {
      try {
        await Filesystem.deleteFile({
          path: entry.path,
          directory: Directory.Data,
        });
      } catch {
        // 무시
      }
    } else {
      try {
        const db = await openIdb();
        const tx = db.transaction(IDB_STORE, 'readwrite');
        tx.objectStore(IDB_STORE).delete(key);
        await new Promise<void>((resolve, reject) => {
          tx.oncomplete = () => resolve();
          tx.onerror = () => reject(tx.error);
        });
        db.close();
      } catch {
        // 무시
      }
    }
    delete manifest.entries[key];
  }

  // 네이티브: 과목 디렉토리도 삭제 시도
  if (isNative) {
    try {
      await Filesystem.rmdir({
        path: `${CACHE_DIR}/${subjectId}`,
        directory: Directory.Data,
        recursive: true,
      });
    } catch {
      // 무시
    }
  }

  await saveManifest();
}

/**
 * 전체 캐시를 삭제한다.
 */
export async function clearAllCache(): Promise<void> {
  if (isNative) {
    try {
      await Filesystem.rmdir({
        path: CACHE_DIR,
        directory: Directory.Data,
        recursive: true,
      });
    } catch {
      // 무시
    }
  } else {
    try {
      const db = await openIdb();
      const tx = db.transaction([IDB_STORE, IDB_META_STORE], 'readwrite');
      tx.objectStore(IDB_STORE).clear();
      tx.objectStore(IDB_META_STORE).clear();
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
      db.close();
    } catch {
      // 무시
    }
  }

  _manifest = { version: 1, entries: {} };
  await saveManifest();
  log.cache('clear_all');
}

/**
 * 과목별 캐시 크기 정보를 반환한다.
 */
export async function getCacheSizeBySubject(): Promise<Record<string, CacheSizeInfo>> {
  const manifest = await loadManifest();
  const result: Record<string, CacheSizeInfo> = {};

  for (const entry of Object.values(manifest.entries)) {
    if (!result[entry.subjectId]) {
      result[entry.subjectId] = { count: 0, totalBytes: 0 };
    }
    result[entry.subjectId].count += 1;
    result[entry.subjectId].totalBytes += entry.size;
  }

  return result;
}

/**
 * 전체 캐시 크기(bytes)를 반환한다.
 */
export async function getTotalCacheSize(): Promise<number> {
  const manifest = await loadManifest();
  return Object.values(manifest.entries).reduce((sum, e) => sum + e.size, 0);
}

/**
 * 전체 캐시 항목 수를 반환한다.
 */
export async function getTotalCacheCount(): Promise<number> {
  const manifest = await loadManifest();
  return Object.keys(manifest.entries).length;
}

// ── 유틸 ────────────────────────────────────────────────────────────────────

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const dataUrl = reader.result as string;
      // data:audio/mpeg;base64,XXXX → XXXX 만 추출
      const base64 = dataUrl.split(',')[1];
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/**
 * 네이티브에서 직접 파일을 쓴 경우, 매니페스트만 업데이트한다.
 * (TTSFile 플러그인이 synthesizeToFile로 직접 파일 생성 후 호출)
 */
export async function markAsCached(
  subjectId: string,
  fileId: string,
  questionId: string,
  fileSizeBytes: number,
  voiceURI: string | null,
): Promise<void> {
  const manifest = await loadManifest();
  const key = cacheKey(subjectId, fileId, questionId);
  const path = cachePath(subjectId, fileId, questionId);

  manifest.entries[key] = {
    subjectId,
    fileId,
    questionId,
    path,
    size: fileSizeBytes,
    cachedAt: new Date().toISOString(),
    voiceURI,
  };

  await saveManifest();
  log.cache('mark_cached', { key: cacheKey(subjectId, fileId, questionId), size: fileSizeBytes });
}

/**
 * 바이트를 사람이 읽기 쉬운 형태로 변환한다. (예: "45.2MB")
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i > 1 ? 1 : 0)}${units[i]}`;
}
