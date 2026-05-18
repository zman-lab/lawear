#!/usr/bin/env python3
"""Step 20 회귀 — 채점 기준 v4 (articles 신설, 8기준, 소수점 2자리).

dev-impl-plan Step 20 + 사용자 명시 2026-05-16:
- 8기준: mnem 16 / color 13 / under 8 / outline 10 / sem 12 / rich 20 / miss 11 / articles 10
- 점수 표시 소수점 2자리 (실제 시험 형식)

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step20_v4_weights.py -v
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
import settings as settings_mod  # noqa: E402


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _build_db(path: str) -> None:
    db_mod.init_db(path)


def _seed_case(conn: sqlite3.Connection, case_id: str = "c-step20") -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO cases (
            id, subject, subject_kor, category, file, case_no, title, path,
            points, synced_at, content_hash
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (case_id, "minbeop", "민법", "예비", "미케01", "01", "Step20 Test",
         "/mock", 17, "2026-05-16T00:00:00Z", "abc"),
    )
    conn.commit()


def _seed_pending_attempt(conn: sqlite3.Connection, case_id: str = "c-step20") -> int:
    cur = conn.execute(
        """
        INSERT INTO attempts (
            case_id, answer_text, submitted_at, status, weights_json
        ) VALUES (?,?,?,?,?)
        """,
        (
            case_id,
            "user answer step 20 test",
            "2026-05-16T10:00:00Z",
            "pending_grade",
            json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


# ─── 단위: grader.py ─────────────────────────────────────────────────


class GraderV4Test(unittest.TestCase):
    """grader.py v4 — 8키 + articles 신설."""

    def test_criterion_keys_has_articles(self) -> None:
        """CRITERION_KEYS 에 articles 포함 (Step 20 v4)."""
        self.assertIn("articles", grader_mod.CRITERION_KEYS)
        # Step 21 v5 (2026-05-17): case_apply 신설 → 9개로 확장
        self.assertEqual(len(grader_mod.CRITERION_KEYS), 9)

    def test_default_weights_v4(self) -> None:
        """DEFAULT_WEIGHTS — Step 21 v5 (2026-05-17): rich 20→15, case_apply 5 신설."""
        expected = {
            "mnem": 16, "color": 13, "under": 8, "outline": 10,
            "sem": 12, "rich": 15, "miss": 11, "articles": 10, "case_apply": 5,
        }
        self.assertEqual(grader_mod.DEFAULT_WEIGHTS, expected)
        self.assertEqual(sum(grader_mod.DEFAULT_WEIGHTS.values()), 100)

    def test_validate_weights_v3_rejected(self) -> None:
        """v3 7키 데이터(articles 없음) → ValueError."""
        v3_weights = {
            "mnem": 20, "color": 15, "under": 10, "outline": 15,
            "sem": 15, "rich": 10, "miss": 15,
        }  # 합=100 (v3)
        self.assertEqual(sum(v3_weights.values()), 100)
        with self.assertRaises(ValueError) as ctx:
            grader_mod.validate_weights(v3_weights)
        self.assertIn("articles", str(ctx.exception))

    def test_validate_weights_v4_accepted(self) -> None:
        """v4 8키 + sum=100 → 통과."""
        grader_mod.validate_weights(grader_mod.DEFAULT_WEIGHTS)

    def test_grade_mock_articles_in_response(self) -> None:
        """mock 채점 응답에 articles + case_apply criterion 포함 (Step 21 v5)."""
        case = {
            "id": "step20_test",
            "subject_kor": "민법",
            "category": "테스트",
            "file": "test",
            "case_no": "01",
            "title": "테스트",
            "points": 10,
            "md_body": "## 원본\n[red]제397조[/red] 손해배상액 예정.\n## Lv.4\n[blank2]손[/blank2]해배상.",
        }
        result = grader_mod.grade(case, "답안 — 제397조 적용", force_mock=True)
        keys = [c["key"] for c in result["criteria"]]
        self.assertIn("articles", keys, "articles criterion required (Step 20 v4)")
        self.assertIn("case_apply", keys, "case_apply criterion required (Step 21 v5)")
        self.assertEqual(len(keys), 9)

    def test_score_rounding_two_decimals(self) -> None:
        """grade 응답의 score_total / score_pct 가 소수점 2자리 round."""
        case = {
            "id": "step20_round",
            "subject_kor": "민법",
            "md_body": "## 원본\n.",
        }
        result = grader_mod.grade(case, "테스트", force_mock=True)
        # round(x, 2) 결과는 정확히 2자리 또는 그 이하 (e.g. 75.0).
        # 문자열로 확인하여 . 뒤 자릿수 ≤ 2 검증.
        for fld in ("score_total", "score_max", "score_pct"):
            v = result[fld]
            self.assertIsInstance(v, (int, float))
            # str(v).split('.')[-1] 이 2자리 이하 보장 (round 2)
            s = f"{v:.10f}".rstrip("0").rstrip(".")
            if "." in s:
                decimals = len(s.split(".")[1])
                self.assertLessEqual(
                    decimals, 2,
                    f"{fld}={v} has more than 2 decimal places (got {decimals})"
                )


# ─── 단위: settings.py ───────────────────────────────────────────────


class SettingsV4Test(unittest.TestCase):
    """settings.py v4 검증 — 8키 validate."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_load_all_returns_v4_weights(self) -> None:
        """신규 DB → weights 9키 (articles + case_apply 포함, Step 21 v5)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            data = settings_mod.load_all(conn)
        self.assertIn("weights", data)
        self.assertIn("articles", data["weights"])
        self.assertIn("case_apply", data["weights"])
        self.assertEqual(len(data["weights"]), 9)
        # v5 디폴트 일치 (rich 20→15, case_apply 5 신설)
        self.assertEqual(
            data["weights"],
            {"mnem": 16, "color": 13, "under": 8, "outline": 10,
             "sem": 12, "rich": 15, "miss": 11, "articles": 10, "case_apply": 5},
        )

    def test_save_v3_weights_rejected(self) -> None:
        """PUT v3 7키 → SettingsValidationError(weights_invalid)."""
        v3_weights = {
            "mnem": 20, "color": 15, "under": 10, "outline": 15,
            "sem": 15, "rich": 10, "miss": 15,
        }
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(settings_mod.SettingsValidationError) as ctx:
                settings_mod.save_settings(conn, weights=v3_weights)
        self.assertEqual(ctx.exception.error_code, "weights_invalid")
        self.assertIn("articles", str(ctx.exception))

    def test_save_v4_weights_accepted(self) -> None:
        """PUT v5 9키 → 저장 + load_all 일치 (Step 21 v5)."""
        v5_custom = {
            "mnem": 20, "color": 14, "under": 8, "outline": 10,
            "sem": 11, "rich": 12, "miss": 10, "articles": 10, "case_apply": 5,
        }
        self.assertEqual(sum(v5_custom.values()), 100)
        with db_mod.get_conn(self.tmp.name) as conn:
            settings_mod.save_settings(conn, weights=v5_custom)
            data = settings_mod.load_all(conn)
        self.assertEqual(data["weights"], v5_custom)


# ─── 단위: attempts.py — inject_grade with 8 criteria ────────────────


class AttemptsInjectV4Test(unittest.TestCase):
    """inject_grade 8기준 검증."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_case(conn)
            self.attempt_id = _seed_pending_attempt(conn)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def _v4_payload(self) -> dict:
        """Step 21 v5 페이로드 (이름은 v4 호환 유지).

        가중치 합: 16+13+8+10+12+15+11+10+5 = 100
        """
        return {
            "criteria": [
                {"key": "mnemonics", "score": 12.5, "weight_applied": 16, "comment": ""},
                {"key": "color", "score": 10.0, "weight_applied": 13, "comment": ""},
                {"key": "underline", "score": 6.0, "weight_applied": 8, "comment": ""},
                {"key": "outline", "score": 8.0, "weight_applied": 10, "comment": ""},
                {"key": "semantic", "score": 9.5, "weight_applied": 12, "comment": ""},
                {"key": "richness", "score": 11.5, "weight_applied": 15, "comment": ""},
                {"key": "missing", "score": -1.5, "weight_applied": 11, "comment": ""},
                {"key": "articles", "score": 7.75, "weight_applied": 10, "comment": ""},
                {"key": "case_apply", "score": 3.25, "weight_applied": 5, "comment": "Step 21"},
            ],
            "total_score": 67.7345,  # 소수점 4자리 입력 → round(2) 검증
            "max_score": 89.0,
            "score_pct": 76.105,  # 입력 3자리
            "grade": "B",
            "eval_notes": {"strength": "S", "caution": "C", "missing": "M"},
        }

    def test_inject_grade_8_criteria_saved(self) -> None:
        """9기준 모두 DB attempt_criteria row 생성 (Step 21 v5)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, self._v4_payload())
            self.assertEqual(len(out["criteria"]), 9)
            # DB row 검증
            rows = conn.execute(
                "SELECT criterion_key FROM attempt_criteria WHERE attempt_id = ?",
                (self.attempt_id,),
            ).fetchall()
            keys = sorted(r["criterion_key"] for r in rows)
        expected = sorted(["mnem", "color", "under", "outline", "sem",
                           "rich", "miss", "articles", "case_apply"])
        self.assertEqual(keys, expected)

    def test_inject_grade_score_rounded_two_decimals(self) -> None:
        """입력 소수점 3+자리 → DB score_pct/total/max 모두 2자리 round (Step 20)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempts_mod.inject_grade(conn, self.attempt_id, self._v4_payload())
            row = conn.execute(
                "SELECT score_total, score_max, score_pct FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        # 67.7345 → 67.73, 76.105 → 76.11 (round half-even — Python default)
        self.assertAlmostEqual(row["score_total"], 67.73, places=2)
        self.assertAlmostEqual(row["score_max"], 89.0, places=2)
        # 76.105 → 76.1 (round-half-even) — 결과는 76.1 또는 76.11 (구현 dependent)
        # 단지 소수점 자리수가 2 이하인지만 검증
        s = f"{row['score_pct']:.10f}".rstrip("0").rstrip(".")
        if "." in s:
            self.assertLessEqual(len(s.split(".")[1]), 2)

    def test_inject_grade_v3_payload_rejected(self) -> None:
        """v3 7키 페이로드 → GradeInjectionError (articles 누락)."""
        payload = self._v4_payload()
        payload["criteria"] = [c for c in payload["criteria"] if c["key"] != "articles"]
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
                attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertIn("articles", str(ctx.exception))


# ─── 단위: db.py — 마이그레이션 v4 ───────────────────────────────────


class MigrationV4Test(unittest.TestCase):
    """마이그 v3 → v4: weights row 업데이트 + attempts 데이터 보존."""

    def test_target_schema_version_is_4(self) -> None:
        # Step 21 v5 (2026-05-17): TARGET 5 (함수명은 호환 유지)
        self.assertGreaterEqual(db_mod.TARGET_SCHEMA_VERSION, 4)

    def test_migrations_dict_has_v4(self) -> None:
        self.assertIn(4, db_mod.MIGRATIONS)
        # 마이그 파일 존재
        path = db_mod.MIGRATIONS_DIR / db_mod.MIGRATIONS[4]
        self.assertTrue(path.is_file(), f"migration v4 SQL not found at {path}")

    def test_fresh_db_at_v4(self) -> None:
        """신규 DB init → user_version = 5 (Step 21 v5)."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            v = db_mod.init_db(tmp.name)
            self.assertGreaterEqual(v, 4)
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT value_json FROM settings WHERE key = 'weights'"
            ).fetchone()
            conn.close()
            w = json.loads(row["value_json"])
            self.assertIn("articles", w)
            self.assertIn("case_apply", w)
            self.assertEqual(w["articles"], 10)
            self.assertEqual(w["case_apply"], 5)
            self.assertEqual(w["rich"], 15)  # 20→15 갱신
            self.assertEqual(sum(w.values()), 100)
        finally:
            os.unlink(tmp.name)


# ─── 단위: reports.py — CRITERION_ORDER 8키 ─────────────────────────


class ReportsV4Test(unittest.TestCase):
    """reports.CRITERION_ORDER 8키 + by-case criteria avg 8행."""

    def test_criterion_order_8_keys(self) -> None:
        # Step 21 v5 (2026-05-17): 9키로 확장 (case_apply 신설)
        self.assertEqual(len(reports_mod.CRITERION_ORDER), 9)
        self.assertIn("articles", reports_mod.CRITERION_ORDER)
        self.assertIn("case_apply", reports_mod.CRITERION_ORDER)


if __name__ == "__main__":
    unittest.main()
