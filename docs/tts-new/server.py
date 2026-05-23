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
# 사용자가 직접 입력하는 5과목 × 2025/2026 = 10 폴더 허용.
# 기존 17895 폴더 (입문_민법 등)는 PUT /api/save 로 처리.
# lawear-7ad6 v2: 형법/형소 추가 + 2025년도 추가 (사용자 직접 입력 확장).
# lawear-7ad6 v3 (팀 7A): 2단 폴더 허용 — `2026_사용자_X/{사용자 카테고리}/{file}.md`.
#   최상위 parent 만 ALLOWED_NEW_DIRS 강제, 2단(카테고리)은 사용자 자유 명명.
_USER_INPUT_SUBJECTS = ('형법', '형소', '부동산등기법', '부동산등기서류', '민사서류')
ALLOWED_NEW_DIRS = frozenset({
    f'{year}_사용자_{subj}'
    for year in ('2025', '2026')
    for subj in _USER_INPUT_SUBJECTS
})

# 한글 폴더명 → 영문 subject 키 매핑 (lawear-7ad6 v3 팀 7A 신규).
# _file_index entry.subject 필드용 — 사이드패널 / 뷰어 URL 슬러그로 사용.
_SUBJECT_TO_EN = {
    '형법': 'hyungbeop',
    '형소': 'hyungso',
    '부동산등기법': 'budeunglaw',
    '부동산등기서류': 'budeungseoryu',
    '민사서류': 'minsaseoryu',
}

# 2단 카테고리 폴더명 정규식 — 영문/한글/숫자/언더스코어/하이픈만 허용 (특수문자/traversal 차단).
_CATEGORY_RE = re.compile(r'^[가-힣A-Za-z0-9_\-]+$')

# auto NN 자리표시자 — input.html 이 NN 모르고 보낼 때 서버가 다음 번호 자동 할당.
_AUTO_NN_TOKEN = '__AUTO_NN__'

# .md 최소 필수 섹션 (design §3, design §4 mirror) — '## 메타' 누락 시 400
META_SECTION_RE = re.compile(r'^##\s*메타\s*$', re.MULTILINE)

# 메타 파싱 정규식 — `- 키: 값` 형식 (앞 공백 허용, 콜론 뒤 공백 1+).
# 키 후보: 과목 / 카테고리 / 제목 / 소제목 / 점수.
_META_LINE_RE = re.compile(r'^\s*-\s*([가-힣A-Za-z]+)\s*[:：]\s*(.+?)\s*$', re.MULTILINE)

# --- 로깅 -----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stderr,
)
log = logging.getLogger('lawear.server')


# ------------------------------------------------------------------------
# 메타 파싱 helper (lawear-7ad6 v3 팀 7A 신규)
# ------------------------------------------------------------------------
def _parse_md_meta(body: str) -> dict:
    """## 메타 섹션에서 `- 키: 값` 형식 파싱.

    Args:
      body: .md 전체 본문 (UTF-8 decode 후).

    Returns:
      {'subject': str|None, 'category': str|None, 'title': str|None,
       'case': str|None, 'points': int|None}.

    Notes:
      - '## 메타' 헤더 이후 다음 '## ' 헤더 직전까지를 메타 블록으로 간주.
      - 점수는 '20' 또는 '20점' 모두 허용 — 숫자만 추출하여 int 변환.
      - 누락된 키는 None 유지 (호출자가 기본값 채움).
    """
    out: dict = {'subject': None, 'category': None, 'file': None, 'title': None, 'case': None, 'points': None}
    # '## 메타' 위치 탐지 후 메타 블록 추출 (다음 '## ' 헤더까지).
    meta_hdr = META_SECTION_RE.search(body)
    if not meta_hdr:
        return out
    start = meta_hdr.end()
    # 다음 '## ' 헤더 위치 (없으면 EOF).
    next_hdr = re.search(r'^##\s+', body[start:], re.MULTILINE)
    block = body[start:start + next_hdr.start()] if next_hdr else body[start:]

    # `- 키: 값` 라인 모두 수집 후 key 별 매핑.
    key_map = {
        '과목': 'subject',
        '카테고리': 'category',
        '파일명': 'file',  # lawear-7ad6 v4 fix — file 메타 (NN 없는 사용자 입력) → L3 자동 그룹화
        '제목': 'title',
        '소제목': 'case',
        '점수': 'points',
    }
    for m in _META_LINE_RE.finditer(block):
        key_kor = m.group(1).strip()
        val = m.group(2).strip()
        slot = key_map.get(key_kor)
        if not slot:
            continue
        if slot == 'points':
            # '20점' 또는 '20' → int 추출. 숫자 없으면 None 유지.
            num = re.search(r'\d+', val)
            out['points'] = int(num.group(0)) if num else None
        else:
            out[slot] = val
    return out


def _resolve_auto_nn(rel_path: str) -> str:
    """rel_path 에 __AUTO_NN__ 토큰 있으면 폴더 스캔하여 다음 NN 할당.

    Args:
      rel_path: 예) `2026_사용자_부동산등기법/1순환/__AUTO_NN___등기의효력.md`.

    Returns:
      NN 자동 치환된 rel_path. 토큰 없으면 원본 반환.

    Notes:
      - 같은 폴더 안 .md 파일 중 앞자리 NN(2자리 숫자_) 패턴을 스캔하여 max+1.
      - 폴더 비어있으면 01 부터. 빈 폴더 자동 mkdir 호출자 책임.
    """
    if _AUTO_NN_TOKEN not in rel_path:
        return rel_path
    target = (ROOT / rel_path).resolve()
    parent = target.parent
    # 폴더 없으면 NN=01 (호출자가 mkdir 처리).
    if not parent.exists():
        next_nn = 1
    else:
        max_nn = 0
        for p in parent.iterdir():
            if not p.is_file() or p.suffix != '.md':
                continue
            m = re.match(r'^(\d{2})_', p.name)
            if m:
                max_nn = max(max_nn, int(m.group(1)))
        next_nn = max_nn + 1
    nn_str = f'{next_nn:02d}'
    log.info("auto NN 할당: %s → %s (폴더=%s)", _AUTO_NN_TOKEN, nn_str, parent.name)
    return rel_path.replace(_AUTO_NN_TOKEN, nn_str)


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

        # --- 0) auto NN 자리표시자 치환 (lawear-7ad6 v3 팀 7A) ----------------
        # 클라이언트가 NN 모르고 보낸 경우 (__AUTO_NN__ 토큰) 폴더 스캔하여 다음 번호 할당.
        # 치환은 path traversal 검증 전 실행 — 치환 후 rel_path 로 모든 후속 검증 수행.
        rel_path = _resolve_auto_nn(rel_path)

        # --- 1) traversal 차단 ------------------------------------------------
        # ROOT 밖으로 빠지는 ../../ 패턴 거부. resolve() 후 relative_to(ROOT)로 검증.
        target = (ROOT / rel_path).resolve()
        try:
            rel_to_root = target.relative_to(ROOT)
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

        # --- 2) 화이트리스트 검증 (1단/2단 폴더 모두 허용 — lawear-7ad6 v3) ----
        # 최상위 parent 가 ALLOWED_NEW_DIRS 에 있어야 함 (2025/2026 × 5과목 = 10폴더).
        # 2단(사용자 카테고리)은 자유 명명 — 단 _CATEGORY_RE 통과 강제 (특수문자 차단).
        # parts 예:
        #   1단: `2026_사용자_부동산등기법/2026_budeunglaw_user_01.md`
        #        → parts = ('2026_사용자_부동산등기법', '2026_budeunglaw_user_01.md')
        #        → top_dir='2026_사용자_부동산등기법', category=None
        #   2단: `2026_사용자_부동산등기법/1순환/01_등기의효력.md`
        #        → parts = ('2026_사용자_부동산등기법', '1순환', '01_등기의효력.md')
        #        → top_dir='2026_사용자_부동산등기법', category='1순환'
        # NOTE: HTTP 상태 라인은 latin-1 인코딩만 허용 → ASCII 메시지만 사용.
        parts = rel_to_root.parts
        if len(parts) < 2 or len(parts) > 3:
            # 0단(파일 직접) 또는 3단 이상(서브 카테고리) 모두 거부.
            log.warning("폴더 깊이 거부: parts=%r (1단/2단만 허용)", parts)
            self.send_error(403, "Invalid folder depth (1 or 2 levels only)")
            return
        top_dir = parts[0]
        category = parts[1] if len(parts) == 3 else None
        if top_dir not in ALLOWED_NEW_DIRS:
            log.warning(
                "화이트리스트 밖 폴더 거부: top=%r (allowed=%s)",
                top_dir, sorted(ALLOWED_NEW_DIRS),
            )
            self.send_error(403, "Folder not in whitelist")
            return
        # 2단 카테고리 명명 규칙 검증 — 특수문자 차단 (path traversal 추가 방어).
        if category is not None:
            if not _CATEGORY_RE.match(category):
                log.warning(
                    "잘못된 카테고리 이름 거부: category=%r (정규식 위반)",
                    category,
                )
                self.send_error(403, "Invalid category name (alnum/hangul/_/- only)")
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
        # lawear-7ad6 v3: 메타 파싱 결과를 entry 에 동적 매핑.
        rel_str = str(target.relative_to(ROOT))
        file_id = target.stem  # ex) 01_등기의효력 또는 2026_budeunglaw_user_01
        meta = _parse_md_meta(content)
        log.info("메타 파싱 결과: %r", meta)
        index_updated = False
        try:
            _append_index_entry(
                file_id=file_id,
                rel_path=rel_str,
                parent=top_dir,
                category=category,  # 2단 폴더명 (None 이면 '사용자' fallback)
                meta=meta,
            )
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
def _append_index_entry(
    file_id: str,
    rel_path: str,
    parent: str,
    category: str | None = None,
    meta: dict | None = None,
) -> None:
    """_file_index.json 에 type:"user_input" 신규 entry append.

    - flock(LOCK_EX) 으로 동시 POST 직렬화 (R3)
    - 임시파일 + os.replace 로 atomic rename
    - 작성 전 .bak 보존 (손상 시 복구 가능)
    - JSON validate 실패 시 .bak 복원 후 예외 전파

    Args:
      file_id: stem (예: 01_등기의효력 또는 2026_budeunglaw_user_01) — _file_index.json id 필드.
      rel_path: ROOT 기준 상대 경로
        (예: 2026_사용자_부동산등기법/1순환/01_등기의효력.md).
      parent: 최상위 폴더명 (예: 2026_사용자_부동산등기법) — subjectKor / year / subject_en 추출용.
      category: 2단 사용자 카테고리 (예: '1순환'). None 이면 '사용자' fallback (1단 폴더).
      meta: _parse_md_meta() 결과 dict — title/case/points/subject 동적 채움 (lawear-7ad6 v3).

    하위 호환: category/meta 둘 다 생략 시 v2 기본 동작 (기존 TC16~TC20 회귀 0).
    """
    meta = meta or {}
    # 부모 폴더명 → subjectKor 매핑 (ALLOWED_NEW_DIRS 와 1:1, lawear-7ad6 v2 — 5과목×2년 자동)
    parent_to_subj_kor = {
        f'{year}_사용자_{subj}': subj
        for year in ('2025', '2026')
        for subj in _USER_INPUT_SUBJECTS
    }
    subj_kor_from_parent = parent_to_subj_kor.get(parent, parent)
    # subject 영문 키 — _SUBJECT_TO_EN 매핑 우선 (lawear-7ad6 v3), 실패 시 file_id 첫 토큰 fallback.
    subject_en = _SUBJECT_TO_EN.get(subj_kor_from_parent)
    if not subject_en:
        # legacy fallback (file_id 예: 2026_budeunglaw_user_01)
        id_parts = file_id.split('_')
        subject_en = id_parts[1] if len(id_parts) >= 2 else 'unknown'
    # year 추출 — parent 폴더명 첫 4자리 우선 (예: 2026_사용자_X → 2026).
    year_m = re.match(r'^(\d{4})_', parent)
    year = year_m.group(1) if year_m else datetime.now().strftime('%Y')

    # 메타 우선, 누락 시 fallback (하위 호환).
    title = meta.get('title') or '사용자 직접 입력'
    case_val = meta.get('case')
    if case_val is None:
        # legacy: file_id 마지막 토큰 (예: 2026_budeunglaw_user_01 → 01)
        case_val = file_id.split('_')[-1] if '_' in file_id else file_id
    points = meta.get('points') if meta.get('points') is not None else 0
    subject_kor = meta.get('subject') or subj_kor_from_parent
    # category — 2단 폴더명 우선, 없으면 meta.category (사용자.md 기재), 없으면 '사용자'.
    category_val = category or meta.get('category') or '사용자'
    # file — 메타 '파일명' 우선 (사용자 입력 그대로, NN prefix 없음 → L3 자동 그룹화).
    #   누락 시 stem에서 ^\d+_ 자동 제거 (예: '01_모고1회' → '모고1회'). 이게 사용자 명시:
    #   "01/02 넘버링 하지말고 동일폴더로 인지" (lawear-7ad6 v4 사이드패널 그룹 fix).
    # 1단 legacy (category 없음) 는 'user' 유지.
    if category:
        file_val = meta.get('파일명') or meta.get('file') or re.sub(r'^\d+_', '', file_id)
    else:
        file_val = 'user'
    file_kor = f"{year}_{subject_kor}_{category_val}_{file_val}"

    new_entry = {
        "id": file_id,
        "subject": subject_en,
        "subjectKor": subject_kor,
        "category": category_val,
        "file": file_val,
        "fileKor": file_kor,
        "case": case_val,
        "title": title,
        "path": rel_path,
        "pdfPath": None,
        "points": points,
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

            # lawear-7ad6 v4 — 주제목(title)에 NN_ 자동 prefix (같은 file 그룹 내 순번)
            #   사용자 명시: 파일명은 그룹화용 (NN 없음), 주제목은 case 식별용 (NN 있음)
            #   같은 (year, subjectKor, category, file) 그룹 안 entry 개수 + 1 → NN
            #   사용자 입력 title에 ^\d+_ prefix 있으면 자동 제거 후 NN 부여 (이중 NN 방지)
            if new_entry.get('type') == 'user_input' and new_entry.get('category') != '사용자':
                existing_nns = []
                for e in files:
                    if (e.get('type') == 'user_input'
                        and e.get('_year') == new_entry.get('_year')
                        and e.get('subjectKor') == new_entry.get('subjectKor')
                        and e.get('category') == new_entry.get('category')
                        and e.get('file') == new_entry.get('file')):
                        m = re.match(r'^(\d+)_', e.get('title', ''))
                        if m:
                            existing_nns.append(int(m.group(1)))
                next_nn = max(existing_nns, default=0) + 1
                clean_title = re.sub(r'^\d+_', '', new_entry.get('title', '')).strip()
                new_entry['title'] = f"{next_nn:02d}_{clean_title}"
                log.info(
                    "title NN 자동 부여 — file=%s NN=%02d title='%s'",
                    new_entry.get('file'), next_nn, new_entry['title'],
                )

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
