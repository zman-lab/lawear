#!/usr/bin/env python3
"""작업 A pytest — POST /api/create + _append_index_entry 회귀 TC1~TC20.

테스트 목적:
  server.py 의 do_POST /api/create 엔드포인트와 _append_index_entry 헬퍼가
  설계 §3 8단계 검증 + 동시성/원자성/.bak 복원 룰을 정확히 지키는지 검증.

근거:
  - 구현 계획: docs/lawear-7ad6_input_mode_3subjects/dev-spec_3_impl_plan.md §2 (TC1~TC20)
  - 설계 문서: docs/lawear-7ad6_input_mode_3subjects/dev-spec_2_design.md §3, §5
  - 대상 코드: docs/tts-new/server.py (433줄)

작성자: lawear-7ad6 (팀 4, Opus + ultrathink)

실행:
  cd /Users/nhn/zman-lab/lawear-lawear-7ad6-input-mode-and-backup/docs/tts-new
  python3 -m pytest tests/test_input_mode_api.py -v

룰:
  - 한 TC당 가능하면 1 assert (디버깅 용이)
  - 가짜 데이터는 실제 흐름과 동일 (UTF-8, '## 메타' 섹션 포함)
  - 자의 해석 금지 — impl_plan.md TC 목록 정확 mirror
"""
from __future__ import annotations

import io
import json
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# server.py 가 있는 디렉토리를 import path 에 추가
_TTS_NEW_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TTS_NEW_DIR))


# ============================================================================
# 공통 fixture
# ============================================================================

# 표준 가짜 .md body — '## 메타' 섹션 포함 (METAREGEX 통과 보장)
SAMPLE_MD = """# 사용자 입력 샘플

## 메타
- 과목: 부동산등기법
- 출처: 사용자 직접 입력

## 문제
가나다라마바사
"""


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    """server.py 의 ROOT/INDEX_PATH 를 tmp_path 로 swap.

    실제 메인 레포 _file_index.json 174KB 을 건드리지 않도록 격리.
    각 TC 종료 시 tmp_path 가 자동 삭제됨 (pytest 보장).
    """
    import server  # type: ignore

    # 원본 보존 후 monkeypatch (yield 종료 시 자동 복원)
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    monkeypatch.setattr(server, 'INDEX_PATH', tmp_path / '_file_index.json')
    monkeypatch.setattr(server, 'STAGING_DIR', tmp_path / '_staging')

    # 화이트리스트 폴더 3개 사전 생성 (parent.mkdir 검증과 별개)
    for d in ('2026_사용자_부동산등기법', '2026_사용자_부동산등기서류', '2026_사용자_민사서류'):
        (tmp_path / d).mkdir(exist_ok=True)

    # 빈 _file_index.json 초기화 (실서비스 항상 존재 가정)
    (tmp_path / '_file_index.json').write_text(
        json.dumps({"files": []}, ensure_ascii=False), encoding='utf-8'
    )
    return tmp_path


def _make_handler(method: str, path: str, body: bytes):
    """가짜 Handler 인스턴스 생성 — wfile/rfile/headers 모킹.

    do_POST/do_PUT 직접 호출용. 실제 socket 연결 없이 단위 테스트.
    """
    import server  # type: ignore

    handler = server.Handler.__new__(server.Handler)  # __init__ 우회
    handler.path = path
    handler.command = method
    handler.client_address = ('127.0.0.1', 12345)
    handler.request_version = 'HTTP/1.1'
    handler.headers = {'Content-Length': str(len(body)), 'Content-Type': 'text/plain; charset=utf-8'}
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    # send_error / send_response / end_headers / send_header 추적용
    handler._response_code = None  # type: ignore[attr-defined]
    handler._error_code = None  # type: ignore[attr-defined]

    def fake_send_response(code, message=None):
        handler._response_code = code  # type: ignore[attr-defined]

    def fake_send_error(code, message=None, explain=None):
        handler._error_code = code  # type: ignore[attr-defined]

    def fake_send_header(*a, **kw):
        pass

    def fake_end_headers():
        pass

    handler.send_response = fake_send_response  # type: ignore[assignment]
    handler.send_error = fake_send_error  # type: ignore[assignment]
    handler.send_header = fake_send_header  # type: ignore[assignment]
    handler.end_headers = fake_end_headers  # type: ignore[assignment]
    handler.log_message = lambda *a, **kw: None  # type: ignore[assignment]
    return handler


# ============================================================================
# 정상 (TC1~TC4)
# ============================================================================

def test_tc1_budeunglaw_create_200(tmp_root):
    """TC1: 부등법 .md POST → 200 + 파일 생성 + bytes 정확.

    설계 §3 정상 흐름 (1~8 단계 모두 통과).
    """
    body = SAMPLE_MD.encode('utf-8')
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_01.md',
        body,
    )
    handler.do_POST()
    target = tmp_root / '2026_사용자_부동산등기법' / '2026_budeunglaw_user_01.md'
    # 의도: 파일이 실제로 생성되었는지 (8단계 중 7번 write_text)
    assert target.exists(), "TC1: 부등법 .md 파일이 생성되지 않음"


def test_tc2_budeungseo_create_200(tmp_root):
    """TC2: 부등서류 .md POST → 200.

    화이트리스트 3과목 중 2번째 (부동산등기서류) 검증.
    """
    body = SAMPLE_MD.encode('utf-8')
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_부동산등기서류/2026_budeungseo_user_01.md',
        body,
    )
    handler.do_POST()
    # 의도: send_error 가 호출되지 않아야 (정상 200)
    assert handler._error_code is None, f"TC2: 부등서류 거부됨 (code={handler._error_code})"


def test_tc3_minsaseo_create_200(tmp_root):
    """TC3: 민사서류 .md POST → 200.

    화이트리스트 3과목 중 3번째 (민사서류) 검증.
    """
    body = SAMPLE_MD.encode('utf-8')
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_민사서류/2026_minsaseo_user_01.md',
        body,
    )
    handler.do_POST()
    # 의도: 응답 코드 200 (send_response 호출)
    assert handler._response_code == 200, f"TC3: 민사서류 거부됨 (code={handler._response_code}, err={handler._error_code})"


def test_tc4_parent_dir_auto_mkdir(tmp_root):
    """TC4: parent 폴더 사전 삭제 → POST → 자동 mkdir (8단계 4번).

    fixture 가 사전 생성한 폴더 강제 삭제 후 POST → mkdir(parents=True) 동작 검증.
    """
    import shutil
    parent = tmp_root / '2026_사용자_부동산등기법'
    if parent.exists():
        shutil.rmtree(parent)  # 사전 삭제 (mkdir 자동 생성 검증)

    body = SAMPLE_MD.encode('utf-8')
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_99.md',
        body,
    )
    handler.do_POST()
    # 의도: parent 폴더가 자동 mkdir 되어야 함
    assert parent.exists() and parent.is_dir(), "TC4: parent 폴더 자동 생성 실패"


# ============================================================================
# 음성 R2 (TC5~TC10) — 거부 케이스
# ============================================================================

def test_tc5_path_traversal_403(tmp_root):
    """TC5: ../../etc/passwd traversal → 403.

    8단계 1번 (relative_to(ROOT) ValueError) 차단 검증.
    """
    body = b"x"
    handler = _make_handler('POST', '/api/create/../../etc/passwd', body)
    handler.do_POST()
    # 의도: traversal 차단 — 403
    assert handler._error_code == 403, f"TC5: traversal 미차단 (code={handler._error_code})"


def test_tc6_whitelist_outside_403(tmp_root):
    """TC6: 화이트리스트 밖 폴더 → 403.

    8단계 2번 (ALLOWED_NEW_DIRS 검사) 차단 검증.
    """
    body = SAMPLE_MD.encode('utf-8')
    handler = _make_handler(
        'POST', '/api/create/random_dir/x.md', body
    )
    handler.do_POST()
    # 의도: 화이트리스트 외 폴더 거부
    assert handler._error_code == 403, f"TC6: 화이트리스트 외 미차단 (code={handler._error_code})"


def test_tc7_non_md_extension_403(tmp_root):
    """TC7: 비-.md 확장자 (.txt) → 403.

    8단계 3번 (suffix != '.md') 차단 검증.
    """
    body = b"x"
    handler = _make_handler(
        'POST', '/api/create/2026_사용자_부동산등기법/x.txt', body
    )
    handler.do_POST()
    # 의도: .md 외 확장자 거부
    assert handler._error_code == 403, f"TC7: 비-.md 미차단 (code={handler._error_code})"


def test_tc8_conflict_409_on_second(tmp_root):
    """TC8: 같은 파일 2회 POST → 1차 200, 2차 409.

    8단계 5번 (target.exists() 시 409 overwrite 거부) 검증.
    """
    body = SAMPLE_MD.encode('utf-8')
    path = '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_02.md'

    # 1차 POST
    h1 = _make_handler('POST', path, body)
    h1.do_POST()
    # 2차 POST — 동일 path
    h2 = _make_handler('POST', path, body)
    h2.do_POST()
    # 의도: 두 번째는 409 (conflict)
    assert h2._error_code == 409, f"TC8: 2차 POST 409 실패 (code={h2._error_code})"


def test_tc9_missing_meta_section_400(tmp_root):
    """TC9: '## 메타' 섹션 누락 → 400.

    8단계 6번 (META_SECTION_RE.search 실패) 차단 검증.
    """
    # 의도적으로 '## 메타' 섹션 없는 body
    body = "# 제목만 있고 메타 섹션 없음\n\n내용...".encode('utf-8')
    handler = _make_handler(
        'POST', '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_03.md', body
    )
    handler.do_POST()
    # 의도: '## 메타' 누락 → 400
    assert handler._error_code == 400, f"TC9: 메타 누락 미차단 (code={handler._error_code})"


def test_tc10_empty_body_400(tmp_root):
    """TC10: Content-Length: 0 빈 body → 400.

    8단계 6번 (content_length == 0) 차단 검증.
    """
    handler = _make_handler(
        'POST', '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_04.md', b''
    )
    handler.do_POST()
    # 의도: 빈 body → 400
    assert handler._error_code == 400, f"TC10: 빈 body 미차단 (code={handler._error_code})"


# ============================================================================
# 엣지 (TC11~TC15)
# ============================================================================

def test_tc11_korean_filename_url_encoding(tmp_root):
    """TC11: 한글 폴더/파일명 URL 인코딩 정상 처리.

    urllib.parse.unquote 가 한글 path 를 정확히 decode 해야 함.
    """
    from urllib.parse import quote
    body = SAMPLE_MD.encode('utf-8')
    # 한글 파일명을 URL encode → 핸들러 내부에서 unquote 로 복원
    encoded_path = '/api/create/' + quote('2026_사용자_부동산등기법/2026_한글_파일_11.md')
    handler = _make_handler('POST', encoded_path, body)
    handler.do_POST()
    target = tmp_root / '2026_사용자_부동산등기법' / '2026_한글_파일_11.md'
    # 의도: URL encoding 된 한글 파일명이 정상 decode 되어 파일 생성
    assert target.exists(), "TC11: 한글 파일명 URL decode 실패"


def test_tc12_large_body_100kb(tmp_root):
    """TC12: 100KB+ body → bytes 정확 (응답 bytes 필드 = 입력 길이).

    HTTP large body 처리 검증.
    """
    # 100KB+ body — '## 메타' 섹션 포함
    big_content = "## 메타\n- 출처: 대용량 테스트\n\n## 본문\n" + ("가" * 50000)
    body = big_content.encode('utf-8')
    assert len(body) >= 100_000, "TC12 사전: 100KB+ body 준비 실패"

    handler = _make_handler(
        'POST', '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_12.md', body
    )
    handler.do_POST()
    target = tmp_root / '2026_사용자_부동산등기법' / '2026_budeunglaw_user_12.md'
    # 의도: 파일 크기가 입력 body 와 정확히 일치 (truncation X)
    assert target.exists() and target.stat().st_size == len(body), \
        f"TC12: bytes mismatch (expected={len(body)}, actual={target.stat().st_size if target.exists() else 'no-file'})"


def test_tc13_special_chars_raw_preserved(tmp_root):
    """TC13: 특수문자 (<>&"' + 한자 + 이모지) raw 보존.

    HTML escape 없이 .md 원문 그대로 저장되어야 함 (사용자 입력 무결성).
    """
    special_body = '## 메타\n- 출처: 특수문자 테스트\n\n## 본문\n<tag>&"\'</tag> 漢字 民事 🎯📚⚖️\n'
    body = special_body.encode('utf-8')
    handler = _make_handler(
        'POST', '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_13.md', body
    )
    handler.do_POST()
    target = tmp_root / '2026_사용자_부동산등기법' / '2026_budeunglaw_user_13.md'
    saved_content = target.read_text(encoding='utf-8')
    # 의도: 특수문자 raw 보존 (HTML escape X)
    assert saved_content == special_body, "TC13: 특수문자 raw 보존 실패 (HTML escape 됨?)"


def test_tc14_concurrent_post_flock_atomic(tmp_root):
    """TC14: 동시 POST 2건 (threading) → flock+atomic, 2 entry append + JSON valid.

    R3 동시성: 두 스레드가 동시에 POST 해도 _file_index.json 손상 X.
    """
    body = SAMPLE_MD.encode('utf-8')
    results = []

    def post_one(file_num):
        # 각 스레드 자체 handler — POST 호출
        h = _make_handler(
            'POST',
            f'/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_14{file_num}.md',
            body,
        )
        h.do_POST()
        results.append(h._error_code)

    t1 = threading.Thread(target=post_one, args=('a',))
    t2 = threading.Thread(target=post_one, args=('b',))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # 의도: 동시 POST 후 _file_index.json 가 유효한 JSON 이고 entry 2개 append
    index_data = json.loads((tmp_root / '_file_index.json').read_text(encoding='utf-8'))
    assert len(index_data['files']) == 2, \
        f"TC14: 동시 POST entry 2개 보장 실패 (entries={len(index_data['files'])}, errors={results})"


def test_tc15_corrupted_index_bak_restore(tmp_root):
    """TC15: _file_index.json 손상 주입 → .bak 복원 후 신규 append.

    R3 복원 로직: 깨진 JSON 만나면 .bak 으로 fallback.
    """
    # .bak 에 유효한 JSON 저장 + 본 파일은 손상
    valid = json.dumps({"files": [{"id": "existing", "type": "user_input"}]}, ensure_ascii=False)
    (tmp_root / '_file_index.json.bak').write_text(valid, encoding='utf-8')
    (tmp_root / '_file_index.json').write_text("{ this is broken json", encoding='utf-8')

    body = SAMPLE_MD.encode('utf-8')
    handler = _make_handler(
        'POST', '/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_15.md', body
    )
    handler.do_POST()

    # 의도: .bak 복원 후 신규 entry append → 총 2개 (existing + 신규)
    index_data = json.loads((tmp_root / '_file_index.json').read_text(encoding='utf-8'))
    assert len(index_data['files']) == 2, \
        f"TC15: .bak 복원 후 append 실패 (entries={len(index_data['files'])})"


# ============================================================================
# 인덱스 (TC16~TC20)
# ============================================================================

def test_tc16_append_index_entry_total_plus_one(tmp_root):
    """TC16: _append_index_entry 정상 append, total +1.

    헬퍼 직접 호출 (POST 우회) — entry append 단독 검증.
    """
    import server  # type: ignore

    # 사전 — files 길이
    before = len(json.loads((tmp_root / '_file_index.json').read_text())['files'])
    server._append_index_entry(
        file_id='2026_budeunglaw_user_16',
        rel_path='2026_사용자_부동산등기법/2026_budeunglaw_user_16.md',
        parent='2026_사용자_부동산등기법',
    )
    after = len(json.loads((tmp_root / '_file_index.json').read_text())['files'])
    # 의도: append 후 total +1
    assert after == before + 1, f"TC16: total +1 실패 (before={before}, after={after})"


def test_tc17_duplicate_id_preserves_existing(tmp_root):
    """TC17: 중복 id 갱신 X, 기존 보존.

    동일 id 두 번 호출 → 두 번째는 skip (총 entry 1개).
    """
    import server  # type: ignore

    server._append_index_entry(
        file_id='2026_budeunglaw_user_17',
        rel_path='path1.md',
        parent='2026_사용자_부동산등기법',
    )
    server._append_index_entry(
        file_id='2026_budeunglaw_user_17',  # 동일 id
        rel_path='path2.md',  # 다른 path
        parent='2026_사용자_부동산등기법',
    )
    files = json.loads((tmp_root / '_file_index.json').read_text())['files']
    # 의도: 중복 id 1개만 보존 (첫 번째 path1.md 유지)
    matching = [f for f in files if f.get('id') == '2026_budeunglaw_user_17']
    assert len(matching) == 1 and matching[0]['path'] == 'path1.md', \
        f"TC17: 중복 id 보존 실패 (matching={len(matching)}, path={matching[0]['path'] if matching else None})"


def test_tc18_bak_created_and_atomic_rename(tmp_root):
    """TC18: .bak 생성 + atomic rename 검증.

    append 호출 후 .bak 파일이 존재해야 함 (이전 상태 보존).
    """
    import server  # type: ignore

    server._append_index_entry(
        file_id='2026_budeunglaw_user_18',
        rel_path='2026_사용자_부동산등기법/2026_budeunglaw_user_18.md',
        parent='2026_사용자_부동산등기법',
    )
    bak = tmp_root / '_file_index.json.bak'
    # 의도: .bak 파일 생성 확인 (atomic rename 전 백업 보존 룰)
    assert bak.exists(), "TC18: .bak 백업 파일 생성 실패"


def test_tc19_json_validate_fail_restore_500(tmp_root):
    """TC19: 인덱스 파일 자체가 깨져있고 .bak 도 없으면 예외 전파.

    server._append_index_entry 가 raise JSONDecodeError → 호출자(do_POST)는
    예외를 catch 하여 index_updated:false 로 응답 (파일은 작성됨).
    """
    import server  # type: ignore

    # 인덱스 깨짐 + .bak 부재
    (tmp_root / '_file_index.json').write_text("not json at all", encoding='utf-8')
    bak = tmp_root / '_file_index.json.bak'
    if bak.exists():
        bak.unlink()

    # 의도: .bak 없을 때 JSONDecodeError 전파
    with pytest.raises(json.JSONDecodeError):
        server._append_index_entry(
            file_id='2026_budeunglaw_user_19',
            rel_path='x.md',
            parent='2026_사용자_부동산등기법',
        )


def test_tc20_index_fields_schema(tmp_root):
    """TC20: 인덱스 entry fields 일치 (id/subject/category/path/type:'user_input').

    design §5 sidebar 분기 기준 필드 모두 포함되어야 함.
    """
    import server  # type: ignore

    server._append_index_entry(
        file_id='2026_budeunglaw_user_20',
        rel_path='2026_사용자_부동산등기법/2026_budeunglaw_user_20.md',
        parent='2026_사용자_부동산등기법',
    )
    files = json.loads((tmp_root / '_file_index.json').read_text())['files']
    entry = files[-1]
    # 의도: 필수 5개 fields 모두 존재 + type='user_input' 정확 (sidebar 분기 키)
    expected = {
        'id': '2026_budeunglaw_user_20',
        'subject': 'budeunglaw',
        'category': '사용자',
        'path': '2026_사용자_부동산등기법/2026_budeunglaw_user_20.md',
        'type': 'user_input',
    }
    actual = {k: entry.get(k) for k in expected}
    assert actual == expected, f"TC20: schema mismatch\nexpected={expected}\nactual={actual}"


# ============================================================================
# lawear-7ad6 v3 팀 7A — 2단 폴더 + 메타 파싱 + auto NN (TC21~24)
# ============================================================================

# 2단 폴더 + 메타 풀세트 샘플 — _parse_md_meta 5필드 모두 채움.
SAMPLE_MD_FULL_META = """# 등기의효력

## 메타
- 과목: 부동산등기법
- 카테고리: 1순환
- 제목: 등기의효력
- 소제목: 약술하시오
- 점수: 20점
- 출처: 사용자 직접 입력

## 문제
등기의 효력을 약술하시오.

## 답안
가나다라마바사
"""


def test_tc21_two_level_folder_create_200(tmp_root):
    """TC21: 2단 폴더 `2026_사용자_부동산등기법/1순환/01_등기의효력.md` POST → 200.

    lawear-7ad6 v3 팀 7A: 사용자 자유 카테고리 (1순환 등) 2단 폴더 허용.
    """
    body = SAMPLE_MD_FULL_META.encode('utf-8')
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_부동산등기법/1순환/01_등기의효력.md',
        body,
    )
    handler.do_POST()
    target = tmp_root / '2026_사용자_부동산등기법' / '1순환' / '01_등기의효력.md'
    # 의도: 2단 폴더 정상 생성 + 파일 작성
    assert target.exists(), \
        f"TC21: 2단 폴더 파일 생성 실패 (err={handler._error_code}, code={handler._response_code})"


def test_tc22_category_path_traversal_403(tmp_root):
    """TC22: 2단 카테고리에 path traversal (..) 또는 특수문자 → 403.

    _CATEGORY_RE 정규식 위반 — `..` 는 ROOT relative_to 단계에서 차단되지만,
    `1순환$` 같은 정상 traversal 아닌 특수문자도 _CATEGORY_RE 에서 차단되어야 함.
    """
    body = SAMPLE_MD_FULL_META.encode('utf-8')
    # 특수문자 `$` 포함 카테고리 — _CATEGORY_RE 위반
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_부동산등기법/1순환$/01_등기의효력.md',
        body,
    )
    handler.do_POST()
    # 의도: 특수문자 카테고리 거부 → 403
    assert handler._error_code == 403, \
        f"TC22: 특수문자 카테고리 미차단 (code={handler._error_code})"


def test_tc23_auto_nn_assigns_next_number(tmp_root):
    """TC23: __AUTO_NN__ 자리표시자 → 폴더 스캔 후 다음 NN 자동 할당 → 200.

    1순환 폴더에 01, 02 사전 생성 → __AUTO_NN___등기의효력.md POST → 03_등기의효력.md.
    """
    # 사전: 1순환 폴더에 01, 02 .md 생성 (auto NN 스캔 대상)
    cat = tmp_root / '2026_사용자_부동산등기법' / '1순환'
    cat.mkdir(parents=True, exist_ok=True)
    (cat / '01_기존1.md').write_text(SAMPLE_MD_FULL_META, encoding='utf-8')
    (cat / '02_기존2.md').write_text(SAMPLE_MD_FULL_META, encoding='utf-8')

    body = SAMPLE_MD_FULL_META.encode('utf-8')
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_부동산등기법/1순환/__AUTO_NN___등기의효력.md',
        body,
    )
    handler.do_POST()
    # 의도: 03_등기의효력.md 자동 생성 (01, 02 다음 번호)
    expected = cat / '03_등기의효력.md'
    assert expected.exists(), \
        f"TC23: auto NN 할당 실패 (err={handler._error_code}, dir={list(cat.iterdir())})"


def test_tc24_meta_parsing_to_index_entry(tmp_root):
    """TC24: .md 메타 파싱 결과가 _file_index entry 에 정확히 반영.

    SAMPLE_MD_FULL_META 의 카테고리/제목/소제목/점수가 entry 필드에 매핑되어야 함.
    """
    body = SAMPLE_MD_FULL_META.encode('utf-8')
    handler = _make_handler(
        'POST',
        '/api/create/2026_사용자_부동산등기법/1순환/01_등기의효력.md',
        body,
    )
    handler.do_POST()
    files = json.loads((tmp_root / '_file_index.json').read_text())['files']
    entry = files[-1]
    # 의도: 메타 5필드 (category/title/case/points + subject_en 매핑) 모두 entry 반영
    expected = {
        'category': '1순환',
        'title': '등기의효력',
        'case': '약술하시오',
        'points': 20,
        'subject': 'budeunglaw',
        'subjectKor': '부동산등기법',
        'file': '01_등기의효력',
        'type': 'user_input',
    }
    actual = {k: entry.get(k) for k in expected}
    assert actual == expected, f"TC24: 메타 매핑 실패\nexpected={expected}\nactual={actual}"
