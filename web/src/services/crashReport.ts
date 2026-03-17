/**
 * 크래시 리포트 서비스
 * - window.onerror / unhandledrejection 캐치
 * - Capacitor Filesystem으로 로컬 저장
 * - GitHub Issues API로 자동 전송
 */
import { Filesystem, Directory, Encoding } from '@capacitor/filesystem';
import { Capacitor } from '@capacitor/core';
import { GITHUB_OWNER, GITHUB_REPO, GITHUB_API, GITHUB_TOKEN } from '../config';
import { APP_VERSION, BUILD_DATE } from '../version';
import { getTrail } from './logger';

interface CrashLog {
  timestamp: string;
  version: string;
  buildDate: string;
  platform: string;
  userAgent: string;
  error: {
    message: string;
    stack?: string;
    source?: string;
    line?: number;
    col?: number;
  };
  trail: string;
}

const CRASH_DIR = 'lawear-crashes';
const MAX_LOCAL_LOGS = 20;

/** 크래시 로그를 로컬에 저장 */
async function saveLocal(log: CrashLog): Promise<string> {
  const filename = `crash-${Date.now()}.json`;
  const path = `${CRASH_DIR}/${filename}`;

  try {
    // 디렉토리 생성 (없으면)
    await Filesystem.mkdir({
      path: CRASH_DIR,
      directory: Directory.Data,
      recursive: true,
    }).catch(() => { /* 이미 존재 */ });

    await Filesystem.writeFile({
      path,
      data: JSON.stringify(log, null, 2),
      directory: Directory.Data,
      encoding: Encoding.UTF8,
    });
    return filename;
  } catch {
    // 파일시스템 실패 시 콘솔에라도 남김
    console.error('[CrashReport] 로컬 저장 실패', log);
    return '';
  }
}

/** GitHub Issue로 전송 */
async function sendToGithub(log: CrashLog): Promise<boolean> {
  if (!GITHUB_TOKEN) return false;

  const title = `[Crash] ${log.error.message.slice(0, 80)}`;
  const body = [
    `**Version**: v${log.version} (${log.buildDate})`,
    `**Platform**: ${log.platform}`,
    `**Time**: ${log.timestamp}`,
    '',
    '```',
    log.error.stack ?? log.error.message,
    '```',
    '',
    log.error.source ? `Source: ${log.error.source}:${log.error.line}:${log.error.col}` : '',
    '',
    log.trail ? `<details><summary>Breadcrumb Trail</summary>\n\n\`\`\`\n${log.trail}\n\`\`\`\n</details>` : '',
  ].join('\n');

  try {
    const res = await fetch(
      `${GITHUB_API}/repos/${GITHUB_OWNER}/${GITHUB_REPO}/issues`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          'Content-Type': 'application/json',
          Accept: 'application/vnd.github+json',
        },
        body: JSON.stringify({ title, body, labels: ['crash'] }),
      },
    );
    return res.ok;
  } catch {
    return false;
  }
}

/** 로컬에 쌓인 미전송 로그를 GitHub로 전송 시도 */
async function flushPending(): Promise<void> {
  if (!GITHUB_TOKEN) return;

  try {
    const result = await Filesystem.readdir({
      path: CRASH_DIR,
      directory: Directory.Data,
    });

    for (const file of result.files) {
      if (!file.name.endsWith('.json')) continue;

      try {
        const content = await Filesystem.readFile({
          path: `${CRASH_DIR}/${file.name}`,
          directory: Directory.Data,
          encoding: Encoding.UTF8,
        });

        const log: CrashLog = JSON.parse(content.data as string);
        const sent = await sendToGithub(log);

        if (sent) {
          await Filesystem.deleteFile({
            path: `${CRASH_DIR}/${file.name}`,
            directory: Directory.Data,
          });
        }
      } catch {
        // 개별 파일 실패는 무시
      }
    }
  } catch {
    // 디렉토리 없으면 미전송 로그 없음
  }
}

/** 오래된 로그 정리 (MAX_LOCAL_LOGS 초과 시) */
async function pruneOldLogs(): Promise<void> {
  try {
    const result = await Filesystem.readdir({
      path: CRASH_DIR,
      directory: Directory.Data,
    });

    const jsonFiles = result.files
      .filter((f) => f.name.endsWith('.json'))
      .sort((a, b) => a.name.localeCompare(b.name));

    if (jsonFiles.length > MAX_LOCAL_LOGS) {
      const toDelete = jsonFiles.slice(0, jsonFiles.length - MAX_LOCAL_LOGS);
      for (const f of toDelete) {
        await Filesystem.deleteFile({
          path: `${CRASH_DIR}/${f.name}`,
          directory: Directory.Data,
        }).catch(() => {});
      }
    }
  } catch {
    // 무시
  }
}

/** 에러를 CrashLog로 변환 후 저장+전송 */
async function reportError(
  message: string,
  stack?: string,
  source?: string,
  line?: number,
  col?: number,
): Promise<void> {
  const log: CrashLog = {
    timestamp: new Date().toISOString(),
    version: APP_VERSION,
    buildDate: BUILD_DATE,
    platform: Capacitor.getPlatform(),
    userAgent: navigator.userAgent,
    error: { message, stack, source, line, col },
    trail: getTrail(),
  };

  await saveLocal(log);
  await sendToGithub(log);
  await pruneOldLogs();
}

/**
 * 크래시 핸들러 초기화 (앱 시작 시 1회 호출)
 * - window.onerror / unhandledrejection 등록
 * - 미전송 로그 flush
 */
export function initCrashReport(): void {
  window.onerror = (message, source, line, col, error) => {
    reportError(
      String(message),
      error?.stack,
      source ?? undefined,
      line ?? undefined,
      col ?? undefined,
    );
  };

  window.onunhandledrejection = (event: PromiseRejectionEvent) => {
    const err = event.reason;
    reportError(
      err?.message ?? String(err),
      err?.stack,
    );
  };

  // 앱 시작 시 미전송 로그 flush (비동기, 실패 무시)
  flushPending().catch(() => {});
}

/** 수동으로 미전송 로그 전송 시도 (설정 화면 등에서 호출) */
export { flushPending };
