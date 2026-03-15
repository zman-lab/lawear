/**
 * 법령 조문 제목 조회 헬퍼.
 *
 * lawArticles.json에서 조문번호 → 조문제목 매핑을 제공하며,
 * TTS 텍스트에 "제XXX조" 뒤에 조문제목을 자동 삽입하는 기능을 포함한다.
 */

import lawArticles from '../data/lawArticles.json';

// --- 타입 ---

interface StatuteData {
  mst: string;
  articles: Record<string, string>;
}

interface LawArticlesJson {
  version: string;
  statutes: Record<string, StatuteData>;
}

const data = lawArticles as LawArticlesJson;

// --- 공개 함수 ---

/**
 * 특정 법령의 조문 제목을 조회한다.
 *
 * @param statute  법령명 (예: "민법", "형법")
 * @param articleNum  조문번호 문자열 (예: "397", "109의2")
 * @returns 조문제목 또는 null (법령/조문이 없거나 제목이 빈 경우)
 *
 * @example
 * getArticleTitle("민법", "397")  // "금전채무불이행에 대한 특칙"
 * getArticleTitle("민법", "9999") // null
 */
export function getArticleTitle(statute: string, articleNum: string): string | null {
  const statuteData = data.statutes[statute];
  if (!statuteData) return null;

  const title = statuteData.articles[articleNum];
  if (title === undefined || title === '') return null;

  return title;
}

/**
 * TTS 텍스트에서 "제XXX조" 패턴을 찾아 조문제목을 뒤에 삽입한다.
 *
 * 처리 패턴:
 *   - "제397조"     → "제397조 금전채무불이행에 대한 특칙"
 *   - "제109조의2"  → "제109조의2 등기정보자료의 제공 등"
 *   - "제9999조"    → "제9999조" (매핑 없으면 그대로)
 *   - 이미 제목이 삽입된 경우 → 중복 삽입하지 않음
 *
 * @param text     TTS 텍스트
 * @param statute  법령명
 * @returns 조문제목이 삽입된 텍스트
 */
export function insertArticleTitles(text: string, statute: string): string {
  const statuteData = data.statutes[statute];
  if (!statuteData) return text;

  // "제XXX조" 또는 "제XXX조의Y" 패턴
  // 뒤에 이미 조문제목이 있으면 (공백+한글) 건너뜀
  const pattern = /제(\d+)조(의\d+)?/g;

  return text.replace(pattern, (match, num: string, suffix: string | undefined, offset: number) => {
    const articleKey = num + (suffix ?? '');
    const title = statuteData.articles[articleKey];

    if (!title) return match;

    // 이미 제목이 바로 뒤에 있는지 확인 (중복 삽입 방지)
    const afterMatch = text.slice(offset + match.length);
    if (afterMatch.startsWith(` ${title}`)) return match;

    return `${match} ${title}`;
  });
}

/**
 * JSON 데이터의 버전(빌드 날짜)을 반환한다.
 */
export function getLawArticlesVersion(): string {
  return data.version;
}

/**
 * 사용 가능한 법령명 목록을 반환한다.
 */
export function getStatuteNames(): string[] {
  return Object.keys(data.statutes);
}
