#!/usr/bin/env python3
"""Step 24-5 — server.py endpoint 다중 설문 D안 확장 단위 테스트.

dev-impl-plan Step 24-5 — HTTP API contract (POST/PUT/GET subq schema + GET cases subqs).

검증 범위 (10+ TC):
1. POST /api/attempts — answer_subq 다중 카드 (200 + attempt_id + 메타)
2. POST /api/attempts — legacy answer_text 호환 (200)
3. POST /api/attempts — 둘 다 비어있음 → 400 subq_empty
4. POST /api/attempts — case_id 없음 → 400 bad_request
5. POST /api/attempts — case_id 미존재 → 404 case_not_found
6. POST /api/attempts — JSON 디코딩 에러 → 400
7. POST /api/attempts — answer_subq 가 dict 아님 → 400 bad_request
8. PUT /api/attempts/{id}/grade — criteria_subq dict (200 + attempt_criteria.subq_key)
9. PUT /api/attempts/{id}/grade — legacy criteria (200, subq_key=NULL)
10. PUT /api/attempts/{id}/grade — 둘 다 없음 → 400 criteria_subq_required
11. PUT /api/attempts/{id}/grade — 잘못된 attempt_id → 404
12. GET /api/attempts — list item 에 hints_used_count + subq_count + total_solve_sec
13. GET /api/attempts/{id} — 다중 카드 채점 후 criteria_subq dict 노출 + 한글 보존
14. GET /api/attempts/{id} — legacy 채점 후 criteria_subq 키 없음
15. GET /api/cases/{id} — subqs + toc + mnemonic 응답 키 + 한글 보존
16. GET /api/cases/{id} — 단일 설문 fallback → subqs=[]
17. GET /api/cases/{id} — case_id 미존재 → 404
18. Method not allowed — DELETE /api/cases/... → 501 not_implemented
19. 한글 키 ensure_ascii=False 보존 (응답 JSON 디코드 확인)

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step24_server.py -v

엔드 투 엔드 HTTP 테스트 — `ThreadingHTTPServer` 를 임시 포트에서 띄움.
DB / .md 베이스를 임시 디렉토리로 격리 (테스트마다 setUp 에서 신규 생성).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

# tests/ → 부모 docs/tts-exam 를 sys.path 에 등록
_THIS_DIR = Path(__file__).parent.resolve()
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

# 테스트 격리 — server.py / cases.py 가 import 시점에 BASE_PATH / DB_PATH 를 굳히기
# 전에 env 세팅. 임시 디렉토리에 더미 .md 1건 + (필요 시) 실 .md 1건 복사.
_TEST_BASE = tempfile.mkdtemp(prefix="lawear_step24_5_base_")
os.environ["LAWEAR_TTS_BASE"] = _TEST_BASE
# DB 도 임시 — 테스트 끼리 동일 DB 공유 (각 테스트 setUp 에서 ROLLBACK 대신 fresh 시드).
_TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TEST_DB.close()
os.environ["LAWEAR_EXAM_DB"] = _TEST_DB.name
# 포트 충돌 회피 — 0 (커널이 자동 할당)
os.environ["LAWEAR_EXAM_PORT"] = "0"
os.environ["LAWEAR_EXAM_BIND"] = "127.0.0.1"

# 더미 .md (legacy 단일 설문)
_DUMMY_DIR = Path(_TEST_BASE) / "_test"
_DUMMY_DIR.mkdir(parents=True, exist_ok=True)
_DUMMY_MD = _DUMMY_DIR / "dummy.md"
_DUMMY_MD.write_text(
    "## 원본 (17점)\n\n### 사실관계\n테스트.\n\n### 답안\n테스트 답안.\n",
    encoding="utf-8",
)
# 다중 설문 더미 .md (패턴 A: ### 설문 N (N점))
_MULTI_MD = _DUMMY_DIR / "multi.md"
_MULTI_MD.write_text(
    "## 원본 (35점)\n\n"
    "### 사실관계\n공통 사실관계 본문.\n\n"
    "### 설문 1 (20점)\n첫 번째 설문 본문.\n\n"
    "### 설문 1 답안\n첫 번째 답안 [blank2]보[/blank2]증, [blank2]필[/blank2]수.\n\n"
    "### 설문 2 (15점)\n두 번째 설문 본문.\n\n"
    "### 설문 2 답안\n두 번째 답안 [blank2]도[/blank2]달주의.\n\n"
    "## Lv.1 빠른복습\n\n"
    "### 목차\n"
    "설문 1 — 시효소멸\n"
    "설문 2 — 채권자대위\n\n"
    "## Lv.4 암기노트\n\n"
    "1. 첫 번째 두문자\n"
    "2. 두 번째 두문자\n"
    "3. 세 번째 두문자\n",
    encoding="utf-8",
)

import attempts as attempts_mod  # noqa: E402
import cases as cases_mod  # noqa: E402
import db as db_mod  # noqa: E402
import grader as grader_mod  # noqa: E402
import server as server_mod  # noqa: E402

# import 이전 BASE_PATH 캐싱 안전화
if str(cases_mod.BASE_PATH) != _TEST_BASE:
    cases_mod.BASE_PATH = Path(_TEST_BASE).resolve()
server_mod.DB_PATH = _TEST_DB.name


# ─── 픽스처 ──────────────────────────────────────────────────────────


def _init_db(db_path: str) -> None:
    """v6 마이그까지 적용된 깨끗한 DB + 케이스 2건 시드 (legacy + multi)."""
    # 기존 파일 비우기
    try:
        os.unlink(db_path)
    except OSError:
        pass
    db_mod.init_db(db_path)
    with db_mod.get_conn(db_path) as conn:
        # legacy 단일 설문 케이스
        conn.execute(
            """
            INSERT OR REPLACE INTO cases
              (id, subject, subject_kor, category, file, case_no, title, path,
               points, synced_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TC_S24_5_LEGACY",
                "minbeop", "민법", "입문", "미케01", "01",
                "Step 24-5 legacy 단일 설문",
                "_test/dummy.md",
                17, "2026-05-18T00:00:00Z", "deadbeef",
            ),
        )
        # 다중 설문 케이스
        conn.execute(
            """
            INSERT OR REPLACE INTO cases
              (id, subject, subject_kor, category, file, case_no, title, path,
               points, synced_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TC_S24_5_MULTI",
                "minbeop", "민법", "예비", "모고01", "01",
                "Step 24-5 다중 설문",
                "_test/multi.md",
                35, "2026-05-18T00:00:00Z", "cafebabe",
            ),
        )
        conn.commit()


def _full_criteria_9() -> list[dict]:
    """9기준 채점 입력 (DEFAULT_WEIGHTS 합=100)."""
    return [
        {"key": "mnem",       "score": 12, "weight_applied": 16, "comment": "두문자 OK"},
        {"key": "color",      "score": 11, "weight_applied": 13, "comment": "색강조"},
        {"key": "under",      "score": 6,  "weight_applied": 8,  "comment": "밑줄"},
        {"key": "outline",    "score": 8,  "weight_applied": 10, "comment": "목차"},
        {"key": "sem",        "score": 10, "weight_applied": 12, "comment": "의미"},
        {"key": "rich",       "score": 12, "weight_applied": 15, "comment": "풍부함"},
        {"key": "miss",       "score": -1, "weight_applied": 11, "comment": "누락"},
        {"key": "articles",   "score": 6,  "weight_applied": 10, "comment": "조문"},
        {"key": "case_apply", "score": 1,  "weight_applied": 5,  "comment": "사안 적용"},
    ]


def _full_eval_notes() -> dict:
    return {"strength": "강점", "caution": "주의", "missing": "누락"}


def _full_grade_legacy() -> dict:
    return {
        "criteria": _full_criteria_9(),
        "total_score": 65.0,
        "max_score": 100.0,
        "score_pct": 65.0,
        "grade": "C",
        "eval_notes": _full_eval_notes(),
    }


def _full_grade_subq() -> dict:
    return {
        "criteria_subq": {
            "설문 1": _full_criteria_9(),
            "설문 2": _full_criteria_9(),
        },
        "total_score": 130.0,
        "max_score": 200.0,
        "score_pct": 65.0,
        "grade": "C",
        "eval_notes": _full_eval_notes(),
        "eval_notes_subq": {
            "설문 1": "강점 1",
            "설문 2": "주의 2",
        },
    }


# ─── HTTP 클라이언트 헬퍼 ─────────────────────────────────────────────


def _request(
    method: str,
    server: ThreadingHTTPServer,
    path: str,
    body: dict | None = None,
) -> tuple[int, dict]:
    """ThreadingHTTPServer 에 요청 송신. 응답 (status, json_dict) 반환.

    Args:
        method: 'GET'/'POST'/'PUT'/'DELETE'.
        server: ThreadingHTTPServer 인스턴스 (server_address 사용).
        path:   '/api/...' 절대 path.
        body:   JSON 직렬화할 dict (POST/PUT 용). None 이면 본문 없음.

    Returns:
        (status_code, parsed_json_or_empty_dict)
    """
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}{path}"
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        headers["Content-Length"] = str(len(data))
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, {"raw": raw.decode("utf-8", errors="replace")}


def _request_raw(
    method: str,
    server: ThreadingHTTPServer,
    path: str,
    raw_body: bytes,
    *,
    content_type: str = "application/json; charset=utf-8",
) -> tuple[int, dict]:
    """raw body 송신 — JSON 디코딩 에러 케이스 테스트용."""
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}{path}"
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(raw_body)),
    }
    req = urllib.request.Request(url, data=raw_body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, {"raw": raw.decode("utf-8", errors="replace")}


# ─── 서버 라이프사이클 베이스 클래스 ──────────────────────────────────


class ServerTestBase(unittest.TestCase):
    """모든 테스트 공통 — 클래스당 한 번 서버 띄우고, 각 테스트마다 DB 재시드.

    설계 결정:
    - 서버 (port=0) 는 클래스당 1회 (setUpClass) — 부팅 비용 분산
    - DB 는 각 테스트 setUp 에서 init_db (멱등) + 시드 재실행 — 격리
    - 모든 핸들러가 `db_mod.get_conn(DB_PATH)` 으로 conn 을 새로 얻으므로 멀티스레드 OK
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_mod.ExamHandler)
        cls.httpd.allow_reuse_address = True
        cls.server_thread = threading.Thread(
            target=cls.httpd.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.httpd.shutdown()
        except Exception:
            pass
        try:
            cls.httpd.server_close()
        except Exception:
            pass

    def setUp(self) -> None:
        # ANTHROPIC_API_KEY 미설정 강제 — auto 모드면 자동 manual fallback
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["LAWEAR_GRADER_MOCK"] = "1"
        _init_db(_TEST_DB.name)


# ─── 1. POST /api/attempts ───────────────────────────────────────────


class PostAttemptsSubqTest(ServerTestBase):
    """POST /api/attempts — 다중 카드 + legacy 호환 + 검증."""

    def test_post_attempts_subq_multi_card(self):
        """answer_subq + subq_elapsed + hints_used → 200 + attempt_id + 메타."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {
                    "설문 1": "첫 번째 답안 본문 가나다",
                    "설문 2": "두 번째 답안 본문 라마",
                },
                "subq_elapsed": {"설문 1": 120, "설문 2": 180},
                "hints_used": {"설문 1": [1, 2], "설문 2": [1]},
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("attempt_id", body)
        self.assertGreater(body["attempt_id"], 0)
        self.assertEqual(body["case_id"], "TC_S24_5_MULTI")
        # Step 24-3 메타
        self.assertEqual(body["subq_count"], 2)
        self.assertEqual(body["hints_used_count"], 3)  # 2 + 1
        self.assertEqual(body["hint_steps_revealed_max"], 2)
        # manual 모드 기본
        self.assertEqual(body["status"], "pending_grade")
        self.assertEqual(body["grading_mode"], "manual")

    def test_post_attempts_legacy_answer_text(self):
        """legacy answer_text 만 — 기존 호환 (200 + subq_count=0)."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_LEGACY",
                "answer_text": "legacy 단일 답안 본문",
            },
        )
        self.assertEqual(status, 200)
        self.assertGreater(body["attempt_id"], 0)
        self.assertEqual(body["subq_count"], 0)
        self.assertEqual(body["hints_used_count"], 0)
        self.assertEqual(body["hint_steps_revealed_max"], 0)
        self.assertEqual(body["status"], "pending_grade")

    def test_post_attempts_both_provided(self):
        """answer_text + answer_subq 양쪽 — 200 (R-09 양쪽 그대로 저장)."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_text": "legacy 답안",
                "answer_subq": {"설문 1": "신규 답안"},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["subq_count"], 1)

    def test_post_attempts_both_empty_400_subq_empty(self):
        """answer_text + answer_subq 둘 다 없음 → 400 subq_empty."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={"case_id": "TC_S24_5_LEGACY"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "subq_empty")

    def test_post_attempts_empty_answer_subq_dict_400(self):
        """answer_subq={} (빈 dict) + answer_text 없음 → 400 subq_empty."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {},
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "subq_empty")

    def test_post_attempts_answer_subq_all_empty_strings(self):
        """answer_subq dict 자체 있지만 모든 값 빈 문자열 → 400 subq_empty."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {"설문 1": "", "설문 2": "   "},
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "subq_empty")

    def test_post_attempts_case_id_missing_400(self):
        """case_id 빈 값 → 400 bad_request."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={"case_id": "", "answer_text": "답안"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "bad_request")

    def test_post_attempts_case_id_not_found_404(self):
        """case_id 미존재 → 404 case_not_found."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={"case_id": "NO_SUCH_CASE", "answer_text": "답안"},
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["error_code"], "case_not_found")

    def test_post_attempts_answer_subq_not_dict_400(self):
        """answer_subq 가 dict 아님 (list/string) → 400 bad_request."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": [1, 2, 3],
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "bad_request")
        self.assertIn("answer_subq", body["message"])

    def test_post_attempts_subq_elapsed_not_dict_400(self):
        """subq_elapsed 가 dict 아님 → 400 bad_request."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {"설문 1": "답안"},
                "subq_elapsed": "not a dict",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("subq_elapsed", body["message"])

    def test_post_attempts_hints_used_not_dict_400(self):
        """hints_used 가 dict 아님 → 400 bad_request."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {"설문 1": "답안"},
                "hints_used": [1, 2],
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("hints_used", body["message"])

    def test_post_attempts_invalid_json_400(self):
        """JSON 디코딩 에러 → 400 bad_request."""
        status, body = _request_raw(
            "POST", self.httpd, "/api/attempts",
            raw_body=b"{not valid json",
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "bad_request")

    def test_post_attempts_korean_preserved_in_response(self):
        """응답 JSON 의 한글 키 보존 (ensure_ascii=False) — case_id, key 직접 확인."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {"설문 1": "한글 답안 가나다"},
            },
        )
        self.assertEqual(status, 200)
        # DB 직접 검증 — 저장된 JSON 도 한글 그대로
        with db_mod.get_conn(_TEST_DB.name) as conn:
            cur = conn.execute(
                "SELECT answer_subq FROM attempts WHERE id = ?",
                (body["attempt_id"],),
            )
            row = cur.fetchone()
        self.assertIn("설문 1", row["answer_subq"])
        self.assertNotIn("\\u", row["answer_subq"])


# ─── 2. PUT /api/attempts/{id}/grade ─────────────────────────────────


class PutGradeSubqTest(ServerTestBase):
    """PUT /api/attempts/{id}/grade — criteria_subq + legacy criteria 호환."""

    def _create_multi_attempt(self) -> int:
        """다중 카드 pending_grade attempt 생성 — 후속 PUT 대상."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {
                    "설문 1": "답안 일",
                    "설문 2": "답안 이",
                },
            },
        )
        self.assertEqual(status, 200)
        return body["attempt_id"]

    def _create_legacy_attempt(self) -> int:
        """legacy 단일 pending_grade attempt 생성."""
        status, body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_LEGACY",
                "answer_text": "legacy 답안",
            },
        )
        self.assertEqual(status, 200)
        return body["attempt_id"]

    def test_put_grade_subq(self):
        """criteria_subq 다중 카드 → 200 + attempt_criteria.subq_key 채움."""
        aid = self._create_multi_attempt()
        status, body = _request(
            "PUT", self.httpd, f"/api/attempts/{aid}/grade",
            body=_full_grade_subq(),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "completed")
        # criteria_subq 노출
        self.assertIn("criteria_subq", body)
        self.assertIn("설문 1", body["criteria_subq"])
        self.assertIn("설문 2", body["criteria_subq"])
        # DB 검증 — subq_key non-NULL
        with db_mod.get_conn(_TEST_DB.name) as conn:
            cur = conn.execute(
                "SELECT criterion_key, subq_key FROM attempt_criteria "
                "WHERE attempt_id = ? ORDER BY subq_key, id ASC",
                (aid,),
            )
            rows = cur.fetchall()
        self.assertEqual(len(rows), 18, "9기준 × 2카드")
        subq_keys = {r["subq_key"] for r in rows}
        self.assertEqual(subq_keys, {"설문 1", "설문 2"})

    def test_put_grade_legacy_criteria(self):
        """legacy criteria 1차원 list → 200, attempt_criteria.subq_key=NULL 보존."""
        aid = self._create_legacy_attempt()
        status, body = _request(
            "PUT", self.httpd, f"/api/attempts/{aid}/grade",
            body=_full_grade_legacy(),
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "completed")
        self.assertNotIn("criteria_subq", body)
        # DB 검증 — 모든 row subq_key=NULL
        with db_mod.get_conn(_TEST_DB.name) as conn:
            cur = conn.execute(
                "SELECT criterion_key, subq_key FROM attempt_criteria "
                "WHERE attempt_id = ? ORDER BY id ASC",
                (aid,),
            )
            rows = cur.fetchall()
        self.assertEqual(len(rows), 9)
        for r in rows:
            self.assertIsNone(r["subq_key"])

    def test_put_grade_missing_both_400(self):
        """criteria 도 criteria_subq 도 없음 → 400 criteria_subq_required."""
        aid = self._create_legacy_attempt()
        status, body = _request(
            "PUT", self.httpd, f"/api/attempts/{aid}/grade",
            body={
                "total_score": 0.0, "max_score": 100.0, "score_pct": 0.0,
                "grade": "F", "eval_notes": _full_eval_notes(),
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "criteria_subq_required")

    def test_put_grade_attempt_not_found_404(self):
        """attempt_id 미존재 → 404 attempt_not_found."""
        status, body = _request(
            "PUT", self.httpd, "/api/attempts/9999999/grade",
            body=_full_grade_legacy(),
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["error_code"], "attempt_not_found")

    def test_put_grade_invalid_attempt_id_400(self):
        """attempt_id 가 int 아님 → 400 bad_request."""
        status, body = _request(
            "PUT", self.httpd, "/api/attempts/notanint/grade",
            body=_full_grade_legacy(),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "bad_request")

    def test_put_grade_subq_empty_dict_400(self):
        """criteria_subq={} (빈 dict) → 400 criteria_subq_required."""
        aid = self._create_multi_attempt()
        payload = {
            "criteria_subq": {},
            "total_score": 0.0, "max_score": 100.0, "score_pct": 0.0,
            "grade": "F", "eval_notes": _full_eval_notes(),
        }
        status, body = _request(
            "PUT", self.httpd, f"/api/attempts/{aid}/grade", body=payload,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "criteria_subq_required")

    def test_put_grade_invalid_json_400(self):
        """JSON 디코딩 에러 → 400 bad_request."""
        aid = self._create_legacy_attempt()
        status, body = _request_raw(
            "PUT", self.httpd, f"/api/attempts/{aid}/grade",
            raw_body=b"{broken json",
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error_code"], "bad_request")


# ─── 3. GET /api/attempts ────────────────────────────────────────────


class GetAttemptsListMetaTest(ServerTestBase):
    """GET /api/attempts — list item 메타 4종 노출."""

    def test_get_attempts_list_hints_meta(self):
        """다중 카드 attempt — list item 에 hints_used_count + steps_max + subq_count + total_solve_sec."""
        # POST 로 다중 카드 attempt 생성
        post_status, post_body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {"설문 1": "답안 일", "설문 2": "답안 이"},
                "subq_elapsed": {"설문 1": 60, "설문 2": 120},
                "hints_used": {"설문 1": [1, 2, 3], "설문 2": [1]},
            },
        )
        self.assertEqual(post_status, 200)

        # GET 로 list 조회
        status, body = _request("GET", self.httpd, "/api/attempts?case_id=TC_S24_5_MULTI")
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 1)
        item = body["attempts"][0]
        self.assertEqual(item["subq_count"], 2)
        self.assertEqual(item["hints_used_count"], 4)  # 3 + 1
        self.assertEqual(item["hint_steps_revealed_max"], 3)
        self.assertEqual(item["total_solve_sec"], 180)  # 60 + 120

    def test_get_attempts_list_legacy_meta_zero(self):
        """legacy attempt — 메타 모두 0/None."""
        _request(
            "POST", self.httpd, "/api/attempts",
            body={"case_id": "TC_S24_5_LEGACY", "answer_text": "legacy 답안"},
        )
        status, body = _request("GET", self.httpd, "/api/attempts?case_id=TC_S24_5_LEGACY")
        self.assertEqual(status, 200)
        item = body["attempts"][0]
        self.assertEqual(item["subq_count"], 0)
        self.assertEqual(item["hints_used_count"], 0)
        self.assertEqual(item["hint_steps_revealed_max"], 0)
        self.assertIsNone(item["total_solve_sec"])


# ─── 4. GET /api/attempts/{id} ───────────────────────────────────────


class GetAttemptDetailTest(ServerTestBase):
    """GET /api/attempts/{id} — 다중 채점 후 criteria_subq dict + 한글 보존."""

    def test_get_attempt_multi_card_after_grading(self):
        """다중 채점 → 응답에 criteria_subq dict + 한글 키 보존."""
        # 1. POST 다중 카드
        _, post_body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {"설문 1": "답안 일", "설문 2": "답안 이"},
            },
        )
        aid = post_body["attempt_id"]

        # 2. PUT 채점
        _request("PUT", self.httpd, f"/api/attempts/{aid}/grade", body=_full_grade_subq())

        # 3. GET 조회 — criteria_subq dict 노출
        status, body = _request("GET", self.httpd, f"/api/attempts/{aid}")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "completed")
        self.assertIn("criteria_subq", body)
        self.assertIn("설문 1", body["criteria_subq"])
        self.assertIn("설문 2", body["criteria_subq"])
        # answer_subq 도 응답에 노출 + 한글 보존
        self.assertEqual(body["answer_subq"]["설문 1"], "답안 일")
        self.assertEqual(body["answer_subq"]["설문 2"], "답안 이")

    def test_get_attempt_legacy_no_criteria_subq(self):
        """legacy 채점 후 criteria_subq 키 없음."""
        _, post_body = _request(
            "POST", self.httpd, "/api/attempts",
            body={"case_id": "TC_S24_5_LEGACY", "answer_text": "legacy"},
        )
        aid = post_body["attempt_id"]
        _request("PUT", self.httpd, f"/api/attempts/{aid}/grade", body=_full_grade_legacy())
        status, body = _request("GET", self.httpd, f"/api/attempts/{aid}")
        self.assertEqual(status, 200)
        self.assertNotIn("criteria_subq", body)
        self.assertEqual(len(body["criteria"]), 9)

    def test_get_attempt_pending_grade_exposes_answer_subq(self):
        """pending_grade 상태 — answer_subq 노출 (Claude Code 외부 채점 자료)."""
        _, post_body = _request(
            "POST", self.httpd, "/api/attempts",
            body={
                "case_id": "TC_S24_5_MULTI",
                "answer_subq": {"설문 1": "답안 가", "설문 2": "답안 나"},
                "hints_used": {"설문 1": [1, 2]},
            },
        )
        aid = post_body["attempt_id"]
        status, body = _request("GET", self.httpd, f"/api/attempts/{aid}")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "pending_grade")
        self.assertEqual(body["answer_subq"], {"설문 1": "답안 가", "설문 2": "답안 나"})
        self.assertEqual(body["hints_used"], {"설문 1": [1, 2]})
        self.assertEqual(body["hints_used_count"], 2)

    def test_get_attempt_not_found_404(self):
        """attempt_id 미존재 → 404."""
        status, body = _request("GET", self.httpd, "/api/attempts/9999999")
        self.assertEqual(status, 404)
        self.assertEqual(body["error_code"], "attempt_not_found")


# ─── 5. GET /api/cases/{id} ──────────────────────────────────────────


class GetCaseDetailTest(ServerTestBase):
    """GET /api/cases/{id} — subqs + toc + mnemonic 응답 키."""

    def test_get_case_subqs_multi(self):
        """다중 설문 — subqs[2] + toc + mnemonic 노출."""
        status, body = _request("GET", self.httpd, "/api/cases/TC_S24_5_MULTI")
        self.assertEqual(status, 200)
        # subqs 배열 (2 카드)
        self.assertIn("subqs", body)
        self.assertEqual(len(body["subqs"]), 2)
        keys = [c["key"] for c in body["subqs"]]
        self.assertEqual(keys, ["설문 1", "설문 2"])
        scores = [c["score_max"] for c in body["subqs"]]
        self.assertEqual(scores, [20, 15])
        # toc (목차 본문)
        self.assertIn("toc", body)
        self.assertIn("설문 1", body["toc"])
        self.assertIn("설문 2", body["toc"])
        self.assertIn("시효소멸", body["toc"])
        # mnemonic (전체 .md [blank2]X[/blank2] 콘텐츠 — Lv.2 힌트, 정답 본문 X)
        # 픽스처: 답안에 [blank2]보[/blank2] [blank2]필[/blank2] [blank2]도[/blank2] 3건.
        self.assertIn("mnemonic", body)
        self.assertEqual(body["mnemonic"], ["보", "필", "도"])
        # subqs[].mnemonic — 해당 subq body+answer 추출 콤마 join
        self.assertEqual(body["subqs"][0]["mnemonic"], "보,필")
        self.assertEqual(body["subqs"][1]["mnemonic"], "도")

    def test_get_case_single_fallback_empty_subqs(self):
        """단일 설문 (### 설문 N 헤더 0개) → subqs=[]."""
        status, body = _request("GET", self.httpd, "/api/cases/TC_S24_5_LEGACY")
        self.assertEqual(status, 200)
        self.assertIn("subqs", body)
        self.assertEqual(body["subqs"], [])
        # toc / mnemonic 도 빈 값
        self.assertEqual(body["toc"], "")
        self.assertEqual(body["mnemonic"], [])

    def test_get_case_not_found_404(self):
        """case_id 미존재 → 404 case_not_found."""
        status, body = _request("GET", self.httpd, "/api/cases/NO_SUCH_CASE")
        self.assertEqual(status, 404)
        self.assertEqual(body["error_code"], "case_not_found")

    def test_get_case_korean_preserved(self):
        """응답 JSON 의 한글 키 (subqs[i].key) ensure_ascii=False 보존."""
        # raw 응답 확인 — urllib 의 read() 가 bytes 라 _request 가 이미 decode 함
        host, port = self.httpd.server_address[:2]
        url = f"http://{host}:{port}/api/cases/TC_S24_5_MULTI"
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        # raw 응답에 \u 없이 한글 그대로
        self.assertIn("설문 1", raw)
        self.assertIn("설문 2", raw)
        self.assertNotIn("\\u", raw, "ensure_ascii=False 가 작동해야 함")


# ─── 6. Method not allowed / 405 ─────────────────────────────────────


class MethodNotAllowedTest(ServerTestBase):
    """잘못된 메서드 — 405 / 501 응답."""

    def test_delete_cases_not_supported_501(self):
        """DELETE /api/cases/... — 등록 안 된 메서드 → 501 not_implemented."""
        status, body = _request("DELETE", self.httpd, "/api/cases/TC_S24_5_MULTI")
        self.assertEqual(status, 501)
        self.assertEqual(body["error_code"], "not_implemented")

    def test_put_attempts_root_405(self):
        """PUT /api/attempts (root, /grade 없음) → 501 placeholder."""
        status, body = _request(
            "PUT", self.httpd, "/api/attempts",
            body={"answer_text": "x"},
        )
        # PUT /api/attempts (no /grade) 는 라우터 placeholder 로 501
        self.assertIn(status, (501, 405))


if __name__ == "__main__":
    unittest.main()
