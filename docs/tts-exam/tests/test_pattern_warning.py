#!/usr/bin/env python3
"""pattern_warning — eval_notes 7번째 확장 키 TC (lawear-e571, 2026-05-19).

[배경]
사용자 요청: 채점평에 "같은 실수 반복 패턴" 경고 추가.
예) 제103↔104조 혼동 — 01-02/01-03 에서 2회 반복.

[스키마]
eval_notes 의 7번째 확장 키:
- pattern_warning: str | None
  - 단일 attempt 내부 패턴 (AI 채점관): 동일 답안에서 발견된 오류 패턴 경고
  - 외부 비교 (메인 메타 분석): 이전 attempt vs 현재 → PUT /grade body 에 직접 주입
  - 형식 예: "🔥 같은 실수 N회 반복 가능성: ..." 또는 "🔥 주의: ..."

[호환]
- pattern_warning 없는 legacy payload 도 그대로 작동 (None 보강).
- str 비어있으면 None 정규화 (UI 분기 단순화).
- list/dict 등 잘못된 타입 → GradeInjectionError 거부.

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_pattern_warning.py -v
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


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _build_db(path: str) -> None:
    db_mod.init_db(path)


def _seed_case(conn: sqlite3.Connection, case_id: str = "c-pw") -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO cases (
            id, subject, subject_kor, category, file, case_no, title, path,
            points, synced_at, content_hash
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            case_id,
            "minbeop",
            "민법",
            "예비",
            "pw_test",
            "01",
            "PatternWarning Test",
            "/mock",
            17,
            "2026-05-19T00:00:00Z",
            "pw-hash",
        ),
    )
    conn.commit()


def _seed_pending_attempt(conn: sqlite3.Connection, case_id: str = "c-pw") -> int:
    cur = conn.execute(
        """
        INSERT INTO attempts (
            case_id, answer_text, submitted_at, status, weights_json
        ) VALUES (?,?,?,?,?)
        """,
        (
            case_id,
            "pattern_warning test user answer",
            "2026-05-19T10:00:00Z",
            "pending_grade",
            json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _v5_payload(**overrides) -> dict:
    """기본 v5 v6 가중치 payload (pattern_warning 미포함)."""
    base = {
        "criteria": [
            {"key": "mnem", "score": 12.5, "weight_applied": 16, "comment": ""},
            {"key": "color", "score": 10.0, "weight_applied": 13, "comment": ""},
            {"key": "under", "score": 6.0, "weight_applied": 8, "comment": ""},
            {"key": "outline", "score": 8.0, "weight_applied": 10, "comment": ""},
            {"key": "sem", "score": 9.5, "weight_applied": 12, "comment": ""},
            {"key": "rich", "score": 11.0, "weight_applied": 15, "comment": ""},
            {"key": "miss", "score": -1.5, "weight_applied": 11, "comment": ""},
            {"key": "articles", "score": 7.75, "weight_applied": 10, "comment": ""},
            {"key": "case_apply", "score": 3.5, "weight_applied": 5, "comment": ""},
        ],
        "total_score": 66.75,
        "max_score": 89.0,
        "score_pct": 75.0,
        "grade": "B",
        "eval_notes": {
            "strength": "조문 인용 충실",
            "caution": "사안 적용 부족",
            "missing": "제126조 표현대리 준용 X",
        },
    }
    base.update(overrides)
    return base


# ─── 단위: _normalize_eval_notes — pattern_warning ─────────────────


class NormalizePatternWarningTest(unittest.TestCase):
    """attempts._normalize_eval_notes — pattern_warning 정규화."""

    def test_missing_key_defaults_to_none(self) -> None:
        """pattern_warning 키 없으면 None (legacy 호환)."""
        out = attempts_mod._normalize_eval_notes({})
        self.assertIn("pattern_warning", out)
        self.assertIsNone(out["pattern_warning"])

    def test_str_value_preserved(self) -> None:
        """str 값 그대로 보존."""
        warning = "🔥 같은 실수 2회 반복 가능성: 제103↔104조 혼동"
        out = attempts_mod._normalize_eval_notes(
            {"pattern_warning": warning}
        )
        self.assertEqual(out["pattern_warning"], warning)

    def test_none_value_preserved(self) -> None:
        """None 명시 입력도 None 유지."""
        out = attempts_mod._normalize_eval_notes({"pattern_warning": None})
        self.assertIsNone(out["pattern_warning"])

    def test_empty_str_normalized_to_none(self) -> None:
        """빈 문자열 / 공백 only → None (UI 분기 단순화)."""
        out_empty = attempts_mod._normalize_eval_notes({"pattern_warning": ""})
        self.assertIsNone(out_empty["pattern_warning"])
        out_spaces = attempts_mod._normalize_eval_notes(
            {"pattern_warning": "   "}
        )
        self.assertIsNone(out_spaces["pattern_warning"])

    def test_list_value_rejected(self) -> None:
        """list 입력 → GradeInjectionError 거부 (str | null 강제)."""
        with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
            attempts_mod._normalize_eval_notes(
                {"pattern_warning": ["wrong", "type"]}
            )
        self.assertIn("pattern_warning", str(ctx.exception))
        self.assertIn("string or null", str(ctx.exception))

    def test_dict_value_rejected(self) -> None:
        """dict 입력 → GradeInjectionError 거부."""
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes(
                {"pattern_warning": {"item": "X"}}
            )

    def test_int_value_rejected(self) -> None:
        """int 입력 → GradeInjectionError 거부 (str 강제)."""
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes({"pattern_warning": 42})

    def test_keys_constant_includes_pattern_warning(self) -> None:
        """_EVAL_NOTES_KEYS 통합 튜플에 pattern_warning 포함."""
        self.assertIn("pattern_warning", attempts_mod._EVAL_NOTES_KEYS)
        self.assertIn(
            "pattern_warning",
            attempts_mod._EVAL_NOTES_KEYS_EXT_OPT_STR,
        )


# ─── 통합: inject_grade — pattern_warning round-trip ───────────────


class InjectGradePatternWarningTest(unittest.TestCase):
    """PUT /api/attempts/{id}/grade — pattern_warning 저장/조회."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_case(conn)
            self.attempt_id = _seed_pending_attempt(conn)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_inject_with_pattern_warning_round_trip(self) -> None:
        """pattern_warning 포함 payload 저장 + 응답 + DB JSON round-trip."""
        warning = (
            "🔥 같은 실수 2회 반복 가능성: 제103조와 제104조 혼동 — "
            "01-02 / 01-03 에서 동일 패턴 발생"
        )
        payload = _v5_payload()
        payload["eval_notes"]["pattern_warning"] = warning

        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)

        # 응답 eval_notes 확인
        self.assertEqual(out["eval_notes"]["pattern_warning"], warning)

        # DB eval_notes_json round-trip
        with db_mod.get_conn(self.tmp.name) as conn:
            row = conn.execute(
                "SELECT eval_notes_json FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        en = json.loads(row["eval_notes_json"])
        self.assertIn("pattern_warning", en)
        self.assertEqual(en["pattern_warning"], warning)

    def test_inject_without_pattern_warning_legacy(self) -> None:
        """pattern_warning 없는 legacy payload 도 그대로 작동 (None 보강)."""
        payload = _v5_payload()
        # pattern_warning 키 부재
        self.assertNotIn("pattern_warning", payload["eval_notes"])

        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)

        # 응답에 None 으로 보강
        self.assertIn("pattern_warning", out["eval_notes"])
        self.assertIsNone(out["eval_notes"]["pattern_warning"])

        # DB JSON 에도 None 직렬화
        with db_mod.get_conn(self.tmp.name) as conn:
            row = conn.execute(
                "SELECT eval_notes_json FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        en = json.loads(row["eval_notes_json"])
        self.assertIn("pattern_warning", en)
        self.assertIsNone(en["pattern_warning"])

    def test_inject_with_invalid_pattern_warning_type_rejected(self) -> None:
        """잘못된 타입(list) → 400 GradeInjectionError 로 거부."""
        payload = _v5_payload()
        payload["eval_notes"]["pattern_warning"] = ["wrong", "type"]

        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
                attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertIn("pattern_warning", str(ctx.exception))


# ─── auto 채점 경로 (_save_grade_result) — pattern_warning ─────────


class SaveGradeResultPatternWarningTest(unittest.TestCase):
    """_save_grade_result — auto 채점에서도 pattern_warning 정규화."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_case(conn)
            cur = conn.execute(
                """INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json)
                   VALUES (?,?,?,?,?)""",
                (
                    "c-pw",
                    "auto pw test",
                    "2026-05-19T10:00:00Z",
                    "grading",
                    json.dumps(
                        dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False
                    ),
                ),
            )
            conn.commit()
            self.attempt_id = int(cur.lastrowid)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_grader_pattern_warning_preserved(self) -> None:
        """grader가 pattern_warning 보내면 그대로 저장."""
        warning = "🔥 주의: 같은 답안 내 사안 적용 누락 2회 (설문1 / 설문2)"
        result = {
            "model": "claude-opus-4-7",
            "score_total": 70.0,
            "score_max": 89.0,
            "score_pct": 78.6,
            "grade": "B",
            "criteria": [
                {"key": k, "score": 1.0, "max": 1.0, "weight": w, "comment": ""}
                for k, w in grader_mod.DEFAULT_WEIGHTS.items()
            ],
            "eval_notes": {
                "strength": "S",
                "caution": "C",
                "missing": "M",
                "pattern_warning": warning,
            },
            "diff_segments": [],
            "raw_response": None,
            "elapsed_sec": 1.0,
            "is_mock": False,
        }
        attempts_mod._save_grade_result(self.tmp.name, self.attempt_id, result)
        with db_mod.get_conn(self.tmp.name) as conn:
            row = conn.execute(
                "SELECT eval_notes_json FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        en = json.loads(row["eval_notes_json"])
        self.assertEqual(en["pattern_warning"], warning)

    def test_grader_no_pattern_warning_defaults_none(self) -> None:
        """grader가 pattern_warning 누락하면 None 보강."""
        result = {
            "model": "claude-opus-4-7",
            "score_total": 70.0,
            "score_max": 89.0,
            "score_pct": 78.6,
            "grade": "B",
            "criteria": [
                {"key": k, "score": 1.0, "max": 1.0, "weight": w, "comment": ""}
                for k, w in grader_mod.DEFAULT_WEIGHTS.items()
            ],
            # pattern_warning 키 부재
            "eval_notes": {"strength": "S", "caution": "C", "missing": "M"},
            "diff_segments": [],
            "raw_response": None,
            "elapsed_sec": 1.0,
            "is_mock": False,
        }
        attempts_mod._save_grade_result(self.tmp.name, self.attempt_id, result)
        with db_mod.get_conn(self.tmp.name) as conn:
            row = conn.execute(
                "SELECT eval_notes_json FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        en = json.loads(row["eval_notes_json"])
        self.assertIn("pattern_warning", en)
        self.assertIsNone(en["pattern_warning"])


# ─── grader.py mock 응답 / SYSTEM_PROMPT — pattern_warning ────────


class GraderMockPatternWarningTest(unittest.TestCase):
    """grader._mock_response + SYSTEM_PROMPT — pattern_warning 포함."""

    def test_mock_response_includes_pattern_warning_none(self) -> None:
        """mock 응답 eval_notes 에 pattern_warning 키 None 으로 포함."""
        case_meta = {"id": "c-pw", "subject_kor": "민법"}
        out = grader_mod._mock_response(case_meta, "테스트 답안", grader_mod.DEFAULT_WEIGHTS)
        self.assertIn("pattern_warning", out["eval_notes"])
        self.assertIsNone(out["eval_notes"]["pattern_warning"])

    def test_system_prompt_documents_pattern_warning(self) -> None:
        """SYSTEM_PROMPT 본문에 pattern_warning 키 안내 포함 (AI 출력 가이드)."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertIn("pattern_warning", prompt)
        # 형식 가이드 (🔥 또는 반복) 둘 중 하나는 명시되어야 함
        self.assertTrue(
            "🔥" in prompt or "반복" in prompt,
            "SYSTEM_PROMPT 에 pattern_warning 형식 가이드 부재",
        )


if __name__ == "__main__":
    unittest.main()
