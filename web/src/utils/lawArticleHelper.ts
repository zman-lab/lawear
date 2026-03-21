/**
 * 법령 조문 제목 조회 헬퍼.
 *
 * lawArticles.json에서 조문번호 → 조문제목 매핑을 제공하며,
 * TTS 텍스트에 "제XXX조" 뒤에 조문제목을 자동 삽입하는 기능을 포함한다.
 *
 * 레벨별 상세도:
 *   Lv.1 (빠른복습): 조문제목 삽입 (예: "제397조 금전채무불이행에 대한 특칙")
 *   Lv.2 (핵심요약): 조문제목 삽입 (Lv.1과 동일)
 *   Lv.3 (슈퍼심플): 제목 삽입 안 함 (번호만 유지)
 */

import lawArticles from '../data/lawArticles.json';
import type { Level } from '../types';

// --- 디버그 플래그 ---

const LAW_ARTICLE_DEBUG =
  typeof localStorage !== 'undefined' && localStorage.getItem('lawear-debug-law') === 'true';

function debugLog(...args: unknown[]) {
  if (LAW_ARTICLE_DEBUG) console.log(...args);
}

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

// --- 초기 로드 로그 ---

{
  const statuteNames = Object.keys(data.statutes);
  const totalArticles = statuteNames.reduce(
    (sum, name) => sum + Object.keys(data.statutes[name].articles).length,
    0,
  );
  debugLog(
    `[LawArticle] lawArticles.json 로드됨 — 버전: ${data.version}, 법령 ${statuteNames.length}개, 총 조문 ${totalArticles}개`,
  );
  debugLog(
    `[LawArticle] 법령 목록: ${statuteNames.map((n) => `${n}(${Object.keys(data.statutes[n].articles).length}조)`).join(', ')}`,
  );
}

// --- 내부 헬퍼 ---

/** lawArticles.json에 등록된 법령명 목록 (검색용) */
const STATUTE_NAMES = Object.keys(data.statutes);

/**
 * "법령명 제N조(의M)" 또는 "제N조(의M)" 패턴을 캡처한다.
 *
 * 캡처 그룹:
 *   1: 법령명 (옵션, 없으면 undefined)
 *   2: 조문번호 (숫자)
 *   3: 가지번호 (예: "의2", 옵션)
 *
 * 법령명은 lawArticles.json에 등록된 이름만 매칭한다.
 */
function buildPattern(): RegExp {
  // 법령명을 길이 내림차순 정렬 (긴 이름 우선 매칭 — "부동산 실권리자명의 등기에 관한 법률" vs "부동산등기법")
  const escaped = STATUTE_NAMES
    .sort((a, b) => b.length - a.length)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const namesGroup = escaped.join('|');
  // "민법 제397조의2" 또는 "제397조의2" (법령명 생략 시 기본 법령 사용)
  return new RegExp(`(?:(${namesGroup})\\s*)?제(\\d+)조(의\\d+)?`, 'g');
}

const ARTICLE_PATTERN = buildPattern();

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
 *   - "제397조"           → "제397조 금전채무불이행에 대한 특칙" (기본 법령 사용)
 *   - "민법 제467조"      → "민법 제467조 변제의 장소" (명시된 법령 사용)
 *   - "제109조의2"        → "제109조의2 등기정보자료의 제공 등"
 *   - "제9999조"          → "제9999조" (매핑 없으면 그대로)
 *   - 이미 제목이 삽입된 경우 → 중복 삽입하지 않음
 *
 * @param text            TTS 텍스트
 * @param defaultStatute  기본 법령명 (법령명이 명시되지 않은 "제N조"에 적용)
 * @param level           레벨 (Lv.3이면 제목 삽입 안 함)
 * @returns 조문제목이 삽입된 텍스트
 */
export function insertArticleTitles(
  text: string,
  defaultStatute: string,
  level: Level = 1,
): string {
  // Lv.3 슈퍼심플: 제목 삽입 안 함
  if (level === 3) {
    debugLog(`[LawArticle] Lv.3 — 조문 제목 삽입 생략`);
    return text;
  }

  debugLog(`[LawArticle] insertArticleTitles 호출 — 기본법령: ${defaultStatute}, 레벨: ${level}`);

  // 매 호출마다 lastIndex 리셋
  ARTICLE_PATTERN.lastIndex = 0;

  let foundCount = 0;
  let matchedCount = 0;
  let insertedCount = 0;

  const result = text.replace(
    ARTICLE_PATTERN,
    (match, statuteName: string | undefined, num: string, suffix: string | undefined, offset: number) => {
      foundCount++;
      // 법령명이 명시되었으면 해당 법령, 아니면 기본 법령
      const statute = statuteName ?? defaultStatute;
      const statuteData = data.statutes[statute];
      if (!statuteData) {
        debugLog(`[LawArticle] 패턴 발견: "${match}" → 법령 "${statute}" 데이터 없음`);
        return match;
      }

      const articleKey = num + (suffix ?? '');
      const title = statuteData.articles[articleKey];

      if (!title) {
        debugLog(`[LawArticle] 조문 제목 없음: ${statute} 제${articleKey}조 → 원본 유지`);
        return match;
      }

      matchedCount++;

      // 이미 제목이 바로 뒤에 있는지 확인 (중복 삽입 방지)
      const afterMatch = text.slice(offset + match.length);
      if (afterMatch.startsWith(` ${title}`)) {
        debugLog(`[LawArticle] 중복 스킵: ${statute} 제${articleKey}조 "${title}"`);
        return match;
      }

      insertedCount++;
      debugLog(`[LawArticle] 조문 제목 매칭: ${statute} 제${articleKey}조 → "${title}"`);
      debugLog(`[LawArticle] 삽입 결과: "${match} ${title}"`);

      return `${match} ${title}`;
    },
  );

  debugLog(
    `[LawArticle] 삽입 완료 — 총 ${foundCount}개 패턴 중 ${matchedCount}개 매칭, ${insertedCount}개 삽입`,
  );

  return result;
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
  return STATUTE_NAMES;
}
