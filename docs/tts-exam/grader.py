#!/usr/bin/env python3
"""Grader — Anthropic Claude API + 7기준 채점 + mock 모드 + env-aware (Step 6).

dev-design archive #48 §5 (채점 프롬프트) + dev-impl-plan #51 Step 6.

핵심:
- `grade(case_meta, user_answer, weights, model='claude-opus-4-7', *, mock=None) -> dict`
  - 입력: 사용자 답안 + 케이스 메타(.md 본문 raw + Lv.1 + Lv.4 + 강조 태그) + 가중치 7항목
  - 출력: 7기준 score/max/weight/comment + total/max/pct + grade + eval_notes + diff_segments
- `_build_prompt(case_meta, user_answer, weights) -> tuple[str, str]` — system + user 분리
- `_parse_response(text) -> dict` — Claude 응답 JSON 추출 (코드펜스 + 견고)
- `_compute_score(criteria, weights) -> tuple[total, max_score, pct, grade]`
- mock 모드: API 키 미설정 또는 model='mock' 또는 env LAWEAR_GRADER_MOCK=1

R-09 (자의적 해석 금지) 준수:
- 채점 프롬프트 자체에 "자료(사실관계/문제/레퍼런스)에 없는 내용 추가 X" 명시
- mock 응답도 자료 유무 무관 디폴트 (자의 X)
- diff_segments 는 사용자 답안 substring 기반만 (자의적 텍스트 생성 X)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# anthropic SDK 는 lazy import (mock 전용 환경에서 의존성 0)
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _ANTHROPIC_AVAILABLE = False


# ─── 설정 (env / 상수) ─────────────────────────────────────────────────
DEFAULT_MODEL: str = os.environ.get("LAWEAR_GRADER_MODEL", "claude-opus-4-7")
MAX_TOKENS: int = int(os.environ.get("LAWEAR_GRADER_MAX_TOKENS", "4096"))
RATE_LIMIT_RETRIES: int = int(os.environ.get("LAWEAR_GRADER_RETRIES", "3"))
RATE_LIMIT_BACKOFF_SEC: float = float(os.environ.get("LAWEAR_GRADER_BACKOFF", "1.0"))

# 7기준 키 (DB CHECK 와 1:1) — dev-design #48 §3-2 / §4-2 attempt_criteria
CRITERION_KEYS: tuple[str, ...] = ("mnem", "color", "under", "outline", "sem", "rich", "miss")

# 기본 가중치 (dev-design #48 §3-2 초기 settings) — 합계 100
DEFAULT_WEIGHTS: dict[str, int] = {
    "mnem": 20,
    "color": 15,
    "under": 10,
    "outline": 15,
    "sem": 15,
    "rich": 10,
    "miss": 15,
}

# Grade threshold (dev-design #48 §5-4 + dev-impl-plan #51 Q9)
GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (90.0, "A"),
    (70.0, "B"),
    (50.0, "C"),
    (0.0, "F"),
]


# ─── 예외 ──────────────────────────────────────────────────────────────


class GraderError(Exception):
    """채점 실패 (HTTP 5xx 매핑 base)."""

    def __init__(self, message: str, error_code: str = "internal_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class GraderRateLimitError(GraderError):
    """Anthropic 429 — 자동 재시도 후에도 실패."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "anthropic_rate_limit")


class GraderBadGatewayError(GraderError):
    """Anthropic 502/5xx — 즉시 error 마킹."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "anthropic_bad_gateway")


class GraderApiKeyMissingError(GraderError):
    """ANTHROPIC_API_KEY 미설정 (HTTP 503)."""

    def __init__(self) -> None:
        super().__init__(
            "ANTHROPIC_API_KEY not set. Configure in .env or system env.",
            "api_key_missing",
        )


class GraderParseError(GraderError):
    """Claude 응답 JSON 파싱 실패."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "parse_failure")


# ─── system 프롬프트 (불변 — ephemeral 캐시 대상) ──────────────────────

SYSTEM_PROMPT: str = """당신은 법무사 2차 시험 채점관입니다. 한국어로 평가하세요.

[채점 7기준 (시안 Evaluation 패널 1:1)]
1. mnem    — Lv.4 두문자([blank2]) 풀이형 키워드 누락 여부 (두문자 그대로 X — 풀이형으로 평가)
2. color   — Color Emphasis ([red]/[blue]/[bold]/[blank]) 키워드가 답안에 반영되었는지
3. under   — Underline Coverage ([u]) 키워드 누락 여부
4. outline — Lv.1 Outline Match: 답안 목차가 Lv.1 기준 목차와 의미 일치
5. sem     — Semantic Match: 강조 태그를 글자 그대로는 못 써도 의미가 유사한지
6. rich    — Richness: 답안 풍부함이 Lv.4(0) / Lv.1(1) / 원본(2) 중 어디에 해당
7. miss    — Missing Arguments: 레퍼런스(Lv.1+원본) 대비 누락 논점 (감점, score 음수 가능)

[강조 태그 의미]
- [red]…[/red]:     빨강 (조문/판례/요건)
- [blue]…[/blue]:   파랑 (개념/논점 제목)
- [bold]…[/bold]:   굵게 (강조)
- [u]…[/u]:         밑줄 (핵심)
- [blank]…[/blank]: 블랭크 (본문 시각 처리)
- [blank2]…[/blank2]: 두문자 (Lv.4 사용자 두문자만)

[채점 규칙 — 절대 준수]
- 자료(사실관계/문제/원본/Lv.1/Lv.4)에 없는 내용을 추가하지 마세요. 자의적 해석 금지.
- 두문자(예 "위,발,간")를 그대로 외운 게 아니라 "풀이형 키워드"(예 "관할위반/발견시 조치/간과판결")로 적었어도 OK.
- 색 강조는 글자가 완전히 똑같지 않아도 의미만 비슷하면 OK (sem 기준에서 가산).
- 누락 논점은 차감 (miss: score 는 0 이하 음수 또는 0, max=0).
- Richness 점수: 0=Lv.4 수준, 1=Lv.1 수준, 2=원본 수준 (max=2).
- comment 는 한국어 1~2 문장, 간결, 자료 인용 가능.

[출력 형식 — JSON only (코드펜스 없이 raw JSON 만)]
{
  "criteria": [
    {"key":"mnem",    "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"color",   "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"under",   "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"outline", "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"sem",     "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"rich",    "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"miss",    "score":<int|float>, "max":0,           "comment":"..."}
  ],
  "eval_notes": {
    "strength": "한국어 1~2 문장",
    "caution":  "한국어 1~2 문장",
    "missing":  "한국어 1~2 문장"
  },
  "diff_segments": [
    {"type":"match",   "text":"사용자 답안의 일치 부분"},
    {"type":"miss",    "text":"사용자 답안에 누락된 핵심 키워드"},
    {"type":"partial", "text":"부분 일치 표현"}
  ]
}

반드시 위 JSON 형식만 출력하세요. 다른 텍스트 (설명, 사과, 코드펜스) 절대 추가 X.
"""


# ─── 프롬프트 빌드 ─────────────────────────────────────────────────────


def _build_prompt(
    case_meta: dict[str, Any], user_answer: str, weights: dict[str, int]
) -> tuple[str, str]:
    """system / user 메시지 분리 생성.

    Args:
        case_meta: get_case() 반환 dict
                   (id, subject_kor, category, file, case_no, title, points,
                    md_body, lv1, lv4, origin).
        user_answer: 사용자 답안 텍스트.
        weights: 7기준 가중치 (합계 100).

    Returns:
        (system_prompt, user_message)
    """
    # 메타 안전 추출 (None → 빈 문자열)
    subject_kor = case_meta.get("subject_kor") or case_meta.get("subject") or ""
    category = case_meta.get("category") or ""
    file_label = case_meta.get("file") or ""
    case_no = case_meta.get("case_no") or ""
    title = case_meta.get("title") or ""
    points = case_meta.get("points") or 0

    # 본문은 md_body raw 우선 (origin + lv1 + lv4 다 포함 = R-26 인용 보존)
    # 단, md_body 가 None 이면 origin/lv1/lv4 조합
    md_body = case_meta.get("md_body")
    if not md_body:
        parts = [
            case_meta.get("origin") or "",
            case_meta.get("lv1") or "",
            case_meta.get("lv4") or "",
        ]
        md_body = "\n\n".join(p for p in parts if p)

    weights_json = json.dumps(weights, ensure_ascii=False)

    user_message = f"""[케이스 ID] {case_meta.get("id", "")}
[과목] {subject_kor} · {category} · {file_label} · 케이스 {case_no}
[제목] {title}
[점수] {points}

[원본 .md 본문 (사실관계 + 문제 + 답안 + Lv.1 + Lv.4 — 강조 태그 보존)]
{md_body}

[사용자 답안]
{user_answer}

[가중치]
{weights_json}

위 채점 7기준에 따라 JSON 형식으로 평가하세요. JSON 외 텍스트 금지.
"""
    return SYSTEM_PROMPT, user_message


# ─── 응답 파싱 ─────────────────────────────────────────────────────────

# 코드펜스 ```json ... ``` 또는 raw JSON 둘 다 허용
_CODEFENCE_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FIRST_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _parse_response(text: str) -> dict[str, Any]:
    """Claude 응답 raw text → JSON dict.

    1차: 코드펜스 ```json ... ``` 추출.
    2차: 첫 `{` ~ 마지막 `}` 슬라이스.
    3차: 실패 시 GraderParseError.

    Raises:
        GraderParseError: 어떤 방식으로도 JSON 추출 실패 / 필수 키 누락.
    """
    raw = text.strip()

    # 1차: code fence
    m = _CODEFENCE_JSON_RE.search(raw)
    candidates: list[str] = []
    if m:
        candidates.append(m.group(1))
    # 2차: 첫 { ... 마지막 }
    m2 = _FIRST_OBJECT_RE.search(raw)
    if m2:
        candidates.append(m2.group(0))
    # 3차: raw 자체가 JSON 인 경우
    candidates.append(raw)

    parsed: dict[str, Any] | None = None
    last_err: str | None = None
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                parsed = obj
                break
        except (json.JSONDecodeError, TypeError) as e:
            last_err = str(e)
            continue

    if parsed is None:
        raise GraderParseError(
            f"failed to extract JSON from response (last_err={last_err}); raw_head={raw[:200]!r}"
        )

    # 필수 키 검증
    if "criteria" not in parsed or not isinstance(parsed["criteria"], list):
        raise GraderParseError("response missing 'criteria' array")
    if "eval_notes" not in parsed or not isinstance(parsed["eval_notes"], dict):
        raise GraderParseError("response missing 'eval_notes' object")
    # diff_segments 는 선택 (없으면 빈 배열 보강)
    if "diff_segments" not in parsed or not isinstance(parsed["diff_segments"], list):
        parsed["diff_segments"] = []

    # criteria 7개 매핑 검증 — key 누락 시 mock 값으로 보강 X (R-09)
    by_key = {c.get("key"): c for c in parsed["criteria"] if isinstance(c, dict)}
    missing = [k for k in CRITERION_KEYS if k not in by_key]
    if missing:
        raise GraderParseError(f"criteria missing keys: {missing}")

    return parsed


# ─── 점수 산정 ─────────────────────────────────────────────────────────


def _compute_score(
    criteria: list[dict[str, Any]], weights: dict[str, int]
) -> tuple[float, float, float, str]:
    """가중치 적용 후 total/max/pct/grade 계산.

    수식:
      각 기준: weighted_i = (score_i / max_i) * weight_i   (max=0 인 miss 는 별도)
      miss: 음수 score 그대로 가산 (감점)
      total = Σ weighted_i + miss.score (음수)
      score_max = Σ weight_i (= 100 가정, 단 합 검증은 호출자 책임)
      pct = total / score_max * 100  (0~100 클램프)
      grade: 90+ A / 70+ B / 50+ C / else F

    Returns:
        (total, score_max, pct, grade)
    """
    by_key = {c["key"]: c for c in criteria if c.get("key") in CRITERION_KEYS}

    weighted_sum: float = 0.0
    weight_total: float = 0.0
    for key in CRITERION_KEYS:
        c = by_key.get(key)
        if c is None:
            continue
        weight = float(weights.get(key, 0))
        weight_total += weight
        if key == "miss":
            # miss: max=0, score 가 음수 또는 0 — 가중치는 cap 으로만 사용
            # weighted = score * (weight/100) 로 환산 (음수 그대로)
            try:
                score = float(c.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0
            # miss 의 weight 는 차감 한도 — score (음수) * (weight/100)
            # 단 dev-design 응답 예시에선 score=-2, max=0 그대로 가산 → 본 구현은 단순 가산
            # (단순 가산 + clamp 으로 처리 — 자료 없으므로 보수적)
            weighted_sum += score * (weight / 100.0)
            continue
        try:
            score = float(c.get("score", 0))
            max_s = float(c.get("max", 0))
        except (TypeError, ValueError):
            score, max_s = 0.0, 0.0
        if max_s > 0:
            weighted_sum += (score / max_s) * weight
        # max=0 인 비-miss 항목은 skip

    # score_max 는 miss 제외 weight 합 (miss 는 감점 전용)
    score_max = weight_total - float(weights.get("miss", 0))
    if score_max <= 0:
        score_max = 100.0  # fallback — 합 0 일 리는 거의 없지만 0 나누기 방지

    pct = (weighted_sum / score_max) * 100.0
    # 0~100 클램프
    pct = max(0.0, min(100.0, pct))

    grade = "F"
    for threshold, g in GRADE_THRESHOLDS:
        if pct >= threshold:
            grade = g
            break

    return weighted_sum, score_max, pct, grade


# ─── mock 응답 생성 ────────────────────────────────────────────────────


def _mock_response(
    case_meta: dict[str, Any], user_answer: str, weights: dict[str, int]
) -> dict[str, Any]:
    """API 키 미설정 또는 mock 모드 시 디폴트 응답.

    Generates a deterministic but realistic-looking mock:
    - 각 기준 score = max * 0.7 (rich 는 1, miss 는 0)
    - eval_notes 는 자료 일반 안내 문구
    - diff_segments 는 user_answer 의 첫 100자 (match 1개) — 자의 X
    """
    # 기준별 mock score
    def _mock_criterion(key: str, max_val: float, comment: str) -> dict[str, Any]:
        if key == "miss":
            score = 0.0
        elif key == "rich":
            score = 1.0  # Lv.1 수준 가정
        else:
            score = round(max_val * 0.7, 1)
        return {
            "key": key,
            "score": score,
            "max": max_val,
            "comment": comment,
        }

    criteria = [
        _mock_criterion("mnem", 4.0, "[mock] 두문자 풀이형 키워드 부분 반영"),
        _mock_criterion("color", 12.0, "[mock] 색 강조 키워드 일부 반영"),
        _mock_criterion("under", 2.0, "[mock] 밑줄 강조 일부 반영"),
        _mock_criterion("outline", 3.0, "[mock] 목차 구조 Lv.1 기준 부분 일치"),
        _mock_criterion("sem", 10.0, "[mock] 의미 유사도 양호"),
        _mock_criterion("rich", 2.0, "[mock] Lv.1 수준 답안"),
        _mock_criterion("miss", 0.0, "[mock] 일부 논점 누락 가능 — 실 채점 필요"),
    ]
    # diff_segments — user_answer 앞 100자 match (자의 텍스트 생성 X)
    head = (user_answer or "").strip()[:120]
    diff_segments: list[dict[str, str]] = []
    if head:
        diff_segments.append({"type": "match", "text": head})
    if len(user_answer or "") > 120:
        diff_segments.append({"type": "match", "text": "…(이하 생략)"})

    return {
        "criteria": criteria,
        "eval_notes": {
            "strength": "[mock] 사용자 답안 구조가 표면적으로 기준에 맞음",
            "caution": "[mock] 자료 인용 정확성은 실 채점 필요",
            "missing": "[mock] mock 응답이므로 누락 논점 분석 불가 — ANTHROPIC_API_KEY 설정 후 재채점",
        },
        "diff_segments": diff_segments,
    }


def _is_mock_mode(model: str | None, *, force_mock: bool | None = None) -> bool:
    """mock 모드 판정.

    우선순위:
    1. force_mock=True/False 명시 (호출자 강제)
    2. model=='mock'
    3. env LAWEAR_GRADER_MOCK=1
    4. ANTHROPIC_API_KEY 미설정 → 자동 mock
    5. anthropic SDK 미설치 → 자동 mock
    """
    if force_mock is True:
        return True
    if force_mock is False:
        return False
    if model == "mock":
        return True
    if os.environ.get("LAWEAR_GRADER_MOCK") in ("1", "true", "yes"):
        return True
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if not _ANTHROPIC_AVAILABLE:
        return True
    return False


# ─── Anthropic 호출 (재시도 포함) ──────────────────────────────────────


def _call_anthropic(
    system_prompt: str, user_message: str, *, model: str
) -> tuple[str, dict[str, Any]]:
    """Anthropic messages.create 호출 + 429 자동 재시도.

    Returns:
        (response_text, usage_dict)

    Raises:
        GraderApiKeyMissingError, GraderRateLimitError, GraderBadGatewayError
    """
    if not _ANTHROPIC_AVAILABLE or anthropic is None:
        raise GraderApiKeyMissingError()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise GraderApiKeyMissingError()

    client = anthropic.Anthropic()

    # system 은 ephemeral 캐시 (Q19 채택 — 토큰 ~30% 절감)
    # NOTE: ephemeral cache_control 은 anthropic SDK 0.20+ 지원
    system_blocks = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    messages = [{"role": "user", "content": user_message}]

    last_err: Exception | None = None
    for attempt in range(1, RATE_LIMIT_RETRIES + 1):
        try:
            print(
                f"[Grader] anthropic call model={model} attempt={attempt}/{RATE_LIMIT_RETRIES}",
                file=sys.stderr,
            )
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=messages,
            )
        except Exception as e:  # noqa: BLE001
            # anthropic SDK 예외 종류: anthropic.RateLimitError, APIError 등
            err_str = type(e).__name__ + ": " + str(e)
            last_err = e
            # 429 / RateLimit → 재시도
            if "RateLimit" in type(e).__name__ or "429" in err_str:
                print(
                    f"[Grader] 429 rate_limit, retry={attempt} backoff={RATE_LIMIT_BACKOFF_SEC}s",
                    file=sys.stderr,
                )
                if attempt < RATE_LIMIT_RETRIES:
                    time.sleep(RATE_LIMIT_BACKOFF_SEC)
                    continue
                raise GraderRateLimitError(
                    f"anthropic rate_limit after {RATE_LIMIT_RETRIES} retries: {err_str}"
                ) from e
            # 그 외 (502/500/APIError) → 즉시 bad_gateway
            print(f"[Grader] anthropic bad_gateway: {err_str}", file=sys.stderr)
            raise GraderBadGatewayError(f"anthropic call failed: {err_str}") from e

        # 응답 텍스트 추출
        text_parts: list[str] = []
        for block in resp.content:
            # block 은 anthropic.types.TextBlock — type='text', text=...
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
        response_text = "".join(text_parts)

        # usage 추출 (있으면)
        usage: dict[str, Any] = {}
        if hasattr(resp, "usage") and resp.usage is not None:
            try:
                usage = {
                    "input_tokens": getattr(resp.usage, "input_tokens", None),
                    "output_tokens": getattr(resp.usage, "output_tokens", None),
                    "cache_creation_input_tokens": getattr(
                        resp.usage, "cache_creation_input_tokens", None
                    ),
                    "cache_read_input_tokens": getattr(
                        resp.usage, "cache_read_input_tokens", None
                    ),
                }
            except AttributeError:
                pass

        return response_text, usage

    # 도달 불가 — 위에서 모두 raise/return
    raise GraderBadGatewayError(
        f"anthropic exhausted retries: {last_err}"
    )


# ─── 공용 API ──────────────────────────────────────────────────────────


def validate_weights(weights: dict[str, int]) -> None:
    """가중치 검증: 합계 100 + 7키 모두 존재.

    Raises:
        ValueError: 합계 != 100 또는 키 누락 (handler 에서 409 weights_invalid 매핑).
    """
    missing = [k for k in CRITERION_KEYS if k not in weights]
    if missing:
        raise ValueError(f"weights missing keys: {missing}")
    total = sum(int(weights[k]) for k in CRITERION_KEYS)
    if total != 100:
        raise ValueError(f"weights sum must be 100, got {total}")


def grade(
    case_meta: dict[str, Any],
    user_answer: str,
    weights: dict[str, int] | None = None,
    *,
    model: str | None = None,
    force_mock: bool | None = None,
) -> dict[str, Any]:
    """채점 핵심 진입점.

    Args:
        case_meta: cases.get_case() 반환 dict
                   (id, subject_kor, category, file, case_no, title, points,
                    md_body / lv1 / lv4 / origin).
        user_answer: 사용자 답안 텍스트 (빈 문자열 거부는 호출자 책임 — POST handler 의 400).
        weights: 가중치 dict (None → DEFAULT_WEIGHTS).
        model: Claude 모델명 (None → DEFAULT_MODEL='claude-opus-4-7').
               'mock' 지정 시 강제 mock 응답.
        force_mock: True/False 명시 강제 (테스트용).

    Returns:
        {
          "model":          "claude-opus-4-7" 또는 "mock",
          "score_total":    14.0,
          "score_max":      85.0,        (miss 제외 weight 합)
          "score_pct":      82.4,
          "grade":          "B",
          "weights_applied": {"mnem":20,...},
          "criteria": [
            {"key":"mnem","score":3,"max":4,"weight":20,"comment":"..."}, ... x7
          ],
          "eval_notes":     {"strength":"...","caution":"...","missing":"..."},
          "diff_segments":  [{"type":"match|miss|partial","text":"..."}, ...],
          "raw_response":   "...",      (mock 시 None)
          "usage":          {...} or {},
          "elapsed_sec":    1.23,
          "is_mock":        bool,
        }

    Raises:
        GraderApiKeyMissingError, GraderRateLimitError, GraderBadGatewayError,
        GraderParseError, ValueError (weights 검증).
    """
    started = time.monotonic()

    # 가중치 기본값 + 검증
    if weights is None:
        weights = dict(DEFAULT_WEIGHTS)
    validate_weights(weights)

    # 모델
    selected_model = model or DEFAULT_MODEL

    # mock 판정
    is_mock = _is_mock_mode(selected_model, force_mock=force_mock)
    if selected_model == "mock":
        # 명시 mock 호출 시 model 라벨도 'mock'
        model_label = "mock"
    elif is_mock:
        # 환경 미설정으로 자동 mock 시도 — 라벨에 명시
        model_label = f"mock(auto:no_api_key)" if not os.environ.get("ANTHROPIC_API_KEY") else "mock"
    else:
        model_label = selected_model

    # 프롬프트 빌드
    system_prompt, user_message = _build_prompt(case_meta, user_answer, weights)

    raw_response: str | None = None
    usage: dict[str, Any] = {}

    if is_mock:
        print(f"[Grader] MOCK mode (model_label={model_label}) case_id={case_meta.get('id')}", file=sys.stderr)
        parsed = _mock_response(case_meta, user_answer, weights)
    else:
        # 실 API 호출
        try:
            raw_response, usage = _call_anthropic(
                system_prompt, user_message, model=selected_model
            )
        except (GraderApiKeyMissingError, GraderRateLimitError, GraderBadGatewayError):
            raise
        # JSON 파싱
        parsed = _parse_response(raw_response)

    # 점수 산정
    total, score_max, pct, grade_letter = _compute_score(parsed["criteria"], weights)

    # criteria 에 weight 주입 (응답엔 없음)
    criteria_with_weight: list[dict[str, Any]] = []
    for c in parsed["criteria"]:
        key = c.get("key")
        if key not in CRITERION_KEYS:
            continue
        criteria_with_weight.append(
            {
                "key": key,
                "score": c.get("score"),
                "max": c.get("max"),
                "weight": int(weights.get(key, 0)),
                "comment": c.get("comment", ""),
            }
        )

    elapsed = time.monotonic() - started
    result = {
        "model": model_label,
        "score_total": round(total, 2),
        "score_max": round(score_max, 2),
        "score_pct": round(pct, 2),
        "grade": grade_letter,
        "weights_applied": dict(weights),
        "criteria": criteria_with_weight,
        "eval_notes": parsed["eval_notes"],
        "diff_segments": parsed.get("diff_segments", []),
        "raw_response": raw_response,
        "usage": usage,
        "elapsed_sec": round(elapsed, 3),
        "is_mock": is_mock,
    }

    print(
        f"[Grader] done case_id={case_meta.get('id')} score={result['score_total']}/"
        f"{result['score_max']} pct={result['score_pct']} grade={grade_letter} "
        f"time={elapsed:.2f}s mock={is_mock}",
        file=sys.stderr,
    )
    return result


# ─── CLI (수동 실 호출 테스트용) ────────────────────────────────────────


def main() -> int:
    """CLI: python3 grader.py --case CASE_ID [--answer-file PATH] [--mock]

    실 API 호출 또는 mock 시뮬레이션. 결과 JSON 을 stdout 으로 출력.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Lawear Grader CLI (단위 테스트/디버그용)")
    parser.add_argument("--case", help="case_id (DB 조회). 없으면 --case-json 사용")
    parser.add_argument(
        "--case-json", help="case_meta JSON 파일 경로 (DB 없이 직접 주입)"
    )
    parser.add_argument(
        "--answer",
        default="테스트 답안: A조합은 비법인사단으로 권리능력 범위 내에서 도급계약을 체결하였다.",
        help="사용자 답안 텍스트",
    )
    parser.add_argument("--answer-file", help="답안 파일 (--answer 우선)")
    parser.add_argument("--mock", action="store_true", help="mock 모드 강제")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"모델 (기본 {DEFAULT_MODEL})")
    args = parser.parse_args()

    # env 로드 (있으면)
    try:
        from env_loader import load_env
        load_env()
    except ImportError:
        pass

    # case_meta 로드
    case_meta: dict[str, Any]
    if args.case_json:
        with open(args.case_json, encoding="utf-8") as f:
            case_meta = json.load(f)
    elif args.case:
        # DB 조회
        import db as db_mod
        import cases as cases_mod

        db_path = os.environ.get(
            "LAWEAR_EXAM_DB",
            str(Path(__file__).parent.resolve() / "exam.db"),
        )
        with db_mod.get_conn(db_path) as conn:
            case_meta = cases_mod.get_case(conn, args.case)
    else:
        # 더미 case_meta (mock 테스트)
        case_meta = {
            "id": "test_case_dummy",
            "subject_kor": "민법",
            "category": "테스트",
            "file": "test01",
            "case_no": "01",
            "title": "더미 케이스",
            "points": 17,
            "md_body": "## 원본\n사실관계 + 문제 + 답안 dummy\n## Lv.1\n목차 dummy",
        }

    # 답안 파일 우선
    if args.answer_file:
        with open(args.answer_file, encoding="utf-8") as f:
            user_answer = f.read()
    else:
        user_answer = args.answer

    # mock 강제
    force_mock = True if args.mock else None
    model = "mock" if args.mock else args.model

    result = grade(case_meta, user_answer, model=model, force_mock=force_mock)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
