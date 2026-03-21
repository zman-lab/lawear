#!/usr/bin/env python3
"""
law.go.kr API로 법령 조문을 조회하여 JSON 매핑 파일을 생성하는 빌드 스크립트.

사용법:
    python3 scripts/build_law_articles.py

출력:
    web/src/data/lawArticles.json
"""

import json
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import date

# === 설정 ===

API_BASE = "http://www.law.go.kr/DRF"
API_KEY = "testapi"
SLEEP_SEC = 1  # API rate limit 방지

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "web" / "src" / "data" / "lawArticles.json"

# 대상 법령 목록 (이름 → MST 번호, 검색으로 미리 확인된 값)
# MST가 None이면 검색 API로 자동 조회
STATUTES = {
    "민법": None,
    "민사소송법": None,
    "민사집행법": None,
    "형법": None,
    "형사소송법": None,
    "부동산등기법": None,
    "부동산 실권리자명의 등기에 관한 법률": None,
    "상법": None,
}


def api_get(endpoint: str, params: dict) -> dict:
    """law.go.kr API 호출 → JSON 파싱."""
    params["OC"] = API_KEY
    params["type"] = "JSON"
    url = f"{API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    print(f"  [BuildLawArticles] 법제처 API 호출: {url}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw)


def search_mst(statute_name: str) -> str:
    """법령명으로 검색하여 MST(법령일련번호)를 반환."""
    data = api_get("lawSearch.do", {
        "target": "law",
        "query": statute_name,
        "display": 100,
    })

    laws = data.get("LawSearch", {}).get("law", [])
    if not isinstance(laws, list):
        laws = [laws]

    # 정확히 일치하는 법령 찾기
    for law in laws:
        name = law.get("법령명한글", "")
        if name == statute_name:
            mst = law.get("법령일련번호", "")
            print(f"  검색 성공: {statute_name} → MST {mst}")
            return str(mst)

    # 못 찾으면 에러
    available = [law.get("법령명한글", "") for law in laws[:10]]
    raise ValueError(
        f"'{statute_name}' 검색 실패. 후보: {available}"
    )


def fetch_articles(mst: str) -> dict[str, str]:
    """MST로 법령 상세 조회 → {조문번호: 조문제목} 딕셔너리 반환."""
    data = api_get("lawService.do", {
        "target": "law",
        "MST": mst,
    })

    law = data.get("법령", {})
    jo_section = law.get("조문", {})
    units = jo_section.get("조문단위", [])

    # 단일 객체인 경우 리스트로 변환
    if isinstance(units, dict):
        units = [units]

    articles: dict[str, str] = {}

    for unit in units:
        # "전문"(편/장 제목)은 건너뛰고 "조문"만 처리
        if unit.get("조문여부") != "조문":
            continue

        base_num = unit.get("조문번호", "").strip()
        title = unit.get("조문제목", "").strip() if unit.get("조문제목") else ""
        content = unit.get("조문내용", "")

        if not base_num:
            continue

        # 조문내용에서 정확한 조문번호 추출 (가지번호 포함)
        # 예: "제109조의2(등기정보자료의 제공 등)" → "109의2"
        article_key = base_num
        m = re.match(r"제(\d+)조(의\d+)?", content)
        if m:
            extracted_num = m.group(1)
            suffix = m.group(2) or ""
            article_key = extracted_num + suffix

        articles[article_key] = title

    return articles


def main():
    print(f"=== 법령 조문 빌드 시작 ({date.today()}) ===\n")

    result = {
        "version": str(date.today()),
        "statutes": {},
    }

    for statute_name in STATUTES:
        print(f"[{statute_name}]")

        # MST 조회
        mst = STATUTES[statute_name]
        if mst is None:
            mst = search_mst(statute_name)
            time.sleep(SLEEP_SEC)
        else:
            mst = str(mst)

        # 조문 조회
        articles = fetch_articles(mst)
        time.sleep(SLEEP_SEC)

        result["statutes"][statute_name] = {
            "mst": mst,
            "articles": articles,
        }

        print(f"  [BuildLawArticles] 응답: {statute_name} — {len(articles)}개 조문 조회")
        print()

    # JSON 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_articles = sum(len(info["articles"]) for info in result["statutes"].values())
    print(f"[BuildLawArticles] 저장: lawArticles.json — 총 {len(result['statutes'])}개 법령, {total_articles}개 조문")
    print(f"=== 완료: {OUTPUT_PATH} ===")
    for name, info in result["statutes"].items():
        print(f"  {name}: {len(info['articles'])}개 조문 (MST: {info['mst']})")


if __name__ == "__main__":
    main()
