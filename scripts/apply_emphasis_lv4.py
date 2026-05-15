#!/usr/bin/env python3
"""
Lv.4 강조 태그 자동 매칭 스크립트 (R-28 보강용)

PDF JSON의 [red]/[blue]/[bold] 키워드를 .md의 Lv.4 본문에서
의미 매칭하여 태그 인라인 삽입한다.

원리:
- 긴 키워드를 4자 이상 핵심 단어로 분할 (false positive 방지)
- Lv.4 본문에서 substring 매칭 → 태그 감싸기
- 이미 태그된 곳 중복 방지
- R-09 절대 준수 (PDF 키워드만 — 자의적 추가 X)

사용:
    python3 scripts/apply_emphasis_lv4.py --case 미케01_01
    python3 scripts/apply_emphasis_lv4.py --file 미케01           # 미케01 13 Case 일괄
    python3 scripts/apply_emphasis_lv4.py --all                  # 전체
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJ = Path("/Users/nhn/zman-lab/lawear")
DATA_DIR = PROJ / "docs" / "tts-new"
JSON_DIR = PROJ / "pipeline" / "raw_texts"

# 디렉토리·과목 매핑 (사용자 매핑 표 기반)
DIR_TO_SUBJECT = {
    "입문_민법": ("minbeop", "immun"),
    "입문_민소": ("minso", "immun"),
    "예비_민법": ("minbeop", "yebi"),
    "예비_민소": ("minso", "yebi"),
    # 형법·형소·부등은 별도 처리 (split files)
}


def load_case_data(case_id: str, dir_name: str) -> dict | None:
    """미케01_01 → JSON cases[0]."""
    m = re.match(r"미케(\d+)_(\d+)", case_id)
    if not m:
        return None
    file_num, case_num = m.group(1), int(m.group(2))
    subject, prefix = DIR_TO_SUBJECT.get(dir_name, (None, None))
    if not subject:
        return None
    json_path = JSON_DIR / subject / f"{prefix}_mike{file_num}.json"
    if not json_path.exists():
        return None
    data = json.load(open(json_path))
    cases = data.get("cases", [])
    if case_num > len(cases):
        return None
    return cases[case_num - 1]


def extract_keywords(case_data: dict) -> dict:
    """JSON에서 [red]/[blue]/[bold] 키워드 추출."""
    out = {"red": [], "blue": [], "bold": []}
    ans = case_data.get("answer", {})
    blob = ans.get("conclusion", "") or ""
    for s in ans.get("sections", []):
        blob += "\n" + (s.get("content", "") or "")
    # problem 영역에 답안이 흡수된 케이스 대비
    blob += "\n" + (case_data.get("problem", "") or "")
    for color in ("red", "blue", "bold"):
        out[color] = re.findall(rf"\[{color}\]([\s\S]+?)\[/{color}\]", blob)
    return out


def split_to_phrases(kw: str, min_len: int = 4) -> list[str]:
    """긴 키워드를 4자 이상 핵심 단어 또는 구절로 분할."""
    # 공백·쉼표·괄호·마침표·꺽쇠로 분리
    parts = re.split(r"[\s,\(\)\[\]\.\<\>『』「」]+", kw)
    out = []
    for p in parts:
        p = p.strip()
        # 한자·특수기호 제거
        p = re.sub(r"[甲乙丙丁戊己庚辛壬癸※○●◯△▲□■★☆]", "", p).strip()
        if len(p) >= min_len:
            out.append(p)
    # 또한 키워드 전체 자체 (조사 포함)도 후보 (조사 떼기 시도)
    full = re.sub(r"[甲乙丙丁戊己庚辛壬癸]", "", kw).strip()
    if len(full) >= min_len and full not in out:
        out.insert(0, full)
    return out


def already_tagged(text: str, phrase: str) -> bool:
    """해당 phrase가 이미 [red]/[blue]/[bold]/[blank]/[u] 태그 안에 있는지."""
    for color in ("red", "blue", "bold", "blank", "u"):
        if f"[{color}]" in text and f"[/{color}]" in text:
            # phrase가 태그 내부에 있는지 정밀 확인
            for m in re.finditer(rf"\[{color}\]([\s\S]+?)\[/{color}\]", text):
                if phrase in m.group(1):
                    return True
    return False


def safe_replace_first(text: str, phrase: str, tag: str) -> tuple[str, bool]:
    """첫 매칭 위치에 태그 감싸기. 이미 태그된 곳·짧은 phrase 제외."""
    if len(phrase) < 4:
        return text, False
    # 태그 안에 있는 phrase 위치는 제외 (lookahead·lookbehind 어려움 → 수동 체크)
    idx = -1
    start = 0
    while True:
        i = text.find(phrase, start)
        if i == -1:
            break
        # 이 위치가 기존 태그 내부인지 확인
        before = text[:i]
        # 가장 가까운 [color] / [/color] 비교
        last_open = max(
            before.rfind(f"[{c}]") for c in ("red", "blue", "bold", "blank", "u")
        )
        last_close = max(
            before.rfind(f"[/{c}]") for c in ("red", "blue", "bold", "blank", "u")
        )
        if last_open > last_close:
            # 태그 내부 → 스킵
            start = i + 1
            continue
        idx = i
        break
    if idx == -1:
        return text, False
    new = text[:idx] + f"[{tag}]{phrase}[/{tag}]" + text[idx + len(phrase) :]
    return new, True


def apply_to_lv4(md_text: str, keywords: dict) -> tuple[str, dict]:
    """Lv.4 섹션에만 태그 적용."""
    # Lv.4 섹션 추출
    pattern = r"(## Lv\.4 암기노트[^\n]*\n)([\s\S]*?)(\n## |\Z)"
    m = re.search(pattern, md_text)
    if not m:
        return md_text, {"red": 0, "blue": 0, "bold": 0}
    lv4_body = m.group(2)
    stats = {"red": 0, "blue": 0, "bold": 0}

    # 우선순위: red > blue > bold (R-28)
    for color in ("red", "blue", "bold"):
        for kw in keywords.get(color, []):
            phrases = split_to_phrases(kw)
            # 긴 구절 먼저 시도 → 못 찾으면 짧은 단어
            for phrase in phrases:
                if already_tagged(lv4_body, phrase):
                    continue
                lv4_body, applied = safe_replace_first(lv4_body, phrase, color)
                if applied:
                    stats[color] += 1
                    break  # 한 키워드당 1회 적용 (중복 방지)

    new_md = md_text[: m.start(2)] + lv4_body + md_text[m.end(2) :]
    return new_md, stats


def process_case(case_id: str, dir_name: str) -> tuple[int, dict] | None:
    md_path = DATA_DIR / dir_name / f"2026_{DIR_TO_SUBJECT[dir_name][0]}_{DIR_TO_SUBJECT[dir_name][1]}_{case_id}.md"
    if not md_path.exists():
        # 다른 명명 시도
        candidates = list((DATA_DIR / dir_name).glob(f"*{case_id}.md"))
        if not candidates:
            return None
        md_path = candidates[0]
    case_data = load_case_data(case_id, dir_name)
    if not case_data:
        return None
    keywords = extract_keywords(case_data)
    md_text = md_path.read_text(encoding="utf-8")
    new_md, stats = apply_to_lv4(md_text, keywords)
    total_kw = sum(len(v) for v in keywords.values())
    total_applied = sum(stats.values())
    if total_applied > 0:
        md_path.write_text(new_md, encoding="utf-8")
    return total_applied, {"total_kw": total_kw, **stats}


def main():
    parser = argparse.ArgumentParser(description="Lv.4 강조 태그 자동 매칭")
    parser.add_argument("--case", help="특정 Case (예: 미케01_01)")
    parser.add_argument("--file", help="시험 파일 단위 (예: 미케01)")
    parser.add_argument("--dir", default="입문_민법", help="과목 디렉토리 (기본: 입문_민법)")
    parser.add_argument("--all", action="store_true", help="전체 디렉토리 모든 Case")
    args = parser.parse_args()

    cases = []
    if args.case:
        cases = [(args.dir, args.case)]
    elif args.file:
        m = re.match(r"미케(\d+)", args.file)
        if not m:
            print(f"잘못된 file: {args.file}")
            return
        # JSON에서 case 수 확인
        subject, prefix = DIR_TO_SUBJECT[args.dir]
        jp = JSON_DIR / subject / f"{prefix}_mike{m.group(1)}.json"
        if not jp.exists():
            print(f"JSON 없음: {jp}")
            return
        data = json.load(open(jp))
        case_count = len(data.get("cases", []))
        cases = [(args.dir, f"미케{m.group(1)}_{i:02d}") for i in range(1, case_count + 1)]
    elif args.all:
        for d in DIR_TO_SUBJECT:
            ddir = DATA_DIR / d
            if not ddir.exists():
                continue
            for f in sorted(ddir.glob("*.md")):
                m = re.search(r"(미케\d+_\d+|모고\d+_\d+|모고\d+)", f.name)
                if m:
                    cases.append((d, m.group(1)))
    else:
        parser.print_help()
        return

    print(f"대상 {len(cases)}개 Case 처리 시작...")
    grand_kw = 0
    grand_applied = 0
    for dir_name, cid in cases:
        result = process_case(cid, dir_name)
        if result is None:
            print(f"  [SKIP] {dir_name}/{cid} — .md 또는 JSON 없음")
            continue
        applied, stats = result
        print(
            f"  {dir_name}/{cid}: 적용 {applied}/{stats['total_kw']} "
            f"(red {stats['red']} / blue {stats['blue']} / bold {stats['bold']})"
        )
        grand_kw += stats["total_kw"]
        grand_applied += applied

    print(f"\n전체: 적용 {grand_applied}/{grand_kw} "
          f"({grand_applied * 100 // max(grand_kw, 1)}%)")


if __name__ == "__main__":
    main()
