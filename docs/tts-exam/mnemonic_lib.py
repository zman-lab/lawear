#!/usr/bin/env python3
"""mnemonic_lib — 두문자 라이브러리 로더 + missing_critical 매칭 (lawear Task #6 M1).

채점 후 missing_critical 항목에 대해 라이브러리에서 두문자/풀이 키워드/조문을
역참조하여 부장판사 QA·강사 QA가 "이 누락은 어느 entry 정본을 가리키는지"를
근거(source_entry, lib_section) 동반으로 제시하도록 한다.

설계 원칙 (R-09):
  1. 라이브러리 .md는 read-only — 매칭만 한다.
  2. 매칭은 substring + 정규식 한정 — AI 의미 추론 금지.
  3. "포기"/"미수록" entry는 abandoned=True → 매칭 결과에서 100% 제외.
  4. letter 묶음 점(·) 분리 단위로 보존 — 분해 금지 (예: "현재·일시불·승낙" → 3 letters).
  5. 매칭 결과는 source_entry + lib_section 의무 — 근거 없으면 자동 reject.
  6. STT 발음/어휘 부합 영역 미진입 — 단순 substring 매칭만.

함수:
  - load_mnemonic_library(subject) -> dict
  - parse_entries(md_body, subject)  -> list[dict]
  - match_missing_to_mnemonic(missing_critical, subject, *, role, limit) -> list[dict]

데이터 형태:
  entry = {
      "section_title": "1-2. 이행지체 성립 요건",
      "letters":        ["무", "도", "가", "귀", "법"],   # 점(·) 분리 단위 보존
      "solving_keywords": "이행기 도래 / 안전이행 / 청구 / ...",  # 풀이형 raw
      "articles":       ["제390조", "제544조"],
      "abandoned":      False,
      "source_entry":   "민법 §1-2",
      "lib_section":    "1",  # 챕터 번호
      "raw_block":      "...",  # H3~다음 H3 사이 본문 (디버그용)
  }
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# ─── 경로 / 과목 매핑 ──────────────────────────────────────────────────────
_LIB_BASE = Path(__file__).resolve().parent.parent / "tts-new" / "두문자"

_SUBJECT_TO_FILE: dict[str, str] = {
    "민법": "민법.md",
    "민소": "민소.md",
    "민사소송법": "민소.md",
    "부동산등기법": "부등법.md",
    "부등법": "부등법.md",
    "형법": "형법.md",
    "형사소송법": "형소.md",
    "형소": "형소.md",
}

_SUBJECT_PREFIX_LABEL: dict[str, str] = {
    "민법.md": "민법",
    "민소.md": "민소",
    "부등법.md": "부등법",
    "형법.md": "형법",
    "형소.md": "형소",
}

# ─── 정규식 ───────────────────────────────────────────────────────────────
# H3 entry 헤더: "### 1-2. 이행지체 성립 요건 (제390조)" → section_no "1-2", title "이행지체 ..."
_RE_H3_ENTRY = re.compile(r"^###\s+(\d+)-(\d+)\.\s+(.+?)\s*$", re.MULTILINE)

# H2 boundary (부록·인덱스 같은 sibling 섹션) — entry raw_block은 다음 H2도 cutoff.
_RE_H2_BOUNDARY = re.compile(r"^##\s+\S", re.MULTILINE)

# 두문자 필드: "- **두문자**: ..." 또는 "- **두문자 (적격)**: ..." (괄호 prefix 허용)
_RE_MNEMONIC_FIELD = re.compile(
    r"^-\s*\*\*두문자[^*]*\*\*\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)

# 풀이형 필드: 두문자와 동일 패턴 (괄호 prefix 허용)
_RE_SOLVING_FIELD = re.compile(
    r"^-\s*\*\*풀이형[^*]*\*\*\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)

# 연관 조문 필드
_RE_RELATED_ARTICLES = re.compile(
    r"^-\s*\*\*연관\s*조문\*\*\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)

# [em1]X[/em1] letter token (em1~em4 허용 — em1 우선이지만 일부 entry는 em2 보충도 있음)
_RE_EM_TOKEN = re.compile(r"\[em[1-4]\]([^\[\]]+?)\[/em[1-4]\]")

# 제N조 (선택적 항·호 포함 무시 — 조 단위만 추출)
_RE_ARTICLE_NUM = re.compile(r"제\s*(\d+)\s*조")

# 포기/미수록 마킹 (필드값에 등장하면 abandoned)
_RE_ABANDONED = re.compile(r"^\s*(<포기|포기\s*[—\-]|미수록)")

# 점(·) — letter 묶음 구분자 (·) — 다른 separator도 일부 있음(/)
_LETTER_SEPARATORS = ("·", " / ", "/", " → ")


def _split_letters_preserve(raw_letters_text: str) -> list[str]:
    """em1 token 추출 후 점/슬래시 등 보존.

    Example:
      input  : "[em1]현재[/em1]·[em1]일[/em1]·[em1]시[/em1]·[em1]불[/em1]·[em1]승낙[/em1] (읽을 때 ...)"
      output : ["현재", "일", "시", "불", "승낙"]
    """
    tokens = _RE_EM_TOKEN.findall(raw_letters_text)
    out: list[str] = []
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        # 점 분리는 이미 em1 wrap이 점 단위로 끊겨 있어 추가 분리 불필요.
        # 하지만 일부 entry는 em1 안에 "일상" 같이 묶음 letter 포함 → 그대로 보존.
        out.append(tok)
    return out


def _is_abandoned_value(value: str) -> bool:
    """필드 값이 '포기'/'미수록' 마킹인지 판정."""
    if not value:
        return True
    return bool(_RE_ABANDONED.match(value.strip()))


def _extract_articles(raw_text: str) -> list[str]:
    """본문에서 제N조 패턴 전부 추출 (중복 제거 + 등장순 유지)."""
    seen: set[str] = set()
    out: list[str] = []
    for num in _RE_ARTICLE_NUM.findall(raw_text):
        art = f"제{num}조"
        if art in seen:
            continue
        seen.add(art)
        out.append(art)
    return out


def parse_entries(md_body: str, subject: str) -> list[dict[str, Any]]:
    """라이브러리 .md 본문을 entry list로 변환.

    Rules:
      - H3 헤더(### N-M. 제목)로 entry split
      - 같은 entry 안에 '- **두문자**:' 라인이 여러 개면 첫 번째만 letters로 사용
        (참고/sub 두문자는 보조 메타로만 보고 letters 본체에는 미포함)
      - '두문자' 필드 자체가 abandoned 마킹이거나, '풀이형' 필드도 같이 abandoned 면
        entry.abandoned = True (lawear-4b59 사고 재현 방지)
      - 미수록 entry는 abandoned True + letters 빈 리스트
    """
    # 파일 헤더(첫 H1, 메타데이터) 컷: 첫 H3 시작점부터 처리
    first_h3_match = _RE_H3_ENTRY.search(md_body)
    if not first_h3_match:
        return []

    body = md_body[first_h3_match.start():]
    # H3 시작점 + H2 boundary 인덱스 (다음 entry 또는 sibling 섹션까지)
    h3_starts = [m.start() for m in _RE_H3_ENTRY.finditer(body)]
    h2_boundaries = [m.start() for m in _RE_H2_BOUNDARY.finditer(body)]
    h3_starts.append(len(body))  # sentinel

    subject_label = _SUBJECT_PREFIX_LABEL.get(
        _SUBJECT_TO_FILE.get(subject, subject), subject
    )

    entries: list[dict[str, Any]] = []
    h3_iter = list(_RE_H3_ENTRY.finditer(body))
    for idx, h3 in enumerate(h3_iter):
        chap_no = h3.group(1)
        sub_no = h3.group(2)
        title_text = h3.group(3).strip()
        section_no = f"{chap_no}-{sub_no}"

        block_start = h3_starts[idx]
        next_h3_start = h3_starts[idx + 1]
        # H2 boundary가 block_start ~ next_h3_start 사이면 더 가까운 boundary로 잘림
        block_end = next_h3_start
        for h2_pos in h2_boundaries:
            if block_start < h2_pos < block_end:
                block_end = h2_pos
                break
        raw_block = body[block_start:block_end]

        # 첫 두문자/풀이 필드만 사용
        mnem_match = _RE_MNEMONIC_FIELD.search(raw_block)
        solv_match = _RE_SOLVING_FIELD.search(raw_block)

        mnem_value = mnem_match.group(1).strip() if mnem_match else ""
        solv_value = solv_match.group(1).strip() if solv_match else ""

        # abandoned 검사 — 마킹된 값에만 True. 필드 부재(빈 문자열)는 abandoned 아님.
        mnem_abandoned = bool(mnem_value) and _is_abandoned_value(mnem_value)
        solv_abandoned = bool(solv_value) and _is_abandoned_value(solv_value)

        # 두문자 자체가 "없음"인 경우 letters 비어있지만 abandoned는 아님
        # ("없음 (일반 요건)" 같은 entry는 풀이형으로 매칭 가능)
        is_no_mnemonic = bool(
            mnem_value and (
                mnem_value.startswith("없음")
                or mnem_value.strip().startswith("없음")
            )
        )

        letters: list[str] = []
        if not mnem_abandoned and not is_no_mnemonic and mnem_value:
            letters = _split_letters_preserve(mnem_value)

        # abandoned 판정: 명세 룰 (포기/미수록 마킹 entry만 abandoned)
        #   - mnem_value 자체가 "<포기..." / "포기 —..." / "미수록..." 마킹 → abandoned
        #   - 두문자 필드 부재 (`mnem_value == ""`) → abandoned 아님
        #     (풀이형 또는 본문 템플릿 키워드로 매칭 가능, letter는 빈 list로 전달)
        #   - "없음 (일반 요건)" → abandoned 아님 (풀이형 매칭 가능)
        abandoned = bool(mnem_abandoned)

        # 풀이형도 포기면 매칭 키워드 신뢰 X — keywords는 비움
        # (단, 두문자 letters는 PDF 정본일 수 있어 letters는 유지)
        if solv_abandoned:
            solving_keywords = ""
        else:
            solving_keywords = solv_value

        # 연관 조문 우선 추출 → 없으면 raw_block에서 fallback
        rel_match = _RE_RELATED_ARTICLES.search(raw_block)
        if rel_match:
            articles = _extract_articles(rel_match.group(1))
        else:
            # H3 헤더의 "(제390조)" 같은 표시도 articles에 잡힘
            articles = _extract_articles(raw_block)

        source_entry = f"{subject_label} §{section_no}"

        entries.append({
            "section_title": f"{section_no}. {title_text}",
            "title_text":    title_text,
            "section_no":    section_no,
            "chapter_no":    chap_no,
            "letters":       letters,
            "solving_keywords": solving_keywords,
            "articles":      articles,
            "abandoned":     abandoned,
            "source_entry":  source_entry,
            "lib_section":   chap_no,
            "raw_block":     raw_block,
        })

    return entries


@lru_cache(maxsize=8)
def load_mnemonic_library(subject: str) -> dict[str, Any]:
    """과목별 두문자 라이브러리 로드.

    Returns:
      {
        "status": "loaded" | "empty" | "missing",
        "subject": "민법" / ...,
        "file_path": "<absolute path>" or None,
        "entries": [...],
        "abandoned_count": int,
        "total_count": int,
      }

    status:
      - "loaded" : entries 1개 이상
      - "empty"  : 파일 존재하지만 entry 0건 (형법/형소 초기 상태)
      - "missing": 파일 자체 부재 (오타·미지원 과목)
    """
    file_name = _SUBJECT_TO_FILE.get(subject)
    if not file_name:
        return {
            "status": "missing",
            "subject": subject,
            "file_path": None,
            "entries": [],
            "abandoned_count": 0,
            "total_count": 0,
        }

    file_path = _LIB_BASE / file_name
    if not file_path.exists():
        return {
            "status": "missing",
            "subject": subject,
            "file_path": str(file_path),
            "entries": [],
            "abandoned_count": 0,
            "total_count": 0,
        }

    # READ-ONLY (R-09)
    with open(file_path, "r", encoding="utf-8") as f:
        md_body = f.read()

    entries = parse_entries(md_body, subject)
    abandoned_count = sum(1 for e in entries if e["abandoned"])

    return {
        "status": "loaded" if entries else "empty",
        "subject": _SUBJECT_PREFIX_LABEL.get(file_name, subject),
        "file_path": str(file_path),
        "entries": entries,
        "abandoned_count": abandoned_count,
        "total_count": len(entries),
    }


# ─── 매칭 ─────────────────────────────────────────────────────────────────
# 한국어 토큰: 한글 2자 이상 묶음 (조사·짧은 단어 제외 효과)
_RE_KO_TOKEN = re.compile(r"[가-힣]{2,}")


def _normalize_item(text: str) -> str:
    """매칭 비교용 정규화 — 공백 압축만, 어휘 변환 X."""
    return re.sub(r"\s+", " ", text or "").strip()


def _tokenize_item(text: str) -> list[str]:
    """한글 토큰 추출 (2자 이상). AI 의미 추론 X — 단순 substring 후보."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for tok in _RE_KO_TOKEN.findall(text):
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _extract_articles_from_item(item_text: str) -> list[str]:
    """missing_critical[].item 에서 제N조 추출."""
    return _extract_articles(item_text)


def _score_entry_against_item(
    entry: dict[str, Any],
    item_norm: str,
    item_tokens: list[str],
    item_articles: list[str],
    role: str,
) -> tuple[float, list[str]]:
    """단일 entry × 단일 missing item 매칭 점수 + 매칭 근거 sample list.

    Score 구성 (자의 해석 X — 기계적 substring/정규식만):
      - title substring 매칭: token 1개당 +2
      - title 정확 substring (item_norm 자체가 title에 포함): +3
      - articles 교집합: 1개당 +3
      - solving_keywords substring (token): 1개당 +1
      - letters 묶음 substring (item_norm 안에 letter 등장): 1개당 +0.5

    role 가중치:
      - "judge"    : articles 점수 ×2
      - "lecturer" : title 점수 ×2
    """
    score = 0.0
    reasons: list[str] = []

    title = entry["title_text"]
    title_full = entry["section_title"]
    solving = entry["solving_keywords"] or ""

    # title 정확 substring (전체 item이 title에 substring으로 포함)
    if item_norm and item_norm in title:
        s = 3.0
        if role == "lecturer":
            s *= 2.0
        score += s
        reasons.append(f"title_exact_substring='{item_norm}'")

    # title token substring
    title_token_hits = 0
    for tok in item_tokens:
        if tok in title:
            title_token_hits += 1
    if title_token_hits:
        s = 2.0 * title_token_hits
        if role == "lecturer":
            s *= 2.0
        score += s
        reasons.append(f"title_token_hits={title_token_hits}")

    # articles 교집합
    if item_articles and entry["articles"]:
        common = [a for a in item_articles if a in entry["articles"]]
        if common:
            s = 3.0 * len(common)
            if role == "judge":
                s *= 2.0
            score += s
            reasons.append(f"articles_match={common}")

    # solving_keywords substring
    solving_hits = 0
    if solving:
        for tok in item_tokens:
            if tok in solving:
                solving_hits += 1
    if solving_hits:
        score += 1.0 * solving_hits
        reasons.append(f"solving_token_hits={solving_hits}")

    # letters 묶음이 item_norm 안에 등장 (예: item_norm="이행지체 무도가귀법 요건" + letters=["무","도",...])
    letter_hits = 0
    for letter in entry["letters"]:
        # 한 글자 letter는 오탐 위험 → 2자 이상 묶음만 가산
        if len(letter) < 2:
            continue
        if letter in item_norm:
            letter_hits += 1
    if letter_hits:
        score += 0.5 * letter_hits
        reasons.append(f"letter_hits={letter_hits}")

    return score, reasons


def match_missing_to_mnemonic(
    missing_critical: list[dict[str, Any]],
    subject: str,
    *,
    role: str = "judge",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """missing_critical 항목과 라이브러리 entry 매칭.

    Inputs:
      missing_critical: grader.py eval_notes.missing_critical 출력 형태
        [{"item": "이행지체 손해배상 요건 누락", "expected_score_impact": -3}, ...]
      subject: "민법" / "민소" / "부등법" / "형법" / "형소" 등
      role: "judge" | "lecturer" — 가중치 분기
      limit: 항목당 상위 N개 매칭 결과 반환

    Output:
      [
        {
          "requirement": "이행지체 손해배상 요건 누락",   # input item 원문
          "suggested_letters": ["무","도","가","귀","법"],
          "suggested_keywords": "이행기 도래 / 안전이행 / ...",
          "source_entry": "민법 §1-2",
          "lib_section": "1",
          "role": "judge",
          "reason_matched": ["title_token_hits=2", "articles_match=['제390조']"],
          "score": 8.0,
          "expected_score_impact": -3,
        },
        ...
      ]

    R-09:
      - abandoned entry는 처음부터 제외
      - source_entry/lib_section 누락 entry는 처음부터 제외
      - 매칭 score 0 인 후보는 결과 제외 (라이브러리 임의 끼워넣기 방지)
    """
    if role not in ("judge", "lecturer"):
        role = "judge"

    if not missing_critical:
        return []

    lib = load_mnemonic_library(subject)
    if lib["status"] != "loaded":
        # empty/missing → 빈 list (R-09: 매칭 결과 없으면 자체 생성 절대 X)
        return []

    active_entries = [
        e for e in lib["entries"]
        if not e["abandoned"]
        and e.get("source_entry")
        and e.get("lib_section")
    ]
    if not active_entries:
        return []

    results: list[dict[str, Any]] = []
    for missing in missing_critical:
        if not isinstance(missing, dict):
            continue
        item_raw = missing.get("item") or ""
        item_raw = item_raw.strip()
        if not item_raw:
            continue
        impact = missing.get("expected_score_impact")

        item_norm = _normalize_item(item_raw)
        item_tokens = _tokenize_item(item_norm)
        item_articles = _extract_articles_from_item(item_norm)

        scored: list[tuple[float, list[str], dict[str, Any]]] = []
        for entry in active_entries:
            s, reasons = _score_entry_against_item(
                entry, item_norm, item_tokens, item_articles, role
            )
            if s > 0.0:
                scored.append((s, reasons, entry))

        # 상위 limit
        scored.sort(key=lambda x: x[0], reverse=True)
        for s, reasons, entry in scored[:limit]:
            results.append({
                "requirement":         item_raw,
                "suggested_letters":   list(entry["letters"]),
                "suggested_keywords":  entry["solving_keywords"],
                "source_entry":        entry["source_entry"],
                "lib_section":         entry["lib_section"],
                "role":                role,
                "reason_matched":      reasons,
                "score":               round(s, 2),
                "expected_score_impact": impact,
            })

    return results


# ─── 직접 실행 시 간단 self-check (CI/디버그 용) ──────────────────────────
if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    print("== Loading libraries ==")
    for subj in ("민법", "민소", "부등법", "형법", "형소"):
        lib = load_mnemonic_library(subj)
        print(
            f"  {subj:6s} status={lib['status']:8s} "
            f"total={lib['total_count']:3d} "
            f"abandoned={lib['abandoned_count']:3d} "
            f"file={lib['file_path']}"
        )

    print("\n== Sample match (judge role) ==")
    sample_missing = [
        {"item": "제390조 이행지체 손해배상 요건 누락", "expected_score_impact": -3},
        {"item": "권리경정등기 요건 (제32조) 미작성", "expected_score_impact": -5},
    ]
    for subj, missings in (
        ("민법", [sample_missing[0]]),
        ("부등법", [sample_missing[1]]),
        ("형법", [sample_missing[0]]),
    ):
        print(f"\n  -- subject={subj} --")
        hits = match_missing_to_mnemonic(missings, subj, role="judge", limit=3)
        print(json.dumps(hits, ensure_ascii=False, indent=2))
