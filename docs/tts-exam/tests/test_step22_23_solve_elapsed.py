#!/usr/bin/env python3
"""Step 22+23 — 다중 설문 파싱 + 풀이 시간 추적.

Step 22:
- splitOriginFactsQuestion 백엔드 영향 없음 (시안 변경) — 본 TC 는 attempts/reports
  의 started_at + solve_elapsed_sec 노출에만 집중.

Step 23 (사용자 명시 2026-05-17):
- attempts._solve_elapsed_sec 헬퍼: started_at/submitted_at 누락/파싱 실패 → None
- _attempt_row_to_dict 응답에 solve_elapsed_sec 포함
- reports.history / recent 응답에 started_at + solve_elapsed_sec 포함
- POST /api/attempts body started_at 수신 → attempts.started_at 컬럼 저장
- GET /api/attempts/{id} 응답에 started_at + solve_elapsed_sec
- GET /api/attempts 응답에 started_at + solve_elapsed_sec

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step22_23_solve_elapsed.py -v
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent.resolve()
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from unittest.mock import patch  # noqa: E402

import attempts as attempts_mod  # noqa: E402
import cases as cases_mod  # noqa: E402
import db as db_mod  # noqa: E402
import grader as grader_mod  # noqa: E402
import reports as reports_mod  # noqa: E402


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _build_db(path: str) -> None:
    db_mod.init_db(path)


def _seed_case(conn: sqlite3.Connection, case_id: str = "c-step23") -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO cases (
            id, subject, subject_kor, category, file, case_no, title, path,
            points, synced_at, content_hash
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (case_id, "minbeop", "민법", "예비", "미케01", "01", "Step23 풀이시간 TC",
         "/mock", 17, "2026-05-17T00:00:00Z", "abc"),
    )
    conn.commit()


def _seed_attempt_with_times(
    conn: sqlite3.Connection,
    case_id: str,
    *,
    started_at: str | None,
    submitted_at: str,
    status: str = "done",
    score_total: float | None = 10.0,
    score_max: float | None = 17.0,
) -> int:
    """attempts 행 INSERT — 임의 시간/상태."""
    cur = conn.execute(
        """
        INSERT INTO attempts (
            case_id, answer_text, started_at, submitted_at, status, weights_json,
            score_total, score_max, score_pct, grade, eval_notes_json,
            completed_at, is_stale, is_mock
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            case_id,
            "TC answer step 23",
            started_at,
            submitted_at,
            status,
            json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
            score_total,
            score_max,
            (
                round((score_total / score_max) * 100, 2)
                if score_total is not None and score_max
                else None
            ),
            "B",
            json.dumps({"strength": "s", "caution": "c", "missing": "m"}),
            submitted_at,
            0,
            0,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


# ─── 단위: _solve_elapsed_sec ────────────────────────────────────────


class SolveElapsedSecTest(unittest.TestCase):
    """attempts._solve_elapsed_sec 순수 함수 검증."""

    def test_basic_delta_seconds(self) -> None:
        """5분 차이 → 300초."""
        sec = attempts_mod._solve_elapsed_sec(
            "2026-05-17T10:00:00Z", "2026-05-17T10:05:00Z"
        )
        self.assertEqual(sec, 300.0)

    def test_hours_minutes(self) -> None:
        """1시간 23분 = 4980초."""
        sec = attempts_mod._solve_elapsed_sec(
            "2026-05-17T10:00:00Z", "2026-05-17T11:23:00Z"
        )
        self.assertEqual(sec, 4980.0)

    def test_started_none(self) -> None:
        """started_at None → None."""
        sec = attempts_mod._solve_elapsed_sec(None, "2026-05-17T10:00:00Z")
        self.assertIsNone(sec)

    def test_submitted_none(self) -> None:
        """submitted_at None → None."""
        sec = attempts_mod._solve_elapsed_sec("2026-05-17T10:00:00Z", None)
        self.assertIsNone(sec)

    def test_both_none(self) -> None:
        """둘 다 None → None."""
        self.assertIsNone(attempts_mod._solve_elapsed_sec(None, None))

    def test_parse_failure(self) -> None:
        """ISO 파싱 실패 → None."""
        sec = attempts_mod._solve_elapsed_sec("not-iso", "also-not-iso")
        self.assertIsNone(sec)

    def test_negative_clamped_to_zero(self) -> None:
        """submitted < started (시계 역행) → 0.0 clamp."""
        sec = attempts_mod._solve_elapsed_sec(
            "2026-05-17T10:05:00Z", "2026-05-17T10:00:00Z"
        )
        self.assertEqual(sec, 0.0)

    def test_with_offset_tz(self) -> None:
        """+09:00 TZ ISO 도 처리 (Z 외 형식)."""
        sec = attempts_mod._solve_elapsed_sec(
            "2026-05-17T19:00:00+09:00", "2026-05-17T19:01:30+09:00"
        )
        self.assertEqual(sec, 90.0)


# ─── 통합: _attempt_row_to_dict — solve_elapsed_sec 노출 ─────────────


class AttemptRowDictSolveElapsedTest(unittest.TestCase):
    """attempts.get_attempt() / list_attempts() 응답에 solve_elapsed_sec 포함."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "c-step23")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_get_attempt_includes_solve_elapsed_sec(self) -> None:
        """started_at + submitted_at 있는 시도 → solve_elapsed_sec 정상."""
        aid = _seed_attempt_with_times(
            self.conn,
            "c-step23",
            started_at="2026-05-17T10:00:00Z",
            submitted_at="2026-05-17T10:07:30Z",
        )
        result = attempts_mod.get_attempt(self.conn, aid)
        self.assertIn("solve_elapsed_sec", result)
        self.assertEqual(result["solve_elapsed_sec"], 450.0)
        self.assertEqual(result["started_at"], "2026-05-17T10:00:00Z")

    def test_get_attempt_no_started_at(self) -> None:
        """started_at 없는 시도 → solve_elapsed_sec None."""
        aid = _seed_attempt_with_times(
            self.conn,
            "c-step23",
            started_at=None,
            submitted_at="2026-05-17T10:07:30Z",
        )
        result = attempts_mod.get_attempt(self.conn, aid)
        self.assertIn("solve_elapsed_sec", result)
        self.assertIsNone(result["solve_elapsed_sec"])
        self.assertIsNone(result["started_at"])

    def test_list_attempts_includes_solve_elapsed_sec(self) -> None:
        """GET /api/attempts list 응답에도 solve_elapsed_sec 포함."""
        _seed_attempt_with_times(
            self.conn,
            "c-step23",
            started_at="2026-05-17T09:00:00Z",
            submitted_at="2026-05-17T09:12:00Z",
        )
        _seed_attempt_with_times(
            self.conn,
            "c-step23",
            started_at=None,
            submitted_at="2026-05-17T10:00:00Z",
        )
        lst = attempts_mod.list_attempts(self.conn, case_id="c-step23")
        items = lst["attempts"] if "attempts" in lst else lst.get("items") or []
        self.assertGreaterEqual(len(items), 2)
        # 모든 row 에 solve_elapsed_sec 키 노출
        for it in items:
            self.assertIn("solve_elapsed_sec", it)
            self.assertIn("started_at", it)
        # 적어도 한 건은 값 존재
        with_value = [
            it for it in items if it.get("solve_elapsed_sec") is not None
        ]
        self.assertGreaterEqual(len(with_value), 1)
        # 12분 = 720초
        self.assertIn(720.0, [it["solve_elapsed_sec"] for it in with_value])


# ─── 통합: create_attempt — started_at 저장 ──────────────────────────


class CreateAttemptStartedAtTest(unittest.TestCase):
    """POST /api/attempts body started_at → attempts.started_at 컬럼 저장."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "c-step23")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _fake_case_meta(self) -> dict:
        """cases.get_case 가 반환할 가짜 case_meta (md_body 포함)."""
        return {
            "id": "c-step23",
            "subject": "minbeop",
            "subject_kor": "민법",
            "category": "예비",
            "file": "미케01",
            "case_no": "01",
            "title": "Step23 풀이시간 TC",
            "path": "/mock",
            "points": 17,
            "md_body": "## 원본\n\n### 사실관계\n test\n\n### 문제\n test\n",
        }

    def test_create_attempt_persists_started_at(self) -> None:
        """started_at 인자 → DB 에 그대로 기록."""
        with patch.object(cases_mod, "get_case", return_value=self._fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "c-step23",
                "TC answer body",
                started_at="2026-05-17T10:00:00Z",
                submitted_at="2026-05-17T10:09:00Z",
                grading_mode="manual",
            )
        aid = result["attempt_id"]
        cur = self.conn.execute(
            "SELECT started_at, submitted_at FROM attempts WHERE id = ?", (aid,)
        )
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["started_at"], "2026-05-17T10:00:00Z")
        self.assertEqual(row["submitted_at"], "2026-05-17T10:09:00Z")

        # GET 응답에 solve_elapsed_sec=540 (9분)
        got = attempts_mod.get_attempt(self.conn, aid)
        self.assertEqual(got["solve_elapsed_sec"], 540.0)

    def test_create_attempt_without_started_at(self) -> None:
        """started_at 누락 → DB 에 NULL, solve_elapsed_sec=None."""
        with patch.object(cases_mod, "get_case", return_value=self._fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "c-step23",
                "TC no started",
                started_at=None,
                submitted_at="2026-05-17T10:09:00Z",
                grading_mode="manual",
            )
        aid = result["attempt_id"]
        got = attempts_mod.get_attempt(self.conn, aid)
        self.assertIsNone(got["started_at"])
        self.assertIsNone(got["solve_elapsed_sec"])


# ─── 통합: reports.by_case history — solve_elapsed_sec ──────────────


class ReportsByCaseHistoryElapsedTest(unittest.TestCase):
    """reports.by_case().history 에 started_at + solve_elapsed_sec 포함."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "c-step23")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_history_includes_solve_elapsed_sec(self) -> None:
        """시도 2건 — 1건은 시간 있음(120초), 1건은 시간 없음(None)."""
        # 첫 시도: 2분 풀이
        _seed_attempt_with_times(
            self.conn,
            "c-step23",
            started_at="2026-05-17T10:00:00Z",
            submitted_at="2026-05-17T10:02:00Z",
        )
        # 두번째 시도: started_at None
        _seed_attempt_with_times(
            self.conn,
            "c-step23",
            started_at=None,
            submitted_at="2026-05-17T11:05:00Z",
        )
        result = reports_mod.by_case(self.conn, "c-step23")
        history = result["history"]
        self.assertEqual(len(history), 2)
        # 정렬 ASC — 첫 시도가 history[0]
        self.assertIn("started_at", history[0])
        self.assertIn("solve_elapsed_sec", history[0])
        self.assertEqual(history[0]["solve_elapsed_sec"], 120.0)
        # 두 번째 시도: started_at None
        self.assertIsNone(history[1]["started_at"])
        self.assertIsNone(history[1]["solve_elapsed_sec"])


# ─── 통합: reports.overall recent — solve_elapsed_sec ────────────────


class ReportsOverallRecentElapsedTest(unittest.TestCase):
    """reports.overall().recent 에 started_at + solve_elapsed_sec 포함."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "c-step23")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_recent_includes_solve_elapsed_sec(self) -> None:
        """recent 응답에 started_at + solve_elapsed_sec 노출."""
        _seed_attempt_with_times(
            self.conn,
            "c-step23",
            started_at="2026-05-17T10:00:00Z",
            submitted_at="2026-05-17T10:10:00Z",
        )
        result = reports_mod.overall(self.conn)
        recent = result["recent"]
        self.assertGreaterEqual(len(recent), 1)
        first = recent[0]
        self.assertIn("started_at", first)
        self.assertIn("solve_elapsed_sec", first)
        self.assertEqual(first["solve_elapsed_sec"], 600.0)
        self.assertEqual(first["started_at"], "2026-05-17T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
