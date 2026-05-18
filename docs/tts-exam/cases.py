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


# ─── Step 24-2 다중 설문 정규식 3종 (8 .md 14 헤더 전수 100% 매칭) ───
#
# 패턴 A: `### 설문 1 (20점)`              — 민법 모고01_01, 민소 모고02_01/02
# 패턴 B: `### 설문 (1) (12점)`            — 민소 모고01_01/02 (괄호 안 숫자)
# 패턴 C: `### 설문 1 가 (12점)`           — 민법 모고02_01/02 (가/나 하위)
#
# `### 설문 N 답안` / `### 설문 N 가 답안` 은 `_SUBQ_HEADER_RE` 에 매칭 X
# (정규식 끝의 `\s*$` 가 "답안" 잔여를 거부).
_SUBQ_HEADER_RE = re.compile(
    r"^### (설문\s+(?:\(\d+\)|\d+))(?:\s+([가-힣]))?\s*(?:\((\d+)\s*점\))?\s*$",
    re.MULTILINE,
)

# `### 설문 N 답안` / `### 설문 (N) 답안` / `### 설문 N 가 답안` 등 답안 헤더.
_SUBQ_ANSWER_HEADER_RE = re.compile(
    r"^### (설문\s+(?:\(\d+\)|\d+))(?:\s+([가-힣]))?\s+답안\s*$",
    re.MULTILINE,
)

# `### 사실관계` / `### 공통된 사실관계` / `### 기본적 사실관계` / `### 변형된 사실관계`.
# group1=prefix(공통된|기본적|변형된) 또는 None(prefix 없음).
_FACTS_HEADER_RE = re.compile(
    r"^### (공통된|기본적|변형된)?\s*사실관계\s*$",
    re.MULTILINE,
)


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


# ─── Step 24-2 다중 설문 파싱 헬퍼 ───────────────────────────────────


def normalize_subq_key(group1: str, group2: str | None) -> str:
    """정규식 캡처 그룹 → 정규화된 subq key (`설문 N` / `설문 N 가`).

    Args:
        group1: `_SUBQ_HEADER_RE` 의 group1 (예: ``"설문 1"`` 또는 ``"설문 (1)"``).
        group2: `_SUBQ_HEADER_RE` 의 group2 (예: ``"가"``, ``"나"`` 또는 None).

    Returns:
        패턴 A `### 설문 1 (20점)`  + group2=None → ``"설문 1"``
        패턴 B `### 설문 (1) (12점)` + group2=None → ``"설문 1"`` (괄호 제거)
        패턴 C `### 설문 1 가 (12점)`+ group2="가"  → ``"설문 1 가"``
        패턴 B+C `### 설문 (1) 가 (12점)` (미래 대비) → ``"설문 1 가"``

    정규화 정책 (dev-design archive #48 G-1 Q6 A 결정):
        - DB attempt_criteria.subq_key TEXT + API JSON dict key 일관성 보장.
        - 표기 변형(괄호/공백 N개)은 통일 — R-09 자의가 아니라 키 매칭용.
    """
    # group1 예: "설문 1" / "설문 (1)" — 공백으로 split 후 [1] 가 숫자 토큰
    parts = group1.split()
    if len(parts) < 2:
        # 안전장치 (실제로는 정규식이 \s+ 강제하므로 도달 불가)
        num_part = group1.strip()
    else:
        num_part = parts[1].strip("()")  # "(1)" → "1"
    if group2:
        return f"설문 {num_part} {group2}"
    return f"설문 {num_part}"


def _extract_section_body(md_text: str, header_line_pos: int, header_match_end: int) -> str:
    """주어진 헤더 위치부터 다음 `^### ` 또는 `^## ` 헤더 전까지의 본문 추출.

    Args:
        md_text:           전체 .md 본문.
        header_line_pos:   header match 의 `start()` (= 줄 시작).
        header_match_end:  header match 의 `end()`.

    Returns:
        헤더 줄을 제외한 본문 (양옆 공백 strip).
    """
    # 다음 `### ` 또는 `## ` 헤더 찾기 (header_match_end 부터)
    # `^### ` 우선 — `^## ` 도 동시 검사 (Lv 섹션 시작이면 종료)
    next_h3 = re.search(r"^### ", md_text[header_match_end:], re.MULTILINE)
    next_h2 = re.search(r"^## ", md_text[header_match_end:], re.MULTILINE)
    candidates = []
    if next_h3:
        candidates.append(header_match_end + next_h3.start())
    if next_h2:
        candidates.append(header_match_end + next_h2.start())
    body_end = min(candidates) if candidates else len(md_text)
    return md_text[header_match_end:body_end].strip()


def parse_md_subqs(md_content: str) -> list[dict]:
    """다중 설문 .md → subq 카드 N개 분해.

    Args:
        md_content: .md 본문 원문 (`read_md_for_case` 결과).

    Returns:
        list[dict] — 각 카드 한 건:
            ``{"key": str, "score_max": int | None, "body": str, "answer": str}``

        - ``key``: 정규화 키 (``"설문 1"`` / ``"설문 1 가"``).
        - ``score_max``: 헤더 ``(NN점)`` 캡처 (없으면 None).
        - ``body``:  ``### 설문 N`` 헤더 다음 줄 ~ 다음 헤더 직전.
        - ``answer``: ``### 설문 N 답안`` 헤더 다음 줄 ~ 다음 헤더 직전.
                     매칭되는 답안 헤더가 없으면 빈 문자열.

        **단일 설문 (legacy fallback)**: ``_SUBQ_HEADER_RE`` 매칭 0건 →
        빈 리스트 ``[]`` 반환. 호출자가 단일 설문 케이스로 판단.

    알고리즘:
        1. `_SUBQ_HEADER_RE.finditer` 로 모든 문제 헤더 위치 수집.
        2. `_SUBQ_ANSWER_HEADER_RE.finditer` 로 모든 답안 헤더 위치 수집.
        3. `normalize_subq_key` 결과를 key 삼아 문제 헤더 ↔ 답안 헤더 짝 매칭.
        4. 본문은 `_extract_section_body` 로 다음 헤더 직전까지 슬라이스.
        5. 0건이면 [] 반환 (legacy).

    8 .md 실측 분포 (dev-design #48 5-2):
        - 패턴 A (4건): 민법 모고01_01 / 민소 모고02_01/02
        - 패턴 B (2건): 민소 모고01_01/02
        - 패턴 C (2건): 민법 모고02_01/02 (가/나 독립 카드)
        - fallback (1건): 민법 모고01_02 (### 설문 N 헤더 0개)
    """
    # 1. 문제 헤더 수집
    subq_headers = list(_SUBQ_HEADER_RE.finditer(md_content))
    if not subq_headers:
        # legacy fallback — 호출자가 단일 설문으로 처리
        return []

    # 2. 답안 헤더를 key 로 인덱싱
    answer_by_key: dict[str, re.Match] = {}
    for m in _SUBQ_ANSWER_HEADER_RE.finditer(md_content):
        key = normalize_subq_key(m.group(1), m.group(2))
        answer_by_key[key] = m

    # 3. 카드 N개 생성
    cards: list[dict] = []
    for m in subq_headers:
        g1 = m.group(1)
        g2 = m.group(2)
        score_str = m.group(3)
        key = normalize_subq_key(g1, g2)
        score_max = int(score_str) if score_str else None
        body = _extract_section_body(md_content, m.start(), m.end())

        ans_match = answer_by_key.get(key)
        if ans_match:
            answer = _extract_section_body(md_content, ans_match.start(), ans_match.end())
        else:
            answer = ""

        cards.append(
            {
                "key": key,
                "score_max": score_max,
                "body": body,
                "answer": answer,
            }
        )
    return cards


def parse_md_toc(md_content: str) -> str:
    """.md 본문에서 `### 목차` 섹션 본문 추출.

    Args:
        md_content: .md 본문 원문.

    Returns:
        ``### 목차`` 헤더 다음 줄 ~ 다음 헤더 직전 본문 (strip).
        헤더 없으면 빈 문자열.

    `### 목차` 는 Lv.1 빠른복습 안의 `### 문제` ~ `### 답안` 사이에 위치.
    """
    m = re.search(r"^### 목차\s*$", md_content, re.MULTILINE)
    if not m:
        return ""
    return _extract_section_body(md_content, m.start(), m.end())


def parse_md_mnemonic(md_content: str) -> list[str]:
    """.md 본문에서 Lv.4 암기노트 번호 목록 추출.

    Args:
        md_content: .md 본문 원문.

    Returns:
        ``## Lv.4`` 섹션 안에 한 줄에 ``N. `` (반각 점 + 공백) 으로 시작하는
        모든 줄 list (번호 prefix 포함, strip).
        Lv.4 섹션이 없거나 번호 목록이 없으면 빈 list.

    예시 (모고01_01.md Lv.4):
        ``["1. B 회사의 대출원리금 ...", "2. A 은행의 1999년 ...", ...]``
    """
    # Lv.4 섹션만 슬라이스 (`^## Lv.4` ~ 다음 `^## ` 또는 EOF)
    lv4_match = re.search(r"^## Lv\.4[^\n]*$", md_content, re.MULTILINE)
    if not lv4_match:
        return []
    lv4_start = lv4_match.end()
    next_h2 = re.search(r"^## ", md_content[lv4_start:], re.MULTILINE)
    lv4_end = lv4_start + next_h2.start() if next_h2 else len(md_content)
    lv4_body = md_content[lv4_start:lv4_end]

    # 번호 목록 라인 ("1. ", "2. ", ...) 추출 — 순서 보존
    items: list[str] = []
    for line in lv4_body.split("\n"):
        if re.match(r"^\s*\d+\.\s", line):
            items.append(line.strip())
    return items


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
