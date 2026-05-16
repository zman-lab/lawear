#!/usr/bin/env python3
"""Reports API 비즈니스 로직 (Step 10).

dev-design archive #48 §3-1 endpoint (Reports 3종) + §4-2 attempts/cases JOIN.
dev-impl-plan archive #51 Step 10 표 — Overall / By Subject / By Case 집계 쿼리.

핵심:
- `overall(conn, window_days=7, stale_days=14, trend_limit=50)`     : GET /api/reports/overall
- `by_subject(conn, subject, *, stale_days=14)`                     : GET /api/reports/by-subject?subject=…
- `by_case(conn, case_id, *, persistent_threshold=3)`               : GET /api/reports/by-case?case_id=…

설계 결정 (R-09 자의적 해석 금지):
- status enum: DB 는 'grading'/'done'/'error'. attempts.py CLIENT_STATUS_MAP 와 일치.
  - 사용자 사양 "completed/failed" = 클라이언트 라벨. 본 모듈은 DB enum 으로 집계.
  - "submitted" 카운트 = status IN ('done','error') ('grading' 제외).
- score 집계: avg_score_pct 는 status='done' AND score_pct IS NOT NULL 만.
  ('error' 시도는 점수 없음 → 평균에 포함 X).
- high_error_cases: case 별 가장 최근 done attempt 의 score_pct < 60% (전수 평균이 아닌 최신).
  dev-impact #45 + dev-impl-plan #51 §6-3 정의와 align.
- long_pending_cases: cases 중 attempts.submitted_at 최댓값 < now - stale_days. attempts 없는 case 는 stale 아님.
  (시안 14d 기준 — settings.bias.stale_threshold_days 호출자가 주입)
- last_week_delta: 최근 N일 카운트 vs 그 직전 N일 카운트.
- avg_score_pct_delta: 최근 30일 평균 vs 그 직전 30일 평균 (단위 pp).
- 빈 데이터 처리: 모든 KPI null 또는 0 + 빈 배열, "no data" 마커 X (호출자가 표현).
- 캐싱: 본 단계 미구현 (단일 1인 도구 + WAL 인덱스 충분).
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from typing import Any

# ─── 상수 ────────────────────────────────────────────────────────────────

DB_STATUS_GRADING: str = "grading"
DB_STATUS_DONE: str = "done"
DB_STATUS_ERROR: str = "error"

# Reports 에서 "submitted" 로 카운트하는 status (grading 제외)
SUBMITTED_STATUSES: tuple[str, ...] = (DB_STATUS_DONE, DB_STATUS_ERROR)

# "최근 N일 추이" 기본
DEFAULT_WINDOW_DAYS: int = 7
DEFAULT_TREND_LIMIT: int = 50
DEFAULT_TREND_DAYS: int = 30
DEFAULT_RECENT_LIMIT: int = 10
DEFAULT_AVG_WINDOW_DAYS: int = 30
DEFAULT_STALE_THRESHOLD_DAYS: int = 14

# high error 임계
HIGH_ERROR_PCT_THRESHOLD: float = 60.0

# persistent_errors: missing 키워드가 N회 이상 등장하면 누락 패턴
DEFAULT_PERSISTENT_THRESHOLD: int = 3

# 채점 8기준 키 순서 (UI Criteria Average 패널과 동일 정렬 보장)
# Step 20 (사용자 2026-05-16): articles 신설 — Lv.4 그룹 뒤, rich/miss 앞에 배치.
CRITERION_ORDER: tuple[str, ...] = (
    "mnem",
    "color",
    "under",
    "outline",
    "sem",
    "articles",
    "rich",
    "miss",
)


# ─── 유틸 ────────────────────────────────────────────────────────────────


def _utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_ago_iso(days: int, now: _dt.datetime | None = None) -> str:
    """now - days 의 ISO-8601 문자열 (UTC)."""
    base = now or _utcnow()
    return (base - _dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str | None) -> _dt.datetime | None:
    """ISO-8601 문자열 → datetime (UTC). 실패 시 None."""
    if not s:
        return None
    try:
        v = s.replace("Z", "+00:00")
        d = _dt.datetime.fromisoformat(v)
        if d.tzinfo is None:
            d = d.replace(tzinfo=_dt.timezone.utc)
        return d
    except (ValueError, TypeError):
        return None


def _round_pct(v: float | None, ndigits: int = 2) -> float | None:
    if v is None:
        return None
    try:
        return round(float(v), ndigits)
    except (TypeError, ValueError):
        return None


def _safe_pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _count_submitted(conn: sqlite3.Connection, *, since: str | None = None) -> int:
    """status IN ('done','error') + (옵션) since 이상 카운트."""
    sql = "SELECT COUNT(*) AS cnt FROM attempts WHERE status IN (?, ?)"
    params: list[Any] = [DB_STATUS_DONE, DB_STATUS_ERROR]
    if since:
        sql += " AND submitted_at >= ?"
        params.append(since)
    cur = conn.execute(sql, tuple(params))
    row = cur.fetchone()
    return int(row["cnt"]) if row and row["cnt"] is not None else 0


def _avg_score_pct(
    conn: sqlite3.Connection, *, since: str | None = None, until: str | None = None
) -> float | None:
    """status='done' AND score_pct IS NOT NULL 의 평균."""
    sql = (
        "SELECT AVG(score_pct) AS avg_pct, COUNT(score_pct) AS n "
        "FROM attempts WHERE status = ? AND score_pct IS NOT NULL"
    )
    params: list[Any] = [DB_STATUS_DONE]
    if since:
        sql += " AND submitted_at >= ?"
        params.append(since)
    if until:
        sql += " AND submitted_at < ?"
        params.append(until)
    cur = conn.execute(sql, tuple(params))
    row = cur.fetchone()
    if not row or row["n"] is None or int(row["n"]) == 0:
        return None
    return _round_pct(row["avg_pct"])


def _high_error_case_ids(
    conn: sqlite3.Connection, *, threshold_pct: float = HIGH_ERROR_PCT_THRESHOLD
) -> list[str]:
    """case 별 가장 최근 done attempt 의 score_pct < threshold_pct 인 case_id.

    Reports KPI "High Error Rate" 카운트용.
    """
    sql = """
        SELECT a.case_id AS cid, a.score_pct AS pct
          FROM attempts a
          JOIN (
            SELECT case_id, MAX(submitted_at) AS last_submitted
              FROM attempts
             WHERE status = ? AND score_pct IS NOT NULL
             GROUP BY case_id
          ) m ON a.case_id = m.case_id AND a.submitted_at = m.last_submitted
         WHERE a.status = ? AND a.score_pct IS NOT NULL AND a.score_pct < ?
    """
    cur = conn.execute(sql, (DB_STATUS_DONE, DB_STATUS_DONE, float(threshold_pct)))
    return [row["cid"] for row in cur.fetchall() if row["cid"]]


def _long_pending_case_ids(
    conn: sqlite3.Connection, *, stale_threshold_days: int
) -> list[str]:
    """cases 중 마지막 attempt(submitted_at) < now - stale_threshold_days.

    attempts 없는 case 는 stale 미포함 (한 번도 안 푼 케이스와 구별).
    """
    threshold_iso = _days_ago_iso(int(stale_threshold_days))
    sql = """
        SELECT c.id AS cid
          FROM cases c
          JOIN (
            SELECT case_id, MAX(submitted_at) AS last_submitted
              FROM attempts
             WHERE status IN (?, ?)
             GROUP BY case_id
          ) m ON c.id = m.case_id
         WHERE m.last_submitted < ?
    """
    cur = conn.execute(
        sql, (DB_STATUS_DONE, DB_STATUS_ERROR, threshold_iso)
    )
    return [row["cid"] for row in cur.fetchall() if row["cid"]]


# ─── Overall ────────────────────────────────────────────────────────────


def overall(
    conn: sqlite3.Connection,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    trend_limit: int = DEFAULT_TREND_LIMIT,
    trend_days: int = DEFAULT_TREND_DAYS,
    recent_limit: int = DEFAULT_RECENT_LIMIT,
    stale_threshold_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
    avg_window_days: int = DEFAULT_AVG_WINDOW_DAYS,
) -> dict[str, Any]:
    """GET /api/reports/overall — KPI 4 + 점수 추이 + 최근 시도.

    Returns:
        {
          "kpi": {
            "submitted": int,
            "last_week_delta": int,        # 최근 N일 카운트 (전주 대비 +N)
            "avg_score_pct": float|None,   # 최근 done 평균 (소수 2)
            "avg_score_pct_delta": float,  # pp 단위 (최근 30일 - 직전 30일)
            "high_error_cases": int,       # 최근 done <60% case 수
            "high_error_delta": int,       # 자료 부족 → 0 (TODO)
            "long_pending_cases": int,     # stale_threshold_days 초과 case 수
          },
          "trend":  [{date, score_pct, attempt_id, case_id}],   # 최근 trend_limit (or trend_days)
          "recent": [{attempt_id, case_id, case_title, submitted_at, ...}], # limit recent_limit
          "window_days": int,
          "stale_threshold_days": int,
          "generated_at": ISO,
          "empty": bool,                   # 시도 0건 → true
        }
    """
    now = _utcnow()
    window_iso = (now - _dt.timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    prev_window_iso_start = (
        now - _dt.timedelta(days=window_days * 2)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    avg_curr_since = (
        now - _dt.timedelta(days=avg_window_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    avg_prev_since = (
        now - _dt.timedelta(days=avg_window_days * 2)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    # KPI 1: submitted total
    submitted_total = _count_submitted(conn)
    # last_week_delta: 최근 N일 카운트만 (전주와 비교는 아닌 absolute count of last N days)
    last_window_count = _count_submitted(conn, since=window_iso)
    prev_window_count = _count_submitted(conn, since=prev_window_iso_start) - last_window_count
    last_week_delta = last_window_count - prev_window_count

    # KPI 2: avg_score_pct (전체 done 평균)
    avg_pct = _avg_score_pct(conn)
    # avg_score_pct_delta (pp) — 최근 N일 vs 직전 N일
    curr_avg = _avg_score_pct(conn, since=avg_curr_since)
    prev_avg = _avg_score_pct(conn, since=avg_prev_since, until=avg_curr_since)
    if curr_avg is not None and prev_avg is not None:
        avg_delta = round(curr_avg - prev_avg, 2)
    else:
        avg_delta = 0.0

    # KPI 3: high_error_cases (최근 done <60%)
    high_err_ids = _high_error_case_ids(conn)
    high_error_cases = len(high_err_ids)
    # high_error_delta: 자료 부족 → 0 (시안 +2 cases 와 별개 — 자의 X)
    high_error_delta = 0

    # KPI 4: long_pending_cases
    long_pending_ids = _long_pending_case_ids(conn, stale_threshold_days=stale_threshold_days)
    long_pending_cases = len(long_pending_ids)

    # 점수 추이 (trend_limit 한정, 시간순 ASC — SVG x축 자연 정렬)
    trend_since_iso = (now - _dt.timedelta(days=trend_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    trend_sql = """
        SELECT a.id AS attempt_id, a.case_id, a.submitted_at, a.score_pct,
               c.title AS case_title
          FROM attempts a
          LEFT JOIN cases c ON a.case_id = c.id
         WHERE a.status = ? AND a.score_pct IS NOT NULL
           AND a.submitted_at >= ?
         ORDER BY a.submitted_at ASC
         LIMIT ?
    """
    cur = conn.execute(
        trend_sql, (DB_STATUS_DONE, trend_since_iso, int(trend_limit))
    )
    trend: list[dict[str, Any]] = []
    for r in cur.fetchall():
        trend.append(
            {
                "attempt_id": r["attempt_id"],
                "case_id": r["case_id"],
                "case_title": r["case_title"],
                "date": r["submitted_at"],
                "score_pct": _round_pct(r["score_pct"]),
            }
        )

    # Recent submissions (limit)
    recent_sql = """
        SELECT a.id AS attempt_id, a.case_id, a.submitted_at, a.completed_at,
               a.status, a.score_total, a.score_max, a.score_pct, a.grade,
               a.is_stale, a.is_mock, a.error_code,
               c.title AS case_title, c.subject AS case_subject,
               c.subject_kor AS case_subject_kor,
               c.file AS case_file, c.case_no AS case_no
          FROM attempts a
          LEFT JOIN cases c ON a.case_id = c.id
         WHERE a.status IN (?, ?)
         ORDER BY a.submitted_at DESC, a.id DESC
         LIMIT ?
    """
    cur = conn.execute(
        recent_sql, (DB_STATUS_DONE, DB_STATUS_ERROR, int(recent_limit))
    )
    recent: list[dict[str, Any]] = []
    for r in cur.fetchall():
        recent.append(
            {
                "attempt_id": r["attempt_id"],
                "case_id": r["case_id"],
                "case_title": r["case_title"],
                "case_subject": r["case_subject"],
                "case_subject_kor": r["case_subject_kor"],
                "case_short_id": (
                    f"{r['case_file']}-{r['case_no']}" if r["case_file"] else None
                ),
                "submitted_at": r["submitted_at"],
                "completed_at": r["completed_at"],
                "status": r["status"],  # 'done' or 'error'
                "score_total": r["score_total"],
                "score_max": r["score_max"],
                "score_pct": _round_pct(r["score_pct"]),
                "grade": r["grade"],
                "is_stale": bool(r["is_stale"]),
                "is_mock": bool(r["is_mock"]),
                "error_code": r["error_code"],
            }
        )

    return {
        "kpi": {
            "submitted": submitted_total,
            "last_week_delta": int(last_week_delta),
            "last_window_count": int(last_window_count),
            "avg_score_pct": avg_pct,
            "avg_score_pct_delta": avg_delta,
            "high_error_cases": high_error_cases,
            "high_error_delta": int(high_error_delta),
            "long_pending_cases": long_pending_cases,
        },
        "trend": trend,
        "recent": recent,
        "window_days": int(window_days),
        "stale_threshold_days": int(stale_threshold_days),
        "trend_days": int(trend_days),
        "generated_at": _utcnow_iso(),
        "empty": submitted_total == 0,
    }


# ─── By Subject ──────────────────────────────────────────────────────────


def _all_subjects(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """cases 테이블에서 distinct subject 추출. 정렬: subject ASC."""
    sql = """
        SELECT subject, subject_kor, COUNT(*) AS n
          FROM cases
         GROUP BY subject, subject_kor
         ORDER BY subject ASC
    """
    cur = conn.execute(sql)
    return [
        {
            "subject": row["subject"],
            "subject_kor": row["subject_kor"],
            "cases": int(row["n"]),
        }
        for row in cur.fetchall()
    ]


def _subject_avg_compare(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """전체 과목의 평균 점수 비교 (Overall 막대 그래프용)."""
    sql = """
        SELECT c.subject AS subject, c.subject_kor AS subject_kor,
               AVG(a.score_pct) AS avg_pct, COUNT(a.id) AS n_attempts,
               COUNT(DISTINCT a.case_id) AS covered_cases
          FROM cases c
          LEFT JOIN attempts a
            ON a.case_id = c.id
           AND a.status = ?
           AND a.score_pct IS NOT NULL
         GROUP BY c.subject, c.subject_kor
         ORDER BY c.subject ASC
    """
    cur = conn.execute(sql, (DB_STATUS_DONE,))
    items: list[dict[str, Any]] = []
    for row in cur.fetchall():
        items.append(
            {
                "subject": row["subject"],
                "subject_kor": row["subject_kor"],
                "avg_pct": _round_pct(row["avg_pct"]),
                "n_attempts": int(row["n_attempts"]) if row["n_attempts"] else 0,
                "covered_cases": int(row["covered_cases"])
                if row["covered_cases"]
                else 0,
            }
        )
    return items


def by_subject(
    conn: sqlite3.Connection,
    subject: str,
    *,
    stale_threshold_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
) -> dict[str, Any]:
    """GET /api/reports/by-subject?subject=… — 단일 과목 KPI + 비교 + 케이스 리스트.

    Args:
        subject: 과목 코드 ('minbeop'/'minso'/'hyungbeop'/'budeung'/'hyungso').

    Returns:
        {
          "subject": str,
          "subject_kor": str,
          "kpi": {cases, submitted, avg_score_pct, top_error_topic, coverage_pct, ...},
          "comparison": [{subject, subject_kor, avg_pct}, ...],
          "cases": [{case_id, case_short_id, title, attempts, avg_pct, best_pct, last_pct, ...}],
          "empty": bool,
          "subject_exists": bool,
          "generated_at": ISO,
        }
    """
    # 과목 존재 확인 (cases 테이블에 1건이라도 있는지)
    cur = conn.execute(
        "SELECT subject, subject_kor, COUNT(*) AS n FROM cases WHERE subject = ? GROUP BY subject",
        (subject,),
    )
    subj_row = cur.fetchone()
    subject_exists = subj_row is not None

    subject_kor: str | None = subj_row["subject_kor"] if subj_row else None
    total_cases: int = int(subj_row["n"]) if subj_row and subj_row["n"] else 0

    # KPI 집계 (단일 과목)
    if subject_exists:
        cur = conn.execute(
            """
            SELECT
              SUM(CASE WHEN a.status IN (?, ?) THEN 1 ELSE 0 END) AS submitted,
              AVG(CASE WHEN a.status = ? AND a.score_pct IS NOT NULL THEN a.score_pct ELSE NULL END) AS avg_pct,
              COUNT(DISTINCT CASE WHEN a.status IN (?, ?) THEN a.case_id END) AS covered_cases
              FROM attempts a
              JOIN cases c ON a.case_id = c.id
             WHERE c.subject = ?
            """,
            (
                DB_STATUS_DONE,
                DB_STATUS_ERROR,
                DB_STATUS_DONE,
                DB_STATUS_DONE,
                DB_STATUS_ERROR,
                subject,
            ),
        )
        row = cur.fetchone()
        submitted = int(row["submitted"]) if row and row["submitted"] else 0
        avg_pct = _round_pct(row["avg_pct"]) if row and row["avg_pct"] is not None else None
        covered_cases = int(row["covered_cases"]) if row and row["covered_cases"] else 0
    else:
        submitted = 0
        avg_pct = None
        covered_cases = 0

    # Top Error Topic: 가장 최근 done attempt 의 score_pct 최저인 cases.title
    top_error_topic = None
    top_error_pct = None
    top_error_case_id = None
    if subject_exists:
        cur = conn.execute(
            """
            SELECT c.id AS cid, c.title AS title, a.score_pct AS pct
              FROM attempts a
              JOIN cases c ON a.case_id = c.id
              JOIN (
                SELECT case_id, MAX(submitted_at) AS last_submitted
                  FROM attempts
                 WHERE status = ? AND score_pct IS NOT NULL
                 GROUP BY case_id
              ) m ON a.case_id = m.case_id AND a.submitted_at = m.last_submitted
             WHERE a.status = ? AND a.score_pct IS NOT NULL AND c.subject = ?
             ORDER BY a.score_pct ASC, a.submitted_at DESC
             LIMIT 1
            """,
            (DB_STATUS_DONE, DB_STATUS_DONE, subject),
        )
        ter_row = cur.fetchone()
        if ter_row:
            top_error_topic = ter_row["title"]
            top_error_pct = _round_pct(ter_row["pct"])
            top_error_case_id = ter_row["cid"]

    # 케이스 리스트 (과목 내 cases + attempts 집계)
    cases: list[dict[str, Any]] = []
    if subject_exists:
        case_sql = """
            SELECT c.id AS cid, c.title AS title, c.file AS file, c.case_no AS case_no,
                   c.category AS category, c.points AS points,
                   COUNT(a.id) AS attempts_count,
                   AVG(CASE WHEN a.status = ? AND a.score_pct IS NOT NULL THEN a.score_pct ELSE NULL END) AS avg_pct,
                   MAX(CASE WHEN a.status = ? AND a.score_pct IS NOT NULL THEN a.score_pct ELSE NULL END) AS best_pct,
                   (SELECT a2.score_pct FROM attempts a2
                     WHERE a2.case_id = c.id AND a2.status = ? AND a2.score_pct IS NOT NULL
                     ORDER BY a2.submitted_at DESC LIMIT 1) AS last_pct,
                   (SELECT a3.submitted_at FROM attempts a3
                     WHERE a3.case_id = c.id AND a3.status IN (?, ?)
                     ORDER BY a3.submitted_at DESC LIMIT 1) AS last_submitted_at
              FROM cases c
              LEFT JOIN attempts a ON a.case_id = c.id
             WHERE c.subject = ?
             GROUP BY c.id, c.title, c.file, c.case_no, c.category, c.points
             ORDER BY c.category ASC, c.file ASC, c.case_no ASC
        """
        cur = conn.execute(
            case_sql,
            (
                DB_STATUS_DONE,
                DB_STATUS_DONE,
                DB_STATUS_DONE,
                DB_STATUS_DONE,
                DB_STATUS_ERROR,
                subject,
            ),
        )
        threshold_iso = _days_ago_iso(int(stale_threshold_days))
        for row in cur.fetchall():
            last_submitted_at = row["last_submitted_at"]
            is_stale = bool(
                last_submitted_at and last_submitted_at < threshold_iso
            )
            cases.append(
                {
                    "case_id": row["cid"],
                    "case_short_id": f"{row['file']}-{row['case_no']}" if row["file"] else None,
                    "title": row["title"],
                    "category": row["category"],
                    "points": row["points"],
                    "attempts": int(row["attempts_count"])
                    if row["attempts_count"]
                    else 0,
                    "avg_pct": _round_pct(row["avg_pct"]),
                    "best_pct": _round_pct(row["best_pct"]),
                    "last_pct": _round_pct(row["last_pct"]),
                    "last_submitted_at": last_submitted_at,
                    "is_stale": is_stale,
                }
            )

    coverage_pct = _safe_pct(covered_cases, total_cases) if total_cases else 0.0

    return {
        "subject": subject,
        "subject_kor": subject_kor,
        "subject_exists": subject_exists,
        "kpi": {
            "cases": total_cases,
            "submitted": submitted,
            "covered_cases": covered_cases,
            "coverage_pct": coverage_pct,
            "avg_score_pct": avg_pct,
            "avg_score_pct_delta": 0.0,
            "top_error_topic": top_error_topic,
            "top_error_pct": top_error_pct,
            "top_error_case_id": top_error_case_id,
        },
        "comparison": _subject_avg_compare(conn),
        "cases": cases,
        "stale_threshold_days": int(stale_threshold_days),
        "generated_at": _utcnow_iso(),
        "empty": submitted == 0,
    }


# ─── By Case ─────────────────────────────────────────────────────────────


def _persistent_errors(
    conn: sqlite3.Connection,
    case_id: str,
    *,
    persistent_threshold: int = DEFAULT_PERSISTENT_THRESHOLD,
) -> dict[str, Any]:
    """attempts.eval_notes_json.missing 등 across 시도 N회 이상 등장 표시.

    구현: missing 필드의 raw 문자열을 그대로 카운트 (해시). 키워드 NLP X (R-09).

    Returns:
        {"count": int, "items": [{"text": str, "occurrences": int}, ...]}
    """
    cur = conn.execute(
        """
        SELECT eval_notes_json FROM attempts
         WHERE case_id = ? AND status = ? AND eval_notes_json IS NOT NULL
         ORDER BY submitted_at ASC
        """,
        (case_id, DB_STATUS_DONE),
    )
    rows = cur.fetchall()
    bucket: dict[str, int] = {}
    for r in rows:
        try:
            notes = json.loads(r["eval_notes_json"]) if r["eval_notes_json"] else {}
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(notes, dict):
            continue
        miss = notes.get("missing")
        if not isinstance(miss, str):
            continue
        key = miss.strip()
        if not key:
            continue
        bucket[key] = bucket.get(key, 0) + 1

    items = [
        {"text": text, "occurrences": cnt}
        for text, cnt in bucket.items()
        if cnt >= int(persistent_threshold)
    ]
    items.sort(key=lambda x: (-x["occurrences"], x["text"]))
    return {"count": len(items), "items": items, "threshold": int(persistent_threshold)}


def _case_criteria_avg(
    conn: sqlite3.Connection, case_id: str
) -> list[dict[str, Any]]:
    """attempt_criteria 의 7기준 평균 (case 단위).

    Returns:
        [{"criterion_key": str, "avg_score": float, "avg_max": float,
          "avg_weight": float, "avg_pct": float, "n": int}, ...]
        CRITERION_ORDER 순.
    """
    sql = """
        SELECT ac.criterion_key AS k,
               AVG(ac.score) AS avg_score,
               AVG(ac.max_score) AS avg_max,
               AVG(ac.weight) AS avg_weight,
               COUNT(*) AS n
          FROM attempt_criteria ac
          JOIN attempts a ON a.id = ac.attempt_id
         WHERE a.case_id = ? AND a.status = ?
         GROUP BY ac.criterion_key
    """
    cur = conn.execute(sql, (case_id, DB_STATUS_DONE))
    by_key: dict[str, dict[str, Any]] = {}
    for row in cur.fetchall():
        avg_score = row["avg_score"] or 0.0
        avg_max = row["avg_max"] or 0.0
        if avg_max > 0:
            avg_pct = round((avg_score / avg_max) * 100.0, 2)
        else:
            # miss 기준은 max=0, score 음수/0 — pct 계산 X, raw score 만 노출
            avg_pct = None
        by_key[row["k"]] = {
            "criterion_key": row["k"],
            "avg_score": round(float(avg_score), 2),
            "avg_max": round(float(avg_max), 2),
            "avg_weight": round(float(row["avg_weight"] or 0.0), 2),
            "avg_pct": avg_pct,
            "n": int(row["n"]),
        }
    # CRITERION_ORDER 보장
    out: list[dict[str, Any]] = []
    for key in CRITERION_ORDER:
        if key in by_key:
            out.append(by_key[key])
        else:
            out.append(
                {
                    "criterion_key": key,
                    "avg_score": 0.0,
                    "avg_max": 0.0,
                    "avg_weight": 0.0,
                    "avg_pct": None,
                    "n": 0,
                }
            )
    return out


def _case_attempts_history(
    conn: sqlite3.Connection, case_id: str
) -> list[dict[str, Any]]:
    """case 의 시도 히스토리 (ASC 순, attempt_num 부여).

    main_miss: eval_notes_json.missing 첫 문장 또는 attempt_criteria 의 최저 코멘트.
    """
    sql = """
        SELECT id, submitted_at, completed_at, status, score_total, score_max,
               score_pct, grade, eval_notes_json, error_code, error_message,
               is_stale, is_mock
          FROM attempts
         WHERE case_id = ?
         ORDER BY submitted_at ASC, id ASC
    """
    cur = conn.execute(sql, (case_id,))
    rows = cur.fetchall()
    history: list[dict[str, Any]] = []
    for idx, r in enumerate(rows, start=1):
        # main_miss 추출
        main_miss: str | None = None
        if r["eval_notes_json"]:
            try:
                notes = json.loads(r["eval_notes_json"])
                if isinstance(notes, dict):
                    miss = notes.get("missing")
                    if isinstance(miss, str) and miss.strip():
                        # 첫 문장만 (마침표 / 줄바꿈 기준)
                        first = miss.strip().split("\n", 1)[0]
                        # 마침표 끝나는 첫 문장
                        if "." in first:
                            first = first.split(".", 1)[0] + "."
                        main_miss = first[:200]
            except (TypeError, json.JSONDecodeError):
                main_miss = None
        # main_miss 가 없고 error 시도면 error_message 사용
        if not main_miss and r["status"] == DB_STATUS_ERROR:
            em = r["error_message"]
            if isinstance(em, str) and em.strip():
                main_miss = f"[error] {em[:200]}"

        history.append(
            {
                "attempt_id": r["id"],
                "attempt_num": idx,
                "submitted_at": r["submitted_at"],
                "completed_at": r["completed_at"],
                "status": r["status"],
                "score_total": r["score_total"],
                "score_max": r["score_max"],
                "score_pct": _round_pct(r["score_pct"]),
                "grade": r["grade"],
                "main_miss": main_miss,
                "is_stale": bool(r["is_stale"]),
                "is_mock": bool(r["is_mock"]),
                "error_code": r["error_code"],
            }
        )
    return history


def by_case(
    conn: sqlite3.Connection,
    case_id: str,
    *,
    persistent_threshold: int = DEFAULT_PERSISTENT_THRESHOLD,
) -> dict[str, Any]:
    """GET /api/reports/by-case?case_id=… — 케이스 KPI + 시도별 + 기준 평균 + 히스토리.

    Args:
        case_id: cases.id (FK). 미존재 시 case_exists=False.

    Returns:
        {
          "case_id": str,
          "case_exists": bool,
          "case_title": str|None,
          "case_short_id": str|None,
          "case_subject": str|None,
          "case_subject_kor": str|None,
          "case_points": int|None,
          "kpi": {attempts, last_pct, last_total, last_max, best_pct, best_total, best_max,
                  persistent_errors_count, since},
          "trend":      [{attempt_num, attempt_id, date, score_pct, score_total, score_max, grade, status}],
          "criteria":   [{criterion_key, avg_score, avg_max, avg_weight, avg_pct, n}],   # 7기준
          "history":    [{attempt_id, attempt_num, date, score_total, score_max, score_pct, grade, main_miss}],
          "persistent_errors": {count, items, threshold},
          "empty": bool,
          "generated_at": ISO,
        }
    """
    # case 메타
    cur = conn.execute(
        """
        SELECT id, title, subject, subject_kor, category, file, case_no, points
          FROM cases WHERE id = ?
        """,
        (case_id,),
    )
    case_row = cur.fetchone()
    case_exists = case_row is not None

    case_title: str | None = None
    case_short_id: str | None = None
    case_subject: str | None = None
    case_subject_kor: str | None = None
    case_points: int | None = None
    if case_row:
        case_title = case_row["title"]
        case_short_id = (
            f"{case_row['file']}-{case_row['case_no']}" if case_row["file"] else None
        )
        case_subject = case_row["subject"]
        case_subject_kor = case_row["subject_kor"]
        case_points = case_row["points"]

    # 시도별 추이 (status='done' 만 — score 있는 시도)
    trend: list[dict[str, Any]] = []
    cur = conn.execute(
        """
        SELECT id, submitted_at, score_total, score_max, score_pct, grade, status
          FROM attempts
         WHERE case_id = ? AND status = ?
         ORDER BY submitted_at ASC, id ASC
        """,
        (case_id, DB_STATUS_DONE),
    )
    for idx, r in enumerate(cur.fetchall(), start=1):
        trend.append(
            {
                "attempt_num": idx,
                "attempt_id": r["id"],
                "date": r["submitted_at"],
                "score_pct": _round_pct(r["score_pct"]),
                "score_total": r["score_total"],
                "score_max": r["score_max"],
                "grade": r["grade"],
                "status": r["status"],
            }
        )

    # KPI 집계
    cur = conn.execute(
        """
        SELECT
          COUNT(*) AS total_attempts,
          SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS done_attempts,
          MIN(submitted_at) AS first_submitted
          FROM attempts WHERE case_id = ?
        """,
        (DB_STATUS_DONE, case_id),
    )
    krow = cur.fetchone()
    total_attempts = int(krow["total_attempts"]) if krow and krow["total_attempts"] else 0
    done_attempts = int(krow["done_attempts"]) if krow and krow["done_attempts"] else 0
    first_submitted = krow["first_submitted"] if krow else None

    last_pct: float | None = None
    last_total: float | None = None
    last_max: float | None = None
    cur = conn.execute(
        """
        SELECT score_pct, score_total, score_max
          FROM attempts WHERE case_id = ? AND status = ? AND score_pct IS NOT NULL
         ORDER BY submitted_at DESC, id DESC LIMIT 1
        """,
        (case_id, DB_STATUS_DONE),
    )
    last_row = cur.fetchone()
    if last_row:
        last_pct = _round_pct(last_row["score_pct"])
        last_total = last_row["score_total"]
        last_max = last_row["score_max"]

    best_pct: float | None = None
    best_total: float | None = None
    best_max: float | None = None
    cur = conn.execute(
        """
        SELECT score_pct, score_total, score_max
          FROM attempts WHERE case_id = ? AND status = ? AND score_pct IS NOT NULL
         ORDER BY score_pct DESC, submitted_at DESC LIMIT 1
        """,
        (case_id, DB_STATUS_DONE),
    )
    best_row = cur.fetchone()
    if best_row:
        best_pct = _round_pct(best_row["score_pct"])
        best_total = best_row["score_total"]
        best_max = best_row["score_max"]

    persistent = _persistent_errors(
        conn, case_id, persistent_threshold=persistent_threshold
    )
    criteria_avg = _case_criteria_avg(conn, case_id)
    history = _case_attempts_history(conn, case_id)

    return {
        "case_id": case_id,
        "case_exists": case_exists,
        "case_title": case_title,
        "case_short_id": case_short_id,
        "case_subject": case_subject,
        "case_subject_kor": case_subject_kor,
        "case_points": case_points,
        "kpi": {
            "attempts": total_attempts,
            "done_attempts": done_attempts,
            "last_pct": last_pct,
            "last_total": last_total,
            "last_max": last_max,
            "best_pct": best_pct,
            "best_total": best_total,
            "best_max": best_max,
            "persistent_errors_count": persistent["count"],
            "since": first_submitted,
        },
        "trend": trend,
        "criteria": criteria_avg,
        "history": history,
        "persistent_errors": persistent,
        "empty": done_attempts == 0,
        "generated_at": _utcnow_iso(),
    }


# ─── 옵션 ────────────────────────────────────────────────────────────────


def list_subjects(conn: sqlite3.Connection) -> dict[str, Any]:
    """GET /api/reports/subjects (옵션) — 과목 리스트 (Reports By Subject 필터 탭용).

    DB 의 cases.subject distinct 를 반환. 빈 DB 면 빈 배열.
    """
    items = _all_subjects(conn)
    return {"subjects": items, "count": len(items), "generated_at": _utcnow_iso()}


def list_cases_for_picker(
    conn: sqlite3.Connection, *, subject: str | None = None
) -> dict[str, Any]:
    """GET /api/reports/cases (옵션) — By Case 셀렉터용 (case_id + 시도 카운트).

    정렬: subject ASC, category ASC, file ASC, case_no ASC.
    """
    where = ""
    params: list[Any] = []
    if subject:
        where = "WHERE c.subject = ?"
        params.append(subject)
    sql = f"""
        SELECT c.id AS cid, c.subject AS subject, c.subject_kor AS subject_kor,
               c.category AS category, c.file AS file, c.case_no AS case_no,
               c.title AS title,
               COUNT(a.id) AS attempts_count
          FROM cases c
          LEFT JOIN attempts a ON a.case_id = c.id AND a.status IN ('done','error')
        {where}
         GROUP BY c.id, c.subject, c.subject_kor, c.category, c.file, c.case_no, c.title
         ORDER BY c.subject ASC, c.category ASC, c.file ASC, c.case_no ASC
    """
    cur = conn.execute(sql, tuple(params))
    items: list[dict[str, Any]] = []
    for row in cur.fetchall():
        items.append(
            {
                "case_id": row["cid"],
                "case_short_id": f"{row['file']}-{row['case_no']}" if row["file"] else None,
                "subject": row["subject"],
                "subject_kor": row["subject_kor"],
                "category": row["category"],
                "title": row["title"],
                "attempts": int(row["attempts_count"])
                if row["attempts_count"]
                else 0,
            }
        )
    return {"cases": items, "count": len(items), "generated_at": _utcnow_iso()}
