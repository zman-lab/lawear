// 학습 진도 추적 서비스
// localStorage key: lawear-progress

const STORAGE_KEY = 'lawear-progress';

export interface ProgressEntry {
  playCount: number;
  lastPlayedAt: number;
  completedAt?: number;
}

export type ProgressMap = Record<string, ProgressEntry>;

export function loadProgress(): ProgressMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as ProgressMap;
  } catch {
    return {};
  }
}

function saveProgress(map: ProgressMap): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 트랙 완료 시 호출 — playCount 증가 + lastPlayedAt + completedAt 기록 */
export function recordCompletion(questionId: string): void {
  const map = loadProgress();
  const prev = map[questionId];
  map[questionId] = {
    playCount: (prev?.playCount ?? 0) + 1,
    lastPlayedAt: Date.now(),
    completedAt: Date.now(),
  };
  saveProgress(map);
}

/** 특정 questionId의 진도 조회 */
export function getProgress(questionId: string): ProgressEntry | null {
  const map = loadProgress();
  return map[questionId] ?? null;
}

/** 오늘 학습한 총 횟수 */
export function getTodayCompletionCount(): number {
  const map = loadProgress();
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayTs = todayStart.getTime();
  return Object.values(map).filter((e) => e.completedAt && e.completedAt >= todayTs).length;
}

/** 날짜를 "M/D" 형식으로 포맷 */
export function formatDate(ts: number): string {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
