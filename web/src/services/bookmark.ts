// 북마크 서비스 (현재 재생 중인 문제 위치 저장)
// localStorage key: lawear-bookmarks

const STORAGE_KEY = 'lawear-bookmarks';

export interface Bookmark {
  id: string;
  questionId: string;
  subjectId: string;
  fileId: string;
  sentenceIndex: number;
  label: string;
  createdAt: number;
}

function load(): Bookmark[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as Bookmark[];
  } catch {
    return [];
  }
}

function save(bookmarks: Bookmark[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 전체 북마크 목록 반환 (최신순) */
export function loadBookmarks(): Bookmark[] {
  return load();
}

/** 북마크 추가 */
export function addBookmark(bookmark: Omit<Bookmark, 'id' | 'createdAt'>): Bookmark {
  const list = load();
  const newBookmark: Bookmark = {
    ...bookmark,
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    createdAt: Date.now(),
  };
  list.unshift(newBookmark);
  save(list);
  return newBookmark;
}

/** 북마크 삭제 */
export function deleteBookmark(id: string): void {
  const list = load().filter((b) => b.id !== id);
  save(list);
}

/** 특정 문제에 북마크가 있는지 확인 */
export function isBookmarked(questionId: string): boolean {
  return load().some((b) => b.questionId === questionId);
}

/** 특정 문제의 북마크 목록 반환 */
export function getBookmarksForQuestion(questionId: string): Bookmark[] {
  return load().filter((b) => b.questionId === questionId);
}
