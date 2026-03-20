// 시험 날짜 D-day 서비스
// localStorage key: lawear-exam-date

const STORAGE_KEY = 'lawear-exam-date';

/** 시험 날짜 저장 (YYYY-MM-DD 형식) */
export function saveExamDate(dateStr: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, dateStr);
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 시험 날짜 불러오기 (YYYY-MM-DD 형식, 없으면 null) */
export function loadExamDate(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** 시험 날짜 삭제 */
export function clearExamDate(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

/**
 * D-day 계산
 * - 양수: 시험까지 남은 일수 (D-N)
 * - 0: 오늘이 시험일 (D-Day)
 * - 음수: 시험 지남 (D+N)
 * - null: 날짜 미설정
 */
export function calcDday(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const exam = new Date(dateStr);
  exam.setHours(0, 0, 0, 0);
  const diffMs = exam.getTime() - today.getTime();
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
}

/** D-day 표시 문자열 (예: "D-42", "D-Day", "D+3") */
export function formatDday(days: number | null): string {
  if (days === null) return '';
  if (days === 0) return 'D-Day';
  if (days > 0) return `D-${days}`;
  return `D+${Math.abs(days)}`;
}
