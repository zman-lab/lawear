import type { PlaylistItem } from '../types';

export interface FavoritePlaylist {
  id: string;
  name: string;
  items: PlaylistItem[];
  createdAt: number;
}

const STORAGE_KEY = 'lawear-favorites';

export function loadFavorites(): FavoritePlaylist[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as FavoritePlaylist[];
  } catch {
    return [];
  }
}

export function saveFavorite(fav: FavoritePlaylist): void {
  try {
    const list = loadFavorites();
    const existing = list.findIndex((f) => f.id === fav.id);
    if (existing >= 0) {
      list[existing] = fav;
    } else {
      list.unshift(fav);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

export function deleteFavorite(id: string): void {
  try {
    const list = loadFavorites().filter((f) => f.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 두 playlist가 동일한지 비교 (순서 포함) */
export function isSamePlaylist(a: PlaylistItem[], b: PlaylistItem[]): boolean {
  if (a.length !== b.length) return false;
  return a.every(
    (item, i) =>
      item.subjectId === b[i]?.subjectId &&
      item.fileId === b[i]?.fileId &&
      item.questionId === b[i]?.questionId,
  );
}

/** 이미 저장된 즐겨찾기 찾기 */
export function findMatchingFavorite(items: PlaylistItem[]): FavoritePlaylist | undefined {
  return loadFavorites().find((fav) => isSamePlaylist(fav.items, items));
}

/** 즐겨찾기 이름 자동 생성 */
export function buildFavoriteName(items: PlaylistItem[], getLabel: (item: PlaylistItem) => string): string {
  if (items.length === 0) return '빈 플레이리스트';
  const first = getLabel(items[0]);
  if (items.length === 1) return first;
  return `${first} 외 ${items.length - 1}곡`;
}

/** 즐겨찾기 이름 변경 */
export function updateFavoriteName(id: string, name: string): void {
  try {
    const list = loadFavorites();
    const idx = list.findIndex((f) => f.id === id);
    if (idx < 0) return;
    list[idx] = { ...list[idx], name };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 즐겨찾기에 곡 추가 (중복 방지) */
export function addItemToFavorite(id: string, item: PlaylistItem): void {
  try {
    const list = loadFavorites();
    const idx = list.findIndex((f) => f.id === id);
    if (idx < 0) return;
    const fav = list[idx];
    const already = fav.items.some((i) => i.questionId === item.questionId);
    if (already) return;
    list[idx] = { ...fav, items: [...fav.items, item] };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 즐겨찾기에서 곡 삭제 */
export function removeItemFromFavorite(id: string, questionId: string): void {
  try {
    const list = loadFavorites();
    const idx = list.findIndex((f) => f.id === id);
    if (idx < 0) return;
    const fav = list[idx];
    list[idx] = { ...fav, items: fav.items.filter((i) => i.questionId !== questionId) };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}

/** 즐겨찾기 곡 순서 변경 */
export function reorderFavoriteItems(id: string, items: PlaylistItem[]): void {
  try {
    const list = loadFavorites();
    const idx = list.findIndex((f) => f.id === id);
    if (idx < 0) return;
    list[idx] = { ...list[idx], items };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage 사용 불가 시 무시
  }
}
