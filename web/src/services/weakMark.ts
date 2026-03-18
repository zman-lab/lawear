// 취약 영역 마킹 서비스
// localStorage key: lawear-weak-marks

const STORAGE_KEY = 'lawear-weak-marks';

function load(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    return new Set(arr);
  } catch {
    return new Set();
  }
}

function save(set: Set<string>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** questionId가 취약 마킹되어 있는지 확인 */
export function isWeakMarked(questionId: string): boolean {
  return load().has(questionId);
}

/** 취약 마킹 토글 (마킹 ↔ 해제). 반환값: 마킹 후 상태 (true = 마킹됨) */
export function toggleWeakMark(questionId: string): boolean {
  const set = load();
  if (set.has(questionId)) {
    set.delete(questionId);
    save(set);
    return false;
  } else {
    set.add(questionId);
    save(set);
    return true;
  }
}

/** 전체 취약 마킹 목록 반환 */
export function loadWeakMarks(): Set<string> {
  return load();
}
