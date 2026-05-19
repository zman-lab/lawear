"""60점 합격선 시각화 (lawear-e571, 2026-05-19).

핵심:
- score_pct >= 60.0 → is_pass=True (합격 배지 조건).
- API 응답 (_attempt_row_to_dict + reports.py 3종) 모두 is_pass 노출.
- 합격선 직전/직후 경계: 59.99 → False, 60.0 → True.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# cases.BASE_PATH 격리
_TEST_BASE = tempfile.mkdtemp(prefix="lawear_passline_base_")
os.environ["LAWEAR_TTS_BASE"] = _TEST_BASE
_DUMMY_DIR = Path(_TEST_BASE) / "_test"
_DUMMY_DIR.mkdir(parents=True, exist_ok=True)
_DUMMY_MD = _DUMMY_DIR / "dummy.md"
_DUMMY_MD.write_text(
    "## 원본 (17점)\n\n### 사실관계\n테스트.\n\n### 답안\n테스트 답안.\n",
    encoding="utf-8",
)

import attempts as attempts_mod  # noqa: E402
import cases as cases_mod  # noqa: E402
import db as db_mod  # noqa: E402
import reports as reports_mod  # noqa: E402

if str(cases_mod.BASE_PATH) != _TEST_BASE:
    cases_mod.BASE_PATH = Path(_TEST_BASE).resolve()


class TestIsPassFunction(unittest.TestCase):
    """attempts._is_pass + reports._is_pass — 60점 합격선 헬퍼."""

    def test_is_pass_60_true(self) -> None:
        """60.0 정확 → True (합격선 정중앙)."""
        self.assertTrue(attempts_mod._is_pass(60.0))
        self.assertTrue(reports_mod._is_pass(60.0))

    def test_is_pass_above_60_true(self) -> None:
        """60+ → True."""
        for pct in [60.01, 65.0, 70.0, 80.0, 100.0]:
            with self.subTest(pct=pct):
                self.assertTrue(attempts_mod._is_pass(pct))
                self.assertTrue(reports_mod._is_pass(pct))

    def test_is_pass_below_60_false(self) -> None:
        """60 미만 → False (불합격)."""
        for pct in [59.99, 55.0, 50.0, 30.0, 0.0]:
            with self.subTest(pct=pct):
                self.assertFalse(attempts_mod._is_pass(pct))
                self.assertFalse(reports_mod._is_pass(pct))

    def test_is_pass_none_false(self) -> None:
        """None → False (안전)."""
        self.assertFalse(attempts_mod._is_pass(None))
        self.assertFalse(reports_mod._is_pass(None))

    def test_is_pass_invalid_false(self) -> None:
        """str / 잘못된 입력 → False."""
        self.assertFalse(attempts_mod._is_pass("abc"))  # type: ignore
        self.assertFalse(reports_mod._is_pass("xyz"))  # type: ignore

    def test_pass_line_constant(self) -> None:
        """PASS_LINE_PCT = 60.0 (양 모듈 동일)."""
        self.assertEqual(attempts_mod.PASS_LINE_PCT, 60.0)
        self.assertEqual(reports_mod.PASS_LINE_PCT, 60.0)


# ─── 통합: _attempt_row_to_dict 가 is_pass 노출 ─────


def _build_db(db_path: str) -> None:
    """공통 DB 시드 — 1 케이스."""
    db_mod.init_db(db_path)
    with db_mod.get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO cases
              (id, subject, subject_kor, category, file, case_no, title, path, points, synced_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TC_PASS",
                "minbeop",
                "민법",
                "입문",
                "미케01",
                "01",
                "합격선 테스트",
                "_test/dummy.md",
                17,
                "2026-05-19T00:00:00Z",
                "deadbeef",
            ),
        )
        conn.commit()


def _seed_done_attempt(conn, case_id: str, score_pct: float, grade_v1: str = "B") -> int:
    """status=done attempts row 1건 직접 시드 — score_pct 만 가변."""
    cur = conn.execute(
        """
        INSERT INTO attempts
          (case_id, status, submitted_at, started_at, completed_at, elapsed_sec,
           score_total, score_max, score_pct, grade, model, eval_notes_json,
           diff_json, raw_response, is_mock, weights_json, is_stale, answer_text)
        VALUES (?, 'done', ?, ?, ?, 0.0, ?, 100.0, ?, ?, 'mock', '{}', '[]', '{}', 0, '{}', 0, '')
        """,
        (
            case_id, "2026-05-19T10:00:00Z", "2026-05-19T09:00:00Z",
            "2026-05-19T10:00:01Z",
            (float(score_pct) / 100.0) * 100.0,  # score_total 도 동일 비율
            float(score_pct), grade_v1,
        ),
    )
    conn.commit()
    return cur.lastrowid


class TestAttemptResponseIsPass(unittest.TestCase):
    """get_attempt 응답에 is_pass 필드 노출 (60+ 합격선)."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_attempt_pct_60_is_pass_true(self) -> None:
        """score_pct=60 → is_pass=True + grade='B' (V2)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempt_id = _seed_done_attempt(conn, "TC_PASS", 60.0, "B")
            out = attempts_mod.get_attempt(conn, attempt_id)
        self.assertTrue(out["is_pass"], "60.0 should be pass")
        self.assertEqual(out["grade"], "B", "V2 grade for 60.0 = B")
        self.assertEqual(out["grade_v1"], "B")

    def test_attempt_pct_59_is_pass_false(self) -> None:
        """score_pct=59.99 → is_pass=False + grade='B-' (V2)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempt_id = _seed_done_attempt(conn, "TC_PASS", 59.99, "B")
            out = attempts_mod.get_attempt(conn, attempt_id)
        self.assertFalse(out["is_pass"], "59.99 should NOT pass")
        self.assertEqual(out["grade"], "B-", "V2 grade for 59.99 = B-")

    def test_attempt_pct_80_aplus(self) -> None:
        """score_pct=80 → A+ (V2) + is_pass=True."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempt_id = _seed_done_attempt(conn, "TC_PASS", 80.0, "A")
            out = attempts_mod.get_attempt(conn, attempt_id)
        self.assertEqual(out["grade"], "A+")
        self.assertEqual(out["grade_v1"], "A")
        self.assertTrue(out["is_pass"])

    def test_attempt_pct_30_f(self) -> None:
        """score_pct=30 → F (V2) + is_pass=False."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempt_id = _seed_done_attempt(conn, "TC_PASS", 30.0, "F")
            out = attempts_mod.get_attempt(conn, attempt_id)
        self.assertEqual(out["grade"], "F")
        self.assertFalse(out["is_pass"])


class TestReportsResponseIsPass(unittest.TestCase):
    """reports.py overall/by_subject/by_case 응답에 is_pass + grade_v2."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_overall_recent_has_is_pass(self) -> None:
        """GET /api/reports/overall → recent[] 에 is_pass 필드."""
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_done_attempt(conn, "TC_PASS", 75.0, "A")  # 합격 (A)
            _seed_done_attempt(conn, "TC_PASS", 45.0, "C")  # 불합격 (C)
            out = reports_mod.overall(conn)
        self.assertGreaterEqual(len(out["recent"]), 2)
        # 가장 최근 (75.0) → 합격 + A
        for r in out["recent"]:
            self.assertIn("is_pass", r)
            self.assertIn("grade", r)
            if abs(r["score_pct"] - 75.0) < 0.01:
                self.assertTrue(r["is_pass"])
                self.assertEqual(r["grade"], "A")
            if abs(r["score_pct"] - 45.0) < 0.01:
                self.assertFalse(r["is_pass"])
                self.assertEqual(r["grade"], "C")

    def test_by_case_trend_has_is_pass(self) -> None:
        """GET /api/reports/by-case → trend[] 에 is_pass + V2 grade."""
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_done_attempt(conn, "TC_PASS", 60.0, "B")  # 합격
            _seed_done_attempt(conn, "TC_PASS", 55.0, "C")  # 불합격
            out = reports_mod.by_case(conn, "TC_PASS")
        self.assertEqual(len(out["trend"]), 2)
        for t in out["trend"]:
            self.assertIn("is_pass", t)
            self.assertIn("grade", t)

    def test_by_case_history_has_is_pass(self) -> None:
        """GET /api/reports/by-case → history[] 에 is_pass + V2 grade."""
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_done_attempt(conn, "TC_PASS", 65.0, "B")  # B+ (V2)
            out = reports_mod.by_case(conn, "TC_PASS")
        self.assertGreaterEqual(len(out["history"]), 1)
        for h in out["history"]:
            self.assertIn("is_pass", h)
            self.assertIn("grade", h)
            if abs(h["score_pct"] - 65.0) < 0.01:
                self.assertEqual(h["grade"], "B+")
                self.assertTrue(h["is_pass"])


if __name__ == "__main__":
    unittest.main()
