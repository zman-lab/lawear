#!/usr/bin/env python3
"""음성 답안 (STT) 오타 교정 — Claude API 2차 패스.

lawear-9bdc/typo-system-v2 작업 (2026-05-19):
- typo_corrector.py (정적 사전 1차 패스) 이후 호출되는 2차 패스.
- typo_dict.json 에 없는 STT 오타를 Claude API 로 보수적 교정.
- ANTHROPIC_API_KEY 없으면 graceful (빈 결과 반환).

설계:
- R-09 자의적 해석 금지: 명백한 STT 오타만, 조문번호/두문자 추정 금지.
- 표준 라이브러리만 사용 (urllib.request, json) — 외부 의존성 0.
- timeout 10s 기본, 예외 시 (text, []) 반환 — 사용자 체감 영향 0.
- 답안 길이 8000자 초과 시 skip (비용 보호).
- 1차 패스에서 이미 적용된 from 은 중복 회피 (set 비교).

핵심 함수:
- `correct_with_ai(text, static_corrections=...) -> (corrected, ai_corrections)`
- `is_available() -> bool`  (ANTHROPIC_API_KEY 환경 검사)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

# ─── 상수 ────────────────────────────────────────────────────────────────

_ANTHROPIC_API_KEY_ENV: str = "ANTHROPIC_API_KEY"
_API_URL: str = "https://api.anthropic.com/v1/messages"
_API_VERSION: str = "2023-06-01"

_DEFAULT_MODEL: str = "claude-haiku-4-5"
_DEFAULT_TIMEOUT: float = 10.0
_DEFAULT_MAX_TOKENS: int = 1024
_MAX_INPUT_CHARS: int = 8000


_SYSTEM_PROMPT: str = (
    "당신은 법무사 2차 시험 음성 답안(STT 입력) 의 오타 교정 전문가입니다.\n"
    "\n"
    "[규칙]\n"
    "1. 법률 용어 + 시험 컨텍스트 + 발음 유사도로 명백한 오타만 교정.\n"
    "2. 조문 번호(제103/104/108/126/397 등) 는 절대 추정 X — 숫자가 다르면 그대로 둠.\n"
    "3. 두문자(축약어) 는 추정 X — 정확히 모르면 그대로 둠.\n"
    "4. 의심스러우면 교정 X. R-09 자의적 해석 금지.\n"
    "5. 동일 from 중복 X — 한 번만 보고.\n"
    "6. 응답: JSON 만, 추가 설명/마크다운 X.\n"
    "\n"
    "[응답 형식 — JSON only]\n"
    '{"corrections": [{"from": "원본", "to": "교정", "reason": "근거 1줄"}]}\n'
    "\n"
    "교정할 항목 없으면 {\"corrections\": []} 반환.\n"
)


# ─── API 호출 ────────────────────────────────────────────────────────────


def _build_user_prompt(text: str, applied_static: list[dict[str, Any]]) -> str:
    if applied_static:
        sample = ", ".join(
            f"{c.get('from')}→{c.get('to')}"
            for c in applied_static[:5]
            if c.get("from") and c.get("to")
        )
        note = f"이미 정적 사전으로 교정된 항목 ({len(applied_static)}건): {sample}.\n"
    else:
        note = "정적 사전 매칭 0건.\n"
    return (
        f"{note}"
        "\n"
        "다음 답안에서 추가 STT 오타를 찾아 JSON 으로 응답:\n"
        "\n"
        "---\n"
        f"{text}\n"
        "---\n"
    )


def _call_anthropic_api(
    model: str,
    system: str,
    user: str,
    api_key: str,
    timeout: float,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        _API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _extract_text(response: dict[str, Any]) -> str:
    content = response.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return "".join(parts).strip()


def _parse_corrections(text: str) -> list[dict[str, Any]]:
    s = text.strip()
    # ```json ... ``` 또는 ``` ... ``` 코드블록 제거
    if s.startswith("```"):
        lines = s.split("\n", 1)
        if len(lines) > 1:
            s = lines[1]
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
        if s.lower().startswith("json"):
            s = s[4:].lstrip()
    obj: Any
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        # 응답 안에 JSON 부분만 substring 추출 시도
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(obj, dict):
        return []
    corrs = obj.get("corrections")
    if not isinstance(corrs, list):
        return []
    out: list[dict[str, Any]] = []
    seen_from: set[str] = set()
    for c in corrs:
        if not isinstance(c, dict):
            continue
        from_v = c.get("from")
        to_v = c.get("to")
        reason = c.get("reason") or "AI 음성 STT 추론 교정"
        if not isinstance(from_v, str) or not isinstance(to_v, str):
            continue
        if not from_v or not to_v or from_v == to_v:
            continue
        if from_v in seen_from:
            continue
        seen_from.add(from_v)
        out.append(
            {
                "from": from_v,
                "to": to_v,
                "reason": str(reason),
                "source": "ai",
            }
        )
    return out


# ─── 공개 API ────────────────────────────────────────────────────────────


def is_available() -> bool:
    """ANTHROPIC_API_KEY 환경에 있는지 확인."""
    return bool(os.environ.get(_ANTHROPIC_API_KEY_ENV))


def correct_with_ai(
    text: str,
    *,
    static_corrections: list[dict[str, Any]] | None = None,
    model: str | None = None,
    timeout: float | None = None,
    api_key: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """텍스트에 AI 2차 패스 교정 적용 (graceful).

    Args:
        text:               1차 (typo_dict) 패스 적용된 텍스트.
        static_corrections: 1차 패스 결과 (프롬프트 컨텍스트 + 중복 회피).
        model:              모델 ID 또는 None (default haiku-4-5).
        timeout:            초 단위 또는 None (default 10).
        api_key:            override 또는 None (환경변수).

    Returns:
        (corrected_text, ai_corrections)
          - corrected_text:  AI 교정 적용된 텍스트 (1차 결과 위에 누적).
          - ai_corrections:  list[{from, to, reason, source: "ai"}]

    실패 시 (key 없음 / timeout / parse 에러) (text, []) 반환 — graceful.
    """
    if not isinstance(text, str) or not text:
        return text or "", []

    # 비용 보호 — 너무 긴 답안 skip
    if len(text) > _MAX_INPUT_CHARS:
        return text, []

    key = api_key or os.environ.get(_ANTHROPIC_API_KEY_ENV) or ""
    if not key:
        return text, []

    static_corrs: list[dict[str, Any]] = static_corrections or []
    used_model = model or _DEFAULT_MODEL
    used_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT

    user_prompt = _build_user_prompt(text, static_corrs)

    try:
        resp = _call_anthropic_api(used_model, _SYSTEM_PROMPT, user_prompt, key, used_timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
        print(f"[AICorrector] API call failed: {type(e).__name__}: {e}", file=sys.stderr)
        return text, []
    except json.JSONDecodeError as e:
        print(f"[AICorrector] response JSON decode failed: {e}", file=sys.stderr)
        return text, []
    except Exception as e:
        print(f"[AICorrector] unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return text, []

    text_response = _extract_text(resp)
    if not text_response:
        return text, []

    ai_corrs = _parse_corrections(text_response)
    if not ai_corrs:
        return text, []

    # 1차 패스에서 이미 적용된 from 은 skip (중복 회피)
    static_froms: set[str] = {
        c.get("from") for c in static_corrs if isinstance(c, dict) and c.get("from")
    }

    # 긴 from 부터 적용 (substring 충돌 방지)
    ai_corrs.sort(key=lambda c: -len(c.get("from") or ""))
    corrected = text
    applied: list[dict[str, Any]] = []
    for c in ai_corrs:
        f = c.get("from")
        t = c.get("to")
        if not f or not t or f in static_froms:
            continue
        if f in corrected:
            corrected = corrected.replace(f, t)
            applied.append(c)

    return corrected, applied
