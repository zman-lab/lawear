// A-B 구간 저장 서비스
// localStorage key: lawear-ab-segments

const STORAGE_KEY = 'lawear-ab-segments';

export interface SavedABSegment {
  id: string;
  title: string;
  subjectId: string;
  fileId: string;
  questionId: string;
  startIndex: number;
  endIndex: number;
  createdAt: number;
}

function load(): SavedABSegment[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as SavedABSegment[];
  } catch {
    return [];
  }
}

function save(segments: SavedABSegment[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(segments));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 전체 A-B 구간 목록 반환 (최신순) */
export function loadABSegments(): SavedABSegment[] {
  return load();
}

/** A-B 구간 저장 */
export function addABSegment(segment: Omit<SavedABSegment, 'id' | 'createdAt'>): SavedABSegment {
  const list = load();
  const newSegment: SavedABSegment = {
    ...segment,
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    createdAt: Date.now(),
  };
  list.unshift(newSegment);
  save(list);
  return newSegment;
}

/** A-B 구간 삭제 */
export function deleteABSegment(id: string): void {
  const list = load().filter((s) => s.id !== id);
  save(list);
}

/** A-B 구간 제목 변경 */
export function updateABSegmentTitle(id: string, title: string): void {
  const list = load();
  const idx = list.findIndex((s) => s.id === id);
  if (idx >= 0) {
    list[idx] = { ...list[idx], title };
    save(list);
  }
}
