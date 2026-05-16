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
import sqlite3
import sys
import threading
import time
from typing import Any

import cases as cases_mod
import db as db_mod
import grader as grader_mod

# ─── 상수 ────────────────────────────────────────────────────────────────

# attempts.status CHECK 는 v1 그대로 ('grading','done','error').
# 사양에서 사용자가 명시한 'completed'/'failed' 는 클라이언트 응답 라벨로만 매핑.
DB_STATUS_GRADING: str = "grading"
DB_STATUS_DONE: str = "done"
DB_STATUS_ERROR: str = "error"

# Reports / 클라이언트 응답에 노출되는 상태 라벨
CLIENT_STATUS_MAP: dict[str, str] = {
    DB_STATUS_GRADING: "grading",
    DB_STATUS_DONE: "completed",  # 사양 align
    DB_STATUS_ERROR: "failed",  # 사양 align
}

# settings.weights 키 (없을 때 fallback)
SETTINGS_WEIGHTS_KEY: str = "weights"

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


# ─── 유틸 ────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    """ISO-8601 UTC ('YYYY-MM-DDTHH:MM:SSZ')."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _client_status(db_status: str) -> str:
    return CLIENT_STATUS_MAP.get(db_status, db_status)


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


def _save_grade_result(db_path: str, attempt_id: int, result: dict[str, Any]) -> None:
    """채점 결과를 단일 트랜잭션으로 저장.

    BEGIN → UPDATE attempts (status=done, score_*, grade, model, eval_notes_json,
            diff_json, raw_response, completed_at, elapsed_sec, is_mock)
         → 7×INSERT OR REPLACE attempt_criteria (criterion_key UNIQUE per attempt)
         → COMMIT
    """
    completed_at = _utcnow_iso()
    eval_notes_json = json.dumps(result.get("eval_notes", {}), ensure_ascii=False)
    diff_json = json.dumps(result.get("diff_segments", []), ensure_ascii=False)
    criteria = result.get("criteria") or []
    is_mock_int = 1 if result.get("is_mock") else 0

    conn = db_mod.get_conn(db_path)
    try:
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
                result.get("grade") or "F",
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
    answer_text: str,
    *,
    started_at: str | None = None,
    submitted_at: str | None = None,
) -> dict[str, Any]:
    """POST /api/attempts — 즉시 INSERT + daemon thread 트리거.

    Args:
        conn:         (요청 핸들러가 보유한) DB connection — INSERT 전용. 트랜잭션 분리.
        db_path:      백그라운드 thread 가 별도 conn 을 열기 위한 경로.
        case_id:      cases.id (FK).
        answer_text:  검토 의견 본문. 빈 값/공백만 → 400.
        started_at:   클라이언트 시작 시각 (선택).
        submitted_at: 클라이언트 제출 시각 (선택, 기본 utcnow).

    Returns:
        {"attempt_id": int, "status": "grading", "case_id": str, "submitted_at": str}

    Raises:
        AttemptValidationError: answer_text 빈 값.
        cases.CaseNotFoundError: case_id 미존재 — 호출자가 404 로 매핑.
    """
    if not answer_text or not answer_text.strip():
        raise AttemptValidationError("answer_text empty", "bad_request")
    if not case_id or not case_id.strip():
        raise AttemptValidationError("case_id empty", "bad_request")

    # case_meta 로드 (.md 본문 포함) — 미존재 시 CaseNotFoundError → 404
    case_meta = cases_mod.get_case(conn, case_id)

    # weights 로드 (없으면 DEFAULT)
    weights = _load_weights(conn)
    weights_json = json.dumps(weights, ensure_ascii=False)

    submitted = submitted_at or _utcnow_iso()

    # INSERT attempts (status='grading')
    cur = conn.execute(
        """
        INSERT INTO attempts
          (case_id, answer_text, started_at, submitted_at, status, weights_json, is_stale)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (
            case_id,
            answer_text,
            started_at,
            submitted,
            DB_STATUS_GRADING,
            weights_json,
        ),
    )
    conn.commit()
    attempt_id = int(cur.lastrowid or 0)
    if attempt_id <= 0:
        raise RuntimeError("attempt INSERT returned invalid lastrowid")

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
        f"thread={th.name} (background)",
        file=sys.stderr,
    )

    return {
        "attempt_id": attempt_id,
        "status": _client_status(DB_STATUS_GRADING),
        "case_id": case_id,
        "submitted_at": submitted,
    }


def _attempt_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """attempts row → API 응답 dict (criteria 제외, 호출자가 join 추가)."""
    db_status = row["status"]
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
        "is_stale": bool(row["is_stale"]),
        "is_mock": bool(row["is_mock"]),
    }
    if db_status == DB_STATUS_DONE:
        out["score_total"] = row["score_total"]
        out["score_max"] = row["score_max"]
        out["score_pct"] = row["score_pct"]
        out["grade"] = row["grade"]
        out["model"] = row["model"]
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
    """GET /api/attempts/{id} — 단건 조회 + criteria 7개 join.

    status='grading': elapsed_sec live 계산.
    status='done':    criteria 배열 + diff_html + eval_notes + weights_applied.
    status='error':   error_code + error_message + retryable.
    """
    cur = conn.execute("SELECT * FROM attempts WHERE id = ?", (int(attempt_id),))
    row = cur.fetchone()
    if row is None:
        raise AttemptNotFoundError(f"attempt_id={attempt_id}")

    out = _attempt_row_to_dict(row)

    # case_title (시안 Reports / Reviewer Notes 등 표시용)
    cur = conn.execute("SELECT title, file, case_no FROM cases WHERE id = ?", (out["case_id"],))
    crow = cur.fetchone()
    if crow:
        out["case_title"] = crow["title"]
        out["case_short_id"] = f"{crow['file']}-{crow['case_no']}"

    # criteria 7개 (done 시만 — grading/error 시도 row 가 있을 수 있으나 비어있음)
    if out["db_status"] == DB_STATUS_DONE:
        cur = conn.execute(
            """
            SELECT criterion_key, score, max_score, weight, comment
              FROM attempt_criteria
             WHERE attempt_id = ?
             ORDER BY id ASC
            """,
            (int(attempt_id),),
        )
        criteria_rows = cur.fetchall()
        # CRITERION_KEYS 순서로 정렬
        by_key = {r["criterion_key"]: r for r in criteria_rows}
        out["criteria"] = []
        for key in grader_mod.CRITERION_KEYS:
            r = by_key.get(key)
            if r is None:
                continue
            out["criteria"].append(
                {
                    "key": r["criterion_key"],
                    "score": r["score"],
                    "max": r["max_score"],
                    "weight": r["weight"],
                    "comment": r["comment"] or "",
                }
            )

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
    page_sql = f"""
        SELECT a.id, a.case_id, a.submitted_at, a.completed_at, a.status,
               a.score_total, a.score_max, a.score_pct, a.grade,
               a.is_stale, a.is_mock, a.error_code,
               c.title AS case_title, c.subject AS case_subject,
               c.subject_kor AS case_subject_kor,
               c.file AS case_file, c.case_no AS case_no_str
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
                "submitted_at": r["submitted_at"],
                "completed_at": r["completed_at"],
                "status": _client_status(r["status"]),
                "score_total": r["score_total"],
                "score_max": r["score_max"],
                "score_pct": r["score_pct"],
                "grade": r["grade"],
                "is_stale": bool(r["is_stale"]),
                "is_mock": bool(r["is_mock"]),
                "error_code": r["error_code"],
            }
        )

    return {
        "attempts": items,
        "total": total,
        "limit": limit_i,
        "offset": offset_i,
    }
