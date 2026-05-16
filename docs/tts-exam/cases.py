#!/usr/bin/env python3
"""케이스 API 비즈니스 로직 (Step 4).

dev-design archive #48 §4-2 (DB) / dev-impl-plan #51 Step 4 1:1.

핵심:
- `list_cases(conn, filters)`         : `GET /api/cases`     (필터링 + 메타 집계)
- `get_case(conn, case_id)`           : `GET /api/cases/{id}` (메타 + .md 파일 파싱)
- `parse_md_file(md_text)`            : .md → {origin, lv1, lv4} 섹션 분리
                                        (R-28 강조 태그 [red][blue][bold][u][blank][blank2] 보존)

설계 결정:
- BASE_PATH: dev-impl-plan §5 Q21 A 결정 — `/Users/nhn/zman-lab/lawear/docs/tts-new` 디스크 직접 read
  (env LAWEAR_TTS_BASE 우선)
- 필터: dev-design #48 §3-1 endpoint 2 — `?filter=all|err|stale|book` + 확장 `subject/category/file/search`
  (dev-impl-plan #51 Step 4 표 '+filter (all/err/stale/book)' 기반, search 는 title LIKE)
- 섹션 분리: `^## ` 헤더 기준 split.
  - `## 원본 (NN점)` → origin
  - `## Lv.1 빠른복습`  → lv1
  - `## Lv.4 암기노트` → lv4 (괄호 안 설명 무관, 'Lv.4' 접두만 매칭)
  - `## 메타` → meta (선택)
- 강조 태그는 텍스트에 raw 로 포함 (브라우저/클라이언트가 파싱).
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

# ─── 설정 (env 우선) ───────────────────────────────────────────────
BASE_PATH: Path = Path(
    os.environ.get("LAWEAR_TTS_BASE", "/Users/nhn/zman-lab/lawear/docs/tts-new")
).resolve()

# 필터 enum (dev-design #48 §3-1)
# 'book' = dev-design 정본, 'bookmarked' = 사용자 사양 alias (Step 9 wire)
ALLOWED_FILTERS = {"all", "err", "stale", "book", "bookmarked"}

# alias 정규화: 클라이언트가 보낸 값 → 내부 정규형
_FILTER_ALIASES = {
    "bookmarked": "book",
}


class CaseNotFoundError(Exception):
    """케이스 ID 미존재 (HTTP 404 매핑)."""


class CaseFileMissingError(Exception):
    """cases.path 가 가리키는 .md 파일이 디스크에 없음 (HTTP 500)."""


# ─── .md 파싱 ──────────────────────────────────────────────────────

# `^## (헤더명)` 매칭 — 헤더명 캡쳐. 헤더 줄 자체는 결과에 포함하지 않음.
_HEADER_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def parse_md_file(md_text: str) -> dict[str, str | None]:
    """.md 본문을 섹션별로 분리.

    Returns:
        {
          "origin":   "## 원본 (17점)\n\n### 사실관계\n..." (raw, 헤더 포함),
          "origin_points": 17 (None 가능),
          "lv1":      "## Lv.1 빠른복습\n\n### 문제\n...",
          "lv4":      "## Lv.4 암기노트 (사용자 스타일)\n결론...",
          "meta":     "## 메타\n- PDF: ...",
        }
        섹션 없으면 해당 키 None.
    """
    # 헤더 위치 모음
    headers: list[tuple[int, str]] = [(m.start(), m.group(1)) for m in _HEADER_RE.finditer(md_text)]
    if not headers:
        return {"origin": None, "origin_points": None, "lv1": None, "lv4": None, "meta": None}

    # 다음 헤더 시작 위치 = 현재 섹션의 끝
    sections: dict[str, str] = {}
    for i, (start, name) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(md_text)
        sections[name] = md_text[start:end].rstrip()

    # 분류
    origin = None
    origin_points = None
    lv1 = None
    lv4 = None
    meta = None

    for name, body in sections.items():
        if name.startswith("원본"):
            origin = body
            # "원본 (17점)" 에서 점수 추출
            m = re.search(r"\((\d+)\s*점\)", name)
            if m:
                try:
                    origin_points = int(m.group(1))
                except ValueError:
                    origin_points = None
        elif name.startswith("Lv.1"):
            lv1 = body
        elif name.startswith("Lv.4"):
            lv4 = body
        elif name.startswith("메타"):
            meta = body

    return {
        "origin": origin,
        "origin_points": origin_points,
        "lv1": lv1,
        "lv4": lv4,
        "meta": meta,
    }


def _resolve_md_path(case_path: str) -> Path:
    """cases.path (예: '입문_민법/2026_minbeop_immun_미케01_01.md') → 절대 경로."""
    p = BASE_PATH / case_path
    # 보안: BASE_PATH 밖으로 escape 금지
    try:
        p.resolve().relative_to(BASE_PATH)
    except ValueError as e:
        raise CaseFileMissingError(f"path_escape: {case_path}") from e
    return p


def read_md_for_case(case_path: str) -> str:
    """디스크 .md 본문 read (UTF-8)."""
    p = _resolve_md_path(case_path)
    if not p.is_file():
        raise CaseFileMissingError(f"md_not_found: {p}")
    return p.read_text(encoding="utf-8")


# ─── 케이스 메타 집계 ───────────────────────────────────────────────


def _case_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """cases row → dict (subjectKor/fileKor 카멜케이스 호환)."""
    return {
        "id": row["id"],
        "subject": row["subject"],
        "subject_kor": row["subject_kor"],
        "category": row["category"],
        "file": row["file"],
        "file_kor": row["file_kor"],
        "case_no": row["case_no"],
        "title": row["title"],
        "path": row["path"],
        "pdf_path": row["pdf_path"],
        "points": row["points"],
        "user_case": row["user_case"],
        "synced_at": row["synced_at"],
        "content_hash": row["content_hash"],
    }


def _enrich_case_with_stats(conn: sqlite3.Connection, case: dict[str, Any]) -> dict[str, Any]:
    """case 에 bookmarked / attempt_count / last_score_pct / has_error / has_stale 추가.

    dev-design #48 §3-2 Case 응답 메시지의 누적 필드.
    """
    cid = case["id"]
    # bookmarked
    cur = conn.execute("SELECT 1 FROM bookmarks WHERE case_id = ?", (cid,))
    case["bookmarked"] = cur.fetchone() is not None

    # attempts 집계 (count / last score / error / stale)
    cur = conn.execute(
        """
        SELECT
          COUNT(*)                                          AS cnt,
          SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END) AS err_cnt,
          SUM(CASE WHEN is_stale = 1       THEN 1 ELSE 0 END) AS stale_cnt
        FROM attempts WHERE case_id = ?
        """,
        (cid,),
    )
    row = cur.fetchone()
    case["attempt_count"] = int(row["cnt"]) if row and row["cnt"] is not None else 0
    case["has_error"] = bool(row["err_cnt"]) if row and row["err_cnt"] is not None else False
    case["has_stale"] = bool(row["stale_cnt"]) if row and row["stale_cnt"] is not None else False

    # 최근 done attempt 의 score_pct
    cur = conn.execute(
        """
        SELECT score_pct FROM attempts
        WHERE case_id = ? AND status = 'done' AND score_pct IS NOT NULL
        ORDER BY submitted_at DESC LIMIT 1
        """,
        (cid,),
    )
    last = cur.fetchone()
    case["last_score_pct"] = float(last["score_pct"]) if last and last["score_pct"] is not None else None

    return case


# ─── 공용 API ──────────────────────────────────────────────────────


def list_cases(
    conn: sqlite3.Connection,
    *,
    filter_name: str = "all",
    subject: str | None = None,
    category: str | None = None,
    file_name: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """케이스 목록 조회 (필터 + 집계).

    Args:
        filter_name: 'all' | 'err' | 'stale' | 'book'
        subject:     subject 코드 (예: 'minbeop')
        category:    카테고리 (예: '입문' / '예비')
        file_name:   파일 코드 (예: '미케01')
        search:      title LIKE %search%

    Returns:
        Case dict 배열 (메타 + bookmarked + attempt_count + last_score_pct + has_error + has_stale).
        정렬: subject ASC, category ASC, file ASC, case_no ASC.
    """
    if filter_name not in ALLOWED_FILTERS:
        filter_name = "all"
    # alias 정규화 (bookmarked → book)
    filter_name = _FILTER_ALIASES.get(filter_name, filter_name)

    # 기본 쿼리 + 동적 WHERE
    where: list[str] = []
    params: list[Any] = []

    if subject:
        where.append("subject = ?")
        params.append(subject)
    if category:
        where.append("category = ?")
        params.append(category)
    if file_name:
        where.append("file = ?")
        params.append(file_name)
    if search:
        where.append("title LIKE ?")
        params.append(f"%{search}%")

    # filter=book → bookmarks JOIN
    if filter_name == "book":
        where.append("id IN (SELECT case_id FROM bookmarks)")
    elif filter_name == "err":
        where.append("id IN (SELECT case_id FROM attempts WHERE status = 'error')")
    elif filter_name == "stale":
        where.append("id IN (SELECT case_id FROM attempts WHERE is_stale = 1)")

    sql = "SELECT * FROM cases"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY subject ASC, category ASC, file ASC, case_no ASC"

    cur = conn.execute(sql, tuple(params))
    rows = cur.fetchall()
    cases = [_enrich_case_with_stats(conn, _case_row_to_dict(r)) for r in rows]
    return cases


def get_case(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    """단건 조회 (메타 + .md 파일 파싱 origin/lv1/lv4 + 집계).

    Raises:
        CaseNotFoundError: cases 테이블 미존재
        CaseFileMissingError: cases.path 의 .md 가 디스크에 없음
    """
    cur = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    row = cur.fetchone()
    if row is None:
        raise CaseNotFoundError(case_id)

    case = _case_row_to_dict(row)
    _enrich_case_with_stats(conn, case)

    # .md 파일 read + 파싱
    md_text = read_md_for_case(case["path"])
    sections = parse_md_file(md_text)

    case["origin"] = sections["origin"]
    case["origin_points"] = sections["origin_points"]
    case["lv1"] = sections["lv1"]
    case["lv4"] = sections["lv4"]
    case["meta"] = sections["meta"]
    # 채점 시 레퍼런스로 쓰는 전체 .md raw (Step 6 grader 에서 활용)
    case["md_body"] = md_text

    return case
