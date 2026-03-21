// 에빙하우스 망각곡선 기반 복습 스케줄 계산
import type { ProgressEntry } from './learningProgress';
import { loadProgress } from './learningProgress';
import { loadWeakMarks } from './weakMark';
import { subjects } from '../data/ttsData';

// 복습 간격 (일 단위): 1일 → 3일 → 7일 → 14일 → 30일
const REVIEW_INTERVALS = [1, 3, 7, 14, 30];
const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** 다음 복습 날짜 계산 (timestamp ms) */
export function getNextReviewDate(reviewLevel: number, baseDate: number): number {
  const idx = Math.min(reviewLevel, REVIEW_INTERVALS.length - 1);
  const intervalDays = REVIEW_INTERVALS[idx];
  return baseDate + intervalDays * MS_PER_DAY;
}

/** 복습 필요 여부 판단 */
export function isReviewDue(entry: ProgressEntry): boolean {
  if (!entry.reviewSchedule) return false;
  return Date.now() >= entry.reviewSchedule.nextReviewAt;
}

/** 복습 우선순위 점수 (높을수록 긴급) */
export function getReviewPriority(entry: ProgressEntry, questionId: string): number {
  if (!entry.reviewSchedule) return 0;
  const now = Date.now();
  const overdueDays = Math.max(0, (now - entry.reviewSchedule.nextReviewAt) / MS_PER_DAY);
  const weakMarks = loadWeakMarks();
  const isWeak = weakMarks.has(questionId);

  // 지연일 * 10 + 취약마킹 50 + 낮은 복습단계 보너스
  let priority = overdueDays * 10;
  if (isWeak) priority += 50;
  priority += (REVIEW_INTERVALS.length - entry.reviewSchedule.reviewLevel) * 5;
  return priority;
}

export interface ReviewItem {
  questionId: string;
  subjectId: string;
  fileId: string;
  questionTitle: string;
  subjectName: string;
  colorClass: string;
  reviewLevel: number;
  daysOverdue: number;
  isWeakMarked: boolean;
}

export interface ReviewSummary {
  dueToday: number;
  overdueCount: number;
  upcomingCount: number;
  items: ReviewItem[];
}

/** 복습 필요한 아이템 목록 + 요약 */
export function getReviewSummary(): ReviewSummary {
  const progress = loadProgress();
  const weakMarks = loadWeakMarks();
  const now = Date.now();
  const weekLater = now + 7 * MS_PER_DAY;
  const todayEnd = new Date();
  todayEnd.setHours(23, 59, 59, 999);
  const todayEndTs = todayEnd.getTime();

  const items: ReviewItem[] = [];
  let dueToday = 0;
  let overdueCount = 0;
  let upcomingCount = 0;

  // questionId → 과목/파일 메타데이터 역색인
  for (const [questionId, entry] of Object.entries(progress)) {
    if (!entry.reviewSchedule) continue;
    const { nextReviewAt, reviewLevel } = entry.reviewSchedule;

    // 5단계 완료(모든 복습 끝) → 건너뜀
    if (entry.reviewSchedule.reviewsCompleted >= REVIEW_INTERVALS.length) continue;

    const isDue = now >= nextReviewAt;
    const isDueToday = nextReviewAt <= todayEndTs;
    const isUpcoming = !isDue && nextReviewAt <= weekLater;

    if (!isDue && !isUpcoming) continue;

    if (isDue) {
      overdueCount++;
      if (isDueToday) dueToday++;
    }
    if (isUpcoming) upcomingCount++;

    if (isDue) {
      // 과목/파일 정보 찾기
      const meta = findQuestionMeta(questionId);
      if (!meta) continue;

      const daysOverdue = Math.floor((now - nextReviewAt) / MS_PER_DAY);
      items.push({
        questionId,
        subjectId: meta.subjectId,
        fileId: meta.fileId,
        questionTitle: meta.label,
        subjectName: meta.subjectName,
        colorClass: meta.colorClass,
        reviewLevel,
        daysOverdue: Math.max(0, daysOverdue),
        isWeakMarked: weakMarks.has(questionId),
      });
    }
  }

  // 우선순위 정렬: 지연일 > 취약마킹 > 복습단계 낮은 것
  items.sort((a, b) => {
    const pa = getReviewPriority(progress[a.questionId], a.questionId);
    const pb = getReviewPriority(progress[b.questionId], b.questionId);
    return pb - pa;
  });

  return { dueToday, overdueCount, upcomingCount, items };
}

/** questionId로 과목/파일 메타데이터 찾기 */
function findQuestionMeta(questionId: string): {
  subjectId: string;
  subjectName: string;
  colorClass: string;
  fileId: string;
  label: string;
} | null {
  for (const subject of subjects) {
    for (const file of subject.files) {
      for (const q of file.questions) {
        if (q.id === questionId) {
          return {
            subjectId: subject.id,
            subjectName: subject.name,
            colorClass: subject.colorClass,
            fileId: file.id,
            label: q.label,
          };
        }
      }
    }
  }
  return null;
}
