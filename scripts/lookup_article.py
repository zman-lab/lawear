#!/usr/bin/env python3
"""
조문 룩업 스크립트. TTS 변환 시 조문명/편/장 조회용.

사용법:
    python3 scripts/lookup_article.py 형사소송법 33
    python3 scripts/lookup_article.py 형법 250
    python3 scripts/lookup_article.py 민법 397
    python3 scripts/lookup_article.py 부동산등기법 109의2

출력 (탭 구분):
    Lv1: 제1편 총칙 제4장 변호 제33조 국선변호인
    Lv2: 제33조 국선변호인
    Lv3: 제33조

여러 조문 한번에 조회:
    python3 scripts/lookup_article.py 형사소송법 33,331,214의2
"""

import json
import sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "web" / "src" / "data" / "lawArticles.json"


def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def lookup(data, statute: str, article_num: str) -> dict:
    """조문 조회 → {title, path, lv1, lv2, lv3} 반환."""
    # 법령명 매칭 (약칭 지원)
    SHORT_NAMES = {
        "형소": "형사소송법", "형법": "형법", "민법": "민법",
        "민소": "민사소송법", "상법": "상법",
        "민집": "민사집행법", "민집규": "민사집행규칙",
        "공탁": "공탁법", "공탁규": "공탁규칙",
        "경직": "경찰관 직무집행법", "폭처": "폭력행위 등 처벌에 관한 법률",
        "성폭력": "성폭력방지 및 피해자보호 등에 관한 법률",
        "통비": "통신비밀보호법", "개보": "개인정보 보호법",
        "신탁": "신탁법",
        "주임": "주택임대차보호법", "상임": "상가건물 임대차보호법",
        "부등": "부동산등기법", "부등규": "부동산등기규칙",
    }
    full_name = SHORT_NAMES.get(statute, statute)

    if full_name not in data.get("statutes", {}):
        return {"error": f"법령 '{statute}' 없음. 가능: {list(data['statutes'].keys())}"}

    articles = data["statutes"][full_name]["articles"]
    info = articles.get(article_num)

    if not info:
        return {"error": f"{full_name} 제{article_num}조 없음"}

    title = info.get("title", "")
    path = info.get("path", "")

    # 편/장/절 분리
    path_parts = [p.strip() for p in path.split(">") if p.strip()] if path else []

    # Lv별 포맷
    jo = f"제{article_num}조"
    jo_with_title = f"{jo} {title}" if title else jo

    if path_parts:
        lv1 = " ".join(path_parts) + " " + jo_with_title
    else:
        lv1 = jo_with_title

    lv2 = jo_with_title
    lv3 = jo

    return {
        "statute": full_name,
        "article": article_num,
        "title": title,
        "path": path,
        "lv1": lv1,
        "lv2": lv2,
        "lv3": lv3,
    }


def main():
    if len(sys.argv) < 3:
        print("사용법: python3 scripts/lookup_article.py <법령명> <조문번호[,조문번호,...]>")
        print("예시: python3 scripts/lookup_article.py 형사소송법 33,331")
        print("약칭: 형소, 형법, 민법, 민소, 상법, 민집, 공탁, 부등, 부등규")
        sys.exit(1)

    data = load_data()
    statute = sys.argv[1]
    article_nums = sys.argv[2].split(",")

    for num in article_nums:
        num = num.strip()
        result = lookup(data, statute, num)

        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Lv1: {result['lv1']}")
            print(f"Lv2: {result['lv2']}")
            print(f"Lv3: {result['lv3']}")
        if len(article_nums) > 1:
            print("---")


if __name__ == "__main__":
    main()
