#!/usr/bin/env python3
"""17896 시험 콘솔 백엔드 — ThreadingHTTPServer + 정적 파일 + API.

launchd com.lawear.examconsole 호출 (포트 17896, 127.0.0.1 바인드).

Step 1 (commit d08b0cd): 정적 + 헬스 + placeholder.
Step 2 (commit 3c6e73e): SQLite 5 테이블 마이그레이션 v1.
Step 3 (본 커밋): 17895 → 17896 동기화 (`/api/sync/preview`, `/api/sync`).

dev-design archive #48 §3-1 endpoint matrix + §3-3 ErrorCode 1:1.
dev-impl-plan #51 Step 3 표 1:1.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import db as db_mod
import syncer as syncer_mod

# ─── 설정 (env 우선, 하드코딩 금지) ────────────────────────────────
PORT: int = int(os.environ.get("LAWEAR_EXAM_PORT", "17896"))
BIND: str = os.environ.get("LAWEAR_EXAM_BIND", "127.0.0.1")
ROOT: Path = Path(__file__).parent.resolve()
DB_PATH: str = os.environ.get("LAWEAR_EXAM_DB", str(ROOT / "exam.db"))
SERVER_NAME: str = "lawear-examconsole"
SERVER_VERSION: str = "0.2.0-sync"


class ExamHandler(SimpleHTTPRequestHandler):
    """정적 파일 + 헬스 + API 라우팅.

    SimpleHTTPRequestHandler 상속: index.html 등 정적 자산은 자동 서빙.
    do_GET / do_POST 오버라이드해 /api/* 라우팅 우선, 나머지는 부모 위임.
    """

    server_version = f"{SERVER_NAME}/{SERVER_VERSION}"

    # ─── 라우팅 ────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 헬스 체크
        if path == "/api/health":
            self._send_json(200, {
                "status": "ok",
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "phase": "sync",
            })
            return

        # 동기화 미리보기
        if path == "/api/sync/preview":
            self._handle_sync_preview()
            return

        # 미구현 API (Step 4+ placeholder)
        if path.startswith("/api/"):
            self._send_error(
                501,
                "not_implemented",
                f"Step 4+ API placeholder ({path})",
            )
            return

        # 정적 파일 (index.html 등) — 부모 위임
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 동기화 적용
        if path == "/api/sync":
            self._handle_sync_apply()
            return

        # 미구현 POST (Step 4+ placeholder)
        if path.startswith("/api/"):
            self._send_error(
                501,
                "not_implemented",
                f"Step 4+ API placeholder ({path})",
            )
            return

        # 정적 자원에 POST 는 405
        self.send_error(405, "Method Not Allowed")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    # ─── API 핸들러 ────────────────────────────────────────────

    def _handle_sync_preview(self) -> None:
        """`GET /api/sync/preview` — diff 만 (DB 변경 X)."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = syncer_mod.sync_preview(conn)
            self._send_json(200, result)
        except syncer_mod.SyncError as e:
            self._send_error(502, "remote_unreachable", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", str(e))

    def _handle_sync_apply(self) -> None:
        """`POST /api/sync` — UPSERT cases + UPDATE attempts.is_stale."""
        try:
            with db_mod.get_conn(DB_PATH) as conn:
                result = syncer_mod.sync_apply(conn)
            self._send_json(200, result)
        except syncer_mod.SyncError as e:
            self._send_error(502, "remote_unreachable", str(e))
        except Exception as e:  # noqa: BLE001
            self._send_error(500, "internal_error", str(e))

    # ─── CORS / 캐시 헤더 ───────────────────────────────────────
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    # ─── 로그 (17895 server.py 패턴) ─────────────────────────────
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        sys.stderr.write(
            f"[{self.log_date_time_string()}] [{SERVER_NAME}] {format % args}\n"
        )

    # ─── 헬퍼 ─────────────────────────────────────────────────
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, error_code: str, message: str) -> None:
        """dev-design #48 §3-3 ErrorCode 형식."""
        self._send_json(status, {
            "error_code": error_code,
            "message": message,
            "path": self.path,
        })


def main() -> int:
    os.chdir(ROOT)
    # DB 초기화 (멱등 — 매 시작 시 user_version 체크 후 v1 까지 적용)
    db_mod.init_db(DB_PATH)

    # ThreadingHTTPServer (dev-design #48 D-2 / archive #51 §5-2)
    httpd = ThreadingHTTPServer((BIND, PORT), ExamHandler)
    httpd.allow_reuse_address = True
    print(
        f"[{SERVER_NAME}] Serving {ROOT} (db={DB_PATH}) at http://{BIND}:{PORT}",
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"[{SERVER_NAME}] shutdown via SIGINT", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
