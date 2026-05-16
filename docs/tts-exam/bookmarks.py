#!/usr/bin/env python3
"""Bookmarks API 비즈니스 로직 (Step 9).

dev-design archive #48 §3-1 endpoint 9 + §4-2 bookmarks 테이블 1:1.
dev-impl-plan #51 Step 9 표 — POST/DELETE 토글, INSERT OR IGNORE / DELETE.

핵심:
- `toggle_add(conn, case_id)`    : POST → INSERT OR IGNORE → {bookmarked: true}
- `toggle_remove(conn, case_id)` : DELETE → DELETE → {bookmarked: false}
- `is_bookmarked(conn, case_id)` : 존재 여부 (테스트/내부용)
- `list_bookmarks(conn)`         : 즐겨찾기 case_id 리스트 (옵션 GET용)

설계 결정:
- 케이스 존재 확인: bookmarks INSERT 는 FK ON DELETE CASCADE 라 cases 미존재 시 FK violation.
  → POST 시점에 명시 SELECT 로 404 'case_not_found' 매핑 (dev-design #48 §3-3 1:1).
- DELETE 는 존재하지 않아도 200 + bookmarked:false (멱등) — DELETE 의 정상 시맨틱.
  단, case_id 가 cases 에 존재하지 않으면 404 (입력 검증 우선 — 일관성).
- 트랜잭션: 단일 statement → autocommit (dev-impl-plan §5-3 D-3 명시 "Bookmarks 토글 단일 INSERT/DELETE 트랜잭션 X").
"""
from __future__ import annotations

import datetime as _dt
import sqlite3
from typing import Any


# ─── 예외 ─────────────────────────────────────────────────────────────


class BookmarkCaseNotFoundError(Exception):
    """case_id 가 cases 테이블에 없음 (HTTP 404 매핑)."""

    def __init__(self, case_id: str) -> None:
        super().__init__(f"case_id={case_id}")
        self.case_id = case_id


# ─── 유틸 ─────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    """ISO-8601 UTC ('YYYY-MM-DDTHH:MM:SSZ')."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _case_exists(conn: sqlite3.Connection, case_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM cases WHERE id = ? LIMIT 1", (case_id,))
    return cur.fetchone() is not None


# ─── 공용 API ──────────────────────────────────────────────────────────


def is_bookmarked(conn: sqlite3.Connection, case_id: str) -> bool:
    """case_id 가 bookmarks 테이블에 있는지 확인."""
    cur = conn.execute(
        "SELECT 1 FROM bookmarks WHERE case_id = ? LIMIT 1", (case_id,)
    )
    return cur.fetchone() is not None


def toggle_add(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    """POST /api/bookmarks/{case_id} — 즐겨찾기 추가 (INSERT OR IGNORE).

    이미 즐겨찾기면 멱등 (bookmarked_at 갱신 X — 최초 추가 시점 보존).

    Returns:
        {"case_id": case_id, "bookmarked": True, "bookmarked_at": ISO}

    Raises:
        BookmarkCaseNotFoundError: cases 에 case_id 미존재.
    """
    if not isinstance(case_id, str) or not case_id.strip():
        raise BookmarkCaseNotFoundError(repr(case_id))

    if not _case_exists(conn, case_id):
        raise BookmarkCaseNotFoundError(case_id)

    now = _utcnow_iso()
    conn.execute(
        "INSERT OR IGNORE INTO bookmarks (case_id, bookmarked_at) VALUES (?, ?)",
        (case_id, now),
    )
    conn.commit()

    # 최초/기존 bookmarked_at 조회 (멱등 시 기존 값 반환)
    cur = conn.execute(
        "SELECT bookmarked_at FROM bookmarks WHERE case_id = ?", (case_id,)
    )
    row = cur.fetchone()
    return {
        "case_id": case_id,
        "bookmarked": True,
        "bookmarked_at": row["bookmarked_at"] if row else now,
    }


def toggle_remove(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    """DELETE /api/bookmarks/{case_id} — 즐겨찾기 해제 (DELETE).

    없어도 멱등 (bookmarked:false 응답). 단, cases 미존재는 404.

    Returns:
        {"case_id": case_id, "bookmarked": False}

    Raises:
        BookmarkCaseNotFoundError: cases 에 case_id 미존재.
    """
    if not isinstance(case_id, str) or not case_id.strip():
        raise BookmarkCaseNotFoundError(repr(case_id))

    if not _case_exists(conn, case_id):
        raise BookmarkCaseNotFoundError(case_id)

    conn.execute("DELETE FROM bookmarks WHERE case_id = ?", (case_id,))
    conn.commit()
    return {"case_id": case_id, "bookmarked": False}


def list_bookmarks(conn: sqlite3.Connection) -> dict[str, Any]:
    """GET /api/bookmarks (옵션) — 즐겨찾기 case_id 리스트 + 카운트.

    Returns:
        {"case_ids": [...], "count": N, "items": [{"case_id":..., "bookmarked_at":...}, ...]}
    """
    cur = conn.execute(
        "SELECT case_id, bookmarked_at FROM bookmarks ORDER BY bookmarked_at DESC"
    )
    items: list[dict[str, Any]] = []
    for row in cur.fetchall():
        items.append(
            {"case_id": row["case_id"], "bookmarked_at": row["bookmarked_at"]}
        )
    return {
        "case_ids": [it["case_id"] for it in items],
        "count": len(items),
        "items": items,
    }
