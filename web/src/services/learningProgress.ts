// 학습 진도 추적 서비스
// localStorage key: lawear-progress

const STORAGE_KEY = 'lawear-progress';

export interface ReviewSchedule {
  nextReviewAt: number;       // 다음 복습 시간 (timestamp ms)
  reviewLevel: number;        // 복습 단계 (0~4, REVIEW_INTERVALS 인덱스)
  reviewsCompleted: number;   // 완료한 복습 횟수
  lastReviewedAt: number;     // 마지막 복습일시
}

export interface ProgressEntry {
  playCount: number;
  lastPlayedAt: number;
  completedAt?: number;
  reviewSchedule?: ReviewSchedule;
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

/** 트랙 완료 시 호출 — playCount 증가 + lastPlayedAt + completedAt 기록 + 첫 완료 시 복습 스케줄 초기화 */
export function recordCompletion(questionId: string): void {
  const map = loadProgress();
  const prev = map[questionId];
  const now = Date.now();
  const MS_PER_DAY = 24 * 60 * 60 * 1000;

  const entry: ProgressEntry = {
    playCount: (prev?.playCount ?? 0) + 1,
    lastPlayedAt: now,
    completedAt: now,
    reviewSchedule: prev?.reviewSchedule,
  };

  // 첫 완료 시 복습 스케줄 초기화 (1일 후 첫 복습)
  if (!entry.reviewSchedule) {
    entry.reviewSchedule = {
      nextReviewAt: now + 1 * MS_PER_DAY,
      reviewLevel: 0,
      reviewsCompleted: 0,
      lastReviewedAt: now,
    };
  }

  map[questionId] = entry;
  saveProgress(map);
}

/** 복습 완료 기록 + 다음 주기 계산 */
export function recordReview(questionId: string): void {
  const map = loadProgress();
  const entry = map[questionId];
  if (!entry?.reviewSchedule) return;

  const REVIEW_INTERVALS = [1, 3, 7, 14, 30];
  const MS_PER_DAY = 24 * 60 * 60 * 1000;
  const now = Date.now();

  const nextLevel = entry.reviewSchedule.reviewLevel + 1;
  const reviewsCompleted = entry.reviewSchedule.reviewsCompleted + 1;

  if (nextLevel >= REVIEW_INTERVALS.length) {
    // 5단계 모두 완료 — 복습 종료 상태
    entry.reviewSchedule = {
      nextReviewAt: now, // 의미 없지만 유지
      reviewLevel: nextLevel,
      reviewsCompleted,
      lastReviewedAt: now,
    };
  } else {
    const intervalDays = REVIEW_INTERVALS[nextLevel];
    entry.reviewSchedule = {
      nextReviewAt: now + intervalDays * MS_PER_DAY,
      reviewLevel: nextLevel,
      reviewsCompleted,
      lastReviewedAt: now,
    };
  }

  entry.lastPlayedAt = now;
  map[questionId] = entry;
  saveProgress(map);
}

/** 현재 복습 필요한 문제 ID 목록 반환 */
export function getReviewDueItems(): string[] {
  const map = loadProgress();
  const now = Date.now();
  const REVIEW_INTERVALS_LENGTH = 5;

  return Object.entries(map)
    .filter(([, entry]) => {
      if (!entry.reviewSchedule) return false;
      if (entry.reviewSchedule.reviewsCompleted >= REVIEW_INTERVALS_LENGTH) return false;
      return now >= entry.reviewSchedule.nextReviewAt;
    })
    .map(([questionId]) => questionId);
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
