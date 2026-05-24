#!/usr/bin/env python3
"""
law.go.kr API로 법령 조문(제목/구조/원문)을 조회하여 JSON 매핑 파일을 생성하는 빌드 스크립트.

시행일 기준:
    사용자 시험일(2026-10-30, TARGET_DATE)에 시행 중인 버전을 정답으로 삼는다.
    target=eflaw(시행일법령) lawSearch 연혁 타임라인에서 "시행일자 <= TARGET_DATE 중 최신"
    레코드의 (MST, 시행일자)를 확정한 뒤, target=eflaw lawService.do?MST&efYd={그_시행일자}
    로 해당 시점 스냅샷을 받아 조문 원문을 파싱한다.
    (※ target=law?MST 는 한 MST에 시행일자가 여러 개면 가장 늦은 버전을 돌려주므로
       시험일 시점 조문을 보장하지 못해 사용하지 않는다 — 2026-05-24 검증)

출력:
    web/src/data/lawArticles.json       — 조문 제목 + 편/장/절/관 경로 (경량 인덱스)
    web/src/data/lawArticlesText.json    — 조문 원문(body) 별도 store (제목의 수십배 용량)

사용법:
    python3 scripts/build_law_articles.py [--resolve-only]
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import date

# === 설정 ===

API_BASE = "http://www.law.go.kr/DRF"
API_KEY = os.getenv("LAW_OC", "testapi")  # 공개키 testapi 폴백
SLEEP_SEC = 1.0          # API rate limit 방지 (조회 간 sleep)
TARGET_DATE = os.getenv("LAW_TARGET_DATE", "20261030")  # 사용자 시험일

DATA_DIR = Path(__file__).resolve().parent.parent / "web" / "src" / "data"
OUTPUT_PATH = DATA_DIR / "lawArticles.json"
TEXT_OUTPUT_PATH = DATA_DIR / "lawArticlesText.json"

# 대상 법령 목록 (이름 → 캐시 MST). 실제 사용 MST는 TARGET_DATE 기준으로 재조회한다.
STATUTES = {
    "형법": 284025,
    "형사소송법": 269945,
    "민법": 284415,
    "민사소송법": 252393,
    "형사소송규칙": 273605,
    "민사소송규칙": 283113,
    "상법": 284143,
    "민사집행법": 268837,
    "민사집행규칙": 272631,
    "공탁법": 284413,
    "공탁규칙": 272613,
    "경찰관 직무집행법": 273315,
    "폭력행위 등 처벌에 관한 법률": 178989,
    "성폭력방지 및 피해자보호 등에 관한 법률": 270807,
    "통신비밀보호법": 268703,
    "개인정보 보호법": 270351,
    "신탁법": 198564,
    "주택임대차보호법": 276291,
    "상가건물 임대차보호법": 276285,
    "부동산등기법": 265377,
    "부동산등기규칙": 266847,
}


def api_get(endpoint: str, params: dict) -> dict:
    """law.go.kr API 호출 → JSON 파싱."""
    params["OC"] = API_KEY
    params["type"] = "JSON"
    url = f"{API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(f"비JSON 응답({len(raw)}B): {raw[:120]!r} | URL={url}")


def resolve_effective(statute_name: str) -> dict:
    """TARGET_DATE 시점에 시행 중인 (MST, 시행일자, 연혁, 공포일자)를 확정.

    target=eflaw lawSearch 연혁 타임라인(sort=efdes + 페이지네이션)에서
    법령명한글 정확 일치 + 시행일자 <= TARGET_DATE 중 최신 레코드를 고른다.
    """
    all_laws: list[dict] = []
    for page in range(1, 6):
        data = api_get("lawSearch.do", {
            "target": "eflaw",
            "query": statute_name,
            "display": 100,
            "page": page,
            "sort": "efdes",
        })
        laws = data.get("LawSearch", {}).get("law", [])
        if isinstance(laws, dict):
            laws = [laws]
        if not laws:
            break
        all_laws.extend(laws)
        if len(laws) < 100:
            break
        time.sleep(0.4)

    exact = [l for l in all_laws if l.get("법령명한글", "") == statute_name]
    if not exact:
        cands = sorted({l.get("법령명한글", "") for l in all_laws})[:8]
        raise ValueError(f"'{statute_name}' 정확 일치 없음. 후보: {cands}")

    eligible = sorted(
        [l for l in exact if l.get("시행일자", "") <= TARGET_DATE],
        key=lambda l: l.get("시행일자", ""),
        reverse=True,
    )
    if not eligible:
        raise ValueError(f"'{statute_name}' {TARGET_DATE} 이전 시행 레코드 없음")

    eff = eligible[0]
    return {
        "mst": str(eff.get("법령일련번호", "")),
        "ef_date": eff.get("시행일자", ""),
        "yh": eff.get("현행연혁코드", ""),
        "promulgation": eff.get("공포일자", ""),
        "promulgation_no": eff.get("공포번호", ""),
    }


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _norm_text(v) -> str:
    """조문내용/항내용 등이 list/None 일 수 있어 안전하게 문자열화."""
    if isinstance(v, list):
        v = " ".join(str(x) for x in v if x)
    if not isinstance(v, str):
        v = str(v) if v else ""
    # 다중 공백 정리 (R-09: 글자는 안 바꾸고 공백만 정규화)
    return re.sub(r"\s+", " ", v).strip()


def fetch_law(mst: str, ef_date: str) -> dict:
    """target=eflaw MST+efYd로 해당 시점 스냅샷 → 조문 단위 원문/제목/경로 파싱.

    반환: {
      "articles": {조문키: {"title", "path"}},          # 경량 인덱스용
      "bodies":   {조문키: {"text", "paragraphs":[...]}}, # 원문 store용
    }
    """
    data = api_get("lawService.do", {
        "target": "eflaw",
        "MST": mst,
        "efYd": ef_date,
    })

    law = data.get("법령", {})
    jo_section = law.get("조문", {})
    units = _as_list(jo_section.get("조문단위", []))

    articles: dict[str, dict] = {}
    bodies: dict[str, dict] = {}

    current_path: list[str] = []
    HIERARCHY = {"편": 1, "장": 2, "절": 3, "관": 4}

    for unit in units:
        jo_type = unit.get("조문여부", "")

        if jo_type != "조문":
            # 편/장/절/관 제목 추출
            content = _norm_text(unit.get("조문내용", ""))
            m = re.match(r"(제\d+편|제\d+장|제\d+절|제\d+관)\s*(.*)", content)
            if m:
                marker = m.group(1)
                label = m.group(2).strip()
                entry = f"{marker} {label}" if label else marker
                for key, level in HIERARCHY.items():
                    if key in marker:
                        current_path = [
                            p for p in current_path
                            if not any(k in p and HIERARCHY.get(k, 99) >= level for k in HIERARCHY)
                        ]
                        current_path.append(entry)
                        break
            continue

        # 조문 처리
        base_num = (unit.get("조문번호") or "").strip()
        title = (unit.get("조문제목") or "").strip()
        content = _norm_text(unit.get("조문내용", ""))
        if not base_num:
            continue

        # 조문내용에서 정확한 조문번호 추출 (가지번호 포함)
        article_key = base_num
        m = re.match(r"제(\d+)조(의\d+)?", content)
        if m:
            article_key = m.group(1) + (m.group(2) or "")

        articles[article_key] = {
            "title": title,
            "path": " > ".join(current_path) if current_path else "",
        }

        # === 원문(body) 파싱: 조문내용 + 항/호/목 (verbatim) ===
        paragraphs = []
        for hang in _as_list(unit.get("항")):
            hang_no = (hang.get("항번호") or "").strip()
            hang_text = _norm_text(hang.get("항내용", ""))
            ho_list = []
            for ho in _as_list(hang.get("호")):
                ho_no = (ho.get("호번호") or "").strip()
                ho_text = _norm_text(ho.get("호내용", ""))
                mok_list = []
                for mok in _as_list(ho.get("목")):
                    mok_no = (mok.get("목번호") or "").strip()
                    mok_text = _norm_text(mok.get("목내용", ""))
                    if mok_text:
                        mok_list.append({"no": mok_no, "text": mok_text})
                ho_entry = {"no": ho_no, "text": ho_text}
                if mok_list:
                    ho_entry["items"] = mok_list
                if ho_text or mok_list:
                    ho_list.append(ho_entry)
            para = {"no": hang_no, "text": hang_text}
            if ho_list:
                para["items"] = ho_list
            if hang_text or ho_list:
                paragraphs.append(para)

        body_entry = {"text": content}
        if paragraphs:
            body_entry["paragraphs"] = paragraphs
        bodies[article_key] = body_entry

    return {"articles": articles, "bodies": bodies}


def main():
    resolve_only = "--resolve-only" in sys.argv
    print(f"=== 법령 조문 빌드 시작 (build={date.today()}, 시행기준={TARGET_DATE}, OC={API_KEY}) ===\n")

    index_result = {
        "version": str(date.today()),
        "target_date": TARGET_DATE,
        "statutes": {},
    }
    text_result = {
        "version": str(date.today()),
        "target_date": TARGET_DATE,
        "statutes": {},
    }

    for statute_name, cache_mst in STATUTES.items():
        print(f"[{statute_name}]")
        try:
            eff = resolve_effective(statute_name)
        except Exception as e:
            print(f"  !! 시행MST 조회 실패: {e}\n")
            continue
        time.sleep(SLEEP_SEC)

        changed = str(eff["mst"]) != str(cache_mst)
        print(f"  시행MST: {eff['mst']} (시행 {eff['ef_date']}, {eff['yh']}, 공포 {eff['promulgation']})"
              f"{'  [MST변경: 캐시 ' + str(cache_mst) + ']' if changed else ''}")

        if resolve_only:
            index_result["statutes"][statute_name] = {
                "mst": eff["mst"], "ef_date": eff["ef_date"], "yh": eff["yh"],
                "promulgation": eff["promulgation"], "cache_mst": str(cache_mst),
                "mst_changed": changed, "articles": {},
            }
            print()
            continue

        parsed = fetch_law(eff["mst"], eff["ef_date"])
        time.sleep(SLEEP_SEC)

        index_result["statutes"][statute_name] = {
            "mst": eff["mst"],
            "ef_date": eff["ef_date"],
            "yh": eff["yh"],
            "promulgation": eff["promulgation"],
            "promulgation_no": eff["promulgation_no"],
            "cache_mst": str(cache_mst),
            "mst_changed": changed,
            "articles": parsed["articles"],
        }
        text_result["statutes"][statute_name] = {
            "mst": eff["mst"],
            "ef_date": eff["ef_date"],
            "bodies": parsed["bodies"],
        }
        print(f"  조문: {len(parsed['articles'])}개\n")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(index_result, f, ensure_ascii=False, indent=2)
    if not resolve_only:
        with open(TEXT_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(text_result, f, ensure_ascii=False, indent=2)

    total = sum(len(s["articles"]) for s in index_result["statutes"].values())
    print(f"[저장] lawArticles.json — {len(index_result['statutes'])}개 법령, {total}개 조문")
    if not resolve_only:
        tb = sum(len(s["bodies"]) for s in text_result["statutes"].values())
        sz = TEXT_OUTPUT_PATH.stat().st_size
        print(f"[저장] lawArticlesText.json — {tb}개 조문 원문, {sz/1024:.0f}KB")
    print("=== 완료 ===")


if __name__ == "__main__":
    main()
