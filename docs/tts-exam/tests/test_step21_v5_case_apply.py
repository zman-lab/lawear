#!/usr/bin/env python3
"""Step 21 — 채점 기준 v5 신규 TC (case_apply 0.5점 신설 + rich 20→15).

dev-impl-plan Step 21 + 사용자 명시 2026-05-17:
- 풍부함 (rich) 가중치 20% → 15% 변경
- 사안의 경우 (case_apply) 0.5점 신설 — 정확 매칭 X, 결론+근거 적용 정도
- rich = 원본 전체 대비 (자세히 적을수록 가점, 의미 유지)

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step21_v5_case_apply.py -v
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


def _seed_case(conn: sqlite3.Connection, case_id: str = "c-step21") -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO cases (
            id, subject, subject_kor, category, file, case_no, title, path,
            points, synced_at, content_hash
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (case_id, "minbeop", "민법", "예비", "미케01", "01", "Step21 v5 Test",
         "/mock", 17, "2026-05-17T00:00:00Z", "abc"),
    )
    conn.commit()


def _seed_pending_attempt(conn: sqlite3.Connection, case_id: str = "c-step21") -> int:
    cur = conn.execute(
        """
        INSERT INTO attempts (
            case_id, answer_text, submitted_at, status, weights_json
        ) VALUES (?,?,?,?,?)
        """,
        (
            case_id,
            "user answer step 21 test",
            "2026-05-17T10:00:00Z",
            "pending_grade",
            json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _v5_payload(**overrides) -> dict:
    """v5 9키 페이로드 — 합계 100."""
    base = {
        "criteria": [
            {"key": "mnem", "score": 12.5, "weight_applied": 16, "comment": ""},
            {"key": "color", "score": 10.0, "weight_applied": 13, "comment": ""},
            {"key": "under", "score": 6.0, "weight_applied": 8, "comment": ""},
            {"key": "outline", "score": 8.0, "weight_applied": 10, "comment": ""},
            {"key": "sem", "score": 9.5, "weight_applied": 12, "comment": ""},
            {"key": "rich", "score": 11.0, "weight_applied": 15, "comment": "Step 21 — 원본 풍부함"},
            {"key": "miss", "score": -1.5, "weight_applied": 11, "comment": ""},
            {"key": "articles", "score": 7.75, "weight_applied": 10, "comment": ""},
            {"key": "case_apply", "score": 3.5, "weight_applied": 5, "comment": "사안 적용 양호 (Step 21)"},
        ],
        "total_score": 66.75,
        "max_score": 89.0,
        "score_pct": 75.0,
        "grade": "B",
        "eval_notes": {"strength": "S", "caution": "C", "missing": "M"},
    }
    base.update(overrides)
    return base


# ─── 단위: grader — v5 9키 ──────────────────────────────────────────


class GraderV5Test(unittest.TestCase):
    """grader.py v5 — case_apply 신설 + rich 20→15."""

    def test_criterion_keys_has_case_apply(self) -> None:
        """CRITERION_KEYS 9개 (mnem~articles+case_apply)."""
        self.assertIn("case_apply", grader_mod.CRITERION_KEYS)
        self.assertEqual(len(grader_mod.CRITERION_KEYS), 9)

    def test_default_weights_current_v6(self) -> None:
        """DEFAULT_WEIGHTS — Phase 4 v6 (lawear-e571, 2026-05-19).

        Historical note (Step 21 v5 → Phase 4 v6):
          v5 (2026-05-17): mnem 16/color 13/under 8/outline 10/sem 12/rich 15/miss 11/articles 10/case_apply 5
          v6 (2026-05-19): 학습 보조 23 + 답안 본질 77 = 100
        """
        expected = {
            "mnem": 10, "color": 8, "under": 5, "outline": 14,
            "sem": 15, "rich": 13, "miss": 13, "articles": 15, "case_apply": 7,
        }
        self.assertEqual(grader_mod.DEFAULT_WEIGHTS, expected)
        self.assertEqual(sum(grader_mod.DEFAULT_WEIGHTS.values()), 100)
        # v5 historical fallback 보존 검증
        v5 = {
            "mnem": 16, "color": 13, "under": 8, "outline": 10,
            "sem": 12, "rich": 15, "miss": 11, "articles": 10, "case_apply": 5,
        }
        self.assertEqual(grader_mod.DEFAULT_WEIGHTS_V5, v5)

    def test_validate_weights_v4_rejected(self) -> None:
        """v4 8키 데이터(case_apply 없음) → ValueError."""
        v4_weights = {
            "mnem": 16, "color": 13, "under": 8, "outline": 10,
            "sem": 12, "rich": 20, "miss": 11, "articles": 10,
        }  # 합=100 (v4)
        self.assertEqual(sum(v4_weights.values()), 100)
        with self.assertRaises(ValueError) as ctx:
            grader_mod.validate_weights(v4_weights)
        self.assertIn("case_apply", str(ctx.exception))

    def test_validate_weights_v5_accepted(self) -> None:
        """v5 9키 + sum=100 → 통과."""
        grader_mod.validate_weights(grader_mod.DEFAULT_WEIGHTS)

    def test_validate_weights_rich_not_20(self) -> None:
        """rich=20 + case_apply 미존재 → 키 누락 에러 (v5 명시 변경)."""
        bad = {
            "mnem": 16, "color": 13, "under": 8, "outline": 10,
            "sem": 12, "rich": 20, "miss": 11, "articles": 10,
            # case_apply 누락
        }
        with self.assertRaises(ValueError):
            grader_mod.validate_weights(bad)

    def test_grade_mock_case_apply_in_response(self) -> None:
        """mock 응답에 case_apply criterion 포함."""
        case = {
            "id": "step21_test",
            "subject_kor": "민법",
            "category": "테스트",
            "file": "test",
            "case_no": "01",
            "title": "테스트",
            "points": 10,
            "md_body": "## 원본\n[red]제397조[/red] 손해배상.",
        }
        result = grader_mod.grade(case, "답안", force_mock=True)
        keys = [c["key"] for c in result["criteria"]]
        self.assertIn("case_apply", keys)
        self.assertEqual(len(keys), 9)


# ─── 단위: settings — v5 9키 검증 ───────────────────────────────────


class SettingsV5Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_load_all_returns_v6_weights(self) -> None:
        """신규 DB → weights 9키 (Phase 4 v6 — 학습보조 23 + 답안본질 77)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            data = settings_mod.load_all(conn)
        self.assertEqual(len(data["weights"]), 9)
        self.assertIn("case_apply", data["weights"])
        # v6 값 (case_apply 5→7, rich 15→13, articles 10→15)
        self.assertEqual(data["weights"]["case_apply"], 7)
        self.assertEqual(data["weights"]["rich"], 13)
        self.assertEqual(data["weights"]["articles"], 15)

    def test_save_v4_weights_rejected(self) -> None:
        """PUT v4 8키 → SettingsValidationError(weights_invalid)."""
        v4_weights = {
            "mnem": 16, "color": 13, "under": 8, "outline": 10,
            "sem": 12, "rich": 20, "miss": 11, "articles": 10,
        }
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(settings_mod.SettingsValidationError) as ctx:
                settings_mod.save_settings(conn, weights=v4_weights)
        self.assertEqual(ctx.exception.error_code, "weights_invalid")
        self.assertIn("case_apply", str(ctx.exception))

    def test_save_v5_weights_accepted(self) -> None:
        """PUT v5 9키 → 저장 + load_all 일치."""
        v5_custom = {
            "mnem": 20, "color": 14, "under": 8, "outline": 10,
            "sem": 11, "rich": 14, "miss": 8, "articles": 10, "case_apply": 5,
        }
        self.assertEqual(sum(v5_custom.values()), 100)
        with db_mod.get_conn(self.tmp.name) as conn:
            settings_mod.save_settings(conn, weights=v5_custom)
            data = settings_mod.load_all(conn)
        self.assertEqual(data["weights"], v5_custom)


# ─── 단위: attempts — 9키 inject ─────────────────────────────────────


class AttemptsInjectV5Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_case(conn)
            self.attempt_id = _seed_pending_attempt(conn)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_inject_grade_9_criteria_saved(self) -> None:
        """9기준 모두 DB attempt_criteria row 생성 (Step 21 v5)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, _v5_payload())
            self.assertEqual(len(out["criteria"]), 9)
            rows = conn.execute(
                "SELECT criterion_key FROM attempt_criteria WHERE attempt_id = ?",
                (self.attempt_id,),
            ).fetchall()
            keys = sorted(r["criterion_key"] for r in rows)
        expected = sorted(["mnem", "color", "under", "outline", "sem",
                           "rich", "miss", "articles", "case_apply"])
        self.assertEqual(keys, expected)

    def test_inject_grade_v4_payload_rejected(self) -> None:
        """v4 8키 페이로드 → GradeInjectionError (case_apply 누락)."""
        payload = _v5_payload()
        payload["criteria"] = [c for c in payload["criteria"] if c["key"] != "case_apply"]
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
                attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertIn("case_apply", str(ctx.exception))

    def test_inject_grade_case_apply_aliases(self) -> None:
        """case_apply 외 'case_application' alias 도 허용."""
        payload = _v5_payload()
        for c in payload["criteria"]:
            if c["key"] == "case_apply":
                c["key"] = "case_application"
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertEqual(out["status"], "completed")
        # DB에는 짧은 이름 'case_apply' 로 저장
        with db_mod.get_conn(self.tmp.name) as conn:
            rows = conn.execute(
                "SELECT criterion_key FROM attempt_criteria WHERE attempt_id = ? AND criterion_key = 'case_apply'",
                (self.attempt_id,),
            ).fetchall()
        self.assertEqual(len(rows), 1)


# ─── 단위: db — 마이그 v5 ─────────────────────────────────────────────


class MigrationV5Test(unittest.TestCase):
    def test_target_schema_version_is_5(self) -> None:
        self.assertGreaterEqual(db_mod.TARGET_SCHEMA_VERSION, 5)

    def test_migrations_dict_has_v5(self) -> None:
        self.assertIn(5, db_mod.MIGRATIONS)
        path = db_mod.MIGRATIONS_DIR / db_mod.MIGRATIONS[5]
        self.assertTrue(path.is_file(), f"migration v5 SQL not found at {path}")

    def test_fresh_db_at_v6(self) -> None:
        """신규 DB init → user_version >= 7 + weights v6 디폴트 (Phase 4)."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            v = db_mod.init_db(tmp.name)
            self.assertGreaterEqual(v, 7)
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT value_json FROM settings WHERE key = 'weights'"
            ).fetchone()
            conn.close()
            w = json.loads(row["value_json"])
            # v6 디폴트 (Phase 4) — case_apply 5→7, rich 15→13, articles 10→15
            self.assertEqual(w["rich"], 13)
            self.assertEqual(w["case_apply"], 7)
            self.assertEqual(w["articles"], 15)
            self.assertEqual(len(w), 9)
            self.assertEqual(sum(w.values()), 100)
        finally:
            os.unlink(tmp.name)

    def test_attempt_criteria_check_accepts_case_apply(self) -> None:
        """attempt_criteria.criterion_key CHECK enum 에 case_apply 포함."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db_mod.init_db(tmp.name)
            with db_mod.get_conn(tmp.name) as conn:
                _seed_case(conn)
                aid = _seed_pending_attempt(conn)
                # 직접 INSERT — CHECK enum 통과 검증
                conn.execute(
                    """INSERT INTO attempt_criteria (attempt_id, criterion_key, score, max_score, weight, comment)
                       VALUES (?, 'case_apply', 3.0, 5.0, 5.0, 'test')""",
                    (aid,),
                )
                conn.commit()
                n = conn.execute(
                    "SELECT count(*) FROM attempt_criteria WHERE criterion_key = 'case_apply'"
                ).fetchone()[0]
            self.assertEqual(n, 1)
        finally:
            os.unlink(tmp.name)


# ─── 단위: reports — 9키 ─────────────────────────────────────────────


class ReportsV5Test(unittest.TestCase):
    def test_criterion_order_9_keys(self) -> None:
        self.assertEqual(len(reports_mod.CRITERION_ORDER), 9)
        self.assertIn("case_apply", reports_mod.CRITERION_ORDER)
        # 정렬 위치: articles 와 rich 사이
        order = list(reports_mod.CRITERION_ORDER)
        self.assertLess(order.index("articles"), order.index("case_apply"))
        self.assertLess(order.index("case_apply"), order.index("rich"))


if __name__ == "__main__":
    unittest.main()
