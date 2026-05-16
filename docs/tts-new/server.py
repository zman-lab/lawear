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
from pathlib import Path
from urllib.parse import unquote

PORT = 17895
BIND = "0.0.0.0"
ROOT = Path(__file__).parent.resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_PUT(self):
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

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
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
