#!/usr/bin/env python3
"""TTS 머지 뷰어 백엔드 — 정적 파일 GET + .md PUT 저장.

launchd com.lawear.ttsmerger에서 호출 (포트 17895).
ROOT 안의 .md 파일만 PUT 허용 (path traversal 방지).
"""
import http.server
import json
import os
import socketserver
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

PORT = 17895
BIND = "0.0.0.0"
ROOT = Path(__file__).parent.resolve()
STAGING_DIR = ROOT / '_staging'
ALLOWED_STAGING_SUBJECTS = {'민법', '민소', '형법', '형소', '부등'}


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_PUT(self):
        # Staging endpoint (라이브러리/두문자 전용 임시 저장 — 뷰어 갱신 X)
        if self.path.startswith('/api/staging/upload/'):
            self._handle_staging_upload()
            return

        if not self.path.startswith('/api/save/'):
            self.send_error(404, "Not Found")
            return

        rel_path = unquote(self.path[len('/api/save/'):])
        target = (ROOT / rel_path).resolve()

        try:
            target.relative_to(ROOT)
        except ValueError:
            self.send_error(403, "Path traversal blocked")
            return

        if target.suffix != '.md':
            self.send_error(403, "Only .md files allowed")
            return

        if not target.parent.exists():
            self.send_error(404, "Parent directory not found")
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_error(400, "Empty body")
            return

        body = self.rfile.read(content_length)
        try:
            content = body.decode('utf-8')
        except UnicodeDecodeError:
            self.send_error(400, "Invalid UTF-8")
            return

        if target.exists():
            backup = target.with_suffix('.md.bak')
            backup.write_text(target.read_text(encoding='utf-8'), encoding='utf-8')

        target.write_text(content, encoding='utf-8')

        response = json.dumps(
            {"saved": str(target.relative_to(ROOT)), "bytes": len(body)},
            ensure_ascii=False
        )
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def _handle_staging_upload(self):
        """라이브러리(두문자) staging 업로드 — 뷰어 즉시 갱신 X.

        AI가 사용자 발화 후 4 케이스 분류 + 머지 + 최종 PUT /api/save/ 처리.
        """
        rel_subject = unquote(self.path[len('/api/staging/upload/'):]).strip('/')

        if rel_subject not in ALLOWED_STAGING_SUBJECTS:
            self.send_error(400, f"Invalid subject (allowed: {sorted(ALLOWED_STAGING_SUBJECTS)})")
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_error(400, "Empty body")
            return

        body = self.rfile.read(content_length)
        try:
            body.decode('utf-8')
        except UnicodeDecodeError:
            self.send_error(400, "Invalid UTF-8")
            return

        STAGING_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        target = STAGING_DIR / f'{rel_subject}_{ts}.md'
        target.write_bytes(body)

        response = json.dumps({
            "staged": f"_staging/{rel_subject}_{ts}.md",
            "subject": rel_subject,
            "bytes": len(body),
            "next_step": f"AI에게 '{rel_subject} 두문자 업로드했어' 말씀하시면 4 케이스 분석 후 처리합니다."
        }, ensure_ascii=False)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    os.chdir(ROOT)
    with ReusableTCPServer((BIND, PORT), Handler) as httpd:
        print(f"Serving {ROOT} at http://{BIND}:{PORT}", file=sys.stderr)
        httpd.serve_forever()
