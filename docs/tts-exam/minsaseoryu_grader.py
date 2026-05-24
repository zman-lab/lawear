"""17896 민사서류 작성연습 트랙 — 청구취지 cloze diff 채점 (1라운드 MVP).

근거: docs/민사서류_작성연습_설계/design_mvp1.md v2 결정 5.

채점 알고리즘 (청구취지 diff):
  1) 빈칸별 정답 추출 (cases.parse_md_subqs.blanks dict — blank_N → 정답값)
  2) 사용자 답안 JSON 파싱
       answer_text = {"format": "cloze", "blanks": {"blank_1": "연대하여", ...}, "raw_text": "..."}
  3) 빈칸별 정답 비교 (normalize 공백/구두점 무시):
       - exact match 또는 normalize 만점 → 1점 (R-09 + 부장판사 권고 D)
       - 오답 → 0점
  4) bold span 가중치 1.5배 (cloze .md의 [bold] / [b] 토큰 추출)
  5) hints_used 감점 (minsaseoryu_modes.HINT_PENALTY 합산)
  6) 점수공식: Σ(빈칸 점수 × 가중치) / Σ(전체 가중치) × 100 × (1 - 힌트감점)

청구원인 채점은 2라운드 이월 — 1라운드는 placeholder 결과 (점수 0 + 비고 메시지).

사용:
    from minsaseoryu_grader import grade
    result = grade(case_meta, answer_text_json, hints_used, db)
    # result = {"total": 75.0, "max": 100, "pct": 75.0, "grade": "B-", ...}
"""
from __future__ import annotations

import json
import re
from typing import Any

try:
    from minsaseoryu_modes import (
        MODE_LABELS,
        BOLD_WEIGHT_DEFAULT,
        NORMAL_WEIGHT_DEFAULT,
        get_hint_penalty,
        get_mode,
        is_round1_mode,
    )
except ImportError:
    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from minsaseoryu_modes import (
        MODE_LABELS,
        BOLD_WEIGHT_DEFAULT,
        NORMAL_WEIGHT_DEFAULT,
        get_hint_penalty,
        get_mode,
        is_round1_mode,
    )


# ============================================================
# normalize — 공백/구두점 차이 흡수 (R-09 부장판사 권고 D)
# ============================================================

# 공백 정규화 정규식 — 연속 공백 → 단일 공백 → 공백 제거
_WHITESPACE_RE = re.compile(r"\s+")

# 공백 정규화 (1라운드, 부장판사 QA 2 PARTIAL 반영) — 구두점 normalize는 2라운드 OPEN_QUESTIONS 4번 동의어 사전과 함께
# 예: "2022.7.1." vs "2022. 7. 1." → 둘 다 "2022.7.1." 로 통일 후 비교
# 단, R-09: 정답 문자열에 의도된 구두점은 보존해야 하므로 normalize 는 비교 전용.
_PUNCT_NORMALIZE_RE = re.compile(r"[\s 　]+")  # 공백 + non-breaking + 전각 공백


def normalize_for_compare(text: str) -> str:
    """채점용 normalize — 공백 차이 흡수 (1라운드. 구두점 normalize는 2라운드 동의어 사전 작업과 함께).

    예:
        "연대하여"     vs "연대 하여"     → 둘 다 "연대하여"
        "2022. 7. 1." vs "2022.7.1."     → 둘 다 "2022.7.1."
        "위 피고들과 연대하여" vs "위피고들과  연대하여" → 동일

    Args:
        text: 비교 대상 문자열 (정답 또는 사용자 입력).

    Returns:
        normalize 결과 (공백 제거).
        None / 빈 문자열 → "".

    R-09 (자의 해석 금지): 단순 공백 통일 + trim 만. 의미 가공/동의어 매핑 X.
    """
    if not text:
        return ""
    # 모든 공백류 제거 (R-09 — 공백만 합리적 허용 범위)
    s = _PUNCT_NORMALIZE_RE.sub("", str(text))
    return s.strip()


def is_match(user_input: str, correct: str) -> tuple[bool, str]:
    """사용자 입력 vs 정답 비교.

    Returns:
        (match: bool, match_type: 'exact' | 'normalized' | 'miss')

    - 'exact': 완전 일치 (공백 포함)
    - 'normalized': normalize 후 일치 (공백/구두점 무시) — 1점 (만점)
    - 'miss': 불일치 — 0점
    """
    if user_input is None:
        user_input = ""
    if correct is None:
        correct = ""
    if user_input == correct:
        return True, "exact"
    if normalize_for_compare(user_input) == normalize_for_compare(correct):
        return True, "normalized"
    return False, "miss"


# ============================================================
# bold span 검출 — cloze .md의 [bold]/[b]/[em1] 토큰
# ============================================================

# bold 토큰 — design v2 결정 5에서 "bold span = 채점키워드"
# cloze .md 의 [blank] 안에 [bold]/[b]/[em1] 이 있으면 1.5배 가중치
# R-09: 토큰이 명시된 경우만. 자의 가중치 X.
_BOLD_TOKEN_RE = re.compile(
    r"\[(?:bold|b|em1)\]([\s\S]+?)\[/(?:bold|b|em1)\]"
)


def is_bold_blank(correct_value: str) -> bool:
    """정답 값에 [bold]/[b]/[em1] 토큰 포함 여부 (가중치 1.5배 조건).

    Args:
        correct_value: cases.parse_md_subqs.blanks[N] 의 정답 값.

    Returns:
        True 면 1.5배 가중치, False 면 1.0배.

    R-09 (자의 해석 금지): 토큰 명시 없으면 False (자의 가중치 부여 X).
    """
    if not correct_value:
        return False
    return bool(_BOLD_TOKEN_RE.search(str(correct_value)))


def strip_bold_tokens(text: str) -> str:
    """정답 값에서 [bold]/[b]/[em1] 토큰 제거 후 raw 값 반환.

    예: "[bold]연대하여[/bold]" → "연대하여"
        "연대하여" → "연대하여" (변경 없음)

    Args:
        text: 원본 텍스트 (정답 값).

    Returns:
        토큰 제거된 raw 값. None/빈 → "".
    """
    if not text:
        return ""
    return _BOLD_TOKEN_RE.sub(r"\1", str(text))


# ============================================================
# 사용자 답안 JSON 파싱
# ============================================================

def parse_user_answer(answer_text: str) -> dict[str, Any]:
    """사용자 답안 JSON 파싱 (legacy free 모드도 호환).

    예상 포맷:
        cloze: {"format": "cloze", "blanks": {"blank_1": "...", ...}, "raw_text": "..."}
        free:  {"format": "free", "raw_text": "..."}
        legacy: 단순 텍스트 (raw_text 로 wrap)

    Args:
        answer_text: attempts.answer_text DB 컬럼 값.

    Returns:
        ``{"format": str, "blanks": dict, "raw_text": str}``.
        파싱 실패 시 format='free' + blanks={} + raw_text=원본.
    """
    if not answer_text:
        return {"format": "free", "blanks": {}, "raw_text": ""}
    s = str(answer_text).strip()
    # JSON 파싱 시도
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return {
                    "format": str(obj.get("format", "free")),
                    "blanks": obj.get("blanks", {}) if isinstance(obj.get("blanks"), dict) else {},
                    "raw_text": str(obj.get("raw_text", "")),
                }
        except json.JSONDecodeError:
            pass
    # legacy 단순 텍스트 — free 모드로 wrap
    return {"format": "free", "blanks": {}, "raw_text": s}


# ============================================================
# 빈칸별 정답 비교 (메인 채점 로직)
# ============================================================

def grade_blanks(
    correct_blanks: dict[str, str],
    user_blanks: dict[str, str],
    bold_weight: float = BOLD_WEIGHT_DEFAULT,
    normal_weight: float = NORMAL_WEIGHT_DEFAULT,
) -> dict[str, Any]:
    """빈칸별 정답 비교 → 점수 산출 (design v2 결정 5).

    점수공식:
        score = Σ(빈칸별 점수 × 가중치) / Σ(전체 가중치) × 100

    Args:
        correct_blanks: ``{"blank_1": "정답값", ...}`` — cases.parse_md_subqs 결과.
            정답 값에 [bold]/[b]/[em1] 토큰 있으면 1.5배 가중치.
        user_blanks: ``{"blank_1": "사용자 입력", ...}`` — answer_text JSON.
        bold_weight: bold span 가중치 (default 1.5).
        normal_weight: 일반 빈칸 가중치 (default 1.0).

    Returns:
        ``{
            "score_pct": 75.0,        # 0~100
            "weighted_score": 7.5,    # 가중치 적용 점수
            "weighted_max": 10.0,     # 가중치 합
            "blank_count": 4,
            "correct_count": 3,
            "blank_results": [
                {"key": "blank_1", "correct": "연대하여", "user": "연대하여",
                 "match": True, "match_type": "exact", "weight": 1.5, "score": 1.5},
                ...
            ],
        }``

    R-09 (자의 해석 금지): 정답 본문은 cases.py parse_md_subqs 가 추출한 그대로. 채점은 normalize 만점/오답.
    """
    blank_results: list[dict[str, Any]] = []
    weighted_score = 0.0
    weighted_max = 0.0
    correct_count = 0

    if not isinstance(correct_blanks, dict) or not correct_blanks:
        return {
            "score_pct": 0.0,
            "weighted_score": 0.0,
            "weighted_max": 0.0,
            "blank_count": 0,
            "correct_count": 0,
            "blank_results": [],
        }

    # 정답 순서대로 진행 (blank_1, blank_2, ...)
    sorted_keys = sorted(
        correct_blanks.keys(),
        key=lambda k: int(k.split("_")[-1]) if k.split("_")[-1].isdigit() else 999,
    )

    for key in sorted_keys:
        correct_raw = correct_blanks.get(key, "")
        # bold 가중치 판정 (raw 에 [bold] 토큰 있으면 1.5배)
        weight = bold_weight if is_bold_blank(correct_raw) else normal_weight
        # bold 토큰 제거한 정답 값 (비교 대상)
        correct_value = strip_bold_tokens(correct_raw)

        user_value = user_blanks.get(key, "") if isinstance(user_blanks, dict) else ""
        match, match_type = is_match(str(user_value), correct_value)

        # 점수 계산: 매칭(exact 또는 normalized) = 1점, 오답 = 0점
        # (design v2 결정 5 + 부장판사 권고 D — normalize 만점)
        per_blank_score = 1.0 if match else 0.0
        weighted_score += per_blank_score * weight
        weighted_max += weight
        if match:
            correct_count += 1

        blank_results.append({
            "key": key,
            "correct": correct_value,
            "user": str(user_value),
            "match": match,
            "match_type": match_type,
            "weight": weight,
            "score": per_blank_score * weight,
            "is_bold": is_bold_blank(correct_raw),
        })

    score_pct = (weighted_score / weighted_max * 100.0) if weighted_max > 0 else 0.0

    return {
        "score_pct": round(score_pct, 2),
        "weighted_score": round(weighted_score, 2),
        "weighted_max": round(weighted_max, 2),
        "blank_count": len(blank_results),
        "correct_count": correct_count,
        "blank_results": blank_results,
    }


# ============================================================
# 등급 매핑 (budeunglaw 패턴 — 합격선 A- 73점)
# ============================================================

def _pct_to_grade(pct: float) -> str:
    """백분율 → 등급 (lawear-2e42 합격선 73 상향 반영)."""
    if pct >= 95: return "A"
    if pct >= 90: return "A-"
    if pct >= 85: return "B+"
    if pct >= 80: return "B"
    if pct >= 73: return "B-"  # 합격선
    if pct >= 65: return "C+"
    if pct >= 60: return "C"
    if pct >= 50: return "D"
    return "F"


# ============================================================
# 메인 grade 함수 (attempts.py 분기에서 호출)
# ============================================================

def grade(
    case_meta: dict[str, Any],
    answer_text: str,
    hints_used: dict[str, Any] | list | None = None,
    db: Any = None,
) -> dict[str, Any]:
    """청구취지 cloze 채점 (메인 진입점).

    Args:
        case_meta: cases.get_case(conn, case_id) 결과 — subqs 포함.
            cloze .md 1개 = 1 case, 문제 N개 = subqs N개.
            subqs[i].blanks = {"blank_1": "정답값", ...} (cases.py parse_md_subqs 확장).
        answer_text: 사용자 답안 JSON 문자열 (또는 legacy 단순 텍스트).
            카드별 dict 모드면 attempts.create_attempt 가 join 한 형태 (라벨 prefix + 본문).
        hints_used: ``{subq_key: [1, 2, 2.5, ...]}`` 카드별 노출 단계.
            None 또는 빈 dict 면 감점 0.
        db: (선택) DB conn — 추가 컨텍스트 로드 시.

    Returns:
        ``{
          "total": 75.0,           # 100점 환산
          "max": 100.0,
          "pct": 75.0,
          "grade": "B-",
          "criteria": [             # UI 호환용 (attempt_criteria 와 별개)
            {"key": "cloze_match", "score": 7.5, "max": 10.0, "comment": "3/4 빈칸 정답"},
            {"key": "hint_penalty", "score": -0.5, "max": 0, "comment": "힌트 2단계 사용"},
          ],
          "eval_notes": {
            "blank_summary": {...},  # blank_results 통합
            "hint_penalty": 0.10,
            "format": "cloze",
          },
          "diff_segments": [...],   # 빈칸별 match/miss (UI 형광펜)
          "subqs_results": [...],   # 문제별 (다중 subq 케이스)
          "weights_version": "v8_civil_doc_cloze",
        }``

    R-09 (자의 해석 금지):
        - 정답 값은 cases.py parse_md_subqs 의 blanks dict 만 사용. AI 추정 X.
        - 청구원인은 placeholder (점수 0 + 비고 메시지).
        - hints_used 감점은 minsaseoryu_modes.HINT_PENALTY 매핑 그대로.
    """
    # 1) 사용자 답안 파싱
    user_data = parse_user_answer(answer_text)
    user_format = user_data.get("format", "free")

    # 2) case 의 subqs 추출 (cases.py parse_md_subqs 확장 결과)
    subqs = case_meta.get("subqs") if isinstance(case_meta, dict) else None
    if not isinstance(subqs, list):
        subqs = []

    # 3) 빈칸별 정답 비교 (subq N개 통합)
    subqs_results: list[dict[str, Any]] = []
    total_weighted = 0.0
    total_max = 0.0
    total_blanks = 0
    total_correct = 0
    all_diff_segments: list[dict[str, Any]] = []

    # 각 subq 마다 채점 (또는 단일 모드면 1회만)
    for idx, subq in enumerate(subqs):
        if not isinstance(subq, dict):
            continue
        subq_key = subq.get("key", f"문제 {idx+1}")
        correct_blanks = subq.get("blanks") or {}
        if not isinstance(correct_blanks, dict):
            continue

        # 사용자 답안 — subq별 dict 또는 통합 dict
        # answer_text JSON 의 blanks 는 통합 dict 또는 {"문제 1": {...}, ...} 중첩 dict
        user_blanks_for_subq: dict[str, Any] = {}
        ub = user_data.get("blanks") or {}
        if isinstance(ub, dict):
            # 1) 중첩 dict: {"문제 1": {"blank_1": "..."}}
            nested = ub.get(subq_key)
            if isinstance(nested, dict):
                user_blanks_for_subq = nested
            else:
                # 2) 단일 평면 dict (subq 1개 케이스 — 통합)
                user_blanks_for_subq = ub if all(
                    k.startswith("blank_") for k in ub.keys()
                ) else {}

        blank_grade = grade_blanks(correct_blanks, user_blanks_for_subq)
        subqs_results.append({
            "key": subq_key,
            "score_max": subq.get("score_max"),
            **blank_grade,
        })
        total_weighted += blank_grade["weighted_score"]
        total_max += blank_grade["weighted_max"]
        total_blanks += blank_grade["blank_count"]
        total_correct += blank_grade["correct_count"]
        # diff segments (UI 형광펜용)
        for br in blank_grade["blank_results"]:
            all_diff_segments.append({
                "text": br["correct"],
                "type": "match" if br["match"] else "miss",
                "blank_key": br["key"],
                "subq_key": subq_key,
            })

    # 4) hints_used 감점 계산 (subq별 step list 합산)
    hint_penalty_total = 0.0
    if isinstance(hints_used, dict):
        # {subq_key: [1, 2, ...]} 형식 — 각 subq 별 감점 평균
        if hints_used:
            penalty_sum = 0.0
            for v in hints_used.values():
                if isinstance(v, list):
                    penalty_sum += get_hint_penalty(v)
            hint_penalty_total = penalty_sum / max(1, len(hints_used))
    elif isinstance(hints_used, list):
        # 통합 list — 단일 step 합산
        hint_penalty_total = get_hint_penalty(hints_used)

    # 5) 점수 산출 + 힌트 감점 적용
    pre_penalty_pct = (total_weighted / total_max * 100.0) if total_max > 0 else 0.0
    final_pct = pre_penalty_pct * (1.0 - hint_penalty_total)
    final_pct = max(0.0, min(100.0, final_pct))

    # 6) 청구원인 placeholder — 1라운드는 점수 0
    # 데이터에 청구원인 영역 표시가 있으면 placeholder 비고 추가
    # (1라운드 MVP: 청구원인은 카드 placeholder UI만, 채점은 청구취지 only)
    cause_placeholder_note: str | None = None
    if case_meta.get("has_cause_section"):
        cause_placeholder_note = (
            "청구원인 작성은 2라운드 예고 — idea4 4단계 중 4단계만 1라운드, 1~3단계는 다음 라운드"
        )

    # 7) criteria UI 호환 (budeunglaw 패턴 — attempt_criteria 와 별개 응답 키)
    criteria: list[dict[str, Any]] = []
    criteria.append({
        "key": "cloze_match",
        "score": round(total_weighted, 2),
        "max": round(total_max, 2),
        "weight": round(total_max, 2),
        "comment": f"{total_correct}/{total_blanks} 빈칸 정답 (normalize 만점 포함)",
    })
    if hint_penalty_total > 0:
        criteria.append({
            "key": "hint_penalty",
            "score": -round(hint_penalty_total * 100, 2),
            "max": 0,
            "weight": 1,
            "comment": f"힌트 사용 {hint_penalty_total:.0%} 감점",
        })

    result: dict[str, Any] = {
        "total": round(final_pct, 2),
        "max": 100.0,
        "pct": round(final_pct, 2),
        "grade": _pct_to_grade(final_pct),
        "criteria": criteria,
        "eval_notes": {
            "blank_summary": {
                "total_blanks": total_blanks,
                "correct_count": total_correct,
                "weighted_score": round(total_weighted, 2),
                "weighted_max": round(total_max, 2),
                "pre_penalty_pct": round(pre_penalty_pct, 2),
                "hint_penalty_pct": round(hint_penalty_total * 100, 2),
            },
            "format": user_format,
            "subq_count": len(subqs_results),
            "weights_version": "v8_civil_doc_cloze",
        },
        "diff_segments": all_diff_segments,
        "subqs_results": subqs_results,
        "weights_version": "v8_civil_doc_cloze",
    }
    if cause_placeholder_note:
        result["eval_notes"]["cause_placeholder_note"] = cause_placeholder_note
    return result


# ============================================================
# CLI 자가 테스트
# ============================================================

if __name__ == "__main__":
    print("=== minsaseoryu_grader 자가 테스트 ===\n")
    # case meta — 빈칸 2개 (1개 bold, 1개 normal)
    case_meta = {
        "id": "2026_civildoc_test_01",
        "subject_type": "civil_doc",
        "subqs": [
            {
                "key": "문제 1",
                "score_max": 10,
                "blanks": {
                    "blank_1": "[bold]연대하여[/bold]",  # bold = 1.5x
                    "blank_2": "다 갚는 날까지",
                },
            },
        ],
    }
    # 정답 시나리오
    for label, user_blanks in [
        ("정상 정답", {"blank_1": "연대하여", "blank_2": "다 갚는 날까지"}),
        ("normalize", {"blank_1": "연대 하여", "blank_2": "다 갚는 날 까지"}),
        ("절반 오답", {"blank_1": "공동하여", "blank_2": "다 갚는 날까지"}),
        ("전부 오답", {"blank_1": "X", "blank_2": "X"}),
    ]:
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        r = grade(case_meta, answer_text, hints_used=None)
        print(f"{label:10s} → pct={r['pct']:6.2f} | grade={r['grade']} | criteria[0]={r['criteria'][0]['comment']}")
