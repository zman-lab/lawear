#!/usr/bin/env python3
"""17895 → 17896 동기화 (content_hash diff + UPSERT cases).

dev-design archive #48 §4-6 / dev-impl-plan #51 Step 3 1:1.

핵심:
- 17895 `/_file_index.json` fetch + 각 entry 의 .md 본문 fetch (sha256 hash)
- 로컬 cases 테이블 (id, content_hash) 와 diff → added / changed / removed
- `sync_preview()` : diff 만 반환 (DB 변경 X)
- `sync_apply()`  : UPSERT cases + UPDATE attempts SET is_stale=1 WHERE case_id IN changed
- removed 처리: Q15 권장 = soft-marking (히스토리 보존). cases 에 별도 stale 컬럼 없으므로,
  현재 단계에서는 cases 에서 삭제하지 않고 응답에 표기만 반환 (히스토리 보존).
  → 추후 cases.stale BOOLEAN 컬럼 추가 시 마킹으로 확장. dev-impl-plan §5 Q15 권장 보존 정책.

설계 결정:
- urllib.request 사용 (외부 의존성 0). 표준 라이브러리만.
- 17895 URL: env LAWEAR_REMOTE_BASE 우선, 기본 http://127.0.0.1:17895
- path 인코딩: urllib.parse.quote(path, safe='/') — 한글 경로 percent-encoded
- 17895 OFF 시: urllib.error.URLError 발생 → handler 에서 500 변환
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

# ─── 설정 (env 우선, 하드코딩 금지) ───────────────────────────────
REMOTE_BASE: str = os.environ.get("LAWEAR_REMOTE_BASE", "http://127.0.0.1:17895")
REMOTE_INDEX_PATH: str = "/_file_index.json"
HTTP_TIMEOUT_SEC: int = int(os.environ.get("LAWEAR_REMOTE_TIMEOUT", "10"))


class SyncError(Exception):
    """동기화 실패 (17895 unreachable, JSON 파싱 실패 등)."""


def _utc_now_iso() -> str:
    """UTC ISO-8601 (Z suffix). dev-design §3-2 synced_at 형식."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_get(url: str) -> bytes:
    """HTTP GET (raw bytes). urllib 표준 라이브러리.

    Raises:
        SyncError: URLError / HTTPError / timeout
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lawear-examconsole/0.1"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:  # noqa: S310
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        raise SyncError(f"remote_unreachable: {url} ({e})") from e


def _fetch_remote_index() -> list[dict[str, Any]]:
    """17895 _file_index.json fetch + parse.

    Returns:
        files 배열 (각 entry: id/subject/subjectKor/category/file/fileKor/case/title/path/pdfPath/points/userCase)
    """
    url = REMOTE_BASE.rstrip("/") + REMOTE_INDEX_PATH
    raw = _http_get(url)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SyncError(f"index_parse_failure: {e}") from e
    files = data.get("files")
    if not isinstance(files, list):
        raise SyncError("index_missing_files: response has no 'files' array")
    return files


def _fetch_remote_md(path: str) -> bytes:
    """17895 의 .md 본문 fetch. path 한글 percent-encode."""
    encoded = urllib.parse.quote(path, safe="/")
    url = REMOTE_BASE.rstrip("/") + "/" + encoded.lstrip("/")
    return _http_get(url)


def _sha256_hex(data: bytes) -> str:
    """sha256 hex digest (lowercase)."""
    return hashlib.sha256(data).hexdigest()


def _load_local_index(conn: sqlite3.Connection) -> dict[str, str]:
    """로컬 cases (id → content_hash) 로드."""
    cur = conn.execute("SELECT id, content_hash FROM cases")
    return {row["id"]: row["content_hash"] for row in cur.fetchall()}


def _entry_to_case_row(entry: dict[str, Any], content_hash: str, synced_at: str) -> dict[str, Any]:
    """_file_index entry → cases 테이블 row (dict).

    _file_index 카멜케이스 → DB 스네이크케이스 매핑.

    lawear-2e42 (2026-05-20): type=library entry (두문자/PDF 라이브러리)는
    category/file/case 키 부재 → placeholder 채워 cases 테이블 등재 (Q2 정책).
    채점/힌트에서 두문자 라이브러리 활용 위해 알아야 함. 단 사이드 패널 트리에서는
    subject IN ('index','pdf_raw') 또는 category='라이브러리' 노드 skip (UI 책임).
    """
    is_library = entry.get("type") == "library"
    return {
        "id": entry["id"],
        "subject": entry["subject"],
        "subject_kor": entry["subjectKor"],
        "category": entry.get("category") or ("라이브러리" if is_library else ""),
        "file": entry.get("file") or (entry.get("case", "라이브러리") if is_library else ""),
        "file_kor": entry.get("fileKor"),
        "case_no": entry.get("case") or "00",
        "title": entry["title"],
        "path": entry["path"],
        "pdf_path": entry.get("pdfPath"),
        "points": int(entry.get("points") or 0),
        # user_case: int 또는 "8-1, 8-2" 문자열 모두 허용 (dev-design §3-2 user_case TEXT)
        "user_case": str(entry["userCase"]) if entry.get("userCase") is not None else None,
        "synced_at": synced_at,
        "content_hash": content_hash,
    }


def sync_preview(conn: sqlite3.Connection) -> dict[str, Any]:
    """동기화 미리보기 (DB 변경 X).

    Returns:
        {
          "remote_count": N,
          "local_count":  M,
          "added":   [{id, title, path}, ...],
          "changed": [{id, title, reason}, ...],
          "removed": [{id}, ...],
          "last_sync_at": ISO8601 또는 None
        }
    """
    remote_entries = _fetch_remote_index()
    local_hashes = _load_local_index(conn)
    remote_by_id: dict[str, dict[str, Any]] = {e["id"]: e for e in remote_entries}

    added: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []

    # added / changed
    for rid, rentry in remote_by_id.items():
        body = _fetch_remote_md(rentry["path"])
        rhash = _sha256_hex(body)
        if rid not in local_hashes:
            added.append({"id": rid, "title": rentry["title"], "path": rentry["path"]})
        elif local_hashes[rid] != rhash:
            changed.append({"id": rid, "title": rentry["title"], "reason": "content_hash_diff"})

    # removed
    for lid in local_hashes:
        if lid not in remote_by_id:
            removed.append({"id": lid})

    # last_sync_at: cases.synced_at 최댓값 (없으면 None)
    cur = conn.execute("SELECT MAX(synced_at) AS last FROM cases")
    last_row = cur.fetchone()
    last_sync_at = last_row["last"] if last_row and last_row["last"] else None

    return {
        "remote_count": len(remote_by_id),
        "local_count": len(local_hashes),
        "added": added,
        "changed": changed,
        "removed": removed,
        "last_sync_at": last_sync_at,
    }


def sync_apply(conn: sqlite3.Connection) -> dict[str, Any]:
    """동기화 적용 (UPSERT cases + UPDATE attempts.is_stale).

    트랜잭션 경계: 단일 BEGIN/COMMIT. 실패 시 ROLLBACK.

    Returns:
        sync_preview 형식 + {"applied_at": ISO8601, "total": N}
    """
    remote_entries = _fetch_remote_index()
    local_hashes = _load_local_index(conn)
    remote_by_id: dict[str, dict[str, Any]] = {e["id"]: e for e in remote_entries}

    # 각 entry 의 hash 미리 계산 (네트워크 IO 트랜잭션 밖)
    entry_with_hash: list[tuple[dict[str, Any], str]] = []
    for rentry in remote_entries:
        body = _fetch_remote_md(rentry["path"])
        rhash = _sha256_hex(body)
        entry_with_hash.append((rentry, rhash))

    added: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    applied_at = _utc_now_iso()

    # diff 분류 (preview 와 동일 로직)
    for rentry, rhash in entry_with_hash:
        rid = rentry["id"]
        if rid not in local_hashes:
            added.append({"id": rid, "title": rentry["title"], "path": rentry["path"]})
        elif local_hashes[rid] != rhash:
            changed.append({"id": rid, "title": rentry["title"], "reason": "content_hash_diff"})

    for lid in local_hashes:
        if lid not in remote_by_id:
            removed.append({"id": lid})

    changed_ids = {c["id"] for c in changed}

    # UPSERT + is_stale 마킹 (단일 트랜잭션)
    try:
        conn.execute("BEGIN")
        for rentry, rhash in entry_with_hash:
            row = _entry_to_case_row(rentry, rhash, applied_at)
            conn.execute(
                """
                INSERT INTO cases (
                  id, subject, subject_kor, category, file, file_kor, case_no,
                  title, path, pdf_path, points, user_case, synced_at, content_hash
                ) VALUES (
                  :id, :subject, :subject_kor, :category, :file, :file_kor, :case_no,
                  :title, :path, :pdf_path, :points, :user_case, :synced_at, :content_hash
                )
                ON CONFLICT(id) DO UPDATE SET
                  subject      = excluded.subject,
                  subject_kor  = excluded.subject_kor,
                  category     = excluded.category,
                  file         = excluded.file,
                  file_kor     = excluded.file_kor,
                  case_no      = excluded.case_no,
                  title        = excluded.title,
                  path         = excluded.path,
                  pdf_path     = excluded.pdf_path,
                  points       = excluded.points,
                  user_case    = excluded.user_case,
                  synced_at    = excluded.synced_at,
                  content_hash = excluded.content_hash
                """,
                row,
            )

        # changed 인 case_id 의 attempts 에 is_stale=1 마킹 (히스토리 보존)
        if changed_ids:
            placeholders = ",".join("?" for _ in changed_ids)
            conn.execute(
                f"UPDATE attempts SET is_stale = 1 WHERE case_id IN ({placeholders})",
                tuple(changed_ids),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "remote_count": len(remote_by_id),
        "local_count": len(local_hashes),
        "added": added,
        "changed": changed,
        "removed": removed,
        "applied_at": applied_at,
        "total": len(remote_by_id),
    }
