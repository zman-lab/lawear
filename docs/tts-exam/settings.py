#!/usr/bin/env python3
"""Settings API 비즈니스 로직 (Step 8).

dev-design archive #48 §3-2 PUT /api/settings + §4-2 settings 테이블 1:1.
dev-impl-plan #51 Step 8 표 — weights/bias/voice 조회/저장 + 합계 100 검증.

핵심:
- `load_all(conn)`            : GET /api/settings  → {weights, bias, voice}
- `save_settings(conn, ...)`  : PUT /api/settings  → 부분 갱신 + 검증 + COMMIT
- `validate_bias(bias)`       : 4키 + 범위 검증
- `validate_voice(voice)`     : lang in ('ko-KR','en-US'), silence_sec 1~60

설계 결정:
- weights 검증은 grader.validate_weights 재사용 (단일 진리원).
- 부분 갱신: PUT body 에서 제공된 섹션(weights/bias/voice)만 UPDATE.
- 트랜잭션: 단일 BEGIN → 1~3 UPDATE → COMMIT (실패 시 ROLLBACK).
- DB row 부재 시 INSERT (멱등 — 마이그 v1 초기 INSERT OR IGNORE 보호).
- 응답: 항상 전체 settings 반환 (GET 응답과 동일 형식).
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from typing import Any

import grader as grader_mod

# ─── 설정 키 (DB row PK) ────────────────────────────────────────────
KEY_WEIGHTS: str = "weights"
KEY_BIAS: str = "bias"
KEY_VOICE: str = "voice"
KEY_GRADING_MODE: str = "grading_mode"
# Phase 4 (lawear-e571, 2026-05-19): 가중치 버전 표시 (DB 마이그 없이 logical 버전)
KEY_WEIGHTS_VERSION: str = "weights_version"

ALL_KEYS: tuple[str, ...] = (
    KEY_WEIGHTS,
    KEY_BIAS,
    KEY_VOICE,
    KEY_GRADING_MODE,
    KEY_WEIGHTS_VERSION,
)

# ─── 디폴트 (마이그 v1/v3 초기 INSERT 와 1:1 — 동기화 의무) ────────────
DEFAULT_WEIGHTS: dict[str, int] = dict(grader_mod.DEFAULT_WEIGHTS)
# Phase 4 — 신규 채점 가중치 버전 (default v6)
DEFAULT_WEIGHTS_VERSION: int = grader_mod.DEFAULT_WEIGHTS_VERSION

DEFAULT_BIAS: dict[str, int] = {
    "err_weight": 60,
    "stale_weight": 40,
    "err_threshold": 3,
    "stale_threshold_days": 14,
}

DEFAULT_VOICE: dict[str, Any] = {
    "lang": "ko-KR",
    "silence_sec": 3,
}

# Step 13 — Claude Code 외부 채점이 기본 (사용자 명시 2026-05-16:
#   "ANTHROPIC_API_KEY 미보유 → manual, 키 생기면 auto 로 전환").
DEFAULT_GRADING_MODE: str = "manual"

# ─── voice 허용값 ────────────────────────────────────────────────────
ALLOWED_VOICE_LANGS: tuple[str, ...] = ("ko-KR", "en-US")
VOICE_SILENCE_MIN: int = 1
# Step 18 — 사용자 명시 (2026-05-16): "잘 생각 안 나면 고민할 수도 있단 말야"
#   기존 max 10초 → 60초로 확장. 1초 단위 그대로.
VOICE_SILENCE_MAX: int = 60

# ─── grading_mode 허용값 ─────────────────────────────────────────────
GRADING_MODE_MANUAL: str = "manual"
GRADING_MODE_AUTO: str = "auto"
ALLOWED_GRADING_MODES: tuple[str, ...] = (GRADING_MODE_MANUAL, GRADING_MODE_AUTO)

# ─── bias 허용 범위 ──────────────────────────────────────────────────
BIAS_WEIGHT_MIN: int = 0
BIAS_WEIGHT_MAX: int = 100
BIAS_ERR_THRESHOLD_MIN: int = 1
BIAS_STALE_THRESHOLD_MIN: int = 1


# ─── 예외 ─────────────────────────────────────────────────────────────


class SettingsValidationError(Exception):
    """입력 검증 실패. error_code 는 핸들러가 HTTP status 매핑에 사용.

    dev-design #48 §3-3 ErrorCode:
        weights_invalid (HTTP 409)
        bad_request     (HTTP 400)
    """

    def __init__(self, message: str, error_code: str = "bad_request") -> None:
        super().__init__(message)
        self.error_code = error_code


# ─── 유틸 ─────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    """ISO-8601 UTC ('YYYY-MM-DDTHH:MM:SSZ')."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coerce_int(value: Any, *, key: str) -> int:
    """JSON int 변환 + 검증. 실패 시 SettingsValidationError(bad_request)."""
    if isinstance(value, bool):
        # JSON bool 은 int 서브타입이지만 의도와 다름 — 거부.
        raise SettingsValidationError(
            f"{key} must be int, got bool", "bad_request"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as e:
            raise SettingsValidationError(
                f"{key} must be int, got {value!r}", "bad_request"
            ) from e
    raise SettingsValidationError(
        f"{key} must be int, got {type(value).__name__}", "bad_request"
    )


# ─── 검증 (외부 노출 — handler / tests 모두 사용) ────────────────────────


def validate_weights(weights: dict[str, Any]) -> dict[str, int]:
    """가중치 7키 + 합계 100 검증 (grader.validate_weights 위임).

    Returns:
        검증/정수화된 weights (그대로 DB JSON 저장 가능).

    Raises:
        SettingsValidationError(weights_invalid): grader 의 ValueError 를 매핑.
    """
    if not isinstance(weights, dict):
        raise SettingsValidationError(
            "weights must be object", "weights_invalid"
        )
    # 정수화 + 키 누락은 grader 가 잡음
    coerced: dict[str, int] = {}
    for k in grader_mod.CRITERION_KEYS:
        if k in weights:
            coerced[k] = _coerce_int(weights[k], key=f"weights.{k}")
    try:
        grader_mod.validate_weights(coerced)
    except ValueError as e:
        raise SettingsValidationError(str(e), "weights_invalid") from e
    return coerced


def validate_bias(bias: dict[str, Any]) -> dict[str, int]:
    """bias 4키 + 정수 + 범위 검증.

    Returns:
        검증/정수화된 bias dict.

    Raises:
        SettingsValidationError(bad_request).
    """
    if not isinstance(bias, dict):
        raise SettingsValidationError("bias must be object", "bad_request")

    missing = [k for k in DEFAULT_BIAS if k not in bias]
    if missing:
        raise SettingsValidationError(
            f"bias missing keys: {missing}", "bad_request"
        )

    coerced: dict[str, int] = {}
    for k in DEFAULT_BIAS:
        coerced[k] = _coerce_int(bias[k], key=f"bias.{k}")

    # 범위 검증
    for wk in ("err_weight", "stale_weight"):
        v = coerced[wk]
        if not (BIAS_WEIGHT_MIN <= v <= BIAS_WEIGHT_MAX):
            raise SettingsValidationError(
                f"bias.{wk} must be in [{BIAS_WEIGHT_MIN},{BIAS_WEIGHT_MAX}], got {v}",
                "bad_request",
            )
    if coerced["err_threshold"] < BIAS_ERR_THRESHOLD_MIN:
        raise SettingsValidationError(
            f"bias.err_threshold must be >= {BIAS_ERR_THRESHOLD_MIN}, got {coerced['err_threshold']}",
            "bad_request",
        )
    if coerced["stale_threshold_days"] < BIAS_STALE_THRESHOLD_MIN:
        raise SettingsValidationError(
            f"bias.stale_threshold_days must be >= {BIAS_STALE_THRESHOLD_MIN}, got {coerced['stale_threshold_days']}",
            "bad_request",
        )
    return coerced


def validate_weights_version(value: Any) -> int:
    """Phase 4 — weights_version 검증: 양의 정수만 허용.

    Returns:
        검증된 int.

    Raises:
        SettingsValidationError(bad_request).
    """
    if isinstance(value, bool):
        raise SettingsValidationError(
            "weights_version must be int, got bool", "bad_request"
        )
    if isinstance(value, int):
        v = value
    elif isinstance(value, str):
        try:
            v = int(value)
        except ValueError as e:
            raise SettingsValidationError(
                f"weights_version must be int, got {value!r}", "bad_request"
            ) from e
    else:
        raise SettingsValidationError(
            f"weights_version must be int, got {type(value).__name__}",
            "bad_request",
        )
    if v < 1:
        raise SettingsValidationError(
            f"weights_version must be >= 1, got {v}", "bad_request"
        )
    return v


def validate_grading_mode(mode: Any) -> str:
    """grading_mode 검증: 'manual' | 'auto' 만 허용.

    Args:
        mode: 문자열 (기타 타입은 거부).

    Returns:
        검증된 문자열 ('manual' 또는 'auto').

    Raises:
        SettingsValidationError(bad_request): 허용값 외.
    """
    if not isinstance(mode, str):
        raise SettingsValidationError(
            f"grading_mode must be string, got {type(mode).__name__}",
            "bad_request",
        )
    normalized = mode.strip()
    if normalized not in ALLOWED_GRADING_MODES:
        raise SettingsValidationError(
            f"grading_mode must be one of {ALLOWED_GRADING_MODES}, got {mode!r}",
            "bad_request",
        )
    return normalized


def validate_voice(voice: dict[str, Any]) -> dict[str, Any]:
    """voice 검증: lang enum + silence_sec 범위.

    Returns:
        검증된 voice dict.

    Raises:
        SettingsValidationError(bad_request).
    """
    if not isinstance(voice, dict):
        raise SettingsValidationError("voice must be object", "bad_request")

    coerced: dict[str, Any] = {}

    # lang (필수)
    if "lang" not in voice:
        raise SettingsValidationError("voice.lang is required", "bad_request")
    lang = voice["lang"]
    if not isinstance(lang, str):
        raise SettingsValidationError(
            f"voice.lang must be string, got {type(lang).__name__}", "bad_request"
        )
    if lang not in ALLOWED_VOICE_LANGS:
        raise SettingsValidationError(
            f"voice.lang must be one of {ALLOWED_VOICE_LANGS}, got {lang!r}",
            "bad_request",
        )
    coerced["lang"] = lang

    # silence_sec (필수)
    if "silence_sec" not in voice:
        raise SettingsValidationError(
            "voice.silence_sec is required", "bad_request"
        )
    silence_sec = _coerce_int(voice["silence_sec"], key="voice.silence_sec")
    if not (VOICE_SILENCE_MIN <= silence_sec <= VOICE_SILENCE_MAX):
        raise SettingsValidationError(
            f"voice.silence_sec must be in [{VOICE_SILENCE_MIN},{VOICE_SILENCE_MAX}], got {silence_sec}",
            "bad_request",
        )
    coerced["silence_sec"] = silence_sec
    return coerced


# ─── DB I/O ──────────────────────────────────────────────────────────


def _load_one(conn: sqlite3.Connection, key: str, default: dict[str, Any]) -> dict[str, Any]:
    """settings 단일 키 로드. 부재/파싱실패 시 default."""
    cur = conn.execute(
        "SELECT value_json FROM settings WHERE key = ?", (key,)
    )
    row = cur.fetchone()
    if row is None or row["value_json"] is None:
        return dict(default)
    try:
        parsed = json.loads(row["value_json"])
        if not isinstance(parsed, dict):
            return dict(default)
        return parsed
    except (json.JSONDecodeError, TypeError):
        return dict(default)


def _load_scalar(conn: sqlite3.Connection, key: str, default: str) -> str:
    """settings 단일 키를 scalar 문자열로 로드.

    Step 13 — grading_mode 처럼 dict 가 아닌 단일 문자열 값 로딩.
    """
    cur = conn.execute(
        "SELECT value_json FROM settings WHERE key = ?", (key,)
    )
    row = cur.fetchone()
    if row is None or row["value_json"] is None:
        return default
    try:
        parsed = json.loads(row["value_json"])
        if isinstance(parsed, str):
            return parsed
        return default
    except (json.JSONDecodeError, TypeError):
        return default


def load_grading_mode(conn: sqlite3.Connection) -> str:
    """settings.grading_mode 로드. 부재/오류 시 DEFAULT_GRADING_MODE.

    Step 13 — POST /api/attempts 분기 + 시안 Settings 라디오에 사용.
    """
    raw = _load_scalar(conn, KEY_GRADING_MODE, DEFAULT_GRADING_MODE)
    # 허용값 외는 디폴트로 강등 (R-09 자의적 해석 X, 안전한 fallback)
    if raw not in ALLOWED_GRADING_MODES:
        return DEFAULT_GRADING_MODE
    return raw


def load_weights_version(conn: sqlite3.Connection) -> int:
    """Phase 4 — settings.weights_version 로드 (logical 버전 표시용).

    DB row 부재 → DEFAULT_WEIGHTS_VERSION (v6).
    잘못된 값 → DEFAULT_WEIGHTS_VERSION fallback.
    """
    try:
        cur = conn.execute(
            "SELECT value_json FROM settings WHERE key = ?", (KEY_WEIGHTS_VERSION,)
        )
        row = cur.fetchone()
        if row is None or row["value_json"] is None:
            return DEFAULT_WEIGHTS_VERSION
        v = json.loads(row["value_json"])
        if isinstance(v, int) and v >= 1:
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except (TypeError, ValueError):
                return DEFAULT_WEIGHTS_VERSION
    except (sqlite3.DatabaseError, json.JSONDecodeError):
        pass
    return DEFAULT_WEIGHTS_VERSION


def load_all(conn: sqlite3.Connection) -> dict[str, Any]:
    """전체 settings 조회. 부재 키는 default 채움.

    Returns:
        {"weights": {...}, "bias": {...}, "voice": {...},
         "grading_mode": "manual"|"auto",
         "weights_version": int (Phase 4 — 신규 채점 가중치 버전 표시, default v6)}
    """
    return {
        "weights": _load_one(conn, KEY_WEIGHTS, DEFAULT_WEIGHTS),
        "bias": _load_one(conn, KEY_BIAS, DEFAULT_BIAS),
        "voice": _load_one(conn, KEY_VOICE, DEFAULT_VOICE),
        "grading_mode": load_grading_mode(conn),
        "weights_version": load_weights_version(conn),
    }


def _upsert(conn: sqlite3.Connection, key: str, value: Any, now: str) -> None:
    """INSERT OR REPLACE — 단일 row UPSERT.

    Step 13: value 가 dict 외 scalar (str) 도 허용 — grading_mode 처럼 단일 값.
    """
    conn.execute(
        """
        INSERT INTO settings (key, value_json, updated_at)
             VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
              value_json = excluded.value_json,
              updated_at = excluded.updated_at
        """,
        (key, json.dumps(value, ensure_ascii=False), now),
    )


def save_settings(
    conn: sqlite3.Connection,
    *,
    weights: dict[str, Any] | None = None,
    bias: dict[str, Any] | None = None,
    voice: dict[str, Any] | None = None,
    grading_mode: str | None = None,
    weights_version: int | None = None,
) -> dict[str, Any]:
    """부분 갱신 저장. 제공된 섹션만 UPDATE.

    Args:
        weights/bias/voice/grading_mode/weights_version: 각각 None 이면 변경 없음.
        weights_version: Phase 4 — 신규 채점 가중치 버전 (default v6).

    Returns:
        저장 후 전체 settings (load_all 동일).

    Raises:
        SettingsValidationError: 검증 실패 (handler 가 409/400 매핑).
    """
    # 1. 검증 (트랜잭션 진입 전 — 실패 시 BEGIN 안 들어감)
    validated: dict[str, Any] = {}
    if weights is not None:
        validated["weights"] = validate_weights(weights)
    if bias is not None:
        validated["bias"] = validate_bias(bias)
    if voice is not None:
        validated["voice"] = validate_voice(voice)
    if grading_mode is not None:
        validated["grading_mode"] = validate_grading_mode(grading_mode)
    if weights_version is not None:
        validated["weights_version"] = validate_weights_version(weights_version)

    # 2. 변경 없음 → 현재 상태 그대로 반환
    if not validated:
        return load_all(conn)

    # 3. 단일 트랜잭션 (1~N UPSERT + COMMIT)
    now = _utcnow_iso()
    try:
        conn.execute("BEGIN")
        if "weights" in validated:
            _upsert(conn, KEY_WEIGHTS, validated["weights"], now)
        if "bias" in validated:
            _upsert(conn, KEY_BIAS, validated["bias"], now)
        if "voice" in validated:
            _upsert(conn, KEY_VOICE, validated["voice"], now)
        if "grading_mode" in validated:
            _upsert(conn, KEY_GRADING_MODE, validated["grading_mode"], now)
        if "weights_version" in validated:
            _upsert(conn, KEY_WEIGHTS_VERSION, validated["weights_version"], now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return load_all(conn)


def reset_to_default(conn: sqlite3.Connection) -> dict[str, Any]:
    """모든 settings 를 default 로 재설정 (편의 함수, handler 에서는 미사용 — 클라이언트가 PUT 으로 처리)."""
    return save_settings(
        conn,
        weights=dict(DEFAULT_WEIGHTS),
        bias=dict(DEFAULT_BIAS),
        voice=dict(DEFAULT_VOICE),
        grading_mode=DEFAULT_GRADING_MODE,
        weights_version=DEFAULT_WEIGHTS_VERSION,
    )
