#!/usr/bin/env python3
"""Step 17 — 재채점 endpoint (DELETE /api/attempts/{id}/grade) 단위 테스트.

- attempts.reset_grade (성공 / 404 / noop 케이스)
- done → pending_grade 전환 + attempt_criteria 삭제 + 답안 보존 검증
- error → pending_grade 전환 (사용자 명시 — error 도 reset OK)
- pending_grade / grading → noop

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step17_regrade.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# cases.BASE_PATH 격리 (test_step13 과 동일 패턴)
_TEST_BASE = tempfile.mkdtemp(prefix="lawear_step17_base_")
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

if str(cases_mod.BASE_PATH) != _TEST_BASE:
    cases_mod.BASE_PATH = Path(_TEST_BASE).resolve()


# ─── 픽스처 ──────────────────────────────────────────────────────────


def _build_db(db_path: str) -> None:
    """v3 마이그 + 케이스 1건 시드."""
    db_mod.init_db(db_path)
    with db_mod.get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO cases
              (id, subject, subject_kor, category, file, case_no, title, path, points, synced_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TC_S17",
                "minbeop",
                "민법",
                "입문",
                "미케01",
                "01",
                "Step 17 테스트 케이스",
                "_test/dummy.md",
                17,
                "2026-05-16T00:00:00Z",
                "deadbeef",
            ),
        )
        conn.commit()


def _full_grade_payload() -> dict:
    """inject_grade 페이로드 — done 상태 만들기용 (Step 21 v5 9기준).

    가중치 합: 16+13+8+10+12+15+11+10+5 = 100
    """
    return {
        "criteria": [
            {"key": "mnemonics", "score": 3, "weight_applied": 16, "comment": ""},
            {"key": "color", "score": 11, "weight_applied": 13, "comment": ""},
            {"key": "underline", "score": 2, "weight_applied": 8, "comment": ""},
            {"key": "outline", "score": 3, "weight_applied": 10, "comment": ""},
            {"key": "semantic", "score": 8, "weight_applied": 12, "comment": ""},
            {"key": "richness", "score": 11, "weight_applied": 15, "comment": ""},
            {"key": "missing", "score": -2, "weight_applied": 11, "comment": ""},
            {"key": "articles", "score": 8, "weight_applied": 10, "comment": ""},
            {"key": "case_apply", "score": 3, "weight_applied": 5, "comment": ""},
        ],
        "total_score": 14.78,
        "max_score": 17.0,
        "score_pct": 82.47,
        "grade": "B",
        "eval_notes": {"strength": "S", "caution": "C", "missing": "M"},
        "diff_segments": [{"type": "match", "text": "재건축조합"}],
    }


def _cleanup_env() -> None:
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["LAWEAR_GRADER_MOCK"] = "1"


# ─── reset_grade ─────────────────────────────────────────────────────


class ResetGradeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        _cleanup_env()
        with db_mod.get_conn(self.tmp.name) as conn:
            self.attempt_id = attempts_mod.create_attempt(
                conn,
                self.tmp.name,
                case_id="TC_S17",
                answer_text="검토 의견 본문 — Step 17",
                grading_mode="manual",
            )["attempt_id"]

    def tearDown(self) -> None:
        os.environ.pop("LAWEAR_GRADER_MOCK", None)
        os.unlink(self.tmp.name)

    # ── 성공 케이스: done → pending_grade ──

    def test_reset_done_attempt_reverts_to_pending_grade(self) -> None:
        """done 상태 → reset → pending_grade. 답안은 보존."""
        with db_mod.get_conn(self.tmp.name) as conn:
            # 먼저 채점 결과 주입해서 done 상태로 만들기
            attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())
            # done 확인
            pre = conn.execute(
                "SELECT status, score_total, grade, answer_text FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
            self.assertEqual(pre["status"], "done")
            # Step 20 v4 (2026-05-16): 페이로드 갱신 — total_score=14.78 (8기준)
            self.assertAlmostEqual(pre["score_total"], 14.78, places=2)

            # reset
            out = attempts_mod.reset_grade(conn, self.attempt_id)
            self.assertEqual(out["attempt_id"], self.attempt_id)
            self.assertEqual(out["status"], "pending_grade")
            self.assertIn("Grade reset OK", out["message"])

            # post 검증 — status / 채점 필드 NULL / 답안 보존
            post = conn.execute(
                """SELECT status, score_total, score_max, score_pct, grade,
                          eval_notes_json, diff_json, raw_response, completed_at,
                          elapsed_sec, model, answer_text, error_code, error_message,
                          is_mock
                     FROM attempts WHERE id = ?""",
                (self.attempt_id,),
            ).fetchone()
        self.assertEqual(post["status"], "pending_grade")
        self.assertIsNone(post["score_total"])
        self.assertIsNone(post["score_max"])
        self.assertIsNone(post["score_pct"])
        self.assertIsNone(post["grade"])
        self.assertIsNone(post["eval_notes_json"])
        self.assertIsNone(post["diff_json"])
        self.assertIsNone(post["raw_response"])
        self.assertIsNone(post["completed_at"])
        self.assertIsNone(post["elapsed_sec"])
        self.assertIsNone(post["model"])
        self.assertIsNone(post["error_code"])
        self.assertIsNone(post["error_message"])
        self.assertEqual(post["is_mock"], 0)
        # 답안 본문은 그대로
        self.assertEqual(post["answer_text"], "검토 의견 본문 — Step 17")

    def test_reset_done_attempt_deletes_attempt_criteria(self) -> None:
        """done → reset → attempt_criteria 9행 모두 삭제 (Step 21 v5)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())
            # 9행 있음 확인 (Step 21 v5 — case_apply 신설)
            pre_n = conn.execute(
                "SELECT count(*) AS n FROM attempt_criteria WHERE attempt_id = ?",
                (self.attempt_id,),
            ).fetchone()["n"]
            self.assertEqual(pre_n, 9)

            attempts_mod.reset_grade(conn, self.attempt_id)

            post_n = conn.execute(
                "SELECT count(*) AS n FROM attempt_criteria WHERE attempt_id = ?",
                (self.attempt_id,),
            ).fetchone()["n"]
        self.assertEqual(post_n, 0)

    def test_reset_after_inject_can_re_inject(self) -> None:
        """reset 후 다시 inject_grade 가능 (재채점 라운드 트립)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())
            attempts_mod.reset_grade(conn, self.attempt_id)
            # 다시 채점
            out = attempts_mod.inject_grade(
                conn, self.attempt_id, _full_grade_payload()
            )
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["grade"], "B")

    # ── 404 케이스 ──

    def test_reset_404_for_unknown_attempt(self) -> None:
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.AttemptNotFoundError):
                attempts_mod.reset_grade(conn, 999999)

    # ── noop 케이스 ──

    def test_reset_pending_grade_is_noop(self) -> None:
        """pending_grade → noop (이미 미채점)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            # setUp 후 바로 reset (pending_grade 상태)
            out = attempts_mod.reset_grade(conn, self.attempt_id)
            self.assertEqual(out["status"], "pending_grade")
            self.assertIn("No grade to reset", out["message"])
            # status 그대로
            row = conn.execute(
                "SELECT status, answer_text FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        self.assertEqual(row["status"], "pending_grade")
        self.assertEqual(row["answer_text"], "검토 의견 본문 — Step 17")

    def test_reset_grading_is_noop(self) -> None:
        """grading 상태 → noop (백그라운드 채점 race 방지)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            # 강제로 status='grading' 시뮬레이트
            conn.execute(
                "UPDATE attempts SET status='grading' WHERE id = ?",
                (self.attempt_id,),
            )
            conn.commit()
            out = attempts_mod.reset_grade(conn, self.attempt_id)
            self.assertEqual(out["status"], "grading")
            self.assertIn("Grading in progress", out["message"])
            # status 그대로
            row = conn.execute(
                "SELECT status FROM attempts WHERE id = ?", (self.attempt_id,)
            ).fetchone()
        self.assertEqual(row["status"], "grading")

    # ── error 케이스 — reset 허용 ──

    def test_reset_error_attempt_reverts_to_pending_grade(self) -> None:
        """error 상태 → reset → pending_grade (사용자 명시: error 도 reset 가능)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            # 강제로 status='error' + 에러 정보 시뮬레이트
            conn.execute(
                """UPDATE attempts
                      SET status='error', error_code='anthropic_rate_limit',
                          error_message='429 too many', completed_at='2026-05-16T01:00:00Z'
                    WHERE id = ?""",
                (self.attempt_id,),
            )
            conn.commit()

            out = attempts_mod.reset_grade(conn, self.attempt_id)
            self.assertEqual(out["status"], "pending_grade")
            self.assertIn("Grade reset OK", out["message"])

            row = conn.execute(
                "SELECT status, error_code, error_message, completed_at FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        self.assertEqual(row["status"], "pending_grade")
        self.assertIsNone(row["error_code"])
        self.assertIsNone(row["error_message"])
        self.assertIsNone(row["completed_at"])


if __name__ == "__main__":
    unittest.main()
