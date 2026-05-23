#!/usr/bin/env python3
"""음성 답안 (STT) 오타 교정 — 정적 사전 1차 패스.

lawear-e571/typo-system 작업 (2026-05-19):
- 사용자 답안은 음성 녹음(STT) 입력이라 오타 다수 발생.
- 법률 용어 + 시험 컨텍스트 기반 정적 사전으로 명백한 오타 1차 교정.
- Opus SE (스킬 `/dev-le-typo-fix`) 가 사전 매칭 후 추가 문맥 분석.

핵심 함수:
- `load_typo_dict(path=None) -> dict`     : typo_dict.json 로드 (없으면 빈 사전).
- `apply_static_replacements(text, d)`    : 사전 매칭 적용 + correction list 반환.
- `correct(text, dict_path=None)`         : 1-shot helper — text → (corrected, corrections).

설계:
- R-09 자의적 해석 금지: 명시된 사전 매칭만 적용. 자유 추측 X.
- 조문 번호 (preserve_terms) 는 절대 변경 X.
- 정렬: 긴 키부터 매칭 (예 "통정 허위 표시" > "통정") — 부분 매칭 충돌 방지.
- 대소문자/공백 normalize 는 적용 X — 음성 인식은 한글이고 띄어쓰기 자체가 오류 단서.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

# ─── 상수 ────────────────────────────────────────────────────────────────

# typo_dict.json 디폴트 경로 — 본 모듈과 같은 디렉토리
_DEFAULT_DICT_PATH: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "typo_dict.json"
)

# 환경변수 override (테스트/외부 사전 주입용)
_ENV_DICT_PATH: str = "LAWEAR_TYPO_DICT_PATH"

# 캐시 (load_typo_dict 결과 단일 인스턴스)
_DICT_CACHE: dict[str, Any] | None = None
_DICT_CACHE_PATH: str | None = None


# ─── 로딩 ────────────────────────────────────────────────────────────────


def _resolve_dict_path(path: str | None) -> str:
    """경로 우선순위: 인자 > 환경변수 > 기본값."""
    if path:
        return path
    env_path = os.environ.get(_ENV_DICT_PATH)
    if env_path:
        return env_path
    return _DEFAULT_DICT_PATH


def load_typo_dict(path: str | None = None, *, force_reload: bool = False) -> dict[str, Any]:
    """typo_dict.json 로드. 파일 없으면 빈 사전 반환 (graceful).

    Args:
        path:          명시 경로 (없으면 환경변수 / 기본값).
        force_reload:  True 면 캐시 무시.

    Returns:
        {
          "version": str,
          "static_replacements": dict[str, str],
          "context_patterns": list[dict],
          "preserve_terms": list[str]
        }
        파일 없거나 파싱 실패 시 빈 구조 반환.
    """
    global _DICT_CACHE, _DICT_CACHE_PATH

    resolved = _resolve_dict_path(path)

    if not force_reload and _DICT_CACHE is not None and _DICT_CACHE_PATH == resolved:
        return _DICT_CACHE

    empty: dict[str, Any] = {
        "version": "0.0",
        "static_replacements": {},
        "context_patterns": [],
        "preserve_terms": [],
    }

    if not os.path.isfile(resolved):
        _DICT_CACHE = empty
        _DICT_CACHE_PATH = resolved
        return empty

    try:
        with open(resolved, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        _DICT_CACHE = empty
        _DICT_CACHE_PATH = resolved
        return empty

    if not isinstance(raw, dict):
        _DICT_CACHE = empty
        _DICT_CACHE_PATH = resolved
        return empty

    # 정규화 — 누락 키는 기본값으로 채움
    static = raw.get("static_replacements") or {}
    if not isinstance(static, dict):
        static = {}
    static = {str(k): str(v) for k, v in static.items() if isinstance(k, str) and isinstance(v, str) and k and v and k != v}

    patterns = raw.get("context_patterns") or []
    if not isinstance(patterns, list):
        patterns = []
    patterns = [p for p in patterns if isinstance(p, dict) and isinstance(p.get("pattern"), str)]

    preserve = raw.get("preserve_terms") or []
    if not isinstance(preserve, list):
        preserve = []
    preserve = [str(t) for t in preserve if isinstance(t, str) and t]

    result: dict[str, Any] = {
        "version": str(raw.get("version") or "0.0"),
        "static_replacements": static,
        "context_patterns": patterns,
        "preserve_terms": preserve,
    }

    _DICT_CACHE = result
    _DICT_CACHE_PATH = resolved
    return result


def clear_cache() -> None:
    """캐시 클리어 (테스트/사전 갱신 후 호출)."""
    global _DICT_CACHE, _DICT_CACHE_PATH
    _DICT_CACHE = None
    _DICT_CACHE_PATH = None


# ─── 사전 매칭 적용 ──────────────────────────────────────────────────────


def _is_preserved(text: str, start: int, end: int, preserve_terms: list[str]) -> bool:
    """매칭 위치가 preserve_terms 중첩되는지 검사.

    조문 번호 인접 영역 (예 "제397조") 은 절대 치환 X.
    ±15자 윈도우 — 조문 번호와 키워드 사이 띄어쓰기/조사 허용.
    """
    if not preserve_terms:
        return False
    window_start = max(0, start - 15)
    window_end = min(len(text), end + 15)
    window = text[window_start:window_end]
    for term in preserve_terms:
        if term in window:
            return True
    return False


def apply_static_replacements(
    text: str,
    typo_dict: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """정적 사전 매칭 적용. 길이 내림차순으로 매칭 — 부분 충돌 방지.

    Args:
        text:      원본 답안 텍스트 (사용자 STT 입력).
        typo_dict: load_typo_dict() 결과 또는 None (기본 사전 로드).

    Returns:
        (corrected_text, corrections)
          - corrected_text: 치환 적용된 텍스트.
          - corrections:    [{"from": str, "to": str, "reason": str, "source": "static_dict"}]
            각 적용된 치환 1건 1 entry — 중복 위치 단일 entry (count 미포함, list 길이 = 치환 횟수).
    """
    if not isinstance(text, str) or not text:
        return text or "", []

    if typo_dict is None:
        typo_dict = load_typo_dict()

    static_map: dict[str, str] = typo_dict.get("static_replacements") or {}
    preserve_terms: list[str] = typo_dict.get("preserve_terms") or []

    if not static_map:
        return text, []

    # 긴 키부터 매칭 (substring 충돌 방지)
    sorted_keys = sorted(static_map.keys(), key=lambda k: (-len(k), k))

    corrections: list[dict[str, Any]] = []
    out_chars: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        matched = False
        for key in sorted_keys:
            klen = len(key)
            if klen == 0 or i + klen > n:
                continue
            if text[i:i + klen] != key:
                continue
            # preserve_terms 인접 보호
            if _is_preserved(text, i, i + klen, preserve_terms):
                continue
            replacement = static_map[key]
            corrections.append({
                "from": key,
                "to": replacement,
                "reason": "음성 STT 정적 사전 매칭",
                "source": "static_dict",
            })
            out_chars.append(replacement)
            i += klen
            matched = True
            break

        if not matched:
            out_chars.append(text[i])
            i += 1

    corrected = "".join(out_chars)
    return corrected, corrections


def correct(
    text: str,
    *,
    dict_path: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """1-shot helper — text + (optional path) → (corrected, corrections).

    Args:
        text:      원본 답안 텍스트.
        dict_path: typo_dict.json 경로 (override). None 이면 기본/환경변수.

    Returns:
        (corrected_text, corrections) — apply_static_replacements 1:1 위임.
    """
    d = load_typo_dict(dict_path)
    return apply_static_replacements(text, d)


# ─── grader 프롬프트 보조 (음성 인식 관용 안내) ───────────────────────────


# 사용자 명시 핵심 오타 (attempt 9 발견 + 명시 보고)
_PRIORITY_EXAMPLE_KEYS: tuple[str, ...] = (
    "파산관제인",
    "통정표시",
    "선한간리주의",
    "아기",
    "법류행위",
    "표면대리",
    "채취",
    "체대",
)


def build_typo_tolerance_note(typo_dict: dict[str, Any] | None = None) -> str:
    """grader.py SYSTEM_PROMPT 에 삽입할 음성 인식 관용 안내문 빌드.

    사용자 명시 우선 키를 먼저 노출 (대표 예시 ~10건, 프롬프트 길이 절약).
    빈 사전이면 빈 문자열 반환 — 호출자가 prompt 분기.
    """
    if typo_dict is None:
        typo_dict = load_typo_dict()

    static_map: dict[str, str] = typo_dict.get("static_replacements") or {}
    if not static_map:
        return ""

    # 우선 노출 키 (사전에 존재하는 것만)
    sample_keys: list[str] = [k for k in _PRIORITY_EXAMPLE_KEYS if k in static_map]
    # 부족하면 긴 키부터 보충 (8건 채우기)
    if len(sample_keys) < 8:
        rest = [k for k in sorted(static_map.keys(), key=lambda k: (-len(k), k)) if k not in sample_keys]
        sample_keys.extend(rest[: max(0, 8 - len(sample_keys))])

    examples = ", ".join(f"{k}={static_map[k]}" for k in sample_keys)

    return (
        "[음성 인식 오타 관용]\n"
        "- 사용자 답안은 음성 녹음(STT) 입력이라 오타 가능성 있음.\n"
        "- 법무사 시험 컨텍스트 + 법률 용어 사전 기반으로 명백한 오타는 의도된 정답으로 해석.\n"
        f"- 예: {examples} 등.\n"
        "- 단, 조문 번호(제103/104/108/126/397 등)와 핵심 두문자는 오타 인정 X — 그건 진짜 모르는 것.\n"
        "- 오타 교정으로 인정한 항목은 eval_notes.typo_corrections 에 명시 가능 "
        "(list[{from, to, reason}], 없으면 null).\n"
    )


# ─── 유틸 ────────────────────────────────────────────────────────────────


def dict_entry_count(typo_dict: dict[str, Any] | None = None) -> int:
    """현재 사전의 static_replacements 항목 수 (테스트/디버그)."""
    if typo_dict is None:
        typo_dict = load_typo_dict()
    return len(typo_dict.get("static_replacements") or {})
