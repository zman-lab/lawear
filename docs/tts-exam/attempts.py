#!/usr/bin/env python3
"""Attempts API 비즈니스 로직 (Step 7).

dev-design archive #48 §3-1, §3-2 (메시지 정의), §3-3 (ErrorCode),
§3-6-1 (시퀀스), §4-2 (DB), §5 (채점 프롬프트).
dev-impl-plan archive #51 Step 7 1:1.

핵심:
- `create_attempt(...)`           : POST /api/attempts 핵심 — INSERT + 백그라운드 grader thread 트리거.
- `get_attempt(conn, attempt_id)` : GET /api/attempts/{id} — status='grading' 폴링 + done 시 7 criteria join.
- `list_attempts(conn, **kwargs)` : GET /api/attempts — case_id / subject / from_date / to_date / limit / offset 필터.
- `mark_orphan_grading(conn)`     : 서버 시작 시 잔존 grading row 마킹 (Q24 A).

설계 결정 (R-09 자의적 해석 금지):
- 채점 결과는 Grader 가 반환한 그대로 저장. comment / eval_notes / diff_segments 가공 X.
- weights 는 settings 테이블에서 동적 로드 (없으면 DEFAULT_WEIGHTS).
- background thread 는 daemon=True — 서버 종료 시 함께 종료.
  종료 시점 grading row → 다음 부팅 시 mark_orphan_grading() 으로 status='error' 마킹.
- DB 트랜잭션:
  POST attempts → INSERT 후 즉시 응답. grade_async 안에서 SELECT settings + Grader.grade + 단일 트랜잭션
  (UPDATE attempts + 7×INSERT attempt_criteria + COMMIT). 실패 시 ROLLBACK + UPDATE status='error'.

threading 주의:
- 백그라운드 thread 에서 별도 conn 사용 (sqlite3 connection 은 thread-safe 가 아님).
- db_path 만 thread 에 넘기고 thread 안에서 get_conn 호출.
- launchd 종료 신호는 daemon=True 로 자동 정리.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
import sys
import threading
import time
from typing import Any

import cases as cases_mod
import db as db_mod
import grader as grader_mod

# ─── 상수 ────────────────────────────────────────────────────────────────

# attempts.status CHECK v3: ('grading','done','error','pending_grade').
# 'pending_grade' = Step 13 manual 채점 대기 (Claude Code 외부 채점 대상).
DB_STATUS_GRADING: str = "grading"
DB_STATUS_DONE: str = "done"
DB_STATUS_ERROR: str = "error"
DB_STATUS_PENDING_GRADE: str = "pending_grade"

# Reports / 클라이언트 응답에 노출되는 상태 라벨
CLIENT_STATUS_MAP: dict[str, str] = {
    DB_STATUS_GRADING: "grading",
    DB_STATUS_DONE: "completed",  # 사양 align
    DB_STATUS_ERROR: "failed",  # 사양 align
    DB_STATUS_PENDING_GRADE: "pending_grade",  # Step 13 — manual 채점 대기
}

# settings.weights 키 (없을 때 fallback)
SETTINGS_WEIGHTS_KEY: str = "weights"

# 채점 모드 (settings.grading_mode 와 1:1)
GRADING_MODE_MANUAL: str = "manual"
GRADING_MODE_AUTO: str = "auto"

# Limit clamp
DEFAULT_LIST_LIMIT: int = 50
MAX_LIST_LIMIT: int = 500


# ─── 예외 ────────────────────────────────────────────────────────────────


class AttemptValidationError(Exception):
    """answer_text 빈 값 등 입력 검증 실패 (HTTP 400)."""

    def __init__(self, message: str, error_code: str = "bad_request") -> None:
        super().__init__(message)
        self.error_code = error_code


class AttemptNotFoundError(Exception):
    """attempt_id 미존재 (HTTP 404)."""


class AttemptAlreadyGradedError(Exception):
    """이미 채점 완료된 attempt 에 PUT /grade 시도 (HTTP 409).

    Step 13 — 재채점은 별도 endpoint 검토 (사용자 명시).
    """


class GradeInjectionError(Exception):
    """PUT /api/attempts/{id}/grade 검증 실패 (HTTP 400).

    criteria 7키 누락 / 잘못된 형식 / 필수 필드 부재.
    """

    def __init__(self, message: str, error_code: str = "bad_request") -> None:
        super().__init__(message)
        self.error_code = error_code


# ─── 유틸 ────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    """ISO-8601 UTC ('YYYY-MM-DDTHH:MM:SSZ')."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _recompute_grade_v2(score_pct: float | None) -> str:
    """score_pct → V2 grade letter (10단계) — API 응답용.

    lawear-e571 (2026-05-19) — DB grade 컬럼은 legacy V1 (A/B/C/F enum).
    API 응답 시 score_pct 기준으로 V2 grade (A+/A/A-/B+/B/B-/C+/C/C-/F) 동적 재계산.

    Args:
        score_pct: attempts.score_pct (0~100). None → "F".

    Returns:
        V2 grade letter.
    """
    return grader_mod.compute_grade_v2(score_pct)


# 합격선 (실제 시험 합격 기준 — lawear-2e42, 2026-05-20 사용자 결정 60→73 상향)
PASS_LINE_PCT: float = 73.0


def _is_pass(score_pct: float | None) -> bool:
    """score_pct >= 73.0 (A-) → 합격 (시각화용 배지 조건)."""
    if score_pct is None:
        return False
    try:
        return float(score_pct) >= PASS_LINE_PCT
    except (TypeError, ValueError):
        return False


def _load_weights(conn: sqlite3.Connection) -> dict[str, int]:
    """settings 테이블에서 weights 로드. 실패 시 DEFAULT_WEIGHTS."""
    try:
        cur = conn.execute(
            "SELECT value_json FROM settings WHERE key = ?", (SETTINGS_WEIGHTS_KEY,)
        )
        row = cur.fetchone()
        if row is None or row["value_json"] is None:
            return dict(grader_mod.DEFAULT_WEIGHTS)
        weights = json.loads(row["value_json"])
        if not isinstance(weights, dict):
            return dict(grader_mod.DEFAULT_WEIGHTS)
        # 정합성 확인 — 누락 키는 default 보충
        merged: dict[str, int] = dict(grader_mod.DEFAULT_WEIGHTS)
        for k in grader_mod.CRITERION_KEYS:
            if k in weights:
                try:
                    merged[k] = int(weights[k])
                except (TypeError, ValueError):
                    pass
        return merged
    except (sqlite3.DatabaseError, json.JSONDecodeError) as e:
        print(f"[Attempts] settings.weights load failed: {e} — using DEFAULT", file=sys.stderr)
        return dict(grader_mod.DEFAULT_WEIGHTS)


def _elapsed_since(submitted_at: str) -> float:
    """submitted_at(ISO-8601) → now 경과초. 파싱 실패 시 0.0."""
    try:
        # 'Z' suffix 허용
        s = submitted_at.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(s)
        now = _dt.datetime.now(_dt.timezone.utc)
        return max(0.0, (now - dt).total_seconds())
    except (ValueError, TypeError):
        return 0.0


def _solve_elapsed_sec(
    started_at: str | None, submitted_at: str | None
) -> float | None:
    """Step 23 — 사용자 풀이 시간 (submitted_at - started_at, 초).

    started_at 또는 submitted_at 누락 / 파싱 실패 시 None.
    음수(시계 역행 등)는 0.0 으로 clamp.
    """
    if not started_at or not submitted_at:
        return None
    try:
        s = str(started_at).replace("Z", "+00:00")
        e = str(submitted_at).replace("Z", "+00:00")
        sd = _dt.datetime.fromisoformat(s)
        ed = _dt.datetime.fromisoformat(e)
        return max(0.0, (ed - sd).total_seconds())
    except (ValueError, TypeError):
        return None


def _compute_total_solve_sec(
    subq_elapsed: dict | None,
    solve_elapsed_sec: float | None,
) -> int | None:
    """lawear-e571 (2026-05-19) — total_solve_sec 계산 + fallback.

    우선순위:
        1) subq_elapsed (dict) 의 값 합산 > 0  → 그 합 (카드별 트래킹 정상)
        2) subq_elapsed 합 == 0 이고 solve_elapsed_sec > 0 → solve_elapsed_sec fallback
           (단일 카드 모드 ``{"단일": 0}`` 또는 다중 카드 트래킹 누락 시 — UI 0초 방지)
        3) 그 외 → None (legacy attempts — 트래킹 데이터 없음)

    Args:
        subq_elapsed: ``{subq_key: int 초}`` 카드별 풀이 시간. None / 빈 dict 허용.
        solve_elapsed_sec: ``_solve_elapsed_sec()`` 결과 (submitted-started, float|None).

    Returns:
        int (초) 또는 None.
    """
    # 1) subq_elapsed 합산
    if isinstance(subq_elapsed, dict) and subq_elapsed:
        try:
            s = sum(
                int(v) for v in subq_elapsed.values()
                if isinstance(v, (int, float))
            )
        except (TypeError, ValueError):
            s = 0
        if s > 0:
            return s
        # subq_elapsed 합=0 → fallback 단계 진입
        if isinstance(solve_elapsed_sec, (int, float)) and solve_elapsed_sec > 0:
            return int(round(solve_elapsed_sec))
        return None  # 둘 다 0 → None (UI 비표시)

    # 2) subq_elapsed 없음 → solve_elapsed_sec 단독 fallback
    #    (legacy 호환 — 기존엔 None 반환. fallback 활성화는 명시 컨텍스트가 있을 때만)
    #    NOTE: subq_elapsed=None 인 순수 legacy attempt 는 기존 동작 유지 (None).
    return None


def _client_status(db_status: str) -> str:
    return CLIENT_STATUS_MAP.get(db_status, db_status)


# ─── Step 24-3 헬퍼: 카드별 dict JSON 직렬화 + 힌트 메타 ─────────────────


def _serialize_subq_dicts(
    answer_subq: dict | None,
    subq_elapsed: dict | None,
    hints_used: dict | None,
) -> tuple[str | None, str | None, str | None]:
    """카드별 3종 dict → JSON 직렬화 (None 보존, 한글 키 ensure_ascii=False).

    Step 24-1 마이그 v6 에서 추가된 attempts.answer_subq / subq_elapsed /
    hints_used (모두 TEXT NULL 허용) 컬럼 직렬화 헬퍼.

    한글 카드 키(예: "설문 1", "설문 1 가")가 escape 없이 그대로 저장되도록
    ``ensure_ascii=False`` 사용 (cases.py 의 normalize_subq_key 결과 호환).

    Args:
        answer_subq:  {subq_key: 답안 텍스트}.  None 또는 빈 dict → None.
        subq_elapsed: {subq_key: int 초}.       None 또는 빈 dict → None.
        hints_used:   {subq_key: list[int]}.    None 또는 빈 dict → None.

    Returns:
        (answer_subq_json, subq_elapsed_json, hints_used_json) — 각 항목은 str 또는 None.
    """
    return (
        json.dumps(answer_subq, ensure_ascii=False) if answer_subq else None,
        json.dumps(subq_elapsed, ensure_ascii=False) if subq_elapsed else None,
        json.dumps(hints_used, ensure_ascii=False) if hints_used else None,
    )


def _deserialize_subq_dicts(
    answer_subq_json: str | None,
    subq_elapsed_json: str | None,
    hints_used_json: str | None,
) -> tuple[dict | None, dict | None, dict | None]:
    """JSON 문자열 → dict (legacy NULL → None 유지).

    NULL/빈 문자열 입력은 None 으로 보존 (legacy answer_text 단일 모드 호환).
    JSON 파싱 실패 시에도 안전하게 None 반환 (raise X — _attempt_row_to_dict
    응답 흐름 차단 방지).

    Args:
        answer_subq_json:  attempts.answer_subq 컬럼 값 (str 또는 None).
        subq_elapsed_json: attempts.subq_elapsed 컬럼 값 (str 또는 None).
        hints_used_json:   attempts.hints_used 컬럼 값 (str 또는 None).

    Returns:
        (answer_subq, subq_elapsed, hints_used) — 각 항목은 dict 또는 None.
        dict 가 아닌 JSON 값(예: list, 문자열) 이 들어오면 None 으로 정규화.
    """
    def _load(j: str | None) -> dict | None:
        if not j:
            return None
        try:
            obj = json.loads(j)
        except (TypeError, json.JSONDecodeError):
            return None
        return obj if isinstance(obj, dict) else None

    return _load(answer_subq_json), _load(subq_elapsed_json), _load(hints_used_json)


def _compute_hint_meta(hints_used: dict | None) -> dict[str, int]:
    """hints_used dict → {count, steps_max} 메타 계산.

    히스토리 패널 "힌트 N회" / "최대 단계 K" 표시용 (Step 24-3 응답 메타).

    Args:
        hints_used: ``{subq_key: list[int]}`` 형식. None 또는 빈 dict 허용.
                    각 step 정수는 1~5 범위 (범위 밖은 무시).

    Returns:
        ``{"count": int, "steps_max": int}``
        - count:     모든 카드의 사용된 힌트 step 총 개수 (1~5 범위만 누적).
        - steps_max: 모든 카드 중 최대 노출 step (1~5 범위만 비교, 없으면 0).
        - hints_used 가 None / 빈 dict → ``{"count": 0, "steps_max": 0}``.
    """
    count = 0
    steps_max = 0
    if not isinstance(hints_used, dict):
        return {"count": count, "steps_max": steps_max}
    for steps in hints_used.values():
        if not isinstance(steps, list):
            continue
        for s in steps:
            try:
                si = int(s)
            except (TypeError, ValueError):
                continue
            if 1 <= si <= 5:
                count += 1
                if si > steps_max:
                    steps_max = si
    return {"count": count, "steps_max": steps_max}


# ─── 잔존 grading 마킹 (Q24 A) ────────────────────────────────────────────


def mark_orphan_grading(conn: sqlite3.Connection) -> int:
    """서버 시작 시 status='grading' 잔존 row 를 'error' 로 마킹.

    Q24 A — daemon thread 가 종료 신호 받기 전 죽은 채점 흔적.
    completed_at 도 함께 채워 Reports 에 표시 가능.

    Returns:
        마킹된 row 수.
    """
    cur = conn.execute(
        """
        UPDATE attempts
           SET status = ?,
               error_code = COALESCE(error_code, 'server_restart'),
               error_message = COALESCE(error_message, 'server restarted during grading'),
               completed_at = COALESCE(completed_at, ?)
         WHERE status = ?
        """,
        (DB_STATUS_ERROR, _utcnow_iso(), DB_STATUS_GRADING),
    )
    conn.commit()
    n = cur.rowcount or 0
    if n > 0:
        print(f"[Attempts] mark_orphan_grading: {n} row(s) → 'error/server_restart'", file=sys.stderr)
    return n


# ─── 백그라운드 채점 ──────────────────────────────────────────────────────


def _grade_async(
    db_path: str,
    attempt_id: int,
    case_meta: dict[str, Any],
    answer_text: str,
    weights: dict[str, int],
) -> None:
    """daemon thread 진입점 — Grader 호출 + DB 단일 트랜잭션 저장.

    실패 시 status='error' + error_code/error_message 만 마킹 (R-09 — 가공 X).
    """
    case_id = case_meta.get("id")
    print(f"[Attempts] grade_async start attempt_id={attempt_id} case_id={case_id}", file=sys.stderr)

    started = time.monotonic()
    try:
        # Grader 호출 (mock 모드 자동 판정 — env LAWEAR_GRADER_MOCK 또는 ANTHROPIC_API_KEY 미설정)
        result = grader_mod.grade(case_meta, answer_text, weights=weights)
    except grader_mod.GraderError as e:
        # api_key_missing / rate_limit / bad_gateway / parse_failure
        _mark_attempt_error(
            db_path,
            attempt_id,
            error_code=e.error_code,
            error_message=str(e),
            elapsed=time.monotonic() - started,
        )
        return
    except Exception as e:  # noqa: BLE001
        _mark_attempt_error(
            db_path,
            attempt_id,
            error_code="internal_error",
            error_message=f"{type(e).__name__}: {e}",
            elapsed=time.monotonic() - started,
        )
        return

    # DB 단일 트랜잭션 저장
    try:
        _save_grade_result(db_path, attempt_id, result)
    except sqlite3.DatabaseError as e:
        _mark_attempt_error(
            db_path,
            attempt_id,
            error_code="db_error",
            error_message=f"save_failed: {e}",
            elapsed=time.monotonic() - started,
        )


def _merge_initial_typo_corrections(
    conn: sqlite3.Connection,
    attempt_id: int,
    eval_notes: dict[str, Any],
) -> None:
    """lawear-9bdc/typo-system-v2 — POST 시점 typo_corrections 머지 (덮어쓰기 방지).

    POST /attempts 시점에 typo_corrector(정적) + ai_corrector(Claude) 가 누적한 초기 corrections 가
    grader 결과 UPDATE 로 손실되지 않도록, 기존 attempts.eval_notes_json 에서 read 후 머지.

    중복 from 은 grader 결과(=새 결과) 우선 — POST 시점 결과는 추가만.
    in-place: ``eval_notes['typo_corrections']`` 갱신 (없으면 추가, 빈 list 면 None).

    Args:
        conn:        attempts 테이블 read 가능한 conn (read-only).
        attempt_id:  attempt 행 ID.
        eval_notes:  grader/inject 결과의 normalized eval_notes dict (in-place 수정).
    """
    try:
        row = conn.execute(
            "SELECT eval_notes_json FROM attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
    except sqlite3.Error:
        return
    if not row:
        return
    raw = row["eval_notes_json"] if "eval_notes_json" in row.keys() else row[0]
    if not raw:
        return
    try:
        existing = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(existing, dict):
        return
    existing_typo = existing.get("typo_corrections")
    if not isinstance(existing_typo, list) or not existing_typo:
        return

    new_typo = eval_notes.get("typo_corrections")
    if not isinstance(new_typo, list):
        new_typo = []
    seen_from: set[str] = {
        c.get("from") for c in new_typo
        if isinstance(c, dict) and isinstance(c.get("from"), str) and c.get("from")
    }
    merged: list[dict[str, Any]] = list(new_typo)
    for c in existing_typo:
        if not isinstance(c, dict):
            continue
        f = c.get("from")
        if isinstance(f, str) and f and f not in seen_from:
            merged.append(c)
            seen_from.add(f)
    eval_notes["typo_corrections"] = merged if merged else None


def _save_grade_result(db_path: str, attempt_id: int, result: dict[str, Any]) -> None:
    """채점 결과를 단일 트랜잭션으로 저장.

    BEGIN → UPDATE attempts (status=done, score_*, grade, model, eval_notes_json,
            diff_json, raw_response, completed_at, elapsed_sec, is_mock)
         → 7×INSERT OR REPLACE attempt_criteria (criterion_key UNIQUE per attempt)
         → COMMIT
    """
    completed_at = _utcnow_iso()
    # Phase 1 — eval_notes 정규화 적용 (확장 키 포함, 빈 키는 빈 문자열/빈 배열)
    raw_eval_notes = result.get("eval_notes") or {}
    if isinstance(raw_eval_notes, dict):
        try:
            eval_notes_normalized = _normalize_eval_notes(raw_eval_notes)
        except GradeInjectionError:
            # grader 응답이 dict 아니면 안전 fallback (빈 dict)
            eval_notes_normalized = _normalize_eval_notes({})
    else:
        eval_notes_normalized = _normalize_eval_notes({})
    diff_json = json.dumps(result.get("diff_segments", []), ensure_ascii=False)
    criteria = result.get("criteria") or []
    is_mock_int = 1 if result.get("is_mock") else 0

    conn = db_mod.get_conn(db_path)
    try:
        # lawear-9bdc/typo-system-v2 — POST 시점 typo_corrections 머지 (BEGIN 전 read)
        _merge_initial_typo_corrections(conn, attempt_id, eval_notes_normalized)
        eval_notes_json = json.dumps(eval_notes_normalized, ensure_ascii=False)

        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            # autocommit 모드일 수도 있음 — 다음 execute 가 트랜잭션 시작
            conn.execute("BEGIN")

        conn.execute(
            """
            UPDATE attempts
               SET status        = ?,
                   score_total   = ?,
                   score_max     = ?,
                   score_pct     = ?,
                   grade         = ?,
                   model         = ?,
                   eval_notes_json = ?,
                   diff_json     = ?,
                   raw_response  = ?,
                   completed_at  = ?,
                   elapsed_sec   = ?,
                   is_mock       = ?,
                   error_code    = NULL,
                   error_message = NULL
             WHERE id = ?
            """,
            (
                DB_STATUS_DONE,
                float(result.get("score_total") or 0.0),
                float(result.get("score_max") or 0.0),
                float(result.get("score_pct") or 0.0),
                # lawear-e571 (2026-05-19) — grader 가 V2 grade (A+/A/A-/B+/...) 반환할 수 있음.
                # DB grade 컬럼은 V1 enum (A/B/C/F) 만 허용 → _to_v1_grade 변환.
                # API 응답에서는 _attempt_row_to_dict 가 score_pct 기준 V2 grade 재계산.
                grader_mod._to_v1_grade(result.get("grade") or "F"),
                result.get("model") or "unknown",
                eval_notes_json,
                diff_json,
                result.get("raw_response"),
                completed_at,
                float(result.get("elapsed_sec") or 0.0),
                is_mock_int,
                attempt_id,
            ),
        )

        # 기존 criteria 삭제 후 재삽입 (재채점 대비 — 본 단계는 새 row 가정이지만 안전 처리)
        conn.execute("DELETE FROM attempt_criteria WHERE attempt_id = ?", (attempt_id,))
        for c in criteria:
            key = c.get("key")
            if key not in grader_mod.CRITERION_KEYS:
                continue
            conn.execute(
                """
                INSERT INTO attempt_criteria
                  (attempt_id, criterion_key, score, max_score, weight, comment)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    key,
                    float(c.get("score") or 0.0),
                    float(c.get("max") or 0.0),
                    float(c.get("weight") or 0.0),
                    c.get("comment") or "",
                ),
            )
        conn.commit()
        print(
            f"[Attempts] saved attempt_id={attempt_id} status=done "
            f"score={result.get('score_total')}/{result.get('score_max')} "
            f"grade={result.get('grade')} mock={bool(is_mock_int)}",
            file=sys.stderr,
        )
    except Exception:
        try:
            conn.rollback()
        except sqlite3.DatabaseError:
            pass
        raise
    finally:
        conn.close()


def _mark_attempt_error(
    db_path: str,
    attempt_id: int,
    *,
    error_code: str,
    error_message: str,
    elapsed: float,
) -> None:
    """채점 실패 — status='error' + 사유 마킹."""
    conn = db_mod.get_conn(db_path)
    try:
        conn.execute(
            """
            UPDATE attempts
               SET status        = ?,
                   error_code    = ?,
                   error_message = ?,
                   completed_at  = ?,
                   elapsed_sec   = ?
             WHERE id = ?
            """,
            (
                DB_STATUS_ERROR,
                error_code,
                error_message,
                _utcnow_iso(),
                float(elapsed),
                attempt_id,
            ),
        )
        conn.commit()
        print(
            f"[Attempts] FAILED attempt_id={attempt_id} code={error_code} elapsed={elapsed:.2f}s msg={error_message!r}",
            file=sys.stderr,
        )
    except sqlite3.DatabaseError as e:
        print(f"[Attempts] _mark_attempt_error DB failure: {e}", file=sys.stderr)
    finally:
        conn.close()


# ─── 공용 API ────────────────────────────────────────────────────────────


def create_attempt(
    conn: sqlite3.Connection,
    db_path: str,
    case_id: str,
    answer_text: str | None = None,
    *,
    answer_subq: dict | None = None,
    subq_elapsed: dict | None = None,
    hints_used: dict | None = None,
    started_at: str | None = None,
    submitted_at: str | None = None,
    grading_mode: str = GRADING_MODE_MANUAL,
) -> dict[str, Any]:
    """POST /api/attempts — 즉시 INSERT + (auto 모드) daemon thread 트리거.

    Step 24-3 확장: 다중 설문 D안 (answer_subq + subq_elapsed + hints_used).
      legacy `answer_text` 단일 모드 fallback 보존 — 둘 중 하나는 반드시 제공.

    Step 13 분기:
      - grading_mode='manual': INSERT row(status='pending_grade'), thread 안 띄움.
        클라이언트가 별도 PUT /api/attempts/{id}/grade 로 결과 주입할 때까지 대기.
      - grading_mode='auto':   기존 흐름 (status='grading' + daemon thread + grader.grade).
        ANTHROPIC_API_KEY 미설정 시 자동으로 manual 강등 + 응답에 warning 포함.

    호환 매트릭스 (Step 24-3 핵심):
        - `answer_subq` 있고 `answer_text` 없음 (신규 D안 다중 설문):
            DB attempts.answer_text NOT NULL → 카드 dict 를 join 해 컬럼 채움.
            attempts.answer_subq 컬럼에 JSON dict 그대로 저장.
        - `answer_subq` 없고 `answer_text` 있음 (legacy 단일 설문):
            attempts.answer_subq NULL → `_attempt_row_to_dict` 시 None 으로 노출.
        - 둘 다 있음: 양쪽 모두 저장 (R-09 — 가공 X).
        - 둘 다 없음: ``AttemptValidationError("answer empty", "subq_empty")``.

    Args:
        conn:         (요청 핸들러가 보유한) DB connection — INSERT 전용. 트랜잭션 분리.
        db_path:      백그라운드 thread 가 별도 conn 을 열기 위한 경로.
        case_id:      cases.id (FK).
        answer_text:  검토 의견 본문 (legacy 단일 카드 모드). answer_subq 와 둘 중 하나 필수.
        answer_subq:  ``{subq_key: 답안 텍스트}`` 다중 카드 모드.
        subq_elapsed: ``{subq_key: int 초}`` 카드별 풀이 시간.
        hints_used:   ``{subq_key: list[int]}`` 카드별 노출 힌트 단계 (1~5).
        started_at:   클라이언트 시작 시각 (선택).
        submitted_at: 클라이언트 제출 시각 (선택, 기본 utcnow).
        grading_mode: 'manual' (디폴트, Step 13) 또는 'auto'.

    Returns:
        manual: {"attempt_id", "status": "pending_grade", "case_id", "submitted_at", "grading_mode": "manual",
                 "subq_count", "hints_used_count", "hint_steps_revealed_max"}
        auto:   {"attempt_id", "status": "grading",       ... (위와 동일)}
        auto+키없음 fallback: 위 manual 응답 + "warning": "api_key_missing — fell back to manual"

    Raises:
        AttemptValidationError: answer_text + answer_subq 둘 다 빈 값.
        cases.CaseNotFoundError: case_id 미존재 — 호출자가 404 로 매핑.
    """
    # 입력 검증 — 둘 다 빈 값 거부 (legacy + 신규 모두 호환)
    text_empty = not answer_text or not answer_text.strip()
    subq_empty = not isinstance(answer_subq, dict) or not answer_subq or not any(
        isinstance(v, str) and v.strip() for v in answer_subq.values()
    )
    if text_empty and subq_empty:
        raise AttemptValidationError(
            "answer empty (provide answer_text or answer_subq)", "subq_empty"
        )
    if not case_id or not case_id.strip():
        raise AttemptValidationError("case_id empty", "bad_request")

    # answer_text 미제공이면 answer_subq 카드를 join 해 NOT NULL 충족.
    # R-09 — 원본 그대로, 카드 라벨을 prefix 로 명시.
    if text_empty and not subq_empty:
        joined = "\n\n---\n\n".join(
            f"[{k}]\n{v}"
            for k, v in answer_subq.items()  # type: ignore[union-attr]
            if isinstance(v, str) and v.strip()
        )
        answer_text = joined

    # lawear-9bdc/typo-system-v2 — POST 시점 STT 오타 1+2 패스 교정 (graceful).
    #   1. typo_corrector (정적 사전 typo_dict.json) → static_corrs
    #   2. ai_corrector (Claude API, ANTHROPIC_API_KEY 있을 때) → ai_corrs
    #   3. answer_text = 교정본 (사용자 정책 확정 — 원본 보존 X)
    #   4. eval_notes_initial.typo_corrections = static + ai (누적, grader 가 머지)
    # 예외 발생/모듈 import 실패 시 모두 graceful — 원본 answer_text 그대로.
    typo_corrections_initial: list[dict[str, Any]] = []
    try:
        import typo_corrector as _tc_initial
        corrected_static, static_corrs_initial = _tc_initial.correct(answer_text)
        if static_corrs_initial:
            typo_corrections_initial.extend(static_corrs_initial)
            answer_text = corrected_static
    except Exception as e:
        print(
            f"[CreateAttempt] typo_corrector skipped: {type(e).__name__}: {e}",
            file=sys.stderr,
        )

    try:
        import ai_corrector as _aic_initial
        if _aic_initial.is_available():
            corrected_ai, ai_corrs_initial = _aic_initial.correct_with_ai(
                answer_text,
                static_corrections=typo_corrections_initial,
            )
            if ai_corrs_initial:
                typo_corrections_initial.extend(ai_corrs_initial)
                answer_text = corrected_ai
    except Exception as e:
        print(
            f"[CreateAttempt] ai_corrector skipped: {type(e).__name__}: {e}",
            file=sys.stderr,
        )

    # eval_notes_initial — typo_corrections 있을 때만 JSON 직렬화 (없으면 NULL 컬럼)
    eval_notes_initial_json: str | None = None
    if typo_corrections_initial:
        eval_notes_initial_json = json.dumps(
            {"typo_corrections": typo_corrections_initial},
            ensure_ascii=False,
        )

    # case_meta 로드 (.md 본문 포함) — 미존재 시 CaseNotFoundError → 404
    case_meta = cases_mod.get_case(conn, case_id)

    # weights 로드 (없으면 DEFAULT)
    weights = _load_weights(conn)
    weights_json = json.dumps(weights, ensure_ascii=False)

    submitted = submitted_at or _utcnow_iso()

    # ─── 모드 분기 ─────────────────────────────────────────────────
    # auto + 키 없음 → manual 강등 (warning 응답 포함)
    warning: str | None = None
    effective_mode = grading_mode
    if effective_mode == GRADING_MODE_AUTO and not os.environ.get("ANTHROPIC_API_KEY"):
        warning = "api_key_missing — fell back to manual grading"
        effective_mode = GRADING_MODE_MANUAL
        print(
            f"[Attempts] grading_mode=auto requested but ANTHROPIC_API_KEY missing — "
            f"degrading to manual (case_id={case_id})",
            file=sys.stderr,
        )

    initial_status = (
        DB_STATUS_GRADING if effective_mode == GRADING_MODE_AUTO else DB_STATUS_PENDING_GRADE
    )

    # Step 24-3 — 카드별 dict 3종 JSON 직렬화 (None 이면 None 유지)
    ans_json, elap_json, hints_json = _serialize_subq_dicts(
        answer_subq, subq_elapsed, hints_used
    )

    # INSERT attempts (마이그 v6 신규 컬럼 3 + lawear-9bdc/typo-system-v2 eval_notes_json 초기 저장)
    cur = conn.execute(
        """
        INSERT INTO attempts
          (case_id, answer_text, started_at, submitted_at, status, weights_json, is_stale,
           answer_subq, subq_elapsed, hints_used, eval_notes_json)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """,
        (
            case_id,
            answer_text,
            started_at,
            submitted,
            initial_status,
            weights_json,
            ans_json,
            elap_json,
            hints_json,
            eval_notes_initial_json,
        ),
    )
    conn.commit()
    attempt_id = int(cur.lastrowid or 0)
    if attempt_id <= 0:
        raise RuntimeError("attempt INSERT returned invalid lastrowid")

    if effective_mode == GRADING_MODE_AUTO:
        # 백그라운드 채점 (daemon — 서버 종료 시 함께 종료)
        th = threading.Thread(
            target=_grade_async,
            args=(db_path, attempt_id, case_meta, answer_text, weights),
            name=f"grader-attempt-{attempt_id}",
            daemon=True,
        )
        th.start()
        print(
            f"[Attempts] created attempt_id={attempt_id} case_id={case_id} "
            f"thread={th.name} mode=auto (background)",
            file=sys.stderr,
        )
    else:
        print(
            f"[Attempts] created attempt_id={attempt_id} case_id={case_id} "
            f"mode=manual (awaiting external grade injection via PUT /api/attempts/{attempt_id}/grade)",
            file=sys.stderr,
        )

    # Step 24-3 — 응답에 subq 메타 키 3개 추가
    hint_meta = _compute_hint_meta(hints_used)
    subq_count_val = len(answer_subq) if isinstance(answer_subq, dict) and answer_subq else 0

    result: dict[str, Any] = {
        "attempt_id": attempt_id,
        "status": _client_status(initial_status),
        "case_id": case_id,
        "submitted_at": submitted,
        "grading_mode": effective_mode,
        "subq_count": subq_count_val,
        "hints_used_count": hint_meta["count"],
        "hint_steps_revealed_max": hint_meta["steps_max"],
    }
    if warning is not None:
        result["warning"] = warning
    return result


# ─── 외부 채점 결과 주입 (Step 13 — PUT /api/attempts/{id}/grade) ─────


# 입력 alias → DB criterion_key (grader.CRITERION_KEYS) 매핑.
# 사용자 워크플로우 (reference_grading_workflow.md) 의 긴 이름 + grader.py 의 짧은 키 둘 다 허용.
# Step 20 (사용자 2026-05-16): articles 신설 — 원본 조문 매칭.
# Step 21 (사용자 2026-05-17): case_apply 신설 — 사안의 경우 결론+근거 적용 (정확 매칭 X).
CRITERIA_KEY_ALIASES: dict[str, str] = {
    # 긴 이름 (사용자 워크플로우)
    "mnemonics": "mnem",
    "color": "color",
    "underline": "under",
    "outline": "outline",
    "semantic": "sem",
    "richness": "rich",
    "missing": "miss",
    "articles": "articles",
    "article": "articles",
    "article_match": "articles",
    "case_apply": "case_apply",
    "case_application": "case_apply",
    "사안의경우": "case_apply",
    # 짧은 이름 (grader.py / DB CHECK)
    "mnem": "mnem",
    "under": "under",
    "sem": "sem",
    "rich": "rich",
    "miss": "miss",
}

# 외부 채점 응답 필수 필드 (메인 응답에 7기준 + total/max/pct + grade + eval_notes 다 필요)
_REQUIRED_INJECT_FIELDS: tuple[str, ...] = (
    "criteria",
    "total_score",
    "max_score",
    "score_pct",
    "grade",
    "eval_notes",
)

# eval_notes 키 — Phase 1 확장 (lawear-e571, 2026-05-19):
#   legacy 키 (호환 보존): strength / caution / missing — str
#   확장 키 (자체 채점 누락 캡처용):
#     - score_summary:        str (3줄 핵심 평가)
#     - strengths:            list[str] (강점 항목)
#     - weaknesses:           list[str] (약점 항목)
#     - missing_critical:     list[dict] [{item, expected_score_impact}]
#     - next_study_oneliner:  str ("💡 다음 +N점 가능: ...")
#     - next_study_actionable:list[str] (실행 가능 학습 액션)
#   7번째 확장 키 (pattern_warning — lawear-e571 추가 2026-05-19):
#     - pattern_warning:      str | null (반복 실수 패턴 경고, 예 "🔥 같은 실수 N회 반복...")
#       AI 채점은 단일 attempt만 보므로 *내부 답안 패턴* 한정.
#       *외부 비교* (이전 attempt vs 현재)는 메인이 메타 분석 후 PUT /grade로 직접 주입.
#   8번째 확장 키 (typo_corrections — lawear-e571/typo-system 추가 2026-05-19):
#     - typo_corrections:     list[dict] | null
#       음성 답안 (STT) 오타 교정 내역. 각 dict: {from, to, reason}.
#       정적 사전(typo_dict.json) 매칭 + Opus SE 문맥 분석 결과 누적.
#       legacy attempts (키 없음) 은 None — UI 분기 graceful.
#
# 사용자 명시 (lawear-e571 작업): SE 보낸 평가 본문이 스키마 불일치로 빈 문자열 저장됨.
# 새 키 못 받으면 빈 문자열/빈 배열로 저장 (호환성).
_EVAL_NOTES_KEYS_LEGACY: tuple[str, ...] = ("strength", "caution", "missing")
_EVAL_NOTES_KEYS_EXT_STR: tuple[str, ...] = ("score_summary", "next_study_oneliner")
_EVAL_NOTES_KEYS_EXT_LIST: tuple[str, ...] = (
    "strengths",
    "weaknesses",
    "missing_critical",
    "next_study_actionable",
)
# pattern_warning 은 str | null — 빈 키 디폴트는 None (legacy str EXT 와 분리)
_EVAL_NOTES_KEYS_EXT_OPT_STR: tuple[str, ...] = ("pattern_warning",)
# typo_corrections — 8번째 확장 키 (lawear-e571/typo-system 추가 2026-05-19):
#   list[dict] | None — 빈 리스트도 None 으로 정규화 (UI 분기 단순화).
#   각 dict: {"from": str, "to": str, "reason": str} — 음성 STT 오타 교정 내역.
_EVAL_NOTES_KEYS_EXT_OPT_LIST: tuple[str, ...] = ("typo_corrections",)
# 통합 (서버 검증 + 응답 형식 일관성)
_EVAL_NOTES_KEYS: tuple[str, ...] = (
    _EVAL_NOTES_KEYS_LEGACY
    + _EVAL_NOTES_KEYS_EXT_STR
    + _EVAL_NOTES_KEYS_EXT_LIST
    + _EVAL_NOTES_KEYS_EXT_OPT_STR
    + _EVAL_NOTES_KEYS_EXT_OPT_LIST
)

# eval_notes alias — 다른 키 이름으로 들어와도 정규화 (호환)
#   strengths/weaknesses 단수형(strength/weakness) → 자체 normalize
#   missing → missing_critical 자동 wrap (legacy missing str 보존)
_EVAL_NOTES_ALIASES: dict[str, str] = {
    # 단수 → 복수 list 키
    "weakness": "weaknesses",
    # missing은 legacy str 보존, 단 새 키로 들어오면 wrap도 가능 — 별도 로직
}

# diff_segments 의 type 화이트리스트
_DIFF_SEGMENT_TYPES: frozenset[str] = frozenset({"match", "miss", "partial"})


def _normalize_criteria(raw: Any) -> list[dict[str, Any]]:
    """입력 criteria 배열을 DB 저장용 7항목으로 정규화.

    Raises:
        GradeInjectionError: 7키 누락 / 형식 오류.

    Returns:
        [{key (DB short), score, weight, max, comment}] × 7 (CRITERION_KEYS 순서).
    """
    if not isinstance(raw, list):
        raise GradeInjectionError(
            f"criteria must be array, got {type(raw).__name__}"
        )

    by_key: dict[str, dict[str, Any]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise GradeInjectionError(
                f"each criteria entry must be object, got {type(entry).__name__}"
            )
        raw_key = entry.get("key")
        if not isinstance(raw_key, str):
            raise GradeInjectionError("criteria entry missing 'key'")
        db_key = CRITERIA_KEY_ALIASES.get(raw_key.strip())
        if db_key is None:
            raise GradeInjectionError(
                f"unknown criteria key {raw_key!r} "
                f"(allowed aliases: {sorted(CRITERIA_KEY_ALIASES)})"
            )
        # score 필수, weight_applied 또는 weight 둘 다 허용, comment 선택
        if "score" not in entry:
            raise GradeInjectionError(f"criteria[{raw_key}] missing 'score'")
        try:
            score = float(entry["score"])
        except (TypeError, ValueError) as e:
            raise GradeInjectionError(
                f"criteria[{raw_key}].score must be number, got {entry['score']!r}"
            ) from e

        # weight_applied (사용자 사양) 또는 weight (grader 사양)
        weight_raw = entry.get("weight_applied")
        if weight_raw is None:
            weight_raw = entry.get("weight", 0)
        try:
            weight = float(weight_raw)
        except (TypeError, ValueError):
            weight = 0.0

        # max 필드 (없으면 weight 동일 — miss 는 0 으로 보정 별도)
        max_raw = entry.get("max")
        if max_raw is None:
            # 외부 채점은 weight_applied 자체가 100점 만점이므로 max = weight
            max_val = weight if db_key != "miss" else 0.0
        else:
            try:
                max_val = float(max_raw)
            except (TypeError, ValueError):
                max_val = weight if db_key != "miss" else 0.0

        comment = entry.get("comment")
        if comment is not None and not isinstance(comment, str):
            comment = str(comment)

        by_key[db_key] = {
            "key": db_key,
            "score": score,
            "max": max_val,
            "weight": weight,
            "comment": comment or "",
        }

    # 7키 모두 존재 검증
    missing = [k for k in grader_mod.CRITERION_KEYS if k not in by_key]
    if missing:
        raise GradeInjectionError(
            f"criteria missing keys: {missing} "
            f"(received: {sorted(by_key.keys())}, "
            f"required: {list(grader_mod.CRITERION_KEYS)})"
        )

    # CRITERION_KEYS 순서로 정렬
    return [by_key[k] for k in grader_mod.CRITERION_KEYS]


def _normalize_eval_notes(raw: Any) -> dict[str, Any]:
    """eval_notes 검증 + 정규화 — Phase 1 확장 (lawear-e571, 2026-05-19).

    legacy 키 (strength/caution/missing) + 확장 키 (strengths/weaknesses/
    missing_critical/score_summary/next_study_oneliner/next_study_actionable/
    pattern_warning/typo_corrections) 모두 보존.

    Raises:
        GradeInjectionError: dict 아님, pattern_warning 잘못된 타입(list/dict),
                             또는 typo_corrections 가 list/null 외 타입.

    Returns:
        {
          "strength": str,
          "caution": str,
          "missing": str,
          "score_summary": str,
          "strengths": list[str],
          "weaknesses": list[str],
          "missing_critical": list[dict],  # [{item, expected_score_impact}]
          "next_study_oneliner": str,
          "next_study_actionable": list[str],
          "pattern_warning": str | None,   # 반복 실수 패턴 경고 (없으면 None)
          "typo_corrections": list[dict] | None,
            # 음성 STT 오타 교정 (없으면 None)
            # 각 dict: {from: str, to: str, reason: str} — 다른 키도 보존 (R-09)
        }

        - 없는 키는 빈 문자열/빈 배열 (호환성 — SE가 일부만 보내도 저장).
        - alias (weakness → weaknesses) 자동 정규화.
        - missing_critical 항목은 {item: str, expected_score_impact: int|float}
          형식으로 강제 — 자유형 dict 도 그대로 보존 (R-09 가공 X).
        - pattern_warning 은 str | None — list/dict 입력 시 GradeInjectionError.
          빈 문자열은 None 으로 정규화 (UI 분기 단순화).
        - typo_corrections 는 list[dict] | None — 빈 list 는 None 으로 정규화.
          각 dict: {from: str, to: str, reason: str} 강제 + 다른 키 보존.
          잘못된 타입(dict/str/int 등)은 GradeInjectionError.
    """
    if not isinstance(raw, dict):
        raise GradeInjectionError(
            f"eval_notes must be object, got {type(raw).__name__}"
        )

    out: dict[str, Any] = {}

    # alias 처리: weakness → weaknesses 미존재 시만 wrap
    src = dict(raw)
    for alias_key, target_key in _EVAL_NOTES_ALIASES.items():
        if alias_key in src and target_key not in src:
            src[target_key] = src.pop(alias_key)

    # legacy str 키 (3개)
    for k in _EVAL_NOTES_KEYS_LEGACY:
        out[k] = str(src.get(k) or "")

    # 확장 str 키 (score_summary / next_study_oneliner)
    for k in _EVAL_NOTES_KEYS_EXT_STR:
        out[k] = str(src.get(k) or "")

    # 확장 list 키 (strengths / weaknesses / missing_critical / next_study_actionable)
    for k in _EVAL_NOTES_KEYS_EXT_LIST:
        v = src.get(k)
        if v is None:
            out[k] = []
        elif isinstance(v, list):
            # missing_critical 만 dict element 허용, 나머지는 str element
            if k == "missing_critical":
                normalized_list: list[dict[str, Any]] = []
                for item in v:
                    if isinstance(item, dict):
                        # item / expected_score_impact 키 정규화 (없으면 그대로)
                        normalized_item: dict[str, Any] = {}
                        if "item" in item:
                            normalized_item["item"] = str(item["item"] or "")
                        if "expected_score_impact" in item:
                            try:
                                normalized_item["expected_score_impact"] = float(
                                    item["expected_score_impact"]
                                )
                            except (TypeError, ValueError):
                                normalized_item["expected_score_impact"] = 0.0
                        # 다른 키도 보존 (R-09 가공 X)
                        for ek, ev in item.items():
                            if ek not in ("item", "expected_score_impact"):
                                normalized_item[ek] = ev
                        normalized_list.append(normalized_item)
                    elif isinstance(item, str):
                        # str 그대로 들어오면 item 키로 wrap
                        normalized_list.append({"item": item, "expected_score_impact": 0.0})
                out[k] = normalized_list
            else:
                # 일반 str list (strengths / weaknesses / next_study_actionable)
                out[k] = [str(x) for x in v if x is not None]
        elif isinstance(v, str):
            # str 단일 값으로 들어오면 1-item list 로 보존 (호환)
            out[k] = [v] if v.strip() else []
        else:
            out[k] = []

    # pattern_warning — str | None (잘못된 타입은 즉시 거부)
    for k in _EVAL_NOTES_KEYS_EXT_OPT_STR:
        v = src.get(k)
        if v is None:
            out[k] = None
        elif isinstance(v, str):
            stripped = v.strip()
            out[k] = stripped if stripped else None
        else:
            raise GradeInjectionError(
                f"eval_notes.{k} must be string or null, got {type(v).__name__}"
            )

    # typo_corrections — list[dict] | None (lawear-e571/typo-system, 2026-05-19)
    # 빈 list 는 None 으로 정규화 — UI 분기 단순화.
    # 각 dict: {from: str, to: str, reason: str} — 다른 키도 보존.
    for k in _EVAL_NOTES_KEYS_EXT_OPT_LIST:
        v = src.get(k)
        if v is None:
            out[k] = None
        elif isinstance(v, list):
            normalized_corrections: list[dict[str, Any]] = []
            for item in v:
                if not isinstance(item, dict):
                    # str / int 등 비-dict 항목은 from-only 로 wrap (graceful, R-09 가공 X)
                    if isinstance(item, str) and item.strip():
                        normalized_corrections.append({
                            "from": item, "to": "", "reason": ""
                        })
                    continue
                normalized_item: dict[str, Any] = {}
                # 필수 3키 (string 강제) — None/missing 도 빈문자로
                normalized_item["from"] = str(item.get("from") or "")
                normalized_item["to"] = str(item.get("to") or "")
                normalized_item["reason"] = str(item.get("reason") or "")
                # 추가 키 보존 (R-09 — source/severity 등 미래 확장)
                for ek, ev in item.items():
                    if ek not in ("from", "to", "reason"):
                        normalized_item[ek] = ev
                # from 이 빈문자면 의미 없음 — skip
                if normalized_item["from"]:
                    normalized_corrections.append(normalized_item)
            out[k] = normalized_corrections if normalized_corrections else None
        else:
            raise GradeInjectionError(
                f"eval_notes.{k} must be array or null, got {type(v).__name__}"
            )

    return out


def _normalize_diff_segments(raw: Any) -> list[dict[str, str]]:
    """diff_segments 검증 + 정규화. None/누락 시 빈 배열."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise GradeInjectionError(
            f"diff_segments must be array, got {type(raw).__name__}"
        )
    out: list[dict[str, str]] = []
    for seg in raw:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type", "match")
        if seg_type not in _DIFF_SEGMENT_TYPES:
            seg_type = "match"
        text = seg.get("text", "")
        if not isinstance(text, str):
            text = str(text)
        out.append({"type": seg_type, "text": text})
    return out


def inject_grade(
    conn: sqlite3.Connection,
    attempt_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """PUT /api/attempts/{id}/grade — 외부 채점 결과 주입.

    Step 13 사용자 명시 (2026-05-16):
      Claude Code 메인 세션(Opus)이 채점 → 결과를 17896 에 주입.
      attempt.status='pending_grade' (또는 호환 'grading') → 'done' 전환.

    Step 24-3 확장 (2026-05-18):
      `criteria_subq` 옵션 추가 — 다중 설문 카드별 9기준 채점 결과 주입.
      legacy `criteria` (1차원 list, subq_key=NULL) 와 양립 가능.

    Args:
        conn:       핸들러 보유 DB connection.
        attempt_id: 대상 attempt PK.
        payload:    외부 채점 결과 JSON. 스키마 (legacy):
            {
              "criteria": [{key, score, weight_applied, comment}] × 9,
              "total_score": float,
              "max_score": float,
              "score_pct": float,
              "grade": "A"|"B"|"C"|"F",
              "eval_notes": {strength, caution, missing},
              "diff_segments": [{type, text}]?,    # optional
              "model": str?,                       # optional — 디폴트 "claude-code-opus"
            }

            Step 24-3 다중 설문 스키마 (criteria 대신):
            {
              "criteria_subq": {
                "설문 1": [{key, score, weight_applied, comment}, ...],
                "설문 2": [...]
              },
              "total_score": float, ...
            }

            ``criteria_subq`` 우선 — 있으면 ``criteria`` 무시 가능 (양쪽 다 있으면
            criteria_subq 만 사용). 빈 dict 또는 dict 아닌 값 → ``GradeInjectionError``.

    Returns:
        {"attempt_id", "status": "completed", "total_score", "max_score",
         "score_pct", "grade", "case_id", ...}

    Raises:
        AttemptNotFoundError:       attempt_id 미존재.
        AttemptAlreadyGradedError:  status='done' (재채점 별도 endpoint).
        GradeInjectionError:        필수 필드 누락 / 9기준 누락 / 형식 오류.
    """
    # 1. attempt 존재 + status 가드
    cur = conn.execute(
        "SELECT id, case_id, status, submitted_at FROM attempts WHERE id = ?",
        (int(attempt_id),),
    )
    row = cur.fetchone()
    if row is None:
        raise AttemptNotFoundError(f"attempt_id={attempt_id}")

    current_status = row["status"]
    if current_status == DB_STATUS_DONE:
        raise AttemptAlreadyGradedError(
            f"attempt {attempt_id} already completed (status='done'). "
            "Re-grading endpoint not implemented in Step 13."
        )
    if current_status not in (DB_STATUS_PENDING_GRADE, DB_STATUS_GRADING):
        raise GradeInjectionError(
            f"attempt {attempt_id} status={current_status!r} is not graded-able "
            f"(allowed: pending_grade, grading)",
            "bad_request",
        )

    # 2. payload 필수 필드 — Step 24-3: criteria 또는 criteria_subq 둘 중 하나 필수
    has_subq_payload = "criteria_subq" in payload
    has_legacy_payload = "criteria" in payload
    if not has_subq_payload and not has_legacy_payload:
        raise GradeInjectionError(
            "missing required fields: either 'criteria' (legacy 1차원) or "
            "'criteria_subq' (다중 설문 dict) required",
            "criteria_subq_required",
        )
    # criteria 외 다른 필수 필드는 그대로 (criteria 자리만 분기)
    other_required = tuple(f for f in _REQUIRED_INJECT_FIELDS if f != "criteria")
    missing_fields = [f for f in other_required if f not in payload]
    if missing_fields:
        raise GradeInjectionError(f"missing required fields: {missing_fields}")

    # 3. 필드별 정규화 — Step 24-3 분기.
    #    criteria_by_subq: {subq_key 또는 None: [{key, score, max, weight, comment}] × 9}
    criteria_by_subq: dict[str | None, list[dict[str, Any]]] = {}
    if has_subq_payload:
        raw_subq = payload["criteria_subq"]
        if not isinstance(raw_subq, dict) or not raw_subq:
            raise GradeInjectionError(
                f"criteria_subq must be non-empty dict, got {type(raw_subq).__name__}",
                "criteria_subq_required",
            )
        for sk, raw_list in raw_subq.items():
            if not isinstance(sk, str) or not sk.strip():
                raise GradeInjectionError(
                    f"criteria_subq key must be non-empty string, got {sk!r}"
                )
            criteria_by_subq[sk.strip()] = _normalize_criteria(raw_list)
    else:
        # legacy 단일 모드 — subq_key=None 으로 1개 entry
        criteria_by_subq[None] = _normalize_criteria(payload["criteria"])

    eval_notes_normalized = _normalize_eval_notes(payload["eval_notes"])
    # lawear-9bdc/typo-system-v2 — POST 시점 typo_corrections 머지 (PUT /grade 덮어쓰기 방지)
    _merge_initial_typo_corrections(conn, int(attempt_id), eval_notes_normalized)
    diff_segments_normalized = _normalize_diff_segments(payload.get("diff_segments"))

    # total/max/pct 숫자 검증
    # Step 20 (v4, 2026-05-16): 소수점 2자리 round — 실제 시험 형식.
    try:
        total_score = round(float(payload["total_score"]), 2)
        max_score = round(float(payload["max_score"]), 2)
        score_pct = round(float(payload["score_pct"]), 2)
    except (TypeError, ValueError) as e:
        raise GradeInjectionError(
            f"total_score/max_score/score_pct must be numbers: {e}"
        ) from e

    # grade enum 검증 (DB CHECK 와 동일)
    # lawear-e571 (2026-05-19) — V2 grade (A+/A/A-/B+/B/B-/C+/C/C-) 도 입력 허용.
    # 단 DB 저장은 V1 enum (A/B/C/F) 강제 — grader_mod._to_v1_grade 변환.
    grade_raw = payload["grade"]
    if not isinstance(grade_raw, str):
        raise GradeInjectionError(
            f"grade must be a string, got {grade_raw!r}"
        )
    grade_input = grade_raw.upper().strip()
    _V1_ENUM = ("A", "B", "C", "F", "ERROR")
    _V2_ENUM = ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "F", "ERROR")
    if grade_input not in _V1_ENUM and grade_input not in _V2_ENUM:
        raise GradeInjectionError(
            f"grade must be one of "
            f"V1 {_V1_ENUM} or V2 {_V2_ENUM}, got {grade_raw!r}"
        )
    # DB 저장은 V1 enum 강제 (CHECK 호환). V2 grade 는 응답 시 score_pct 기준 재계산.
    if grade_input in ("ERROR",):
        grade = "ERROR"
    elif grade_input in _V1_ENUM:
        grade = grade_input
    else:
        grade = grader_mod._to_v1_grade(grade_input)

    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        model = "claude-code-opus"  # 디폴트 — Claude Code 메인 세션이 채점

    # 4. 단일 트랜잭션 — UPDATE attempts + INSERT attempt_criteria × (N카드 × 9기준)
    completed_at = _utcnow_iso()
    elapsed = _elapsed_since(row["submitted_at"])
    eval_notes_json = json.dumps(eval_notes_normalized, ensure_ascii=False)
    diff_json = json.dumps(diff_segments_normalized, ensure_ascii=False)
    raw_response = json.dumps(payload, ensure_ascii=False)
    # diff_html (시안 .diff-area 호환)
    diff_html = _diff_segments_to_html(diff_segments_normalized)

    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            conn.execute("BEGIN")

        conn.execute(
            """
            UPDATE attempts
               SET status         = ?,
                   score_total    = ?,
                   score_max      = ?,
                   score_pct      = ?,
                   grade          = ?,
                   model          = ?,
                   eval_notes_json = ?,
                   diff_json      = ?,
                   raw_response   = ?,
                   completed_at   = ?,
                   elapsed_sec    = ?,
                   is_mock        = 0,
                   error_code     = NULL,
                   error_message  = NULL
             WHERE id = ?
            """,
            (
                DB_STATUS_DONE,
                total_score,
                max_score,
                score_pct,
                grade,
                model,
                eval_notes_json,
                diff_json,
                raw_response,
                completed_at,
                elapsed,
                int(attempt_id),
            ),
        )

        # pending_grade 였으면 row 없음. grading 이었으면 부분 채점 row 있을 수 있어 DELETE.
        conn.execute(
            "DELETE FROM attempt_criteria WHERE attempt_id = ?", (int(attempt_id),)
        )
        # Step 24-3 — subq_key 별로 9기준 row 다중 INSERT (legacy NULL 모드 호환)
        for sk, criteria_list in criteria_by_subq.items():
            for c in criteria_list:
                conn.execute(
                    """
                    INSERT INTO attempt_criteria
                      (attempt_id, subq_key, criterion_key, score, max_score, weight, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(attempt_id),
                        sk,  # None=legacy 단일 / 문자열=다중 카드
                        c["key"],
                        float(c["score"]),
                        float(c["max"]),
                        float(c["weight"]),
                        c["comment"],
                    ),
                )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except sqlite3.DatabaseError:
            pass
        raise

    print(
        f"[Attempts] inject_grade attempt_id={attempt_id} status=done "
        f"score={total_score}/{max_score} pct={score_pct} grade={grade} model={model} "
        f"subqs={len(criteria_by_subq)}",
        file=sys.stderr,
    )

    # 5. 응답 — 클라이언트 폴링이 받을 형식과 동일하게
    return get_attempt(conn, attempt_id)


def reset_grade(conn: sqlite3.Connection, attempt_id: int) -> dict[str, Any]:
    """DELETE /api/attempts/{id}/grade — 채점 결과 reset (답안 보존).

    Step 17 (사용자 명시 2026-05-16):
      Evaluation 탭/Reports 모달의 "재채점" 버튼 진입점.
      attempt 의 answer_text/started_at/submitted_at/weights_json 는 그대로 두고,
      채점 산출물만 NULL 로 비운 뒤 status='pending_grade' 로 되돌림.

    동작 매트릭스:
      - status='done'           → UPDATE + attempt_criteria DELETE (재채점 진입)
      - status='pending_grade'  → noop (이미 미채점 상태)
      - status='grading'        → noop (백그라운드 채점 진행 중 — 강제 reset 위험)
      - status='error'          → reset (error 도 다시 채점 받을 수 있어야 함 — 사용자 명시)

    단일 트랜잭션. attempt_criteria 는 done/error 시도에만 존재 가능.

    Raises:
        AttemptNotFoundError: attempt_id 미존재 (HTTP 404).

    Returns:
        {"attempt_id", "status": "pending_grade", "message": str}
        - reset 수행 시: message="Grade reset OK"
        - noop 시:      message="No grade to reset (status=...)"
    """
    cur = conn.execute(
        "SELECT id, status FROM attempts WHERE id = ?", (int(attempt_id),)
    )
    row = cur.fetchone()
    if row is None:
        raise AttemptNotFoundError(f"attempt_id={attempt_id}")

    current_status = row["status"]

    # noop — 이미 채점 결과가 없는 상태
    if current_status == DB_STATUS_PENDING_GRADE:
        return {
            "attempt_id": int(attempt_id),
            "status": _client_status(DB_STATUS_PENDING_GRADE),
            "message": f"No grade to reset (status='{current_status}')",
        }
    if current_status == DB_STATUS_GRADING:
        # 백그라운드 채점 진행 중일 가능성 — 강제 reset 시 race condition.
        # 사용자 명시: grading 도 noop (진행 중인 자동 채점 중단 권한은 별도 endpoint 필요).
        return {
            "attempt_id": int(attempt_id),
            "status": _client_status(DB_STATUS_GRADING),
            "message": f"Grading in progress — reset skipped (status='{current_status}')",
        }

    # done / error → reset
    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            conn.execute("BEGIN")

        conn.execute(
            """
            UPDATE attempts
               SET status          = ?,
                   score_total     = NULL,
                   score_max       = NULL,
                   score_pct       = NULL,
                   grade           = NULL,
                   eval_notes_json = NULL,
                   diff_json       = NULL,
                   raw_response    = NULL,
                   completed_at    = NULL,
                   elapsed_sec     = NULL,
                   model           = NULL,
                   is_mock         = 0,
                   error_code      = NULL,
                   error_message   = NULL
             WHERE id = ?
            """,
            (DB_STATUS_PENDING_GRADE, int(attempt_id)),
        )
        conn.execute(
            "DELETE FROM attempt_criteria WHERE attempt_id = ?", (int(attempt_id),)
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except sqlite3.DatabaseError:
            pass
        raise

    print(
        f"[Attempts] reset_grade attempt_id={attempt_id} "
        f"prev_status={current_status!r} → 'pending_grade'",
        file=sys.stderr,
    )

    return {
        "attempt_id": int(attempt_id),
        "status": _client_status(DB_STATUS_PENDING_GRADE),
        "message": "Grade reset OK",
    }


def _attempt_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """attempts row → API 응답 dict (criteria 제외, 호출자가 join 추가).

    Step 23 — solve_elapsed_sec: 사용자 풀이 시간 (submitted_at - started_at).
    기존 elapsed_sec 는 grader 채점 elapsed (의미 다름) — 둘 다 노출.

    Step 24-3 — answer_subq / subq_elapsed / hints_used (마이그 v6) + 메타.
      - legacy attempts (answer_subq NULL) → 위 3키 모두 None 노출 + 메타 0.
      - 다중 카드 attempts → JSON dict deserialize + 메타 계산.
    """
    db_status = row["status"]

    # Step 24-3 — 카드별 dict 3종 deserialize (legacy NULL → None 유지)
    # sqlite3.Row 는 컬럼 미존재 시 IndexError, _attempt_row_to_dict 가 v5 이하
    # DB 에서 호출되는 일은 없으나 안전성 강화 (try/except).
    try:
        ans_json = row["answer_subq"]
    except (IndexError, KeyError):
        ans_json = None
    try:
        elap_json = row["subq_elapsed"]
    except (IndexError, KeyError):
        elap_json = None
    try:
        hints_json = row["hints_used"]
    except (IndexError, KeyError):
        hints_json = None
    answer_subq_val, subq_elapsed_val, hints_used_val = _deserialize_subq_dicts(
        ans_json, elap_json, hints_json
    )
    hint_meta = _compute_hint_meta(hints_used_val)

    out: dict[str, Any] = {
        "id": row["id"],
        "attempt_id": row["id"],  # 클라이언트 호환 alias
        "case_id": row["case_id"],
        "status": _client_status(db_status),
        "db_status": db_status,  # 디버그용
        "submitted_at": row["submitted_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "elapsed_sec": row["elapsed_sec"],
        "solve_elapsed_sec": _solve_elapsed_sec(
            row["started_at"], row["submitted_at"]
        ),
        "is_stale": bool(row["is_stale"]),
        "is_mock": bool(row["is_mock"]),
        # Step 24-3 — 다중 설문 D안 키 5종
        "answer_subq": answer_subq_val,
        "subq_elapsed": subq_elapsed_val,
        "hints_used": hints_used_val,
        "hints_used_count": hint_meta["count"],
        "hint_steps_revealed_max": hint_meta["steps_max"],
    }
    # lawear-e571 (2026-05-19) — total_solve_sec fallback (단건 get_attempt 누락 fix).
    # list_attempts 와 동일 로직: subq_elapsed 합 우선, 0 또는 None 시 solve_elapsed_sec fallback.
    out["total_solve_sec"] = _compute_total_solve_sec(
        subq_elapsed_val, out["solve_elapsed_sec"]
    )
    if db_status == DB_STATUS_DONE:
        out["score_total"] = row["score_total"]
        out["score_max"] = row["score_max"]
        out["score_pct"] = row["score_pct"]
        # lawear-e571 (2026-05-19) — DB grade 는 legacy V1 (A/B/C/F), 응답은 V2 (10단계) 재계산.
        # legacy attempts 도 V2 grade 가 score_pct 기준으로 일관 표시됨.
        out["grade"] = _recompute_grade_v2(row["score_pct"])
        out["grade_v1"] = row["grade"]  # 디버그/하위호환용 (legacy A/B/C/F)
        out["is_pass"] = _is_pass(row["score_pct"])  # 합격선 (60+) 시각화용
        out["model"] = row["model"]
        # Step 14 — 시안 Reference Diff 2열 분할(내 답안 vs Lv.1)을 위해 done 응답에도 answer_text 포함.
        # pending_grade 와 대칭. R-09 — 원문 그대로 (가공 X).
        try:
            out["answer_text"] = row["answer_text"]
        except (IndexError, KeyError):
            out["answer_text"] = None
        # eval_notes_json / diff_json 파싱
        try:
            out["eval_notes"] = json.loads(row["eval_notes_json"]) if row["eval_notes_json"] else {}
        except (TypeError, json.JSONDecodeError):
            out["eval_notes"] = {}
        try:
            out["diff_segments"] = json.loads(row["diff_json"]) if row["diff_json"] else []
        except (TypeError, json.JSONDecodeError):
            out["diff_segments"] = []
        # weights_applied
        try:
            out["weights_applied"] = json.loads(row["weights_json"]) if row["weights_json"] else {}
        except (TypeError, json.JSONDecodeError):
            out["weights_applied"] = {}
        # diff_html: diff_segments → 단순 HTML span 렌더 (시안 호환)
        out["diff_html"] = _diff_segments_to_html(out["diff_segments"])
    elif db_status == DB_STATUS_GRADING:
        # elapsed_sec live 계산 (폴링)
        out["elapsed_sec"] = round(_elapsed_since(row["submitted_at"]), 2)
    elif db_status == DB_STATUS_PENDING_GRADE:
        # Step 13 — Claude Code 외부 채점 대기. elapsed_sec live + answer_text 노출 (채점 자료).
        out["elapsed_sec"] = round(_elapsed_since(row["submitted_at"]), 2)
        # answer_text 전체 — 메인 Opus 가 채점에 사용 (R-09: 요약 X)
        try:
            out["answer_text"] = row["answer_text"]
        except (IndexError, KeyError):
            out["answer_text"] = None
    elif db_status == DB_STATUS_ERROR:
        out["error_code"] = row["error_code"]
        out["error_message"] = row["error_message"]
        out["retryable"] = (row["error_code"] or "") in (
            "anthropic_rate_limit",
            "anthropic_bad_gateway",
        )
    return out


def _diff_segments_to_html(segments: list[dict[str, str]]) -> str:
    """diff_segments → HTML (시안 .diff-area .match/.miss/.partial 와 동일 클래스)."""
    if not segments:
        return ""
    out_parts: list[str] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type", "match")
        if seg_type not in ("match", "miss", "partial"):
            seg_type = "match"
        text = str(seg.get("text") or "")
        # 최소 escape — diff_segments 의 text 는 사용자/Grader 입력
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
        out_parts.append(f'<span class="{seg_type}">{escaped}</span>')
    return "".join(out_parts)


def get_attempt(conn: sqlite3.Connection, attempt_id: int) -> dict[str, Any]:
    """GET /api/attempts/{id} — 단건 조회 + criteria N개 join.

    status='grading': elapsed_sec live 계산.
    status='done':    criteria 배열 + diff_html + eval_notes + weights_applied.
    status='error':   error_code + error_message + retryable.

    Step 24-3 — attempt_criteria.subq_key 노출:
      - 다중 설문 (subq_key non-NULL) → ``criteria_subq`` dict 추가 (legacy ``criteria``
        는 첫 카드 또는 단일 모드만 보존).
      - 단일 설문 (subq_key NULL) → 기존 ``criteria`` list 그대로 (legacy 호환).
    """
    cur = conn.execute("SELECT * FROM attempts WHERE id = ?", (int(attempt_id),))
    row = cur.fetchone()
    if row is None:
        raise AttemptNotFoundError(f"attempt_id={attempt_id}")

    out = _attempt_row_to_dict(row)

    # case_title (시안 Reports / Reviewer Notes 등 표시용)
    # e571-score-display — case_points 추가 (실제 시험 배점, 100점 환산용)
    cur = conn.execute(
        "SELECT title, file, case_no, points FROM cases WHERE id = ?",
        (out["case_id"],),
    )
    crow = cur.fetchone()
    if crow:
        out["case_title"] = crow["title"]
        out["case_short_id"] = f"{crow['file']}-{crow['case_no']}"
        # case_points: cases.points (시험 배점) — legacy cases 면 None graceful
        try:
            out["case_points"] = crow["points"]
        except (IndexError, KeyError):
            out["case_points"] = None
    else:
        out["case_points"] = None

    # criteria (done 시만 — grading/error 시도 row 가 있을 수 있으나 비어있음)
    if out["db_status"] == DB_STATUS_DONE:
        cur = conn.execute(
            """
            SELECT criterion_key, score, max_score, weight, comment, subq_key
              FROM attempt_criteria
             WHERE attempt_id = ?
             ORDER BY id ASC
            """,
            (int(attempt_id),),
        )
        criteria_rows = cur.fetchall()

        # Step 24-3 — subq_key 별 그룹핑. NULL=legacy 단일 모드.
        criteria_subq_map: dict[str | None, dict[str, dict[str, Any]]] = {}
        for r in criteria_rows:
            try:
                sk = r["subq_key"]
            except (IndexError, KeyError):
                sk = None
            ck = r["criterion_key"]
            criteria_subq_map.setdefault(sk, {})[ck] = {
                "key": ck,
                "score": r["score"],
                "max": r["max_score"],
                "weight": r["weight"],
                "comment": r["comment"] or "",
            }

        # 다중 설문 — subq_key non-NULL 1개 이상이면 criteria_subq 추가.
        non_null_subq_keys = [k for k in criteria_subq_map if k is not None]
        if non_null_subq_keys:
            criteria_subq_out: dict[str, list[dict[str, Any]]] = {}
            for sk in non_null_subq_keys:
                by_key = criteria_subq_map[sk]
                criteria_subq_out[sk] = [
                    by_key[ck] for ck in grader_mod.CRITERION_KEYS if ck in by_key
                ]
            out["criteria_subq"] = criteria_subq_out
            # legacy criteria — 첫 카드 (호환용 1차원 list)
            first_sk = non_null_subq_keys[0]
            out["criteria"] = criteria_subq_out[first_sk]
        else:
            # 단일 모드 (legacy) — criteria_subq_map[None] 에서 추출
            by_key = criteria_subq_map.get(None, {})
            out["criteria"] = [
                by_key[ck] for ck in grader_mod.CRITERION_KEYS if ck in by_key
            ]

    return out


def list_attempts(
    conn: sqlite3.Connection,
    *,
    case_id: str | None = None,
    subject: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    status: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    """GET /api/attempts — 시도 목록 (Reports / 사이드바 보조용).

    Returns:
        {
          "attempts": [...],       # 페이지 결과 (한건당 정렬: submitted_at DESC)
          "total":    N,           # 총 (필터 적용 후) 카운트
          "limit":    int,
          "offset":   int,
        }

    Args:
        case_id:   exact match
        subject:   cases.subject = 'minbeop' 등 (JOIN)
        from_date: 'YYYY-MM-DD' or ISO-8601 (submitted_at >= ?)
        to_date:   같은 형식 (submitted_at <= ?)
        status:    'completed' / 'failed' / 'grading' (클라이언트 라벨) → db_status 매핑
        limit:     클램프 1..MAX_LIST_LIMIT
        offset:    >=0
    """
    where: list[str] = []
    params: list[Any] = []

    if case_id:
        where.append("a.case_id = ?")
        params.append(case_id)
    if subject:
        where.append("c.subject = ?")
        params.append(subject)
    if from_date:
        where.append("a.submitted_at >= ?")
        params.append(from_date)
    if to_date:
        where.append("a.submitted_at <= ?")
        params.append(to_date)
    if status:
        # 클라이언트 라벨 → DB enum (역매핑)
        rev = {v: k for k, v in CLIENT_STATUS_MAP.items()}
        db_st = rev.get(status, status)  # 'grading'/'done'/'error' 직접 허용
        where.append("a.status = ?")
        params.append(db_st)

    # clamp
    try:
        limit_i = max(1, min(MAX_LIST_LIMIT, int(limit)))
    except (TypeError, ValueError):
        limit_i = DEFAULT_LIST_LIMIT
    try:
        offset_i = max(0, int(offset))
    except (TypeError, ValueError):
        offset_i = 0

    where_sql = " AND ".join(where) if where else "1=1"

    # 총 카운트 (limit 무시)
    count_sql = f"""
        SELECT COUNT(*) AS cnt
          FROM attempts a
          LEFT JOIN cases c ON a.case_id = c.id
         WHERE {where_sql}
    """
    cur = conn.execute(count_sql, tuple(params))
    crow = cur.fetchone()
    total = int(crow["cnt"]) if crow else 0

    # 페이지
    # Step 13 — pending_grade 필터 시 answer_text 도 반환 (외부 채점 자료).
    # 다른 status 에서도 응답에 포함 (메인 Opus 가 'pending 채점' 명령으로 본 endpoint 호출).
    # Step 23 — started_at + solve_elapsed_sec (= submitted - started) 노출.
    # Step 24-3 — answer_subq / subq_elapsed / hints_used (JSON TEXT) 노출
    #            → 히스토리 패널 "힌트 N회" / "최대 단계 K" / "카드 수 M" 표시용 메타.
    page_sql = f"""
        SELECT a.id, a.case_id, a.started_at, a.submitted_at, a.completed_at, a.status,
               a.answer_text,
               a.answer_subq, a.subq_elapsed, a.hints_used,
               a.score_total, a.score_max, a.score_pct, a.grade,
               a.is_stale, a.is_mock, a.error_code,
               c.title AS case_title, c.subject AS case_subject,
               c.subject_kor AS case_subject_kor,
               c.file AS case_file, c.case_no AS case_no_str,
               c.points AS case_points
          FROM attempts a
          LEFT JOIN cases c ON a.case_id = c.id
         WHERE {where_sql}
         ORDER BY a.submitted_at DESC, a.id DESC
         LIMIT ? OFFSET ?
    """
    cur = conn.execute(page_sql, tuple(params) + (limit_i, offset_i))
    rows = cur.fetchall()
    items: list[dict[str, Any]] = []
    for r in rows:
        # Step 24-3 — 카드별 dict 3종 deserialize + 메타 산출
        ans_subq, elap, hints = _deserialize_subq_dicts(
            r["answer_subq"], r["subq_elapsed"], r["hints_used"]
        )
        hint_meta_row = _compute_hint_meta(hints)
        subq_count_val = len(ans_subq) if isinstance(ans_subq, dict) and ans_subq else 0
        # total_solve_sec — 카드별 elapsed 합산 (legacy 단일 → None)
        # lawear-e571/grader-tune-fallback (2026-05-19): subq_elapsed 합=0이고
        # solve_elapsed_sec(submitted-started)>0 → 트래킹 누락 시 solve_elapsed_sec fallback.
        # 단일 카드 모드("단일": 0) 또는 다중 카드 트래킹 실패 시 UI 0초 표시 방지.
        solve_elapsed_val = _solve_elapsed_sec(r["started_at"], r["submitted_at"])
        total_solve = _compute_total_solve_sec(elap, solve_elapsed_val)

        # e571-score-display — case_points 노출 (legacy NULL 그대로)
        try:
            case_points_val = r["case_points"]
        except (IndexError, KeyError):
            case_points_val = None

        items.append(
            {
                "id": r["id"],
                "attempt_id": r["id"],
                "case_id": r["case_id"],
                "case_title": r["case_title"],
                "case_short_id": f"{r['case_file']}-{r['case_no_str']}"
                if r["case_file"]
                else None,
                "case_subject": r["case_subject"],
                "case_subject_kor": r["case_subject_kor"],
                # e571-score-display — 실제 시험 배점 (n/case_points 표시용)
                "case_points": case_points_val,
                "started_at": r["started_at"],
                "submitted_at": r["submitted_at"],
                "completed_at": r["completed_at"],
                "status": _client_status(r["status"]),
                "answer_text": r["answer_text"],
                "score_total": r["score_total"],
                "score_max": r["score_max"],
                "score_pct": r["score_pct"],
                "grade": r["grade"],
                "is_stale": bool(r["is_stale"]),
                "is_mock": bool(r["is_mock"]),
                "error_code": r["error_code"],
                "solve_elapsed_sec": solve_elapsed_val,
                # Step 24-3 메타 (히스토리 패널 표시용)
                "subq_count": subq_count_val,
                "hints_used_count": hint_meta_row["count"],
                "hint_steps_revealed_max": hint_meta_row["steps_max"],
                "total_solve_sec": total_solve,
            }
        )

    return {
        "attempts": items,
        "total": total,
        "limit": limit_i,
        "offset": offset_i,
    }
