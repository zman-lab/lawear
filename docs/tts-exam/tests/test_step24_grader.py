#!/usr/bin/env python3
"""Grader 다중 설문 D안 카드별 채점 단위 테스트 (Step 24-4).

dev-design archive §3-7 / dev-impl-plan Phase 1 Step 24-4.

신규 함수:
- ``_build_prompt_subq(case, subq, user_answer, hints_used_steps)``
- ``grade_attempt_subq(case, attempt, weights, model)``
- ``_normalize_subq_grades(grade_dict)``
- ``grade_attempt(case, attempt, weights, model)`` — legacy + 다중 라우팅

실 anthropic API 호출 X — patch + mock 으로 격리.

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step24_grader.py -v
    # 또는 standalone:
    python3 tests/test_step24_grader.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

# tests/ → 부모 (docs/tts-exam) 를 sys.path 에 추가
_THIS_DIR = Path(__file__).parent.resolve()
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import grader  # noqa: E402


# ─── 픽스처 ──────────────────────────────────────────────────────────


def _sample_case_multi() -> dict:
    """다중 설문 (2 카드) 더미 케이스 — 민법 모고01_01 패턴 A 유사."""
    return {
        "id": "2026_minbeop_yebi_mogo01_01",
        "subject": "minbeop",
        "subject_kor": "민법",
        "category": "예비",
        "file": "모고01",
        "case_no": "01",
        "title": "다중설문 테스트 (2 카드)",
        "points": 35,
        "md_body": "## 원본 (35점)\n### 공통된 사실관계\nA 은행은 1997년...\n",
        "common_facts": "A 은행은 1997년 10월 20일 B 주식회사에 대출...",
        "subqs": [
            {
                "key": "설문 1",
                "label": "설문 1 (20점)",
                "score_max": 20,
                "body": "C의 주장은 타당한가? 시효소멸 여부를 논하라.",
                "answer": (
                    "1. 결론: C의 주장은 타당하다.\n"
                    "2. 근거: [red]제166조 제1항[/red] 및 [red]제178조 제2항[/red]에 따라..."
                ),
            },
            {
                "key": "설문 2",
                "label": "설문 2 (15점)",
                "score_max": 15,
                "body": "E의 C에 대한 청구는 인용되는가?",
                "answer": (
                    "1. 결론: 청구는 일부 인용된다.\n"
                    "2. 근거: [blue]채권자대위[/blue] 요건 충족..."
                ),
            },
        ],
    }


def _sample_case_single() -> dict:
    """단일 설문 (가/나 또는 단일) 더미 케이스."""
    return {
        "id": "2026_minbeop_immun_mike01_01",
        "subject": "minbeop",
        "subject_kor": "민법",
        "category": "입문",
        "file": "미케01",
        "case_no": "01",
        "title": "비법인사단",
        "points": 17,
        "md_body": (
            "## 원본 (17점)\n### 사실관계\nA조합...\n### 답안\n1. 결론..."
        ),
    }


def _sample_case_with_ga_na() -> dict:
    """가/나 하위 케이스 더미 — 민법 모고02_01 패턴 C."""
    return {
        "id": "2026_minbeop_yebi_mogo02_01",
        "subject": "minbeop",
        "subject_kor": "민법",
        "category": "예비",
        "file": "모고02",
        "case_no": "01",
        "title": "가/나 독립 카드",
        "points": 25,
        "common_facts": "갑은 을에게...",
        "subqs": [
            {
                "key": "설문 1 가",
                "label": "설문 1 가 (12점)",
                "score_max": 12,
                "body": "권리능력자는 누구인가?",
                "answer": "자연인과 법인이다.",
            },
            {
                "key": "설문 1 나",
                "label": "설문 1 나 (13점)",
                "score_max": 13,
                "body": "을이 사망한 경우 효과는?",
                "answer": "상속이 개시된다.",
            },
        ],
    }


def _sample_attempt_multi(
    *,
    answers: dict | None = None,
    hints_used: dict | None = None,
    subq_elapsed: dict | None = None,
) -> dict:
    """다중 카드 attempt 더미."""
    return {
        "answer_subq": answers or {
            "설문 1": "C의 주장은 타당하다. 제166조에 따라 시효는 진행된다.",
            "설문 2": "E의 청구는 인용된다. 채권자대위 요건이 충족된다.",
        },
        "hints_used": hints_used or {},
        "subq_elapsed": subq_elapsed or {},
    }


# ─── 테스트: _build_prompt_subq ─────────────────────────────────────


def test_build_prompt_subq_basic() -> None:
    """TC: _build_prompt_subq 기본 동작 — case + subq + answer → prompt 문자열 검증."""
    case = _sample_case_multi()
    subq = case["subqs"][0]  # 설문 1
    answer = "사용자 답안: 시효 소멸 여부 논의"

    system, user = grader._build_prompt_subq(case, subq, answer, hints_used_steps=[])

    # system 은 SYSTEM_PROMPT 동일 (ephemeral 캐시 적중)
    assert system == grader.SYSTEM_PROMPT, "system_prompt must equal SYSTEM_PROMPT (cache hit)"
    # user_message 필수 요소
    assert case["id"] in user, f"user must include case_id, got: {user[:200]}"
    assert "설문 1" in user, "user must include subq label"
    assert "20" in user, "user must include score_max"
    assert answer in user, "user must include user answer"
    assert "공통된 사실관계" not in user or case.get("common_facts") in user, \
        "user must include common_facts"
    assert subq["body"] in user, "user must include question body"
    assert subq["answer"] in user, "user must include answer body (정답지)"
    assert "JSON 외 텍스트 금지" in user, "user must enforce JSON-only output"


def test_build_prompt_subq_with_hints() -> None:
    """TC: hints_used_steps 가 있으면 메타 문구 첨부 + 점수 영향 X 명시."""
    case = _sample_case_multi()
    subq = case["subqs"][0]
    answer = "답안"

    system, user = grader._build_prompt_subq(case, subq, answer, hints_used_steps=[1, 3, 4])

    # 힌트 메타 문구 포함
    assert "힌트 사용 메타" in user, "user must include hint meta block"
    # 노출된 단계가 포함되어야 함
    assert "1" in user and "3" in user and "4" in user, "hint steps 1/3/4 must appear"
    # 점수 영향 X 명시
    assert "점수 영향 X" in user, "user must state hints do NOT affect score"
    # R-09 인용
    assert "R-09" in user, "user must reference R-09 자의적 해석 금지"


def test_build_prompt_subq_hints_empty_no_block() -> None:
    """TC: hints_used_steps 빈 list / None → 힌트 메타 블록 누락."""
    case = _sample_case_multi()
    subq = case["subqs"][0]

    _system, user_none = grader._build_prompt_subq(case, subq, "답안", hints_used_steps=None)
    _system, user_empty = grader._build_prompt_subq(case, subq, "답안", hints_used_steps=[])

    assert "힌트 사용 메타" not in user_none, "empty hints → no meta block (None)"
    assert "힌트 사용 메타" not in user_empty, "empty hints → no meta block ([])"


def test_build_prompt_subq_invalid_hints_filtered() -> None:
    """TC: 1~5 범위 밖 step / 비숫자 입력은 무시 + 빈 list 와 동등."""
    case = _sample_case_multi()
    subq = case["subqs"][0]

    # 범위 밖 (0, 6, 10) — 모두 무시
    _system, user = grader._build_prompt_subq(case, subq, "답안", hints_used_steps=[0, 6, 10])
    assert "힌트 사용 메타" not in user, "out-of-range hint steps must be filtered → no block"

    # 1~5 일부 + 범위 밖 혼합 → 유효 step 만 포함
    _system, user2 = grader._build_prompt_subq(case, subq, "답안", hints_used_steps=[2, 99, 5])
    assert "힌트 사용 메타" in user2, "valid steps must produce hint block"
    # 유효 step만 노출
    assert "2" in user2 and "5" in user2, "valid steps 2, 5 must appear"


# ─── 테스트: grade_attempt_subq (mock 모드) ─────────────────────────


def test_grade_attempt_subq_multi_card() -> None:
    """TC: 다중 카드 채점 — criteria_subq / eval_notes_subq / diff_subq 모두 카드별 dict."""
    case = _sample_case_multi()
    attempt = _sample_attempt_multi()

    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    # 기본 필드
    assert result["is_mock"] is True
    assert "model" in result and "mock" in str(result["model"]).lower()

    # criteria_subq 는 dict — 카드별
    assert isinstance(result["criteria_subq"], dict), "criteria_subq must be dict"
    assert set(result["criteria_subq"].keys()) == {"설문 1", "설문 2"}, \
        f"criteria_subq keys mismatch: {set(result['criteria_subq'].keys())}"

    # 각 카드: 9기준
    for subq_key, criteria_list in result["criteria_subq"].items():
        assert isinstance(criteria_list, list), f"{subq_key}: criteria must be list"
        assert len(criteria_list) == 9, f"{subq_key}: 9 keys required, got {len(criteria_list)}"
        keys = {c["key"] for c in criteria_list}
        assert keys == set(grader.CRITERION_KEYS), f"{subq_key}: criterion keys mismatch"
        for c in criteria_list:
            for fld in ("key", "score", "max", "weight", "comment"):
                assert fld in c, f"{subq_key}: missing field {fld}"

    # eval_notes_subq + diff_subq 도 카드별
    assert isinstance(result["eval_notes_subq"], dict)
    assert set(result["eval_notes_subq"].keys()) == {"설문 1", "설문 2"}
    assert isinstance(result["diff_subq"], dict)
    assert set(result["diff_subq"].keys()) == {"설문 1", "설문 2"}

    # subq_count 정확
    assert result["subq_count"] == 2
    assert result["solved_cards"] == ["설문 1", "설문 2"]
    assert result["skipped_cards"] == []

    # 점수 필드
    assert 0.0 <= result["score_pct"] <= 100.0, f"pct out of range: {result['score_pct']}"
    assert result["grade"] in ("A", "B", "C", "F")
    assert result["score_max"] > 0


def test_grade_attempt_subq_partial_matching() -> None:
    """TC: 3 카드 중 2 풀이 → 부분 점수 (빈 카드 score_max 제외)."""
    case = {
        "id": "test_partial",
        "subject_kor": "민법",
        "category": "테스트",
        "file": "test",
        "case_no": "01",
        "title": "부분 매칭 테스트",
        "points": 30,
        "subqs": [
            {"key": "설문 1", "label": "설문 1 (10점)", "score_max": 10, "body": "Q1", "answer": "A1"},
            {"key": "설문 2", "label": "설문 2 (10점)", "score_max": 10, "body": "Q2", "answer": "A2"},
            {"key": "설문 3", "label": "설문 3 (10점)", "score_max": 10, "body": "Q3", "answer": "A3"},
        ],
    }
    attempt = {
        "answer_subq": {
            "설문 1": "답안 1 내용",
            "설문 2": "",  # 빈 카드 — skip
            "설문 3": "답안 3 내용",
        },
    }

    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    # 풀린 카드만 채점
    assert result["solved_cards"] == ["설문 1", "설문 3"], \
        f"solved: {result['solved_cards']}"
    assert result["skipped_cards"] == ["설문 2"], \
        f"skipped: {result['skipped_cards']}"
    assert result["subq_count"] == 2, "subq_count counts only solved cards"

    # criteria_subq 는 풀린 카드만 포함
    assert set(result["criteria_subq"].keys()) == {"설문 1", "설문 3"}, \
        "criteria_subq must NOT include empty card"

    # 점수 — 빈 카드 score_max 미합산
    # 2 카드 * 89 (mock max, miss 제외 weight 합) = 178 — 정확값은 mock 의존이지만 > 0 보장
    assert result["score_max"] > 0


def test_grade_attempt_subq_all_empty_zero_pct() -> None:
    """TC: 모든 카드 빈 답안 → score_pct = 0 + grade = F + subq_count = 0."""
    case = _sample_case_multi()
    attempt = {
        "answer_subq": {
            "설문 1": "",
            "설문 2": "   ",  # whitespace only
        },
    }

    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    assert result["solved_cards"] == [], "no solved cards"
    assert len(result["skipped_cards"]) == 2, "both cards skipped"
    assert result["subq_count"] == 0
    assert result["score_pct"] == 0.0, f"all empty → pct=0, got {result['score_pct']}"
    assert result["grade"] == "F"
    assert result["criteria_subq"] == {}


def test_grade_attempt_subq_single_card() -> None:
    """TC: N=1 단일 카드 (다중 설문이지만 1개만 있는 케이스) — 분기 정상."""
    case = {
        "id": "test_single_subq",
        "subject_kor": "민법",
        "category": "테스트",
        "file": "test",
        "case_no": "01",
        "title": "단일 카드",
        "points": 15,
        "subqs": [
            {"key": "설문 1", "label": "설문 1 (15점)", "score_max": 15, "body": "Q", "answer": "A"},
        ],
    }
    attempt = {"answer_subq": {"설문 1": "단일 답안"}}

    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    assert result["subq_count"] == 1
    assert result["solved_cards"] == ["설문 1"]
    assert "설문 1" in result["criteria_subq"]
    assert len(result["criteria_subq"]["설문 1"]) == 9


def test_grade_attempt_subq_ga_na_keys() -> None:
    """TC: 가/나 하위 케이스 한글 키 보존 — 패턴 C (민법 모고02_01)."""
    case = _sample_case_with_ga_na()
    attempt = {
        "answer_subq": {
            "설문 1 가": "권리능력자는 자연인과 법인이다.",
            "설문 1 나": "을의 사망으로 상속이 개시된다.",
        },
        "hints_used": {"설문 1 가": [1, 2], "설문 1 나": [1]},
    }

    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    # 한글 키 보존 (escape X)
    assert set(result["criteria_subq"].keys()) == {"설문 1 가", "설문 1 나"}, \
        "Korean keys with spaces must be preserved exactly"
    assert result["solved_cards"] == ["설문 1 가", "설문 1 나"]
    assert result["subq_count"] == 2


def test_grade_attempt_subq_hints_passed_to_prompt() -> None:
    """TC: hints_used 가 _build_prompt_subq 에 전달되는지 검증 (mock 모드에서도 호출 추적)."""
    case = _sample_case_multi()
    attempt = _sample_attempt_multi(hints_used={"설문 1": [1, 2, 3], "설문 2": []})

    # _build_prompt_subq 를 spy 로 — 실제 호출은 그대로
    with patch.object(grader, "_build_prompt_subq", wraps=grader._build_prompt_subq) as spy:
        result = grader.grade_attempt_subq(case, attempt, force_mock=True)
        # 2 카드 → 2회 호출
        assert spy.call_count == 2, f"expected 2 calls, got {spy.call_count}"
        # 첫 호출 (설문 1) 의 hints 인자 검증
        calls = list(spy.call_args_list)
        # call.args[3] 또는 call.kwargs["hints_used_steps"]
        first_call = calls[0]
        hints_arg = first_call.args[3] if len(first_call.args) >= 4 else first_call.kwargs.get("hints_used_steps")
        assert hints_arg == [1, 2, 3], f"hints for 설문 1 must be [1,2,3], got {hints_arg}"

    assert result["subq_count"] == 2


def test_grade_attempt_subq_real_api_mocked() -> None:
    """TC: _call_anthropic + _parse_response 를 patch 해 real API 경로 검증 (mock 응답 주입)."""
    case = _sample_case_multi()
    attempt = _sample_attempt_multi()

    # mock parse 결과 — 모든 카드에 동일한 응답 반환
    fake_parsed = {
        "criteria": [
            {"key": k, "score": 1, "max": 1, "comment": "OK"}
            for k in grader.CRITERION_KEYS
        ],
        "eval_notes": {"strength": "OK", "caution": "OK", "missing": "OK"},
        "diff_segments": [{"type": "match", "text": "답안"}],
    }
    fake_raw = json.dumps(fake_parsed)

    # force_mock=False + _call_anthropic patch + _parse_response patch
    with patch.object(grader, "_is_mock_mode", return_value=False), \
         patch.object(grader, "_call_anthropic", return_value=(fake_raw, {"input_tokens": 100})) as call_spy, \
         patch.object(grader, "_parse_response", return_value=fake_parsed) as parse_spy:
        result = grader.grade_attempt_subq(case, attempt, model="claude-opus-4-7", force_mock=False)

    # 2 카드 → 2회 anthropic 호출 + 2회 파싱
    assert call_spy.call_count == 2, f"expected 2 anthropic calls, got {call_spy.call_count}"
    assert parse_spy.call_count == 2, f"expected 2 parse calls, got {parse_spy.call_count}"

    # 결과 형식
    assert result["is_mock"] is False
    assert result["model"] == "claude-opus-4-7"
    assert set(result["criteria_subq"].keys()) == {"설문 1", "설문 2"}


# ─── 테스트: grade_attempt (legacy fallback + 라우팅) ───────────────


def test_grade_attempt_legacy_fallback() -> None:
    """TC: answer_subq=None / 빈 dict → 기존 grade() 로직 (legacy answer_text 단일)."""
    case = _sample_case_single()

    # 1. answer_subq 누락 — answer_text 만
    attempt_legacy = {"answer_text": "단일 답안 텍스트"}
    result_legacy = grader.grade_attempt(case, attempt_legacy, force_mock=True)

    # legacy 결과는 criteria 1차원 + eval_notes + diff_segments (criteria_subq 없음)
    assert "criteria" in result_legacy, "legacy result must have criteria (1차원)"
    assert isinstance(result_legacy["criteria"], list)
    assert len(result_legacy["criteria"]) == 9
    assert "criteria_subq" not in result_legacy, \
        "legacy path must NOT have criteria_subq (그대로 grade() 결과)"

    # 2. answer_subq 빈 dict → 동일 legacy 분기
    attempt_empty_subq = {"answer_text": "답안", "answer_subq": {}}
    result_empty = grader.grade_attempt(case, attempt_empty_subq, force_mock=True)
    assert "criteria" in result_empty, "empty answer_subq dict → legacy"
    assert "criteria_subq" not in result_empty

    # 3. answer_subq None → legacy
    attempt_none = {"answer_text": "답안", "answer_subq": None}
    result_none = grader.grade_attempt(case, attempt_none, force_mock=True)
    assert "criteria" in result_none


def test_grade_attempt_multi_routing() -> None:
    """TC: answer_subq 가 non-empty dict → grade_attempt_subq 위임."""
    case = _sample_case_multi()
    attempt = _sample_attempt_multi()

    result = grader.grade_attempt(case, attempt, force_mock=True)

    # 다중 분기 — criteria_subq 가 있어야 함
    assert "criteria_subq" in result, "multi-subq path must produce criteria_subq"
    assert isinstance(result["criteria_subq"], dict)
    assert set(result["criteria_subq"].keys()) == {"설문 1", "설문 2"}


def test_grade_attempt_validates_input() -> None:
    """TC: attempt 가 dict 아님 → ValueError."""
    case = _sample_case_single()
    try:
        grader.grade_attempt(case, "not a dict", force_mock=True)  # type: ignore[arg-type]
    except ValueError as e:
        assert "dict" in str(e), f"error must mention dict, got {e}"
        return
    raise AssertionError("expected ValueError for non-dict attempt")


def test_grade_attempt_subq_validates_input() -> None:
    """TC: grade_attempt_subq 직접 호출 — answer_subq 누락 시 ValueError."""
    case = _sample_case_multi()
    try:
        grader.grade_attempt_subq(case, {"answer_text": "x"}, force_mock=True)
    except ValueError as e:
        assert "answer_subq" in str(e), f"error must mention answer_subq, got {e}"
        return
    raise AssertionError("expected ValueError for missing answer_subq")


# ─── 테스트: _normalize_subq_grades ────────────────────────────────


def test_normalize_subq_grades_legacy_wrap() -> None:
    """TC: legacy grade() 결과 (1차원 criteria) → criteria_subq = {"전체": [...]} wrap."""
    # legacy 형식 — grade() 결과 시뮬
    legacy_result = {
        "model": "mock",
        "score_total": 60.0,
        "score_max": 89.0,
        "score_pct": 67.4,
        "grade": "C",
        "weights_applied": dict(grader.DEFAULT_WEIGHTS),
        "criteria": [
            {"key": k, "score": 1, "max": 1, "weight": int(grader.DEFAULT_WEIGHTS[k]), "comment": ""}
            for k in grader.CRITERION_KEYS
        ],
        "eval_notes": {"strength": "S", "caution": "C", "missing": "M"},
        "diff_segments": [{"type": "match", "text": "x"}],
        "is_mock": True,
        "elapsed_sec": 0.1,
    }

    normalized = grader._normalize_subq_grades(legacy_result)

    # criteria_subq wrap 검증
    assert "criteria_subq" in normalized
    assert isinstance(normalized["criteria_subq"], dict)
    assert "전체" in normalized["criteria_subq"], "legacy → '전체' key"
    assert len(normalized["criteria_subq"]["전체"]) == 9

    assert "eval_notes_subq" in normalized
    assert "전체" in normalized["eval_notes_subq"]
    assert normalized["eval_notes_subq"]["전체"]["strength"] == "S"

    assert "diff_subq" in normalized
    assert "전체" in normalized["diff_subq"]

    # 기존 키 보존
    assert normalized["score_total"] == 60.0
    assert normalized["grade"] == "C"


def test_normalize_subq_grades_subq_passthrough() -> None:
    """TC: subq 결과 (이미 criteria_subq 있음) → 그대로 보존 + legacy criteria 호환 보강."""
    subq_result = {
        "model": "mock",
        "score_total": 70.0,
        "score_max": 100.0,
        "score_pct": 70.0,
        "grade": "B",
        "weights_applied": dict(grader.DEFAULT_WEIGHTS),
        "criteria_subq": {
            "설문 1": [
                {"key": k, "score": 1, "max": 1, "weight": int(grader.DEFAULT_WEIGHTS[k]), "comment": ""}
                for k in grader.CRITERION_KEYS
            ],
        },
        "eval_notes_subq": {"설문 1": {"strength": "S", "caution": "C", "missing": "M"}},
        "diff_subq": {"설문 1": []},
        "subq_count": 1,
        "is_mock": True,
        "elapsed_sec": 0.1,
    }

    normalized = grader._normalize_subq_grades(subq_result)

    # criteria_subq 보존
    assert normalized["criteria_subq"] == subq_result["criteria_subq"]
    # 단일 카드 케이스 — legacy criteria 호환 (첫 카드 그대로)
    assert "criteria" in normalized
    assert len(normalized["criteria"]) == 9
    # eval_notes 호환 (첫 카드)
    assert normalized["eval_notes"]["strength"] == "S"


def test_normalize_subq_grades_subq_multi_no_legacy_criteria() -> None:
    """TC: 다중 카드 (N>1) — legacy criteria 자동 생성 X (애매하므로 명시 X)."""
    subq_result = {
        "criteria_subq": {
            "설문 1": [{"key": k, "score": 0, "max": 1, "weight": 1, "comment": ""} for k in grader.CRITERION_KEYS],
            "설문 2": [{"key": k, "score": 0, "max": 1, "weight": 1, "comment": ""} for k in grader.CRITERION_KEYS],
        },
        "eval_notes_subq": {"설문 1": {"strength": "S1", "caution": "C", "missing": "M"},
                            "설문 2": {"strength": "S2", "caution": "C", "missing": "M"}},
        "diff_subq": {},
        "score_total": 0.0, "score_max": 0.0, "score_pct": 0.0, "grade": "F",
    }

    normalized = grader._normalize_subq_grades(subq_result)

    assert "criteria_subq" in normalized
    # 다중 카드 → legacy criteria 단일 자동 생성 X (모호함)
    assert "criteria" not in normalized, "multi-card → no legacy criteria auto"


def test_normalize_subq_grades_roundtrip() -> None:
    """TC: _normalize_subq_grades(_normalize_subq_grades(x)) == _normalize_subq_grades(x) — 멱등."""
    legacy_result = {
        "score_total": 60.0,
        "score_max": 89.0,
        "score_pct": 67.4,
        "grade": "C",
        "criteria": [{"key": k, "score": 1, "max": 1, "weight": 1, "comment": ""} for k in grader.CRITERION_KEYS],
        "eval_notes": {"strength": "S", "caution": "C", "missing": "M"},
        "diff_segments": [],
    }

    first = grader._normalize_subq_grades(legacy_result)
    second = grader._normalize_subq_grades(first)

    # criteria_subq 동일
    assert first["criteria_subq"] == second["criteria_subq"], "roundtrip: criteria_subq must be idempotent"
    assert first["eval_notes_subq"] == second["eval_notes_subq"]
    assert first["diff_subq"] == second["diff_subq"]


def test_normalize_subq_grades_rejects_non_dict() -> None:
    """TC: _normalize_subq_grades(None) → ValueError."""
    for bad in (None, "x", 42, [1, 2, 3]):
        try:
            grader._normalize_subq_grades(bad)  # type: ignore[arg-type]
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_grade_attempt_subq_korean_keys_preserved() -> None:
    """TC: 한글 키 (설문 N, 설문 N 가/나) 정확 보존 — JSON 직렬화 호환 검증."""
    case = _sample_case_with_ga_na()
    attempt = {
        "answer_subq": {
            "설문 1 가": "답 가",
            "설문 1 나": "답 나",
        },
    }
    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    # 한글 키 그대로 보존
    assert "설문 1 가" in result["criteria_subq"]
    assert "설문 1 나" in result["criteria_subq"]

    # JSON 직렬화 (ensure_ascii=False) 시 escape 없이 한글 보존
    serialized = json.dumps(result["criteria_subq"], ensure_ascii=False)
    assert "설문 1 가" in serialized, "한글 키 must remain unescaped in JSON"
    assert "\\u" not in serialized, "no unicode escapes when ensure_ascii=False"


# ─── 테스트: weights 검증 ──────────────────────────────────────────


def test_grade_attempt_subq_weights_invalid_raises() -> None:
    """TC: 잘못된 weights → ValueError (legacy validate_weights 와 동일 동작)."""
    case = _sample_case_multi()
    attempt = _sample_attempt_multi()
    bad_weights = dict(grader.DEFAULT_WEIGHTS)
    bad_weights["mnem"] = 50  # 합계 != 100

    try:
        grader.grade_attempt_subq(case, attempt, weights=bad_weights, force_mock=True)
    except ValueError as e:
        assert "100" in str(e), f"error must mention 100, got {e}"
        return
    raise AssertionError("expected ValueError for invalid weights")


def test_grade_attempt_subq_default_weights() -> None:
    """TC: weights=None → DEFAULT_WEIGHTS 적용 + criteria.weight 일치."""
    case = _sample_case_multi()
    attempt = _sample_attempt_multi()

    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    assert result["weights_applied"] == grader.DEFAULT_WEIGHTS
    # 각 카드의 criteria.weight 가 DEFAULT_WEIGHTS 와 일치
    for subq_key, criteria in result["criteria_subq"].items():
        by_key = {c["key"]: c["weight"] for c in criteria}
        for k, v in grader.DEFAULT_WEIGHTS.items():
            assert by_key[k] == v, f"{subq_key}/{k} weight: {by_key[k]} != {v}"


# ─── 테스트: case.subqs 없을 때 (fallback) ───────────────────────


def test_grade_attempt_subq_no_case_subqs_fallback() -> None:
    """TC: case 에 subqs 키 없어도 answer_subq 키 기반으로 채점 가능 (stub subq 사용)."""
    case = {
        "id": "test_no_subqs",
        "subject_kor": "민법",
        "category": "테스트",
        "file": "test",
        "case_no": "01",
        "title": "subqs 없음",
        "points": 20,
        # subqs 키 없음 — answer_subq 키만으로 stub 생성
    }
    attempt = {
        "answer_subq": {
            "설문 1": "답안 1",
            "설문 2": "답안 2",
        },
    }

    result = grader.grade_attempt_subq(case, attempt, force_mock=True)

    # 정상 동작 — answer_subq 키 기반 stub
    assert result["subq_count"] == 2
    assert set(result["criteria_subq"].keys()) == {"설문 1", "설문 2"}


# ─── standalone 실행 (pytest 없이 통과) ──────────────────────────────

TESTS = [
    test_build_prompt_subq_basic,
    test_build_prompt_subq_with_hints,
    test_build_prompt_subq_hints_empty_no_block,
    test_build_prompt_subq_invalid_hints_filtered,
    test_grade_attempt_subq_multi_card,
    test_grade_attempt_subq_partial_matching,
    test_grade_attempt_subq_all_empty_zero_pct,
    test_grade_attempt_subq_single_card,
    test_grade_attempt_subq_ga_na_keys,
    test_grade_attempt_subq_hints_passed_to_prompt,
    test_grade_attempt_subq_real_api_mocked,
    test_grade_attempt_legacy_fallback,
    test_grade_attempt_multi_routing,
    test_grade_attempt_validates_input,
    test_grade_attempt_subq_validates_input,
    test_normalize_subq_grades_legacy_wrap,
    test_normalize_subq_grades_subq_passthrough,
    test_normalize_subq_grades_subq_multi_no_legacy_criteria,
    test_normalize_subq_grades_roundtrip,
    test_normalize_subq_grades_rejects_non_dict,
    test_grade_attempt_subq_korean_keys_preserved,
    test_grade_attempt_subq_weights_invalid_raises,
    test_grade_attempt_subq_default_weights,
    test_grade_attempt_subq_no_case_subqs_fallback,
]


def main() -> int:
    """standalone — pytest 없이 통과 시 0, 실패 시 1."""
    passed = 0
    failed: list[tuple[str, str]] = []
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
    print(f"\n[test_step24_grader] {passed}/{total} passed")
    if failed:
        print("[test_step24_grader] FAILURES:", file=sys.stderr)
        for n, err in failed:
            print(f"  - {n}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
