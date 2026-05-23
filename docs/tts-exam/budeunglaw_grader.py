"""부등법(부동산등기법) 5모드 채점 wrapper.

grader.py와의 관계:
  - grader.py의 grade()는 9키 v6 가정 (민법/민소)
  - budeunglaw_grader.py는 부등법 11키 v7 + 5모드 채점
  - server.py의 채점 dispatcher가 cases.subject_type을 보고 분기:
      'lv1234' (민법/민소) → grader.grade()
      'problem_answer' (부등법) → budeunglaw_grader.grade_multimode()

사용:
    from budeunglaw_grader import grade_multimode, grade_single_mode
    results = grade_multimode(case_meta, user_answer, modes=None)  # 5 mode 전부
    # 또는
    result = grade_single_mode(case_meta, user_answer, mode="hybrid")
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    from budeunglaw_modes import (
        MODE_ORDER, MODE_LABELS,
        get_mode_weights, get_mode_prompt, get_all_modes,
        adjust_weights_for_case_type, format_score_display,
        summarize_multi_mode_results, guess_outline_category,
        is_short_answer, BASE_PROMPT_BUDEUNGLAW,
    )
except ImportError:
    # 동일 디렉토리 import fallback
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from budeunglaw_modes import (
        MODE_ORDER, MODE_LABELS,
        get_mode_weights, get_mode_prompt, get_all_modes,
        adjust_weights_for_case_type, format_score_display,
        summarize_multi_mode_results, guess_outline_category,
        is_short_answer, BASE_PROMPT_BUDEUNGLAW,
    )


# ============================================================
# Anthropic API client (grader.py와 동일 패턴)
# ============================================================

def _get_client():
    """Anthropic client 생성 (env-aware)."""
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError("anthropic SDK not installed") from e
    return Anthropic()


DEFAULT_MODEL = os.getenv("LAWEAR_GRADER_MODEL", "claude-opus-4-7")


# ============================================================
# 부등법 SYSTEM_PROMPT 본문 (5 mode 공통 prefix + mode별 suffix)
# ============================================================

GRADING_INSTRUCTIONS = """
[채점 절차 (모든 모드 공통)]
1. 원본 답안(reference)을 읽고 만능목차 카테고리, 인용 조문/규칙/선례/예규, 첨부정보 칸, 절차 단계, 효력 결론을 추출
2. 사용자 답안(user_answer)을 읽고 위 추출 항목별 매칭률 산출
3. 각 채점 키별로 score (0~max) + comment 작성
4. 누락 critical(missing)은 음수 score 가능 (max=0, score는 -10 ~ 0)
5. 최종 total = Σ(score × weight) / Σ(weight) × 100 (백분율 환산)

[출력 JSON 형식 — 엄격]
{
  "criteria": {
    "outline":          {"score": 14, "max": 17, "comment": "기본 목차 채택, 효과 단계 누락"},
    "articles":         {"score": 10, "max": 15, "comment": "조문 5/8 매칭, 규칙 2/3 매칭"},
    "precedent":        {"score":  5, "max":  8, "comment": "[선례] 1/2, [예규] 0/1"},
    "attached":         {"score": 11, "max": 13, "comment": "인감증명 8칸 중 6칸 명시"},
    "procedure":        {"score":  9, "max": 12, "comment": "개시 분류 OK, 통지 누락"},
    "effect":           {"score":  8, "max": 10, "comment": "직권말소 범위 정확, 각하사유 호수 누락"},
    "case_apply":       {"score":  9, "max": 11, "comment": "사안 인물 받음, 일자 적용 일부"},
    "richness":         {"score":  7, "max":  9, "comment": "원본 대비 80% 분량"},
    "missing":          {"score": -3, "max":  0, "comment": "재결로 인정된 권리 직권말소 예외 누락"}
  },
  "total":          70.0,
  "max":           100.0,
  "pct":            70.0,
  "grade":           "B",
  "eval_notes":     "강사 모드 — 만능목차 첨부서면 골격 부분 누락, 조문 인용 깊이 보통",
  "diff_segments": [...]
}

[R-09 절대 — 자의적 해석 금지]
- 답안에 명시되지 않은 논점을 "의도했을 것 같다"고 가점 X
- 모든 score는 user_answer에 적힌 그대로 평가
- comment에 근거 (원본의 어느 부분과 매칭) 명시

[합격선]
- A:  95~100
- A-: 90~94 (lawear-2e42 사용자 명시, 합격선 73 별도)
- B+: 85~89
- B:  80~84
- B-: 73~79 (합격선)
- C+: 65~72
- C:  60~64
- D:  50~59
- F:  0~49
"""


def _build_prompt(case_meta: dict, user_answer: str, mode: str, weights: dict) -> tuple[str, str]:
    """system + user prompt 생성 (mode별 분기)."""
    system = get_mode_prompt(mode) + "\n" + GRADING_INSTRUCTIONS

    # weights를 system에 명시 (모델이 가중치 인식)
    weights_str = json.dumps({k: v for k, v in weights.items() if v != 0}, ensure_ascii=False, indent=2)
    system += f"\n[현재 모드 가중치 (max 값)]\n{weights_str}\n"

    # user prompt
    title = case_meta.get("title", "")
    case = case_meta.get("case", "")
    points = case_meta.get("points", 100)
    problem = case_meta.get("origin_text", "") or case_meta.get("problem", "")
    answer_ref = case_meta.get("answer_template", "") or case_meta.get("lv4_text", "")
    outline_cat = case_meta.get("outline_category") or guess_outline_category(title, case)

    user = f"""[채점 대상]
- 제목: {title}
- 소제목: {case}
- 점수: {points}점
- 만능목차 카테고리 (자동 추정): {outline_cat}
- 약술형 여부: {is_short_answer(points, problem)}

[원본 문제]
{problem}

[원본 답안 (강사 모범, reference)]
{answer_ref}

[사용자 답안]
{user_answer}

위 컨텍스트로 부등법 5모드 중 '{mode}' ({MODE_LABELS[mode]}) 모드 채점을 수행하시오.
JSON 형식으로만 출력. 다른 텍스트 X.
"""
    return system, user


# ============================================================
# 단일 모드 채점
# ============================================================

def grade_single_mode(
    case_meta: dict,
    user_answer: str,
    mode: str = "hybrid",
    model: str = None,
    mock: bool = None,
) -> dict:
    """부등법 단일 모드 채점.

    Args:
      case_meta: cases 테이블 row dict (title, case, points, origin_text, answer_template, outline_category)
      user_answer: 사용자 답안 텍스트
      mode: 5개 모드 중 하나 (judge/lecturer/hybrid/main_opus/strict_outline)
      model: Anthropic 모델 ID (default: claude-opus-4-7)
      mock: True면 mock 결과 반환 (테스트용)

    Returns:
      {
        "mode": "hybrid",
        "criteria": {...},
        "total": 73.0,
        "max": 100.0,
        "pct": 73.0,
        "grade": "B-",
        "absolute_score": 21,    # 사용자 요청 형식
        "absolute_max": 30,
        "score_display": "21/30 (73/100)",
        "eval_notes": "...",
        "weights_version": "v7_budeunglaw_hybrid",
      }
    """
    if mode not in MODE_ORDER:
        raise ValueError(f"Unknown mode: {mode}")

    # 가중치 동적 조정 (사례형/약술형)
    base_weights = get_mode_weights(mode)
    adjusted = adjust_weights_for_case_type(
        base_weights,
        points=case_meta.get("points", 100),
        title=case_meta.get("title", ""),
        case=case_meta.get("case", ""),
        problem_text=case_meta.get("origin_text", "") or case_meta.get("problem", ""),
    )

    if mock or os.getenv("LAWEAR_GRADER_MOCK") == "1":
        return _mock_result(case_meta, mode, adjusted)

    model = model or DEFAULT_MODEL
    system, user = _build_prompt(case_meta, user_answer, mode, adjusted)

    client = _get_client()
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text if msg.content else "{}"

    # JSON 파싱 (앞뒤 텍스트 잘라내기)
    result = _parse_json(raw)
    result["mode"] = mode
    result["weights_version"] = f"v7_budeunglaw_{mode}"

    # 점수 표시 추가 (사용자 요청 10/50 (20/100))
    display = format_score_display(
        raw_score=result.get("total", 0),
        raw_max=result.get("max", 100),
        problem_points=case_meta.get("points", 100),
    )
    result["absolute_score"] = display["absolute_score"]
    result["absolute_max"] = display["absolute_max"]
    result["score_display"] = display["combined"]

    return result


# ============================================================
# 5모드 일괄 채점
# ============================================================

def grade_multimode(
    case_meta: dict,
    user_answer: str,
    modes: list[str] = None,
    model: str = None,
    mock: bool = None,
    parallel: bool = True,
) -> dict:
    """부등법 5모드 일괄 채점.

    Args:
      modes: 채점할 모드 리스트 (None이면 5 mode 전부)
      parallel: True면 ThreadPoolExecutor 병렬

    Returns:
      {
        "modes_results": {mode: result, ...},
        "summary": {modes: [...], highest_mode, lowest_mode, spread_pct, consensus_grade},
        "case_meta": {...},
      }
    """
    if modes is None:
        modes = get_all_modes()

    results = {}

    if parallel and not mock:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(grade_single_mode, case_meta, user_answer, m, model, mock): m
                for m in modes
            }
            for fut in as_completed(futures):
                m = futures[fut]
                try:
                    results[m] = fut.result()
                except Exception as e:
                    results[m] = {"mode": m, "error": str(e)}
    else:
        for m in modes:
            try:
                results[m] = grade_single_mode(case_meta, user_answer, m, model, mock)
            except Exception as e:
                results[m] = {"mode": m, "error": str(e)}

    summary = summarize_multi_mode_results(results)

    return {
        "modes_results": results,
        "summary": summary,
        "case_meta": {
            "id": case_meta.get("id"),
            "title": case_meta.get("title"),
            "case": case_meta.get("case"),
            "points": case_meta.get("points"),
            "subject": case_meta.get("subject"),
        },
    }


# ============================================================
# 헬퍼
# ============================================================

def _parse_json(raw: str) -> dict:
    """Claude 응답에서 JSON 추출 (앞뒤 ```json ... ``` 처리)."""
    raw = raw.strip()
    # ```json ... ``` 제거
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    # 첫 { ~ 마지막 } 추출
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # fallback
        return {"error": "JSON parse failed", "raw": raw[:500]}


def _mock_result(case_meta: dict, mode: str, weights: dict) -> dict:
    """테스트용 mock 결과 (실제 API 호출 X)."""
    pos_weights = {k: v for k, v in weights.items() if v > 0}
    total_max = sum(pos_weights.values())
    # 모드별 다른 mock 점수 (테스트용)
    mock_pct = {
        "judge": 75,
        "lecturer": 70,
        "hybrid": 73,
        "main_opus": 78,
        "strict_outline": 60,
    }.get(mode, 70)
    total = mock_pct
    points = case_meta.get("points", 100)
    display = format_score_display(total, 100, points)
    return {
        "mode": mode,
        "criteria": {k: {"score": int(v * mock_pct / 100), "max": v, "comment": f"mock {k}"} for k, v in pos_weights.items()},
        "total": total,
        "max": 100,
        "pct": mock_pct,
        "grade": _pct_to_grade(mock_pct),
        "absolute_score": display["absolute_score"],
        "absolute_max": display["absolute_max"],
        "score_display": display["combined"],
        "eval_notes": f"[MOCK] {MODE_LABELS[mode]} 모드 — 가상 채점",
        "weights_version": f"v7_budeunglaw_{mode}",
    }


def _pct_to_grade(pct: float) -> str:
    """백분율 → 등급."""
    if pct >= 95: return "A"
    if pct >= 90: return "A-"
    if pct >= 85: return "B+"
    if pct >= 80: return "B"
    if pct >= 73: return "B-"
    if pct >= 65: return "C+"
    if pct >= 60: return "C"
    if pct >= 50: return "D"
    return "F"


# ============================================================
# CLI 테스트
# ============================================================

if __name__ == "__main__":
    import sys
    print("=== 부등법 5모드 mock 채점 테스트 ===\n")
    case_meta = {
        "id": "2025_budeunglaw_user_test",
        "title": "01_등기의 추정력",
        "case": "추정력의 범위와 효과",
        "points": 30,
        "origin_text": "사례: 甲은 ...",
        "answer_template": "1. 의의\n2. 범위\n3. 효과",
        "subject": "budeunglaw",
    }
    user_answer = "1. 추정력의 의의는 ...\n2. 범위는 ...\n3. 효과는 ..."
    result = grade_multimode(case_meta, user_answer, mock=True, parallel=False)
    print("5모드 결과:")
    for mode, r in result["modes_results"].items():
        print(f"  {mode:18s} | {r['score_display']:18s} | grade {r['grade']}")
    print()
    print(f"highest: {result['summary']['highest_mode']}")
    print(f"lowest:  {result['summary']['lowest_mode']}")
    print(f"spread:  {result['summary']['spread_pct']:.1f}점")
    print(f"consensus grade: {result['summary']['consensus_grade']}")
