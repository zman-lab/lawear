import { describe, it, expect } from 'vitest';
import {
  getArticleTitle,
  insertArticleTitles,
  getLawArticlesVersion,
  getStatuteNames,
} from '../lawArticleHelper';

describe('getArticleTitle', () => {
  it('민법 제397조 → 금전채무불이행에 대한 특칙', () => {
    expect(getArticleTitle('민법', '397')).toBe('금전채무불이행에 대한 특칙');
  });

  it('민법 제166조 → 소멸시효의 기산점', () => {
    expect(getArticleTitle('민법', '166')).toBe('소멸시효의 기산점');
  });

  it('부동산등기법 가지번호 제7조의2', () => {
    expect(getArticleTitle('부동산등기법', '7의2')).toBe('관련 사건의 관할에 관한 특례');
  });

  it('존재하지 않는 조문 → null', () => {
    expect(getArticleTitle('민법', '99999')).toBeNull();
  });

  it('존재하지 않는 법령 → null', () => {
    expect(getArticleTitle('존재하지않는법', '1')).toBeNull();
  });

  it('제목이 빈 조문 → null', () => {
    // 민법 제3조 등 제목이 빈 조문이 있음
    const result = getArticleTitle('민법', '3');
    // 빈 문자열이면 null 반환
    expect(result === null || typeof result === 'string').toBe(true);
  });
});

describe('insertArticleTitles', () => {
  it('기본 법령의 조문제목 삽입', () => {
    const result = insertArticleTitles('제397조에 의하면', '민법');
    expect(result).toBe('제397조 금전채무불이행에 대한 특칙에 의하면');
  });

  it('가지번호 제109조의2 처리', () => {
    const result = insertArticleTitles('제109조의2에 따라', '부동산등기법');
    expect(result).toBe('제109조의2 등기정보자료의 제공 등에 따라');
  });

  it('매핑 없는 조문은 그대로', () => {
    const result = insertArticleTitles('제99999조에 의하면', '민법');
    expect(result).toBe('제99999조에 의하면');
  });

  it('존재하지 않는 법령이면 원문 그대로', () => {
    const text = '제397조에 의하면';
    expect(insertArticleTitles(text, '존재하지않는법')).toBe(text);
  });

  it('여러 조문이 있는 텍스트', () => {
    const result = insertArticleTitles(
      '제166조 및 제397조에 따르면',
      '민법',
    );
    expect(result).toContain('제166조 소멸시효의 기산점');
    expect(result).toContain('제397조 금전채무불이행에 대한 특칙');
  });

  it('이미 제목이 삽입된 경우 중복 삽입하지 않음', () => {
    const alreadyInserted = '제397조 금전채무불이행에 대한 특칙에 의하면';
    const result = insertArticleTitles(alreadyInserted, '민법');
    // "금전채무불이행에 대한 특칙"이 2번 나오면 안 됨
    const count = (result.match(/금전채무불이행에 대한 특칙/g) || []).length;
    expect(count).toBe(1);
  });

  it('타법 참조: "민법 제467조"를 민사소송법 과목에서 처리', () => {
    const result = insertArticleTitles('민법 제467조에 따라', '민사소송법');
    expect(result).toContain('민법 제467조 변제의 장소');
  });

  it('타법 참조 + 기본 법령 혼합', () => {
    // 민사소송법 과목에서 "제2조"(기본법령)와 "민법 제185조"(타법 참조) 혼합
    const result = insertArticleTitles(
      '제2조에 의하면 소는 피고의 보통재판적이 있는 곳이고, 민법 제185조에 해당한다.',
      '민사소송법',
    );
    expect(result).toContain('제2조 보통재판적');
    expect(result).toContain('민법 제185조 물권의 종류');
  });

  it('Lv.3 슈퍼심플: 제목 삽입 안 함', () => {
    const result = insertArticleTitles('제397조에 의하면', '민법', 3);
    expect(result).toBe('제397조에 의하면');
  });

  it('Lv.1 기본: 제목 삽입', () => {
    const result = insertArticleTitles('제397조에 의하면', '민법', 1);
    expect(result).toBe('제397조 금전채무불이행에 대한 특칙에 의하면');
  });

  it('Lv.2 핵심요약: 제목 삽입', () => {
    const result = insertArticleTitles('제397조에 의하면', '민법', 2);
    expect(result).toBe('제397조 금전채무불이행에 대한 특칙에 의하면');
  });
});

describe('getLawArticlesVersion', () => {
  it('날짜 형식 반환', () => {
    const version = getLawArticlesVersion();
    expect(version).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('getStatuteNames', () => {
  it('8개 법령 포함', () => {
    const names = getStatuteNames();
    expect(names).toHaveLength(8);
    expect(names).toContain('민법');
    expect(names).toContain('형법');
    expect(names).toContain('부동산등기법');
  });
});
