#!/usr/bin/env python3
"""TTS 머지 뷰어 백엔드 — 정적 파일 GET + .md PUT 저장 + POST 신규 생성.

launchd com.lawear.ttsmerger에서 호출 (포트 17895).
ROOT 안의 .md 파일만 PUT 허용 (path traversal 방지).

엔드포인트:
  - GET  /<path>                       정적 파일 서빙 (SimpleHTTPRequestHandler 기본)
  - PUT  /api/save/<rel_path>          기존 .md 갱신 (parent 존재 강제)
  - PUT  /api/staging/upload/<subj>    라이브러리/두문자 staging 업로드
  - POST /api/create/<rel_path>        신규 .md 생성 (parent mkdir, 화이트리스트 검증) -- lawear-7ad6 신규
"""
import fcntl
import http.server
import json
import logging
import os
import re
import socketserver
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

# --- 상수 -----------------------------------------------------------------
PORT = 17895
BIND = "0.0.0.0"
ROOT = Path(__file__).parent.resolve()
STAGING_DIR = ROOT / '_staging'
INDEX_PATH = ROOT / '_file_index.json'

# 라이브러리/두문자 staging 업로드 허용 과목 — lawear-7ad6: 민사서류/부등서류 추가
ALLOWED_STAGING_SUBJECTS = {
    '민법', '민소', '형법', '형소', '부등',
    '민사서류', '부등서류',  # lawear-7ad6 (작업 A) — 3과목 입력 모드 동기
}

# POST /api/create 신규 생성 허용 폴더 화이트리스트 (작업 A — design §3 결정)
# 사용자가 직접 입력하는 3과목만 허용. 기존 17895 폴더는 PUT /api/save 로 처리.
ALLOWED_NEW_DIRS = frozenset({
    '2026_사용자_부동산등기법',
    '2026_사용자_부동산등기서류',
    '2026_사용자_민사서류',
})

# .md 최소 필수 섹션 (design §3, design §4 mirror) — '## 메타' 누락 시 400
META_SECTION_RE = re.compile(r'^##\s*메타\s*$', re.MULTILINE)

# --- 로깅 -----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stderr,
)
log = logging.getLogger('lawear.server')


class Handler(http.server.SimpleHTTPRequestHandler):
    # --------------------------------------------------------------------
    # PUT — 기존 .md 갱신 + staging 업로드 (변경 없음, 기존 17895 무손상)
    # --------------------------------------------------------------------
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

    # --------------------------------------------------------------------
    # POST — 신규 .md 생성 (lawear-7ad6 작업 A 신규)
    # --------------------------------------------------------------------
    def do_POST(self):
        """POST 라우터. 현재는 /api/create/<rel_path> 만 처리."""
        if self.path.startswith('/api/create/'):
            self._handle_create()
            return
        self.send_error(404, "Not Found")

    def _handle_create(self):
        """POST /api/create/<rel_path> — 신규 .md 생성 + _file_index.json append.

        design §3 8단계 순서대로 수행:
          1) relative_to(ROOT) traversal 차단 (403)
          2) target.parent.name in ALLOWED_NEW_DIRS 화이트리스트 (403)
          3) .md 확장자 강제 (403)
          4) target.parent.mkdir(parents=True, exist_ok=True) 자동 생성
          5) target.exists() 시 409 (overwrite 거부 — PUT /save 가 처리)
          6) body UTF-8 + '## 메타' 정규식 최소 검증 (400)
          7) target.write_text(body)
          8) _append_index_entry(...) 호출

        성공 시 200 + {"status":"ok","path":"...","bytes":N,
                       "created":"...","index_updated":bool,"id":"..."}.
        실패 시 send_error 로 표준 응답.
        """
        rel_path = unquote(self.path[len('/api/create/'):])
        log.info("POST /api/create 요청 받음: rel_path=%r", rel_path)

        # --- 1) traversal 차단 ------------------------------------------------
        # ROOT 밖으로 빠지는 ../../ 패턴 거부. resolve() 후 relative_to(ROOT)로 검증.
        target = (ROOT / rel_path).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            log.warning("traversal 차단: %r -> %s", rel_path, target)
            self.send_error(403, "Path traversal blocked")
            return

        # --- 3) .md 확장자 강제 (2 보다 먼저 — 비-.md 즉시 거부) ----------------
        # 확장자 검증을 먼저 하면 화이트리스트 폴더 검사에서 불필요한 의존성을 피함.
        if target.suffix != '.md':
            log.warning("비-.md 거부: %s", target.name)
            self.send_error(403, "Only .md files allowed")
            return

        # --- 2) 화이트리스트 검증 --------------------------------------------
        # target 의 parent 폴더명이 ALLOWED_NEW_DIRS 에 있어야 함.
        # 사용자 입력 3과목 폴더만 신규 생성 허용. 기존 17895 폴더는 PUT /save 사용.
        # NOTE: HTTP 상태 라인은 latin-1 인코딩만 허용 → 한글 메시지 금지. ASCII 만 사용.
        if target.parent.name not in ALLOWED_NEW_DIRS:
            log.warning(
                "화이트리스트 밖 폴더 거부: parent=%r (allowed=%s)",
                target.parent.name, sorted(ALLOWED_NEW_DIRS),
            )
            self.send_error(403, "Folder not in whitelist")
            return

        # --- 4) parent dir 자동 mkdir ----------------------------------------
        # mkdir -p 동작. 화이트리스트 통과 후이므로 안전.
        target.parent.mkdir(parents=True, exist_ok=True)
        log.info("parent dir 확보: %s", target.parent)

        # --- 5) 존재 시 409 (overwrite 거부) ---------------------------------
        # POST 는 신규 전용. 갱신은 PUT /api/save/ 사용. 클라이언트가 +1 재시도.
        if target.exists():
            log.info("conflict (이미 존재): %s", target.name)
            self.send_error(409, "File already exists (use PUT /api/save/ to update)")
            return

        # --- 6) body 검증 -----------------------------------------------------
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            log.warning("빈 body 거부: %s", target.name)
            self.send_error(400, "Empty body")
            return

        body = self.rfile.read(content_length)
        try:
            content = body.decode('utf-8')
        except UnicodeDecodeError:
            log.warning("invalid UTF-8: %s", target.name)
            self.send_error(400, "Invalid UTF-8")
            return

        # '## 메타' 섹션 누락 시 400 (design §3 + §4 mirror)
        # NOTE: HTTP 상태 라인은 latin-1 만 허용 → 한글 금지. ASCII 메시지로 표기.
        if not META_SECTION_RE.search(content):
            log.warning("'## 메타' 섹션 누락: %s", target.name)
            self.send_error(400, "Missing required meta section")
            return
        log.info("검증 통과: %s (%d bytes)", target.name, len(body))

        # --- 7) 파일 작성 -----------------------------------------------------
        target.write_text(content, encoding='utf-8')
        log.info("파일 작성 완료: %s (%d bytes)", target.relative_to(ROOT), len(body))

        # --- 8) _file_index.json append --------------------------------------
        # 헬퍼 실패 시에도 파일은 이미 작성됨 — index_updated:false 응답.
        rel_str = str(target.relative_to(ROOT))
        file_id = target.stem  # ex) 2026_budeunglaw_user_01
        index_updated = False
        try:
            _append_index_entry(file_id=file_id, rel_path=rel_str, parent=target.parent.name)
            index_updated = True
            log.info("_file_index.json 갱신 완료: id=%s", file_id)
        except Exception as e:
            # 인덱스 갱신 실패는 200 응답 유지하고 클라이언트에 플래그로 전달.
            # (파일은 이미 작성됨 — 재시도 시 409 발생 방지)
            log.exception("_file_index.json 갱신 실패 (파일은 작성됨): %s", e)

        response = json.dumps({
            "status": "ok",
            "path": rel_str,
            "bytes": len(body),
            "created": rel_str,
            "id": file_id,
            "index_updated": index_updated,
        }, ensure_ascii=False)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    # --------------------------------------------------------------------
    # CORS / OPTIONS / 로깅
    # --------------------------------------------------------------------
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        # lawear-7ad6: POST 추가
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        # 기존 호환 — http.server 의 access log 는 stderr 로 그대로 출력.
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


# ------------------------------------------------------------------------
# _file_index.json 헬퍼 (S3) — flock + atomic rename + .bak (R3 동시성)
# ------------------------------------------------------------------------
def _append_index_entry(file_id: str, rel_path: str, parent: str) -> None:
    """_file_index.json 에 type:"user_input" 신규 entry append.

    - flock(LOCK_EX) 으로 동시 POST 직렬화 (R3)
    - 임시파일 + os.replace 로 atomic rename
    - 작성 전 .bak 보존 (손상 시 복구 가능)
    - JSON validate 실패 시 .bak 복원 후 예외 전파

    Args:
      file_id: stem (예: 2026_budeunglaw_user_01) — _file_index.json id 필드.
      rel_path: ROOT 기준 상대 경로 (예: 2026_사용자_부동산등기법/2026_budeunglaw_user_01.md).
      parent: 부모 폴더명 (예: 2026_사용자_부동산등기법) — subjectKor 추출용.
    """
    # 부모 폴더명 → subjectKor 매핑 (ALLOWED_NEW_DIRS 와 1:1)
    parent_to_subj_kor = {
        '2026_사용자_부동산등기법': '부동산등기법',
        '2026_사용자_부동산등기서류': '부동산등기서류',
        '2026_사용자_민사서류': '민사서류',
    }
    # id 에서 subject 영문 추출 (예: 2026_budeunglaw_user_01 -> budeunglaw)
    parts = file_id.split('_')
    subject_en = parts[1] if len(parts) >= 2 else 'unknown'
    case_num = parts[-1] if len(parts) >= 1 else '01'
    year = parts[0] if parts and parts[0].isdigit() else datetime.now().strftime('%Y')

    new_entry = {
        "id": file_id,
        "subject": subject_en,
        "subjectKor": parent_to_subj_kor.get(parent, parent),
        "category": "사용자",  # design §5 사이드패널 신규 카테고리
        "file": "user",
        "fileKor": f"{year}_{parent_to_subj_kor.get(parent, parent)}_사용자",
        "case": case_num,
        "title": "사용자 직접 입력",
        "path": rel_path,
        "pdfPath": None,
        "points": 0,
        "userCase": None,
        "type": "user_input",  # design §5 merge.html 분기 키
        "_addedBy": "lawear-7ad6-input-mode",
        "_year": year,
    }

    # 인덱스 파일 없으면 빈 구조로 초기화 (실서비스는 항상 존재)
    if not INDEX_PATH.exists():
        log.warning("_file_index.json 없음 — 신규 생성: %s", INDEX_PATH)
        INDEX_PATH.write_text(json.dumps({"files": []}, ensure_ascii=False), encoding='utf-8')

    # 별도 lock file (.json.lock) 로 동시 POST 직렬화 (R3) — atomic rename 호환
    # TC14 race fix: 기존엔 INDEX_PATH 자체에 flock + atomic rename 시 두 번째 호출자가 stale inode 작업
    # 별도 lock 파일은 atomic rename 영향 X — 모든 호출자가 동일 lock 경로 공유.
    LOCK_PATH = INDEX_PATH.with_suffix('.json.lock')
    LOCK_PATH.touch(exist_ok=True)
    with open(LOCK_PATH, 'r') as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            # lock 획득 후 INDEX_PATH 새로 read — 이전 호출자의 atomic rename 결과 반영
            try:
                data = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                log.error("_file_index.json 파싱 실패: %s — .bak 복원 시도", e)
                bak = INDEX_PATH.with_suffix('.json.bak')
                if bak.exists():
                    data = json.loads(bak.read_text(encoding='utf-8'))
                    log.info("_file_index.json.bak 에서 복원")
                else:
                    raise

            files = data.setdefault('files', [])

            # 중복 id 갱신 X — 기존 보존 (TC17)
            if any(f.get('id') == file_id for f in files):
                log.info("중복 id 스킵 (기존 보존): %s", file_id)
                return

            files.append(new_entry)

            # 백업 보존 — 신규 entry 추가 전 INDEX_PATH 내용을 .bak 으로 (R3)
            bak = INDEX_PATH.with_suffix('.json.bak')
            try:
                bak.write_text(INDEX_PATH.read_text(encoding='utf-8'), encoding='utf-8')
            except Exception as e:
                log.warning(".bak 작성 실패 (무시 가능): %s", e)

            # atomic write — 임시 파일 + os.replace
            new_content = json.dumps(data, ensure_ascii=False, indent=2)
            # validate (load -> dump 라운드트립 의미는 없으나, dumps 가 성공한 시점에서 JSON 유효)
            tmp_fd, tmp_path = tempfile.mkstemp(
                prefix='_file_index.', suffix='.tmp', dir=str(ROOT)
            )
            try:
                with os.fdopen(tmp_fd, 'w', encoding='utf-8') as tmp:
                    tmp.write(new_content)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                # atomic rename (POSIX). flock 은 유지됨 — replace 후에도 fd 는 stale 데이터를 가리키지만
                # 다음 호출자가 새로 열어 정상 데이터를 본다.
                os.replace(tmp_path, INDEX_PATH)
                log.info("_file_index.json atomic rename 완료 (+1 entry, total=%d)", len(files))
            except Exception:
                # 실패 시 임시파일 정리
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
        finally:
            # lock file fd 해제 (with 종료 시 close — flock 자동 해제)
            try:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


# ------------------------------------------------------------------------
# 엔트리포인트
# ------------------------------------------------------------------------
class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    os.chdir(ROOT)
    # R6: 워크트리 임시 포트 (env PORT override 가능)
    port = int(os.environ.get('PORT', PORT))
    with ReusableTCPServer((BIND, port), Handler) as httpd:
        log.info("Serving %s at http://%s:%d", ROOT, BIND, port)
        httpd.serve_forever()
