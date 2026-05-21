"""eval_notes.typo_corrections 키 — 정규화 + 저장/조회 round-trip.

lawear-e571/typo-system (2026-05-19).
8번째 확장 키 — list[dict] | None. legacy attempts (키 없음) graceful.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import attempts as attempts_mod  # noqa: E402
import db as db_mod  # noqa: E402


# ─── 1. _normalize_eval_notes 직접 검증 ─────────────────────────────────


class TestNormalizeEvalNotesTypoCorrections(unittest.TestCase):
    """_normalize_eval_notes — typo_corrections 키 처리."""

    def test_typo_corrections_none_normalizes_to_none(self):
        """typo_corrections=None → None 보존."""
        notes = attempts_mod._normalize_eval_notes({"typo_corrections": None})
        self.assertIsNone(notes["typo_corrections"])

    def test_typo_corrections_missing_key_defaults_to_none(self):
        """typo_corrections 키 없으면 None (legacy graceful)."""
        notes = attempts_mod._normalize_eval_notes({"strength": "x"})
        self.assertIn("typo_corrections", notes)
        self.assertIsNone(notes["typo_corrections"])

    def test_typo_corrections_empty_list_normalizes_to_none(self):
        """빈 list → None (UI 분기 단순화)."""
        notes = attempts_mod._normalize_eval_notes({"typo_corrections": []})
        self.assertIsNone(notes["typo_corrections"])

    def test_typo_corrections_valid_list_preserved(self):
        """정상 list[dict] 보존."""
        input_list = [
            {"from": "파산관제인", "to": "파산관재인", "reason": "음성 STT 오타"},
            {"from": "통정표시", "to": "통정허위표시", "reason": "법률 용어"},
        ]
        notes = attempts_mod._normalize_eval_notes({"typo_corrections": input_list})
        self.assertEqual(len(notes["typo_corrections"]), 2)
        self.assertEqual(notes["typo_corrections"][0]["from"], "파산관제인")
        self.assertEqual(notes["typo_corrections"][0]["to"], "파산관재인")
        self.assertEqual(notes["typo_corrections"][1]["from"], "통정표시")

    def test_typo_corrections_missing_required_keys_wraps_strings(self):
        """str 항목 → {from, to:'', reason:''} graceful wrap."""
        notes = attempts_mod._normalize_eval_notes({
            "typo_corrections": ["문자열 항목"]
        })
        self.assertEqual(len(notes["typo_corrections"]), 1)
        self.assertEqual(notes["typo_corrections"][0]["from"], "문자열 항목")
        self.assertEqual(notes["typo_corrections"][0]["to"], "")
        self.assertEqual(notes["typo_corrections"][0]["reason"], "")

    def test_typo_corrections_preserves_extra_keys(self):
        """추가 키 (source/severity) 보존 — R-09 가공 X."""
        input_list = [
            {"from": "아기", "to": "악의", "reason": "음성", "source": "static_dict", "severity": "high"},
        ]
        notes = attempts_mod._normalize_eval_notes({"typo_corrections": input_list})
        item = notes["typo_corrections"][0]
        self.assertEqual(item["from"], "아기")
        self.assertEqual(item["to"], "악의")
        self.assertEqual(item["source"], "static_dict")
        self.assertEqual(item["severity"], "high")

    def test_typo_corrections_dict_input_raises(self):
        """dict (list 아닌) 입력 → GradeInjectionError."""
        with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
            attempts_mod._normalize_eval_notes({"typo_corrections": {"key": "value"}})
        self.assertIn("typo_corrections", str(ctx.exception))

    def test_typo_corrections_string_input_raises(self):
        """str 입력 → GradeInjectionError."""
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes({"typo_corrections": "단일 문자열"})

    def test_typo_corrections_int_input_raises(self):
        """int 입력 → GradeInjectionError."""
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes({"typo_corrections": 42})

    def test_typo_corrections_empty_from_filtered(self):
        """from=빈문자 → skip (의미 없음)."""
        notes = attempts_mod._normalize_eval_notes({
            "typo_corrections": [
                {"from": "", "to": "X", "reason": "y"},  # skip
                {"from": "정상", "to": "Y", "reason": "z"},
            ]
        })
        self.assertEqual(len(notes["typo_corrections"]), 1)
        self.assertEqual(notes["typo_corrections"][0]["from"], "정상")


# ─── 2. 다른 eval_notes 키와 공존 검증 ──────────────────────────────────


class TestEvalNotesTypoCorrectionsCoexist(unittest.TestCase):
    """typo_corrections 와 기존 7개 키 동시 사용."""

    def test_all_keys_present_normalized(self):
        """8개 확장 키 모두 포함 → 모두 정규화 후 보존."""
        raw = {
            "strength": "강점",
            "caution": "주의",
            "missing": "누락",
            "score_summary": "요약",
            "strengths": ["a", "b"],
            "weaknesses": ["c"],
            "missing_critical": [{"item": "d", "expected_score_impact": -2}],
            "next_study_oneliner": "💡 학습",
            "next_study_actionable": ["액션1"],
            "pattern_warning": "🔥 반복",
            "typo_corrections": [{"from": "오타", "to": "정정", "reason": "STT"}],
        }
        notes = attempts_mod._normalize_eval_notes(raw)
        # 모든 키 보존
        for k in ["strength", "caution", "missing", "score_summary", "strengths",
                  "weaknesses", "missing_critical", "next_study_oneliner",
                  "next_study_actionable", "pattern_warning", "typo_corrections"]:
            self.assertIn(k, notes, f"키 {k} 누락")
        self.assertEqual(notes["typo_corrections"][0]["from"], "오타")
        self.assertEqual(notes["pattern_warning"], "🔥 반복")

    def test_pattern_warning_typo_corrections_independent(self):
        """pattern_warning + typo_corrections 동시 None 가능."""
        notes = attempts_mod._normalize_eval_notes({})
        self.assertIsNone(notes["pattern_warning"])
        self.assertIsNone(notes["typo_corrections"])


# ─── 3. _EVAL_NOTES_KEYS 통합 검증 ───────────────────────────────────────


class TestEvalNotesKeysTuple(unittest.TestCase):
    """_EVAL_NOTES_KEYS 에 typo_corrections 포함."""

    def test_typo_corrections_in_eval_notes_keys(self):
        """통합 키 튜플에 typo_corrections 포함."""
        self.assertIn("typo_corrections", attempts_mod._EVAL_NOTES_KEYS)

    def test_typo_corrections_in_opt_list_keys(self):
        """OPT_LIST 그룹에 typo_corrections 포함."""
        self.assertIn("typo_corrections", attempts_mod._EVAL_NOTES_KEYS_EXT_OPT_LIST)

    def test_total_keys_count_15(self):
        """총 15개 키 — Phase 1 (11) + 옵션 C 4 (inline_comments, gap_roadmap,
        judge_quote, lecturer_quote).

        분해: legacy 3 + EXT_STR 2 + EXT_LIST 4 + OPT_STR 3 + OPT_LIST 1
              + OPT_DICT_LIST 1 + OPT_DICT 1 = 15.
        (lawear-c63e 2026-05-21 옵션 C 도입 — 명세서 #2111)
        """
        self.assertEqual(len(attempts_mod._EVAL_NOTES_KEYS), 15)


# ─── 4. DB round-trip — inject_grade → get_attempt ──────────────────────


class TestTypoCorrectionsRoundTrip(unittest.TestCase):
    """PUT /grade body 의 typo_corrections → DB → GET /attempts/{id} round-trip."""

    def setUp(self) -> None:
        # 임시 DB + 마이그레이션 (db.init_db 명시 호출)
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_typo.db")
        db_mod.init_db(self.db_path)

        # 최소 case 1건 INSERT 필요
        with db_mod.get_conn(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO cases (
                    id, subject, subject_kor, category, file, case_no, title, path,
                    points, synced_at, content_hash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                ("test_case_typo", "minbeop", "민법", "입문", "test.md", "1",
                 "test", "/mock", 30, "2026-05-19T00:00:00Z", "abc")
            )
            conn.commit()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_pending_attempt(self) -> int:
        """pending_grade attempt 생성 → attempt_id 반환."""
        import grader as grader_mod
        with db_mod.get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO attempts (
                    case_id, answer_text, submitted_at, status, weights_json
                ) VALUES (?,?,?,?,?)
                """,
                ("test_case_typo", "사용자 답안",
                 "2026-05-19T10:00:00Z", "pending_grade",
                 json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False))
            )
            attempt_id = cur.lastrowid
            conn.commit()
        return attempt_id

    def _build_grade_payload(self, typo_corr) -> dict:
        """완전한 grade payload — typo_corrections 만 외부 주입."""
        return {
            "criteria": [
                {"key": "mnem", "score": 10, "weight_applied": 16, "max": 16, "comment": "ok"},
                {"key": "color", "score": 8, "weight_applied": 13, "max": 13, "comment": "ok"},
                {"key": "under", "score": 5, "weight_applied": 8, "max": 8, "comment": "ok"},
                {"key": "outline", "score": 7, "weight_applied": 10, "max": 10, "comment": "ok"},
                {"key": "sem", "score": 9, "weight_applied": 12, "max": 12, "comment": "ok"},
                {"key": "rich", "score": 10, "weight_applied": 15, "max": 15, "comment": "ok"},
                {"key": "miss", "score": 0, "weight_applied": 11, "max": 0, "comment": "ok"},
                {"key": "articles", "score": 8, "weight_applied": 10, "max": 10, "comment": "ok"},
                {"key": "case_apply", "score": 3, "weight_applied": 5, "max": 5, "comment": "ok"},
            ],
            "total_score": 60.0,
            "max_score": 89.0,
            "score_pct": 67.4,
            "grade": "C",
            "eval_notes": {
                "strength": "강",
                "caution": "주의",
                "missing": "누락",
                "score_summary": "요약",
                "strengths": ["s1"],
                "weaknesses": ["w1"],
                "missing_critical": [],
                "next_study_oneliner": "💡",
                "next_study_actionable": [],
                "pattern_warning": None,
                "typo_corrections": typo_corr,
            },
            "diff_segments": [],
            "model": "test-model",
        }

    def test_inject_grade_with_typo_corrections_round_trip(self):
        """typo_corrections 주입 → DB 저장 → GET 시 그대로 반환."""
        attempt_id = self._create_pending_attempt()
        typo_corr = [
            {"from": "파산관제인", "to": "파산관재인", "reason": "음성 STT"},
            {"from": "통정표시", "to": "통정허위표시", "reason": "법률용어"},
        ]
        payload = self._build_grade_payload(typo_corr)

        with db_mod.get_conn(self.db_path) as conn:
            attempts_mod.inject_grade(conn, attempt_id, payload)

        # 조회
        with db_mod.get_conn(self.db_path) as conn:
            row = attempts_mod.get_attempt(conn, attempt_id)

        self.assertIn("eval_notes", row)
        notes = row["eval_notes"]
        self.assertIn("typo_corrections", notes)
        self.assertIsNotNone(notes["typo_corrections"])
        self.assertEqual(len(notes["typo_corrections"]), 2)
        self.assertEqual(notes["typo_corrections"][0]["from"], "파산관제인")
        self.assertEqual(notes["typo_corrections"][0]["to"], "파산관재인")

    def test_inject_grade_without_typo_corrections_stores_none(self):
        """typo_corrections 키 미지정 → DB 에 None 저장 (legacy graceful)."""
        attempt_id = self._create_pending_attempt()
        payload = self._build_grade_payload(None)

        with db_mod.get_conn(self.db_path) as conn:
            attempts_mod.inject_grade(conn, attempt_id, payload)

        with db_mod.get_conn(self.db_path) as conn:
            row = attempts_mod.get_attempt(conn, attempt_id)

        # 신규 키도 키 자체는 존재 (None)
        notes = row["eval_notes"]
        self.assertIn("typo_corrections", notes)
        self.assertIsNone(notes["typo_corrections"])

    def test_inject_grade_empty_typo_corrections_list_stores_none(self):
        """빈 list → None 정규화 후 저장."""
        attempt_id = self._create_pending_attempt()
        payload = self._build_grade_payload([])

        with db_mod.get_conn(self.db_path) as conn:
            attempts_mod.inject_grade(conn, attempt_id, payload)

        with db_mod.get_conn(self.db_path) as conn:
            row = attempts_mod.get_attempt(conn, attempt_id)

        notes = row["eval_notes"]
        self.assertIsNone(notes["typo_corrections"])

    def test_inject_grade_invalid_typo_corrections_400(self):
        """잘못된 typo_corrections 타입 → GradeInjectionError."""
        attempt_id = self._create_pending_attempt()
        payload = self._build_grade_payload("not a list")  # str → 거부

        with self.assertRaises(attempts_mod.GradeInjectionError):
            with db_mod.get_conn(self.db_path) as conn:
                attempts_mod.inject_grade(conn, attempt_id, payload)


class TestMergeInitialTypoCorrections(unittest.TestCase):
    """lawear-9bdc/typo-system-v2 — _merge_initial_typo_corrections 단위 검증.

    POST 시점 typo_corrections (typo_corrector + ai_corrector) 가 grader 결과 UPDATE 로
    덮어쓰이지 않도록 머지하는 헬퍼. 중복 from 은 grader(새) 우선.
    """

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE attempts (id INTEGER PRIMARY KEY, eval_notes_json TEXT)"
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_merge_preserves_post_corrs(self):
        """기존 POST corrections + grader 결과 → 둘 다 누적."""
        initial = {"typo_corrections": [
            {"from": "둑은", "to": "또는", "source": "static_dict"},
            {"from": "AI오타", "to": "AI교정", "source": "ai"},
        ]}
        self.conn.execute(
            "INSERT INTO attempts (id, eval_notes_json) VALUES (?, ?)",
            (42, json.dumps(initial, ensure_ascii=False)),
        )
        grader_notes = {"typo_corrections": [
            {"from": "LLM오타", "to": "LLM교정", "source": "grader"}
        ]}
        attempts_mod._merge_initial_typo_corrections(self.conn, 42, grader_notes)
        merged = grader_notes["typo_corrections"]
        self.assertIsNotNone(merged)
        froms = {c["from"] for c in merged}
        self.assertEqual(froms, {"둑은", "AI오타", "LLM오타"})

    def test_merge_no_existing_unchanged(self):
        """기존 eval_notes 비어있으면 변화 없음."""
        self.conn.execute(
            "INSERT INTO attempts (id, eval_notes_json) VALUES (?, NULL)", (1,)
        )
        grader_notes = {
            "typo_corrections": [{"from": "x", "to": "y", "source": "grader"}]
        }
        attempts_mod._merge_initial_typo_corrections(self.conn, 1, grader_notes)
        self.assertEqual(len(grader_notes["typo_corrections"]), 1)
        self.assertEqual(grader_notes["typo_corrections"][0]["from"], "x")

    def test_merge_dedupe_from_grader_wins(self):
        """동일 from 은 grader(새) 우선, POST(기존) skip."""
        initial = {"typo_corrections": [
            {"from": "X", "to": "OLD_TO", "source": "static_dict"}
        ]}
        self.conn.execute(
            "INSERT INTO attempts (id, eval_notes_json) VALUES (?, ?)",
            (1, json.dumps(initial, ensure_ascii=False)),
        )
        grader_notes = {"typo_corrections": [
            {"from": "X", "to": "NEW_TO", "source": "grader"}
        ]}
        attempts_mod._merge_initial_typo_corrections(self.conn, 1, grader_notes)
        merged = grader_notes["typo_corrections"]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["to"], "NEW_TO")

    def test_merge_attempt_not_found_graceful(self):
        """존재 안 하는 attempt_id 머지 → 변화 없음."""
        grader_notes = {
            "typo_corrections": [{"from": "x", "to": "y", "source": "grader"}]
        }
        attempts_mod._merge_initial_typo_corrections(self.conn, 9999, grader_notes)
        self.assertEqual(len(grader_notes["typo_corrections"]), 1)

    def test_merge_invalid_json_graceful(self):
        """기존 eval_notes_json 이 invalid JSON 이면 변화 없음."""
        self.conn.execute(
            "INSERT INTO attempts (id, eval_notes_json) VALUES (?, ?)",
            (1, "not-json"),
        )
        grader_notes = {
            "typo_corrections": [{"from": "x", "to": "y", "source": "grader"}]
        }
        attempts_mod._merge_initial_typo_corrections(self.conn, 1, grader_notes)
        self.assertEqual(len(grader_notes["typo_corrections"]), 1)

    def test_merge_grader_notes_no_typo_key(self):
        """grader 결과에 typo_corrections 키 자체가 없을 때 기존만 살림."""
        initial = {"typo_corrections": [
            {"from": "POST키", "to": "교정", "source": "static_dict"}
        ]}
        self.conn.execute(
            "INSERT INTO attempts (id, eval_notes_json) VALUES (?, ?)",
            (5, json.dumps(initial, ensure_ascii=False)),
        )
        grader_notes: dict = {}  # typo_corrections 키 없음
        attempts_mod._merge_initial_typo_corrections(self.conn, 5, grader_notes)
        self.assertIn("typo_corrections", grader_notes)
        merged = grader_notes["typo_corrections"]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["from"], "POST키")


if __name__ == "__main__":
    unittest.main()
