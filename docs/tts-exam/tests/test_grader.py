#!/usr/bin/env python3
"""Grader 단위 테스트 (mock 모드 — API 키 없이 통과).

dev-impl-plan #51 Step 6 6-3 / TC-02, TC-04, TC-09 매핑.

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_grader.py -v
    # 또는 단독:
    python3 tests/test_grader.py

pytest 없어도 main() 으로 standalone assertion 실행 가능.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# tests/ → 부모 (docs/tts-exam) 를 sys.path 에 추가
_THIS_DIR = Path(__file__).parent.resolve()
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import grader  # noqa: E402


# ─── 픽스처 ──────────────────────────────────────────────────────────


def _sample_case_meta() -> dict:
    """미케01_01 (재건축조합 비법인사단) 더미 case_meta."""
    return {
        "id": "2026_minbeop_immun_mike01_01",
        "subject": "minbeop",
        "subject_kor": "민법",
        "category": "입문",
        "file": "미케01",
        "case_no": "01",
        "title": "비법인사단 · 대표권 제한",
        "points": 17,
        "md_body": (
            "## 원본 (17점)\n\n### 사실관계\nA조합은 재건축조합...\n\n### 문제\n법원의 결론...\n\n"
            "### 답안\n1. A조합의 법적 성격\n재건축조합은 [blue]비법인사단[/blue]에 해당한다.\n\n"
            "## Lv.1 빠른복습\n### 목차\n1. 법적 성격\n2. 계약 효력\n3. 사안의 경우\n\n"
            "## Lv.4 암기노트\n1. [blue]비법인사단[/blue]이란, "
            "[blank2]조[/blank2][blue]직[/blue]을 갖출것 ..."
        ),
        "lv1": "## Lv.1 빠른복습\n...",
        "lv4": "## Lv.4 암기노트\n...",
    }


def _sample_user_answer() -> str:
    return (
        "재건축조합은 단체로서의 조직과 다수결 원칙을 갖춘 비법인사단에 해당한다. "
        "비법인사단은 정관에 따라 권리능력을 가지며, 총회 결의를 거치지 않은 총유물 처분은 무효이지만, "
        "설계용역계약은 단순 채무부담행위이므로 총유물 처분이 아니다. "
        "따라서 을회사가 정관상 대표권 제한을 알았거나 알 수 있었음을 A조합측이 증명하지 못하는 한 "
        "계약은 유효하며 청구는 인용된다."
    )


# ─── 테스트 ──────────────────────────────────────────────────────────


def test_mock_mode_basic() -> None:
    """TC: mock 모드에서 grade() 호출 → 형식 검증."""
    case = _sample_case_meta()
    answer = _sample_user_answer()

    result = grader.grade(case, answer, force_mock=True)

    assert isinstance(result, dict), "result must be dict"
    assert result["is_mock"] is True, "force_mock=True → is_mock"
    # model 라벨
    assert "mock" in str(result["model"]).lower(), f"model label should contain 'mock', got {result['model']}"


def test_mock_criteria_eight_keys() -> None:
    """TC: 9기준 모두 포함 + 각 항목 schema (Step 21 v5 — case_apply 신설).

    NOTE: 함수명은 'eight_keys' 유지 (이력 호환) — 실 검증은 9기준.
    """
    result = grader.grade(_sample_case_meta(), _sample_user_answer(), force_mock=True)

    criteria = result["criteria"]
    assert isinstance(criteria, list), "criteria must be list"
    assert len(criteria) == 9, f"criteria must have 9 entries (v5), got {len(criteria)}"

    keys = {c["key"] for c in criteria}
    expected_keys = set(grader.CRITERION_KEYS)
    assert "articles" in keys, "articles key required (Step 20 v4)"
    assert "case_apply" in keys, "case_apply key required (Step 21 v5)"
    assert keys == expected_keys, f"criteria keys mismatch: {keys} != {expected_keys}"

    # 각 항목 schema: key/score/max/weight/comment
    for c in criteria:
        assert "key" in c
        assert "score" in c
        assert "max" in c
        assert "weight" in c
        assert "comment" in c
        assert isinstance(c["weight"], int), f"weight must be int, got {type(c['weight'])}"
        assert c["weight"] >= 0


def test_mock_total_score_pct_grade() -> None:
    """TC: total_score / score_pct / grade 형식 + 계산 일관성."""
    result = grader.grade(_sample_case_meta(), _sample_user_answer(), force_mock=True)

    # 점수 필드 타입/범위
    assert isinstance(result["score_total"], (int, float)), "score_total must be numeric"
    assert isinstance(result["score_max"], (int, float)), "score_max must be numeric"
    assert isinstance(result["score_pct"], (int, float)), "score_pct must be numeric"
    assert 0.0 <= result["score_pct"] <= 100.0, f"pct out of range: {result['score_pct']}"

    # grade in A/B/C/F
    assert result["grade"] in ("A", "B", "C", "F"), f"unknown grade: {result['grade']}"


def test_mock_eval_notes_three_blocks() -> None:
    """TC: eval_notes 에 strength/caution/missing 3블록."""
    result = grader.grade(_sample_case_meta(), _sample_user_answer(), force_mock=True)
    notes = result["eval_notes"]
    assert isinstance(notes, dict)
    for k in ("strength", "caution", "missing"):
        assert k in notes, f"eval_notes missing {k}"
        assert isinstance(notes[k], str), f"eval_notes.{k} must be string"


def test_mock_diff_segments() -> None:
    """TC: diff_segments 는 list of {type, text}."""
    user_answer = _sample_user_answer()
    result = grader.grade(_sample_case_meta(), user_answer, force_mock=True)

    diff = result["diff_segments"]
    assert isinstance(diff, list)
    # mock 은 항상 1+ segment (head match)
    assert len(diff) >= 1, "mock diff_segments must have at least 1 entry"
    for seg in diff:
        assert "type" in seg
        assert seg["type"] in ("match", "miss", "partial"), f"invalid type: {seg['type']}"
        assert "text" in seg
        assert isinstance(seg["text"], str)

    # 첫 segment 는 user_answer 의 prefix (자의 텍스트 X)
    head_text = diff[0]["text"]
    assert head_text in user_answer or head_text == user_answer.strip()[:120], \
        "first diff segment must be substring of user_answer"


def test_mock_weights_applied_default() -> None:
    """TC: weights=None → DEFAULT_WEIGHTS 적용 + 합=100."""
    result = grader.grade(_sample_case_meta(), _sample_user_answer(), force_mock=True)
    w = result["weights_applied"]
    assert w == grader.DEFAULT_WEIGHTS, f"weights_applied mismatch: {w}"
    assert sum(w.values()) == 100, f"weights sum must be 100, got {sum(w.values())}"


def test_mock_weights_custom() -> None:
    """TC: 커스텀 weights 전달 → 그대로 반영 + criteria.weight 갱신 (9키, v5)."""
    custom = {
        "mnem": 20,
        "color": 15,
        "under": 10,
        "outline": 10,
        "sem": 10,
        "rich": 10,
        "miss": 10,
        "articles": 10,  # Step 20 v4 신설
        "case_apply": 5,  # Step 21 v5 신설
    }
    assert sum(custom.values()) == 100
    result = grader.grade(_sample_case_meta(), _sample_user_answer(), weights=custom, force_mock=True)

    assert result["weights_applied"] == custom
    # 각 criterion 의 weight 도 일치
    by_key = {c["key"]: c["weight"] for c in result["criteria"]}
    for k, v in custom.items():
        assert by_key[k] == v, f"criterion {k} weight mismatch: {by_key[k]} != {v}"


def test_weights_invalid_sum_raises() -> None:
    """TC-04: 가중치 합 != 100 → ValueError (handler 에서 409 매핑). v5 9키."""
    bad_weights = {
        "mnem": 50,
        "color": 20,
        "under": 10,
        "outline": 15,
        "sem": 15,
        "rich": 10,
        "miss": 0,
        "articles": 10,
        "case_apply": 5,  # Step 21 v5
    }  # 합=135
    assert sum(bad_weights.values()) == 135
    try:
        grader.grade(_sample_case_meta(), _sample_user_answer(), weights=bad_weights, force_mock=True)
    except ValueError as e:
        assert "100" in str(e), f"error must mention 100, got {e}"
        return
    raise AssertionError("expected ValueError for weights sum != 100")


def test_weights_missing_key_raises() -> None:
    """TC: 8키 중 하나라도 누락 → ValueError (Step 20 v4 — articles 누락 검증)."""
    # articles 누락 (7키만) — v3 호환 데이터가 와도 거부되어야 함
    bad = {"mnem": 20, "color": 15, "under": 10, "outline": 15, "sem": 15, "rich": 10, "miss": 15}
    assert "articles" not in bad
    try:
        grader.grade(_sample_case_meta(), _sample_user_answer(), weights=bad, force_mock=True)
    except ValueError as e:
        assert "articles" in str(e), f"error must mention missing 'articles', got {e}"
        return
    raise AssertionError("expected ValueError for missing 'articles' key")


def test_compute_score_basic() -> None:
    """TC: _compute_score 단독 — 만점/0점 경계 (Step 21 v5 9기준)."""
    # 만점 (모든 score=max, miss=0)
    full = [
        {"key": "mnem", "score": 4, "max": 4},
        {"key": "color", "score": 12, "max": 12},
        {"key": "under", "score": 2, "max": 2},
        {"key": "outline", "score": 3, "max": 3},
        {"key": "sem", "score": 10, "max": 10},
        {"key": "rich", "score": 2, "max": 2},
        {"key": "miss", "score": 0, "max": 0},
        {"key": "articles", "score": 5, "max": 5},  # Step 20 v4
        {"key": "case_apply", "score": 2, "max": 2},  # Step 21 v5
    ]
    total, max_s, pct, grade_letter = grader._compute_score(full, grader.DEFAULT_WEIGHTS)
    # weight_total - miss_weight = 100 - 11 = 89 (v5 동일)
    assert abs(max_s - 89.0) < 0.01, f"max_s={max_s}"
    # 8개 비-miss 항목 모두 만점 → weighted_sum = 89
    assert abs(total - 89.0) < 0.01, f"total={total}"
    assert pct == 100.0, f"pct={pct}"
    assert grade_letter == "A"

    # 빵점 (모든 score=0, miss=-5)
    zero = [
        {"key": "mnem", "score": 0, "max": 4},
        {"key": "color", "score": 0, "max": 12},
        {"key": "under", "score": 0, "max": 2},
        {"key": "outline", "score": 0, "max": 3},
        {"key": "sem", "score": 0, "max": 10},
        {"key": "rich", "score": 0, "max": 2},
        {"key": "miss", "score": -5, "max": 0},
        {"key": "articles", "score": 0, "max": 5},
        {"key": "case_apply", "score": 0, "max": 2},  # Step 21 v5
    ]
    total, max_s, pct, grade_letter = grader._compute_score(zero, grader.DEFAULT_WEIGHTS)
    assert total <= 0, f"total={total} (miss 감점)"
    assert pct == 0.0, f"pct={pct} (clamped to 0)"
    assert grade_letter == "F"


def test_parse_response_raw_json() -> None:
    """TC: _parse_response — raw JSON 정상 파싱 (Step 21 v5 9기준)."""
    raw = json.dumps({
        "criteria": [
            {"key": "mnem", "score": 2, "max": 4, "comment": "OK"},
            {"key": "color", "score": 8, "max": 12, "comment": "OK"},
            {"key": "under", "score": 1, "max": 2, "comment": "OK"},
            {"key": "outline", "score": 2, "max": 3, "comment": "OK"},
            {"key": "sem", "score": 7, "max": 10, "comment": "OK"},
            {"key": "rich", "score": 1, "max": 2, "comment": "OK"},
            {"key": "miss", "score": -1, "max": 0, "comment": "OK"},
            {"key": "articles", "score": 4, "max": 5, "comment": "OK"},  # Step 20 v4
            {"key": "case_apply", "score": 1, "max": 2, "comment": "OK"},  # Step 21 v5
        ],
        "eval_notes": {"strength": "A", "caution": "B", "missing": "C"},
        "diff_segments": [{"type": "match", "text": "x"}],
    })
    parsed = grader._parse_response(raw)
    assert len(parsed["criteria"]) == 9
    assert parsed["eval_notes"]["strength"] == "A"


def test_parse_response_codefence() -> None:
    """TC: _parse_response — code fence 안의 JSON 추출 (9기준 v5)."""
    payload = {
        "criteria": [
            {"key": k, "score": 1, "max": 1, "comment": ""}
            for k in grader.CRITERION_KEYS
        ],
        "eval_notes": {"strength": "", "caution": "", "missing": ""},
    }
    raw = "Here is your evaluation:\n```json\n" + json.dumps(payload) + "\n```\nThanks."
    parsed = grader._parse_response(raw)
    assert len(parsed["criteria"]) == 9


def test_parse_response_missing_keys_raises() -> None:
    """TC: criteria 에 키 누락 → GraderParseError (Step 20 v4 — articles 누락 검증)."""
    # mnem 빠짐 (articles 포함 → mnem 만 누락으로 검증)
    bad = {
        "criteria": [
            {"key": "color", "score": 1, "max": 1},
            {"key": "under", "score": 1, "max": 1},
            {"key": "outline", "score": 1, "max": 1},
            {"key": "sem", "score": 1, "max": 1},
            {"key": "rich", "score": 1, "max": 1},
            {"key": "miss", "score": 0, "max": 0},
            {"key": "articles", "score": 1, "max": 1},
        ],
        "eval_notes": {"strength": "", "caution": "", "missing": ""},
    }
    try:
        grader._parse_response(json.dumps(bad))
    except grader.GraderParseError as e:
        assert "missing" in str(e).lower() and "mnem" in str(e)
        return
    raise AssertionError("expected GraderParseError for missing 'mnem'")


def test_parse_response_missing_articles_raises() -> None:
    """TC (Step 20 v4): articles 누락 → GraderParseError (v3 호환 데이터 거부)."""
    # v3 7기준 응답 (articles 누락) → 거부
    bad = {
        "criteria": [
            {"key": "mnem", "score": 2, "max": 4},
            {"key": "color", "score": 8, "max": 12},
            {"key": "under", "score": 1, "max": 2},
            {"key": "outline", "score": 2, "max": 3},
            {"key": "sem", "score": 7, "max": 10},
            {"key": "rich", "score": 1, "max": 2},
            {"key": "miss", "score": -1, "max": 0},
        ],
        "eval_notes": {"strength": "", "caution": "", "missing": ""},
    }
    try:
        grader._parse_response(json.dumps(bad))
    except grader.GraderParseError as e:
        assert "articles" in str(e), f"error must mention missing 'articles', got {e}"
        return
    raise AssertionError("expected GraderParseError for missing 'articles' (Step 20 v4)")


def test_parse_response_invalid_json_raises() -> None:
    """TC: raw 텍스트가 JSON 아님 → GraderParseError."""
    try:
        grader._parse_response("This is not JSON at all.")
    except grader.GraderParseError as e:
        assert "json" in str(e).lower() or "extract" in str(e).lower()
        return
    raise AssertionError("expected GraderParseError for invalid JSON")


def test_build_prompt_includes_md_body_and_weights() -> None:
    """TC: _build_prompt 결과에 md_body + weights 포함."""
    case = _sample_case_meta()
    answer = "user answer 12345"
    weights = grader.DEFAULT_WEIGHTS
    system, user = grader._build_prompt(case, answer, weights)

    assert "법무사" in system, "system must mention 법무사"
    assert "JSON" in system, "system must specify JSON format"
    assert "자의적 해석 금지" in system, "system must enforce R-09"
    assert answer in user, "user message must include answer"
    assert case["id"] in user, "user message must include case_id"
    # md_body 의 강조 태그 보존 (substring 매칭)
    assert "[blue]비법인사단[/blue]" in user, "user message must preserve emphasis tags"
    # weights JSON 포함 (Step 20 v4 — articles 신설, 디폴트 mnem=16)
    assert "mnem" in user and "16" in user, "user message must include weights (mnem=16, v4)"
    assert "articles" in user, "user message must include articles (Step 20 v4)"


def test_grade_with_empty_md_body_falls_back() -> None:
    """TC: md_body 없어도 origin/lv1/lv4 조합으로 동작."""
    case = {
        "id": "test_no_md_body",
        "subject_kor": "민법",
        "category": "테스트",
        "file": "test01",
        "case_no": "01",
        "title": "테스트",
        "points": 10,
        "md_body": None,
        "origin": "## 원본\n사실관계 dummy",
        "lv1": "## Lv.1\n목차 dummy",
        "lv4": "## Lv.4\n암기노트 dummy",
    }
    result = grader.grade(case, "test answer", force_mock=True)
    assert result["is_mock"] is True
    assert result["score_total"] is not None


def test_mock_no_api_key_auto() -> None:
    """TC-09: ANTHROPIC_API_KEY 미설정 → 자동 mock (예외 X)."""
    # env 백업
    backup = os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("LAWEAR_GRADER_MOCK", None)  # 명시 mock도 끔
    try:
        # force_mock=None + model 명시 → 자동 mock 으로 fallback
        result = grader.grade(_sample_case_meta(), _sample_user_answer(), model="claude-opus-4-7")
        assert result["is_mock"] is True, "API key 없으면 자동 mock 이어야 함"
        assert "mock" in str(result["model"]).lower()
    finally:
        if backup is not None:
            os.environ["ANTHROPIC_API_KEY"] = backup


def test_validate_weights_directly() -> None:
    """TC: validate_weights 단독 호출."""
    # 정상
    grader.validate_weights(grader.DEFAULT_WEIGHTS)
    # sum != 100
    bad = dict(grader.DEFAULT_WEIGHTS)
    bad["mnem"] = 100
    try:
        grader.validate_weights(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for sum != 100")


# ─── standalone 실행 (pytest 없이도 통과) ──────────────────────────────

TESTS = [
    test_mock_mode_basic,
    test_mock_criteria_eight_keys,
    test_mock_total_score_pct_grade,
    test_mock_eval_notes_three_blocks,
    test_mock_diff_segments,
    test_mock_weights_applied_default,
    test_mock_weights_custom,
    test_weights_invalid_sum_raises,
    test_weights_missing_key_raises,
    test_compute_score_basic,
    test_parse_response_raw_json,
    test_parse_response_codefence,
    test_parse_response_missing_keys_raises,
    test_parse_response_missing_articles_raises,  # Step 20 v4
    test_parse_response_invalid_json_raises,
    test_build_prompt_includes_md_body_and_weights,
    test_grade_with_empty_md_body_falls_back,
    test_mock_no_api_key_auto,
    test_validate_weights_directly,
]


def main() -> int:
    """standalone — pytest 없이 통과 시 0, 실패 시 1."""
    passed = 0
    failed = []
    for fn in TESTS:
        name = fn.__name__
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}", file=sys.stderr)
            failed.append((name, str(e)))
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {name}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append((name, f"{type(e).__name__}: {e}"))

    total = len(TESTS)
    print(f"\n[test_grader] {passed}/{total} passed")
    if failed:
        print("[test_grader] FAILURES:", file=sys.stderr)
        for n, err in failed:
            print(f"  - {n}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
