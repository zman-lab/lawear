#!/usr/bin/env python3
"""17896 시험 콘솔 백엔드 — ThreadingHTTPServer + 정적 파일 서빙.

launchd com.lawear.examconsole에서 호출 (포트 17896, 127.0.0.1 바인드).
Step 1 부트스트랩: 정적 파일 서빙 + 헬스 체크 + API placeholder만.
Step 2~ API/DB/Claude 채점/동기화는 후속 Step에서 본 파일에 추가.

dev-design archive #48 / dev-impl-plan archive #51 H2 7 paste 본문 1:1.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ─── 설정 (하드코딩 금지 — env 우선, 기본값 fallback) ────────────────
PORT: int = int(os.environ.get("LAWEAR_EXAM_PORT", "17896"))
BIND: str = os.environ.get("LAWEAR_EXAM_BIND", "127.0.0.1")
ROOT: Path = Path(__file__).parent.resolve()
SERVER_NAME: str = "lawear-examconsole"
SERVER_VERSION: str = "0.1.0-bootstrap"


class ExamHandler(SimpleHTTPRequestHandler):
    """정적 파일 + 헬스체크 + API placeholder.

    SimpleHTTPRequestHandler 상속: index.html 등 정적 자산은 자동 서빙.
    do_GET을 오버라이드해 /api/* 라우팅을 먼저 처리, 나머지는 부모로 위임.
    """

    server_version = f"{SERVER_NAME}/{SERVER_VERSION}"

    # ─── 라우팅 ────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802 (Python HTTP API 규약)
        if self.path == "/api/health":
            self._send_json(200, {
                "status": "ok",
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "phase": "bootstrap",
            })
            return
        if self.path.startswith("/api/"):
            self._send_json(501, {
                "error_code": "not_implemented",
                "message": "Step 2~ API placeholder. 후속 Step에서 구현.",
                "path": self.path,
            })
            return
        # 정적 파일 (index.html 등) — 부모 위임
        super().do_GET()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    # ─── CORS / 캐시 헤더 ───────────────────────────────────────
    def end_headers(self) -> None:
        # 1인 로컬 도구 — 127.0.0.1 바인드 + CORS 허용
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
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    os.chdir(ROOT)
    # ThreadingHTTPServer: dev-design #48 D-2 / archive #51 §5-2 명시 — 단일 스레드 금지
    httpd = ThreadingHTTPServer((BIND, PORT), ExamHandler)
    httpd.allow_reuse_address = True
    print(
        f"[{SERVER_NAME}] Serving {ROOT} at http://{BIND}:{PORT}",
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
