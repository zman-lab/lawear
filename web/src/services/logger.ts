/**
 * 앱 로거 — 유저 행동 + 시스템 이벤트 브레드크럼
 *
 * 순환 버퍼로 최근 200개 이벤트를 보관한다.
 * 크래시 발생 시 crashReport가 이 trail을 포함하여 전송한다.
 *
 * 카테고리:
 *   nav    — 화면 전환
 *   ui     — 유저 클릭/탭
 *   player — 재생 상태 변경
 *   tts    — TTS 엔진 이벤트
 *   media  — MediaSession/알림바
 *   cache  — 오디오 캐시/렌더링
 *   error  — 에러 (crashReport에도 전달됨)
 *   life   — 앱 생명주기
 */

export type LogCategory = 'nav' | 'ui' | 'player' | 'tts' | 'media' | 'cache' | 'error' | 'life';
export type LogLevel = 'info' | 'warn' | 'error';

export interface LogEntry {
  /** 밀리초 타임스탬프 */
  ts: number;
  /** 카테고리 */
  cat: LogCategory;
  /** 레벨 */
  lv: LogLevel;
  /** 메시지 */
  msg: string;
  /** 추가 데이터 (선택) */
  data?: Record<string, unknown>;
}

// ── 순환 버퍼 ────────────────────────────────────────────────────────────────

const MAX_ENTRIES = 200;
const _buffer: LogEntry[] = [];

function push(entry: LogEntry): void {
  if (_buffer.length >= MAX_ENTRIES) {
    _buffer.shift();
  }
  _buffer.push(entry);

  // 개발 콘솔에도 출력 (프로덕션에서는 조용히)
  if (import.meta.env.DEV) {
    const tag = `[${entry.cat}]`;
    if (entry.lv === 'error') {
      console.error(tag, entry.msg, entry.data ?? '');
    } else if (entry.lv === 'warn') {
      console.warn(tag, entry.msg, entry.data ?? '');
    } else {
      console.log(tag, entry.msg, entry.data ?? '');
    }
  }
}

// ── Public API ───────────────────────────────────────────────────────────────

function write(cat: LogCategory, lv: LogLevel, msg: string, data?: Record<string, unknown>): void {
  push({ ts: Date.now(), cat, lv, msg, data });
}

/** 카테고리별 info 로그 헬퍼 */
export const log = {
  nav:    (msg: string, data?: Record<string, unknown>) => write('nav', 'info', msg, data),
  ui:     (msg: string, data?: Record<string, unknown>) => write('ui', 'info', msg, data),
  player: (msg: string, data?: Record<string, unknown>) => write('player', 'info', msg, data),
  tts:    (msg: string, data?: Record<string, unknown>) => write('tts', 'info', msg, data),
  media:  (msg: string, data?: Record<string, unknown>) => write('media', 'info', msg, data),
  cache:  (msg: string, data?: Record<string, unknown>) => write('cache', 'info', msg, data),
  life:   (msg: string, data?: Record<string, unknown>) => write('life', 'info', msg, data),

  warn:  (cat: LogCategory, msg: string, data?: Record<string, unknown>) => write(cat, 'warn', msg, data),
  error: (cat: LogCategory, msg: string, data?: Record<string, unknown>) => write(cat, 'error', msg, data),
};

/**
 * 전체 브레드크럼 trail을 포맷팅된 문자열로 반환한다.
 * crashReport에서 호출하여 크래시 로그에 포함.
 */
export function getTrail(): string {
  return _buffer.map((e) => {
    const time = new Date(e.ts).toISOString().slice(11, 23); // HH:mm:ss.SSS
    const lvTag = e.lv === 'info' ? '' : ` [${e.lv.toUpperCase()}]`;
    const dataStr = e.data ? ' ' + JSON.stringify(e.data) : '';
    return `${time} [${e.cat}]${lvTag} ${e.msg}${dataStr}`;
  }).join('\n');
}

/**
 * 원본 LogEntry 배열을 반환한다 (JSON 직렬화용).
 */
export function getEntries(): LogEntry[] {
  return [..._buffer];
}

/**
 * 버퍼를 비운다.
 */
export function clearLog(): void {
  _buffer.length = 0;
}
