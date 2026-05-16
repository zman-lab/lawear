#!/usr/bin/env python3
"""17896 시험 콘솔 — SQLite 5 테이블 + 마이그레이션 v1.

dev-design archive #48 §4-2 DDL 1:1.
SQL은 migrations/001_initial.sql 파일 single source of truth.

사용:
    from db import init_db, get_conn
    init_db("exam.db")                     # 멱등 — 여러 번 호출 OK
    with get_conn("exam.db") as conn:
        rows = conn.execute("SELECT * FROM cases").fetchall()
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# ─── 설정 (하드코딩 금지 — 모듈 상수로 분리) ──────────────────────────
DB_DIR: Path = Path(__file__).parent.resolve()
MIGRATIONS_DIR: Path = DB_DIR / "migrations"
DEFAULT_DB_FILENAME: str = "exam.db"
TARGET_SCHEMA_VERSION: int = 5
BUSY_TIMEOUT_MS: int = 5000  # archive #51 H2 7 ChE7 명시

# 마이그레이션 매트릭스 — 버전: SQL 파일명
# 새 버전 추가 시 이 dict + migrations/ 파일만 갱신.
MIGRATIONS: dict[int, str] = {
    1: "001_initial.sql",
    2: "002_attempts_extras.sql",  # Step 7 — attempts 컬럼 4개 추가
    3: "003_manual_grading.sql",   # Step 13 — manual 채점 모드 + status='pending_grade'
    4: "004_v4_weights.sql",       # Step 20 — 채점 기준 v4 (articles 신설, 8기준)
    5: "005_v5_case_apply.sql",    # Step 21 — 채점 기준 v5 (case_apply 신설 + rich 20→15)
}


def _migration_sql(version: int) -> str:
    """버전별 마이그레이션 SQL 본문 로드."""
    if version not in MIGRATIONS:
        raise ValueError(f"unknown migration version: {version}")
    path = MIGRATIONS_DIR / MIGRATIONS[version]
    if not path.is_file():
        raise FileNotFoundError(f"migration sql not found: {path}")
    return path.read_text(encoding="utf-8")


def _current_user_version(conn: sqlite3.Connection) -> int:
    cur = conn.execute("PRAGMA user_version;")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def get_conn(db_path: str | Path = DEFAULT_DB_FILENAME) -> sqlite3.Connection:
    """SQLite 연결 + PRAGMA 적용.

    - foreign_keys=ON: FK 강제
    - busy_timeout: 동시성 락 대기 5초
    - row_factory: dict-like access
    """
    path = Path(db_path)
    if not path.is_absolute():
        path = DB_DIR / path
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS};")
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_FILENAME) -> int:
    """DB 초기화 + 마이그레이션 v1 적용 (멱등).

    Returns:
        적용 후 user_version (TARGET_SCHEMA_VERSION).
    """
    conn = get_conn(db_path)
    try:
        current = _current_user_version(conn)
        if current >= TARGET_SCHEMA_VERSION:
            print(
                f"[DB] schema already at v{current} (target=v{TARGET_SCHEMA_VERSION}) — skip",
                file=sys.stderr,
            )
            return current

        # v1까지 순차 적용 (현재는 v1뿐, 향후 v2/v3 추가 시 동일 패턴 확장)
        for version in range(current + 1, TARGET_SCHEMA_VERSION + 1):
            print(
                f"[DB] applying migration v{version} ({MIGRATIONS[version]})",
                file=sys.stderr,
            )
            sql = _migration_sql(version)
            # executescript: 다중 statement + PRAGMA + DDL + INSERT 일괄
            conn.executescript(sql)
            conn.commit()
            print(f"[DB] migration v{version} done", file=sys.stderr)

        final = _current_user_version(conn)
        if final != TARGET_SCHEMA_VERSION:
            # 마이그레이션 SQL이 PRAGMA user_version 설정을 누락한 경우 보정
            conn.execute(f"PRAGMA user_version = {TARGET_SCHEMA_VERSION};")
            conn.commit()
            final = _current_user_version(conn)
        print(f"[DB] schema now at v{final}", file=sys.stderr)
        return final
    finally:
        conn.close()


def main() -> int:
    """CLI: python3 db.py [db_path]"""
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_FILENAME
    version = init_db(db_path)
    print(f"[DB] OK — db={db_path} version={version}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
