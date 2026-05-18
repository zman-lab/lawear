#!/usr/bin/env python3
"""Phase 4 — 9키 가중치 v6 재조정 TC (lawear-e571, 2026-05-19).

[배경]
사용자 자체 채점이 더 엄격 (자체 58 vs 기존 63, articles 4→2).
v5 (학습보조 37 + 답안본질 63) → v6 (학습보조 23 + 답안본질 77) 무게 이동.

[v6 가중치]
학습 보조 (낮춤, 합 23):
  - mnem    16 → 10
  - color   13 →  8
  - under    8 →  5
답안 본질 (높임, 합 77):
  - outline 10 → 14
  - sem     12 → 15
  - rich    15 → 13 (본질 우선이라 약간 낮춤)
  - miss    11 → 13
  - articles 10 → 15
  - case_apply 5 →  7
  → 합 = 100

[중요]
- 기존 attempts 점수는 그대로 (마이그 X — 사용자 명시)
- 신규 채점만 v6 사용
- v5 가중치는 DEFAULT_WEIGHTS_V5 fallback 으로 보존
- settings.weights_version 키 신설 (default 6)

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_phase4_weights_v6.py -v
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
import settings as settings_mod  # noqa: E402


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _build_db(path: str) -> None:
    db_mod.init_db(path)


# ─── 단위: grader.py — v6 default ───────────────────────────────────


class GraderV6DefaultTest(unittest.TestCase):
    """grader.DEFAULT_WEIGHTS v6 + DEFAULT_WEIGHTS_V5 fallback."""

    def test_v6_default_weights_values(self) -> None:
        """v6 가중치 — 학습 보조 23 + 답안 본질 77 = 100."""
        expected_v6 = {
            "mnem": 10, "color": 8, "under": 5, "outline": 14,
            "sem": 15, "rich": 13, "miss": 13, "articles": 15, "case_apply": 7,
        }
        self.assertEqual(grader_mod.DEFAULT_WEIGHTS, expected_v6)
        self.assertEqual(grader_mod.DEFAULT_WEIGHTS_V6, expected_v6)
        self.assertEqual(sum(grader_mod.DEFAULT_WEIGHTS_V6.values()), 100)
        # 학습 보조 합 = 23 (mnem 10 + color 8 + under 5)
        self.assertEqual(
            sum(grader_mod.DEFAULT_WEIGHTS_V6[k] for k in ("mnem", "color", "under")),
            23,
        )
        # 답안 본질 합 = 77
        body_keys = ("outline", "sem", "rich", "miss", "articles", "case_apply")
        self.assertEqual(
            sum(grader_mod.DEFAULT_WEIGHTS_V6[k] for k in body_keys),
            77,
        )

    def test_v5_default_weights_preserved(self) -> None:
        """v5 가중치는 DEFAULT_WEIGHTS_V5 으로 fallback 보존."""
        expected_v5 = {
            "mnem": 16, "color": 13, "under": 8, "outline": 10,
            "sem": 12, "rich": 15, "miss": 11, "articles": 10, "case_apply": 5,
        }
        self.assertEqual(grader_mod.DEFAULT_WEIGHTS_V5, expected_v5)
        self.assertEqual(sum(grader_mod.DEFAULT_WEIGHTS_V5.values()), 100)

    def test_v5_v6_distinct(self) -> None:
        """v5 와 v6 가 서로 다른 dict (참조 분리)."""
        self.assertNotEqual(
            grader_mod.DEFAULT_WEIGHTS_V5,
            grader_mod.DEFAULT_WEIGHTS_V6,
        )
        # 같은 객체 참조도 X
        self.assertIsNot(
            grader_mod.DEFAULT_WEIGHTS,
            grader_mod.DEFAULT_WEIGHTS_V5,
        )
        self.assertIsNot(
            grader_mod.DEFAULT_WEIGHTS_V6,
            grader_mod.DEFAULT_WEIGHTS_V5,
        )

    def test_v6_version_constants(self) -> None:
        """버전 상수 — WEIGHTS_VERSION_V5/V6 + DEFAULT_WEIGHTS_VERSION."""
        self.assertEqual(grader_mod.WEIGHTS_VERSION_V5, 5)
        self.assertEqual(grader_mod.WEIGHTS_VERSION_V6, 6)
        self.assertEqual(grader_mod.DEFAULT_WEIGHTS_VERSION, 6)

    def test_v6_weights_validate_passes(self) -> None:
        """v6 가중치 validate_weights 통과."""
        grader_mod.validate_weights(grader_mod.DEFAULT_WEIGHTS_V6)

    def test_v5_weights_validate_passes(self) -> None:
        """v5 가중치도 여전히 validate_weights 통과 (fallback)."""
        grader_mod.validate_weights(grader_mod.DEFAULT_WEIGHTS_V5)


# ─── 단위: settings.py — weights_version 키 ─────────────────────────


class SettingsWeightsVersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_load_weights_version_default_v6(self) -> None:
        """신규 DB init → weights_version = 6."""
        with db_mod.get_conn(self.tmp.name) as conn:
            v = settings_mod.load_weights_version(conn)
        self.assertEqual(v, 6)

    def test_load_all_includes_weights_version(self) -> None:
        """load_all 응답에 weights_version 키 포함."""
        with db_mod.get_conn(self.tmp.name) as conn:
            data = settings_mod.load_all(conn)
        self.assertIn("weights_version", data)
        self.assertEqual(data["weights_version"], 6)

    def test_validate_weights_version_int(self) -> None:
        """validate_weights_version — 정상 int 통과."""
        self.assertEqual(settings_mod.validate_weights_version(6), 6)
        self.assertEqual(settings_mod.validate_weights_version("7"), 7)

    def test_validate_weights_version_invalid(self) -> None:
        """0 / 음수 / 잘못된 타입 → bad_request."""
        with self.assertRaises(settings_mod.SettingsValidationError):
            settings_mod.validate_weights_version(0)
        with self.assertRaises(settings_mod.SettingsValidationError):
            settings_mod.validate_weights_version(-1)
        with self.assertRaises(settings_mod.SettingsValidationError):
            settings_mod.validate_weights_version(None)
        with self.assertRaises(settings_mod.SettingsValidationError):
            settings_mod.validate_weights_version(True)

    def test_save_settings_weights_version(self) -> None:
        """save_settings 에 weights_version 전달 시 저장 + load 일치."""
        with db_mod.get_conn(self.tmp.name) as conn:
            settings_mod.save_settings(conn, weights_version=7)
            data = settings_mod.load_all(conn)
        self.assertEqual(data["weights_version"], 7)

    def test_save_v5_weights_with_version_5(self) -> None:
        """v5 weights + version=5 명시 저장 (호환 시나리오)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            settings_mod.save_settings(
                conn,
                weights=dict(grader_mod.DEFAULT_WEIGHTS_V5),
                weights_version=5,
            )
            data = settings_mod.load_all(conn)
        self.assertEqual(data["weights_version"], 5)
        self.assertEqual(data["weights"], grader_mod.DEFAULT_WEIGHTS_V5)


# ─── 통합: 마이그 v7 — settings.weights v6 + weights_version row ────


class MigrationV7Test(unittest.TestCase):
    def test_target_schema_version_is_7(self) -> None:
        """db.TARGET_SCHEMA_VERSION = 7 (Phase 4)."""
        self.assertGreaterEqual(db_mod.TARGET_SCHEMA_VERSION, 7)

    def test_migrations_v7_file_exists(self) -> None:
        """007_v6_weights.sql 파일 존재."""
        self.assertIn(7, db_mod.MIGRATIONS)
        path = db_mod.MIGRATIONS_DIR / db_mod.MIGRATIONS[7]
        self.assertTrue(path.is_file(), f"migration v7 SQL not found at {path}")

    def test_fresh_db_v6_weights_in_db(self) -> None:
        """신규 DB → settings.weights row 가 v6 값으로 INSERT."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            v = db_mod.init_db(tmp.name)
            self.assertGreaterEqual(v, 7)
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
            # weights row 검증
            row_w = conn.execute(
                "SELECT value_json FROM settings WHERE key = 'weights'"
            ).fetchone()
            self.assertIsNotNone(row_w)
            w = json.loads(row_w["value_json"])
            # v6 값 검증
            self.assertEqual(w["mnem"], 10)
            self.assertEqual(w["articles"], 15)
            self.assertEqual(w["case_apply"], 7)
            # weights_version row 검증
            row_v = conn.execute(
                "SELECT value_json FROM settings WHERE key = 'weights_version'"
            ).fetchone()
            self.assertIsNotNone(row_v)
            self.assertEqual(json.loads(row_v["value_json"]), 6)
            conn.close()
        finally:
            os.unlink(tmp.name)


# ─── 통합: 기존 attempts 미터치 (마이그 X) ─────────────────────────


class LegacyAttemptsPreservedTest(unittest.TestCase):
    """v7 마이그 적용 후에도 기존 attempts.weights_json/score 미터치 검증."""

    def test_pre_existing_v5_attempt_preserved(self) -> None:
        """v5 가중치로 저장된 기존 attempt 의 weights_json/score 모두 변경 X."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            # v7 마이그 적용 (신규 DB)
            db_mod.init_db(tmp.name)
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            # case + v5 weights 기존 attempt 시뮬레이션
            conn.execute(
                """INSERT INTO cases (id, subject, subject_kor, category, file, case_no, title, path, points, synced_at, content_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                ("c-legacy-v5", "minbeop", "민법", "예비", "legacy", "01", "Legacy V5",
                 "/mock", 17, "2026-05-17T00:00:00Z", "abc"),
            )
            v5_json = json.dumps(grader_mod.DEFAULT_WEIGHTS_V5, ensure_ascii=False)
            conn.execute(
                """INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json,
                                          score_total, score_max, score_pct, grade)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                ("c-legacy-v5", "legacy answer", "2026-05-17T10:00:00Z", "done",
                 v5_json, 65.0, 89.0, 73.0, "B"),
            )
            conn.commit()
            # 다시 init_db (멱등 — 이미 v7) → attempts 미터치 검증
            db_mod.init_db(tmp.name)
            row = conn.execute(
                "SELECT weights_json, score_total, score_max, score_pct, grade FROM attempts WHERE case_id = ?",
                ("c-legacy-v5",),
            ).fetchone()
            saved_weights = json.loads(row["weights_json"])
            # v5 가중치 그대로 — v6 으로 변경 X
            self.assertEqual(saved_weights, grader_mod.DEFAULT_WEIGHTS_V5)
            # score 도 그대로
            self.assertEqual(row["score_total"], 65.0)
            self.assertEqual(row["score_max"], 89.0)
            self.assertEqual(row["grade"], "B")
            conn.close()
        finally:
            os.unlink(tmp.name)


# ─── 통합: grader._build_prompt — v6 weights JSON serialize ────────


class BuildPromptV6Test(unittest.TestCase):
    def test_build_prompt_default_weights_v6_in_user_message(self) -> None:
        """_build_prompt 호출 시 user_message 에 v6 가중치 값 직렬화."""
        case = {
            "id": "phase4_test",
            "subject_kor": "민법",
            "category": "테스트",
            "file": "test",
            "case_no": "01",
            "title": "Phase 4 V6 Test",
            "points": 10,
            "md_body": "## 원본\n테스트.",
        }
        _, user = grader_mod._build_prompt(case, "답안", grader_mod.DEFAULT_WEIGHTS)
        # v6 가중치 mnem=10, articles=15 가 user_message 에 노출
        weights_json = json.loads(
            user.split("[가중치]")[1].strip().split("\n위 채점")[0].strip()
        )
        self.assertEqual(weights_json["mnem"], 10)
        self.assertEqual(weights_json["articles"], 15)
        self.assertEqual(weights_json["case_apply"], 7)


if __name__ == "__main__":
    unittest.main()
