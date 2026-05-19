"""attempts._compute_total_solve_sec + reports._subq_meta — fallback 검증.

lawear-e571/grader-tune-fallback (2026-05-19).

배경:
- 사용자 보고: att 15/16 가 단일 카드 답안(answer_subq={"단일": ...}, subq_elapsed={"단일": 0})
  인데 UI 에서 총 풀이 시간이 0초로 표시됨.
- 원인: total_solve_sec 가 subq_elapsed 합을 사용하는데, 카드 트래킹이 0 으로 시작되어
  실제 풀이 시간(submitted_at - started_at) 이 반영 안 됨.

수정:
- subq_elapsed 합 == 0 이고 solve_elapsed_sec > 0 → solve_elapsed_sec fallback.
- 정상 트래킹(subq_elapsed 합 > 0) 은 영향 X.
- legacy attempt (subq_elapsed=None) 도 영향 X (None 유지).

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_total_solve_sec_fallback.py -v
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

import attempts as attempts_mod  # noqa: E402
import db as db_mod  # noqa: E402
import grader as grader_mod  # noqa: E402
import reports as reports_mod  # noqa: E402


# ─── 단위: attempts._compute_total_solve_sec ─────────────────────────


class ComputeTotalSolveSecTest(unittest.TestCase):
    """attempts._compute_total_solve_sec 순수 함수 검증."""

    def test_normal_subq_elapsed_sum_used(self):
        """subq_elapsed 합 > 0 → 그 합."""
        total = attempts_mod._compute_total_solve_sec({"a": 10, "b": 20}, 100.0)
        self.assertEqual(total, 30)

    def test_normal_subq_no_fallback_when_sum_positive(self):
        """subq_elapsed 합 > 0 이면 solve_elapsed_sec 무시."""
        total = attempts_mod._compute_total_solve_sec({"a": 10, "b": 20}, 5000.0)
        self.assertEqual(total, 30, "subq 합 우선 — solve_elapsed_sec 무시")

    def test_fallback_subq_sum_zero_uses_solve_elapsed(self):
        """subq_elapsed 합 == 0 + solve_elapsed_sec > 0 → solve_elapsed_sec."""
        total = attempts_mod._compute_total_solve_sec({"단일": 0}, 600.0)
        self.assertEqual(total, 600)

    def test_fallback_subq_all_zero_uses_solve_elapsed(self):
        """다중 카드 모두 0 + solve_elapsed_sec > 0 → fallback (round)."""
        total = attempts_mod._compute_total_solve_sec(
            {"설문 1": 0, "설문 2": 0}, 1249.5
        )
        # round(1249.5) → 1250 (banker's rounding) 또는 1249 — Python 표준
        self.assertIn(total, (1249, 1250), f"실측 {total}")

    def test_subq_zero_and_solve_zero_returns_none(self):
        """subq 합 0 + solve_elapsed_sec 0 → None (UI 비표시)."""
        total = attempts_mod._compute_total_solve_sec({"단일": 0}, 0.0)
        self.assertIsNone(total)

    def test_subq_zero_and_solve_none_returns_none(self):
        """subq 합 0 + solve_elapsed_sec None → None."""
        total = attempts_mod._compute_total_solve_sec({"단일": 0}, None)
        self.assertIsNone(total)

    def test_legacy_subq_none_returns_none(self):
        """subq_elapsed None (legacy 단일 모드) → None 유지."""
        total = attempts_mod._compute_total_solve_sec(None, 600.0)
        self.assertIsNone(total, "legacy attempt 는 fallback 비활성 — 기존 동작 유지")

    def test_legacy_subq_empty_dict_returns_none(self):
        """subq_elapsed 빈 dict → None."""
        total = attempts_mod._compute_total_solve_sec({}, 600.0)
        self.assertIsNone(total)

    def test_subq_with_non_numeric_values(self):
        """subq_elapsed 에 비숫자 값 → 무시 (graceful)."""
        total = attempts_mod._compute_total_solve_sec(
            {"a": "bad", "b": 10}, 600.0
        )
        # "bad" 무시 → 합 10 → 10 반환 (fallback 비활성)
        self.assertEqual(total, 10)

    def test_subq_with_all_non_numeric(self):
        """모든 값 비숫자 → 합 0 → fallback 적용."""
        total = attempts_mod._compute_total_solve_sec(
            {"a": "bad", "b": None}, 600.0
        )
        self.assertEqual(total, 600, "모두 무시 → 합 0 → fallback")

    def test_att_15_16_reproduce(self):
        """사용자 보고 att 15/16 시나리오 재현.

        att 15: started=00:12:01.862, submitted=00:22:53.126 (≈651초), subq={"단일":0} → 651
        att 16: started=00:12:35.469, submitted=00:33:24.385 (≈1249초), subq={"단일":0} → 1249
        """
        # att 15: solve_elapsed_sec 직접 계산 (실 ISO)
        solve_15 = attempts_mod._solve_elapsed_sec(
            "2026-05-19T00:12:01.862Z", "2026-05-19T00:22:53.126Z"
        )
        total_15 = attempts_mod._compute_total_solve_sec({"단일": 0}, solve_15)
        self.assertEqual(total_15, 651, "att 15: 10분 51초 표시되어야")
        # att 16
        solve_16 = attempts_mod._solve_elapsed_sec(
            "2026-05-19T00:12:35.469Z", "2026-05-19T00:33:24.385Z"
        )
        total_16 = attempts_mod._compute_total_solve_sec({"단일": 0}, solve_16)
        self.assertEqual(total_16, 1249, "att 16: 20분 49초 표시되어야")


# ─── 단위: reports._subq_meta — fallback ─────────────────────────────


class ReportsSubqMetaFallbackTest(unittest.TestCase):
    """reports._subq_meta 가 started_at/submitted_at 인자로 fallback 적용."""

    def test_subq_meta_normal_sum_no_fallback(self):
        """subq_elapsed 합 > 0 → 그 합 (fallback X)."""
        meta = reports_mod._subq_meta(
            json.dumps({"a": "x"}),
            json.dumps({"a": 30}),
            None,
            started_at="2026-05-19T00:00:00Z",
            submitted_at="2026-05-19T00:10:00Z",
        )
        self.assertEqual(meta["total_solve_sec"], 30)

    def test_subq_meta_fallback_zero_subq(self):
        """subq 합 0 + solve_elapsed 양수 → fallback."""
        meta = reports_mod._subq_meta(
            json.dumps({"단일": "answer"}),
            json.dumps({"단일": 0}),
            None,
            started_at="2026-05-19T00:00:00Z",
            submitted_at="2026-05-19T00:10:51Z",
        )
        # solve_elapsed = 651초 → 651 fallback
        self.assertEqual(meta["total_solve_sec"], 651)

    def test_subq_meta_legacy_no_started_no_fallback(self):
        """started_at None → fallback 비활성 (legacy 호환)."""
        meta = reports_mod._subq_meta(
            json.dumps({"단일": "ans"}),
            json.dumps({"단일": 0}),
            None,
            # started_at / submitted_at 미전달 (None 기본)
        )
        # subq 합 0 + solve_elapsed None → None
        self.assertIsNone(meta["total_solve_sec"])

    def test_subq_meta_legacy_signature_unchanged(self):
        """기존 3-arg 호출 — 기본값 None 으로 호환 유지."""
        # 명시적으로 started_at/submitted_at 인자 없이 호출
        meta = reports_mod._subq_meta(
            json.dumps({"a": "ans"}),
            json.dumps({"a": 100}),
            json.dumps({}),
        )
        # subq 합 100 → 100 반환 (fallback 무관)
        self.assertEqual(meta["total_solve_sec"], 100)
        self.assertEqual(meta["subq_count"], 1)

    def test_subq_meta_both_zero_returns_none(self):
        """subq 0 + solve_elapsed 0 → None."""
        meta = reports_mod._subq_meta(
            json.dumps({"단일": "ans"}),
            json.dumps({"단일": 0}),
            None,
            started_at="2026-05-19T00:00:00Z",
            submitted_at="2026-05-19T00:00:00Z",  # 동일 → 0
        )
        self.assertIsNone(meta["total_solve_sec"])


# ─── 통합: attempts.list_attempts — att 15/16 시나리오 ───────────────


class ListAttemptsFallbackTest(unittest.TestCase):
    """list_attempts() 응답에 fallback total_solve_sec 노출."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        db_mod.init_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        # case seed
        self.conn.execute(
            """
            INSERT OR IGNORE INTO cases (
                id, subject, subject_kor, category, file, case_no, title, path,
                points, synced_at, content_hash
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            ("c-e571-fb", "minbeop", "민법", "예비", "미케01", "10",
             "Fallback TC", "/mock", 17, "2026-05-19T00:00:00Z", "abc"),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _seed_attempt(
        self,
        case_id: str,
        *,
        started_at: str | None,
        submitted_at: str,
        subq_elapsed: dict | None,
        answer_subq: dict | None = None,
    ) -> int:
        ans_json = json.dumps(answer_subq, ensure_ascii=False) if answer_subq else None
        elap_json = json.dumps(subq_elapsed, ensure_ascii=False) if subq_elapsed else None
        cur = self.conn.execute(
            """
            INSERT INTO attempts (
                case_id, answer_text, answer_subq, subq_elapsed, hints_used,
                started_at, submitted_at, status, weights_json,
                score_total, score_max, score_pct, grade, eval_notes_json,
                completed_at, is_stale, is_mock
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                case_id, "ans text",
                ans_json, elap_json, None,
                started_at, submitted_at, "done",
                json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
                10.0, 17.0, 58.8, "C",
                json.dumps({"strength": "s", "caution": "c", "missing": "m"}),
                submitted_at, 0, 0,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def test_att_15_like_scenario_fallback_in_list(self):
        """att 15 시뮬레이션: subq_elapsed={"단일":0}, solve_elapsed=651 → 651."""
        self._seed_attempt(
            "c-e571-fb",
            started_at="2026-05-19T00:12:01.862Z",
            submitted_at="2026-05-19T00:22:53.126Z",
            subq_elapsed={"단일": 0},
            answer_subq={"단일": "사용자 답안"},
        )
        result = attempts_mod.list_attempts(self.conn, limit=10, offset=0)
        self.assertEqual(len(result["attempts"]), 1)
        item = result["attempts"][0]
        # solve_elapsed_sec = 651.264 → 651 fallback
        self.assertIsNotNone(item["total_solve_sec"])
        self.assertGreater(item["total_solve_sec"], 600,
                           f"fallback 적용 — 실측 {item['total_solve_sec']}")
        self.assertLess(item["total_solve_sec"], 700)

    def test_att_16_like_scenario_fallback_in_list(self):
        """att 16 시뮬레이션: 20분 49초 fallback."""
        self._seed_attempt(
            "c-e571-fb",
            started_at="2026-05-19T00:12:35.469Z",
            submitted_at="2026-05-19T00:33:24.385Z",
            subq_elapsed={"단일": 0},
            answer_subq={"단일": "사용자 답안"},
        )
        result = attempts_mod.list_attempts(self.conn, limit=10, offset=0)
        item = result["attempts"][0]
        self.assertIsNotNone(item["total_solve_sec"])
        self.assertGreater(item["total_solve_sec"], 1200)
        self.assertLess(item["total_solve_sec"], 1300)

    def test_normal_subq_no_fallback(self):
        """정상 트래킹 (subq 합 양수) — fallback 무영향."""
        self._seed_attempt(
            "c-e571-fb",
            started_at="2026-05-19T01:00:00Z",
            submitted_at="2026-05-19T01:30:00Z",  # 1800초
            subq_elapsed={"설문 1": 100, "설문 2": 200},  # 합 300
            answer_subq={"설문 1": "a", "설문 2": "b"},
        )
        result = attempts_mod.list_attempts(self.conn, limit=10, offset=0)
        item = result["attempts"][0]
        # 정상 트래킹 합 300 사용 — solve_elapsed 1800 무시
        self.assertEqual(item["total_solve_sec"], 300)

    def test_legacy_attempt_no_subq(self):
        """legacy attempt (subq_elapsed=None) — fallback 비활성."""
        self._seed_attempt(
            "c-e571-fb",
            started_at="2026-05-19T02:00:00Z",
            submitted_at="2026-05-19T02:10:00Z",
            subq_elapsed=None,
            answer_subq=None,
        )
        result = attempts_mod.list_attempts(self.conn, limit=10, offset=0)
        item = result["attempts"][0]
        # legacy → None 유지 (fallback X)
        self.assertIsNone(item["total_solve_sec"])


# ─── 통합: reports.overall().recent — fallback ───────────────────────


class ReportsRecentFallbackTest(unittest.TestCase):
    """reports.overall().recent[] 가 fallback 적용된 total_solve_sec 노출."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        db_mod.init_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO cases (
                id, subject, subject_kor, category, file, case_no, title, path,
                points, synced_at, content_hash
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            ("c-e571-rep", "minbeop", "민법", "예비", "미케01", "10",
             "Reports FB TC", "/mock", 17, "2026-05-19T00:00:00Z", "abc"),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _seed(self, started_at, submitted_at, subq_elapsed, answer_subq):
        ans_json = json.dumps(answer_subq, ensure_ascii=False) if answer_subq else None
        elap_json = json.dumps(subq_elapsed, ensure_ascii=False) if subq_elapsed else None
        cur = self.conn.execute(
            """
            INSERT INTO attempts (
                case_id, answer_text, answer_subq, subq_elapsed, hints_used,
                started_at, submitted_at, status, weights_json,
                score_total, score_max, score_pct, grade, eval_notes_json,
                completed_at, is_stale, is_mock
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "c-e571-rep", "ans",
                ans_json, elap_json, None,
                started_at, submitted_at, "done",
                json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
                10.0, 17.0, 58.8, "C",
                json.dumps({"strength": "s", "caution": "c", "missing": "m"}),
                submitted_at, 0, 0,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def test_recent_includes_fallback_total_solve_sec(self):
        """overall().recent[] 에 fallback 적용된 시간 노출."""
        self._seed(
            "2026-05-19T00:12:01.862Z",
            "2026-05-19T00:22:53.126Z",
            {"단일": 0},
            {"단일": "ans"},
        )
        result = reports_mod.overall(self.conn)
        self.assertIn("recent", result)
        self.assertGreaterEqual(len(result["recent"]), 1)
        rec = result["recent"][0]
        # fallback 적용 (UI 0초 표시 방지)
        self.assertIsNotNone(rec["total_solve_sec"])
        self.assertGreater(rec["total_solve_sec"], 600)

    def test_recent_normal_subq_no_fallback(self):
        """정상 트래킹 — fallback 비적용."""
        self._seed(
            "2026-05-19T01:00:00Z",
            "2026-05-19T01:30:00Z",
            {"a": 100, "b": 200},
            {"a": "x", "b": "y"},
        )
        result = reports_mod.overall(self.conn)
        rec = result["recent"][0]
        self.assertEqual(rec["total_solve_sec"], 300)


# ─── 통합: reports.by_case().history + trend — fallback ──────────────


class ReportsByCaseFallbackTest(unittest.TestCase):
    """by_case().history + trend 가 fallback 적용."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        db_mod.init_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO cases (
                id, subject, subject_kor, category, file, case_no, title, path,
                points, synced_at, content_hash
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            ("c-e571-bc", "minbeop", "민법", "예비", "미케01", "11",
             "ByCase FB TC", "/mock", 17, "2026-05-19T00:00:00Z", "abc"),
        )
        self.conn.commit()
        self.conn.execute(
            """
            INSERT INTO attempts (
                case_id, answer_text, answer_subq, subq_elapsed, hints_used,
                started_at, submitted_at, status, weights_json,
                score_total, score_max, score_pct, grade, eval_notes_json,
                completed_at, is_stale, is_mock
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "c-e571-bc", "ans",
                json.dumps({"단일": "ans"}, ensure_ascii=False),
                json.dumps({"단일": 0}, ensure_ascii=False),
                None,
                "2026-05-19T00:12:35.469Z", "2026-05-19T00:33:24.385Z", "done",
                json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
                10.0, 17.0, 58.8, "C",
                json.dumps({"strength": "s", "caution": "c", "missing": "m"}),
                "2026-05-19T00:33:24.385Z", 0, 0,
            ),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_by_case_history_fallback(self):
        """by_case().history[] 에 fallback total_solve_sec 노출."""
        result = reports_mod.by_case(self.conn, "c-e571-bc")
        self.assertIn("history", result)
        self.assertGreaterEqual(len(result["history"]), 1)
        hist = result["history"][0]
        self.assertIsNotNone(hist["total_solve_sec"])
        self.assertGreater(hist["total_solve_sec"], 1200,
                           f"실측 {hist['total_solve_sec']}")

    def test_by_case_trend_fallback(self):
        """by_case().trend[] 에도 fallback 적용 (trend SQL 에 started_at 추가됨)."""
        result = reports_mod.by_case(self.conn, "c-e571-bc")
        self.assertIn("trend", result)
        self.assertGreaterEqual(len(result["trend"]), 1)
        tr = result["trend"][0]
        self.assertIsNotNone(tr["total_solve_sec"])
        self.assertGreater(tr["total_solve_sec"], 1200)


if __name__ == "__main__":
    unittest.main()
