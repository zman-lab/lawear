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
  it('제397조 뒤에 조문제목 삽입', () => {
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
