#!/usr/bin/env python3
"""Phase 1 — eval_notes 스키마 확장 TC (lawear-e571, 2026-05-19).

[배경]
사용자 보고: SE 보낸 평가 본문 텍스트가 서버 스키마 불일치로 빈 문자열 저장.
강점/약점/누락/한줄평 다 저장되게 fix.

[확장 키]
- score_summary:        str (3줄 핵심 평가)
- strengths:            list[str] (강점)
- weaknesses:           list[str] (약점)
- missing_critical:     list[dict] [{item, expected_score_impact}]
- next_study_oneliner:  str ("💡 다음 +N점 가능: ...")
- next_study_actionable:list[str] (실행 액션)

[호환]
- legacy 키 (strength/caution/missing) 그대로 보존.
- 새 키 없으면 빈 문자열/빈 배열 저장.
- alias (weakness → weaknesses) 자동 정규화.

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_phase1_eval_notes_ext.py -v
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


def _seed_case(conn: sqlite3.Connection, case_id: str = "c-phase1") -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO cases (
            id, subject, subject_kor, category, file, case_no, title, path,
            points, synced_at, content_hash
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (case_id, "minbeop", "민법", "예비", "phase1", "01", "Phase1 Test",
         "/mock", 17, "2026-05-19T00:00:00Z", "abc"),
    )
    conn.commit()


def _seed_pending_attempt(conn: sqlite3.Connection, case_id: str = "c-phase1") -> int:
    cur = conn.execute(
        """
        INSERT INTO attempts (
            case_id, answer_text, submitted_at, status, weights_json
        ) VALUES (?,?,?,?,?)
        """,
        (
            case_id,
            "phase1 user answer",
            "2026-05-19T10:00:00Z",
            "pending_grade",
            json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _v5_payload_with_ext_eval_notes(**overrides) -> dict:
    """확장 eval_notes를 포함한 v5 페이로드."""
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
            # legacy 키 (호환)
            "strength": "조문 인용 충실",
            "caution": "사안 적용 부족",
            "missing": "제126조 표현대리 준용 X",
            # 확장 키
            "score_summary": "총평 3줄: 조문/근거 양호, 사안 적용 미흡, 풀이형 키워드 부족.",
            "strengths": ["조문 인용 정확", "결론 명확"],
            "weaknesses": ["사안 적용 부족", "두문자 풀이형 미사용"],
            "missing_critical": [
                {"item": "비법인사단 인정 근거 4요소", "expected_score_impact": -4},
                {"item": "제34조 유추적용", "expected_score_impact": -3},
            ],
            "next_study_oneliner": "💡 다음 +6~9점 가능: 조문 5개 + 비법인사단 근거 4요소",
            "next_study_actionable": [
                "비법인사단 인정 근거 4요소 두문자 학습",
                "제126조 표현대리 사례 5건 복습",
            ],
        },
    }
    base.update(overrides)
    return base


# ─── 단위: _normalize_eval_notes ────────────────────────────────────


class NormalizeEvalNotesTest(unittest.TestCase):
    """attempts._normalize_eval_notes — 확장 키 정규화."""

    def test_empty_dict_safe_fallback(self) -> None:
        """빈 dict → 모든 키 빈 값 (호환성 보장)."""
        out = attempts_mod._normalize_eval_notes({})
        # legacy 3개
        self.assertEqual(out["strength"], "")
        self.assertEqual(out["caution"], "")
        self.assertEqual(out["missing"], "")
        # 확장 str 2개
        self.assertEqual(out["score_summary"], "")
        self.assertEqual(out["next_study_oneliner"], "")
        # 확장 list 4개
        self.assertEqual(out["strengths"], [])
        self.assertEqual(out["weaknesses"], [])
        self.assertEqual(out["missing_critical"], [])
        self.assertEqual(out["next_study_actionable"], [])

    def test_legacy_only_keys_preserved(self) -> None:
        """legacy 키만 들어오면 기존 그대로 + 확장 키는 빈 값 보강."""
        raw = {
            "strength": "S",
            "caution": "C",
            "missing": "M",
        }
        out = attempts_mod._normalize_eval_notes(raw)
        self.assertEqual(out["strength"], "S")
        self.assertEqual(out["caution"], "C")
        self.assertEqual(out["missing"], "M")
        # 확장 키 빈 값
        self.assertEqual(out["strengths"], [])
        self.assertEqual(out["missing_critical"], [])

    def test_ext_keys_all_present(self) -> None:
        """확장 키 전체 들어오면 그대로 보존."""
        raw = {
            "score_summary": "3줄 핵심",
            "strengths": ["조문 인용", "결론 명확"],
            "weaknesses": ["사안 적용 부족"],
            "missing_critical": [
                {"item": "제126조 누락", "expected_score_impact": -3},
            ],
            "next_study_oneliner": "💡 +6점 가능",
            "next_study_actionable": ["조문 복습"],
        }
        out = attempts_mod._normalize_eval_notes(raw)
        self.assertEqual(out["score_summary"], "3줄 핵심")
        self.assertEqual(out["strengths"], ["조문 인용", "결론 명확"])
        self.assertEqual(out["weaknesses"], ["사안 적용 부족"])
        self.assertEqual(len(out["missing_critical"]), 1)
        self.assertEqual(out["missing_critical"][0]["item"], "제126조 누락")
        self.assertEqual(out["missing_critical"][0]["expected_score_impact"], -3.0)
        self.assertEqual(out["next_study_oneliner"], "💡 +6점 가능")
        self.assertEqual(out["next_study_actionable"], ["조문 복습"])

    def test_alias_weakness_to_weaknesses(self) -> None:
        """단수형 weakness 도 weaknesses 로 정규화."""
        raw = {"weakness": ["단수형 입력"]}
        out = attempts_mod._normalize_eval_notes(raw)
        self.assertEqual(out["weaknesses"], ["단수형 입력"])

    def test_str_input_wrap_to_list(self) -> None:
        """str 단일 값 → 1-item list로 wrap (호환)."""
        raw = {"strengths": "단일 강점"}
        out = attempts_mod._normalize_eval_notes(raw)
        self.assertEqual(out["strengths"], ["단일 강점"])

    def test_missing_critical_str_wrap(self) -> None:
        """missing_critical 항목이 str로 들어오면 dict로 wrap."""
        raw = {"missing_critical": ["조문 누락"]}
        out = attempts_mod._normalize_eval_notes(raw)
        self.assertEqual(len(out["missing_critical"]), 1)
        self.assertEqual(out["missing_critical"][0]["item"], "조문 누락")
        self.assertEqual(out["missing_critical"][0]["expected_score_impact"], 0.0)

    def test_missing_critical_extra_keys_preserved(self) -> None:
        """missing_critical dict의 추가 키도 보존 (R-09)."""
        raw = {
            "missing_critical": [
                {"item": "X", "expected_score_impact": -2, "subq_key": "설문 1"},
            ],
        }
        out = attempts_mod._normalize_eval_notes(raw)
        self.assertEqual(out["missing_critical"][0]["subq_key"], "설문 1")

    def test_non_dict_input_raises(self) -> None:
        """dict 외 입력 → GradeInjectionError."""
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes("not a dict")


# ─── 통합: inject_grade — 확장 eval_notes 저장 + 응답 ──────────────


class InjectGradePhase1Test(unittest.TestCase):
    """PUT /api/attempts/{id}/grade — Phase 1 eval_notes 저장."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_case(conn)
            self.attempt_id = _seed_pending_attempt(conn)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_inject_ext_eval_notes_saved(self) -> None:
        """확장 eval_notes 6개 키 모두 DB 저장 + GET 응답에 노출."""
        payload = _v5_payload_with_ext_eval_notes()
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)

        # 응답 eval_notes 확인
        en = out["eval_notes"]
        # legacy
        self.assertEqual(en["strength"], "조문 인용 충실")
        self.assertEqual(en["caution"], "사안 적용 부족")
        # 확장
        self.assertIn("총평 3줄", en["score_summary"])
        self.assertEqual(len(en["strengths"]), 2)
        self.assertEqual(len(en["weaknesses"]), 2)
        self.assertEqual(len(en["missing_critical"]), 2)
        self.assertEqual(en["missing_critical"][0]["item"], "비법인사단 인정 근거 4요소")
        self.assertIn("+6~9점 가능", en["next_study_oneliner"])
        self.assertEqual(len(en["next_study_actionable"]), 2)

    def test_inject_legacy_only_still_works(self) -> None:
        """legacy 키만 보낸 payload 도 그대로 작동 (호환성)."""
        payload = _v5_payload_with_ext_eval_notes()
        payload["eval_notes"] = {
            "strength": "S only",
            "caution": "C only",
            "missing": "M only",
        }
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)
        en = out["eval_notes"]
        self.assertEqual(en["strength"], "S only")
        # 확장 키 빈 값
        self.assertEqual(en["strengths"], [])
        self.assertEqual(en["missing_critical"], [])

    def test_db_eval_notes_json_contains_ext_keys(self) -> None:
        """DB eval_notes_json 컬럼에 확장 키 6개가 JSON serialized 됨."""
        payload = _v5_payload_with_ext_eval_notes()
        with db_mod.get_conn(self.tmp.name) as conn:
            attempts_mod.inject_grade(conn, self.attempt_id, payload)
            row = conn.execute(
                "SELECT eval_notes_json FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
        en = json.loads(row["eval_notes_json"])
        # 키 9개 (legacy 3 + 확장 6)
        for k in (
            "strength", "caution", "missing",  # legacy
            "score_summary", "strengths", "weaknesses",
            "missing_critical", "next_study_oneliner", "next_study_actionable",  # 확장
        ):
            self.assertIn(k, en, f"DB JSON에 {k} 누락")


# ─── _save_grade_result (auto 채점 경로) ────────────────────────────


class SaveGradeResultPhase1Test(unittest.TestCase):
    """_save_grade_result — auto 채점 결과도 확장 키 보강."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            _seed_case(conn)
            # auto 모드는 grading status 로 시작
            cur = conn.execute(
                """INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json)
                   VALUES (?,?,?,?,?)""",
                ("c-phase1", "auto test", "2026-05-19T10:00:00Z", "grading",
                 json.dumps(dict(grader_mod.DEFAULT_WEIGHTS), ensure_ascii=False)),
            )
            conn.commit()
            self.attempt_id = int(cur.lastrowid)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_grader_legacy_eval_notes_normalized(self) -> None:
        """grader가 legacy 키만 보내도 _save_grade_result에서 확장 키 보강."""
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
        # 확장 키 빈 값 보강
        self.assertEqual(en["strengths"], [])
        self.assertEqual(en["missing_critical"], [])
        self.assertEqual(en["next_study_oneliner"], "")

    def test_grader_ext_eval_notes_preserved(self) -> None:
        """grader가 확장 키 보내면 그대로 저장."""
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
                "score_summary": "auto 채점 요약",
                "strengths": ["A1", "A2"],
                "weaknesses": ["B1"],
                "missing_critical": [{"item": "X", "expected_score_impact": -2}],
                "next_study_oneliner": "💡 +N점",
                "next_study_actionable": ["학습 액션"],
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
        self.assertEqual(en["score_summary"], "auto 채점 요약")
        self.assertEqual(len(en["strengths"]), 2)
        self.assertEqual(en["missing_critical"][0]["item"], "X")


# ─── mnemonic_suggestions (lawear-6be6 #6, 2026-05-26) ───────────────


class MnemonicSuggestionsNormalizeTest(unittest.TestCase):
    """attempts._normalize_eval_notes — mnemonic_suggestions 키 정규화.

    M4 attempts.py L1567-L1595 (mnemonic_suggestions 블록) 검증.
    구조: {judge: list[dict], lecturer: list[dict]} | None.
    R-09: 각 dict 통째 보존(extra_field_xyz/nested 등). 캡 10 silent slice.
    """

    def test_mnemonic_suggestions_legacy_attempt(self) -> None:
        """레거시 attempts (mnemonic_suggestions 키 미존재) → None 자동 정규화.

        [블록 1] 사용자 룰 #1 backward compat 100% — legacy attempt 미존재키 graceful.
        """
        out = attempts_mod._normalize_eval_notes({"strength": "..."})
        self.assertIn("mnemonic_suggestions", out)
        self.assertIsNone(out["mnemonic_suggestions"])

    def test_mnemonic_suggestions_explicit_none(self) -> None:
        """명시 None → None 통과 (attempts.py L1572-L1573)."""
        out = attempts_mod._normalize_eval_notes({"mnemonic_suggestions": None})
        self.assertIsNone(out["mnemonic_suggestions"])

    def test_mnemonic_suggestions_empty_both_lists_to_none(self) -> None:
        """양쪽 빈 list → None 정규화 (UI 분기 단순화, attempts.py L1584-L1585)."""
        out = attempts_mod._normalize_eval_notes(
            {"mnemonic_suggestions": {"judge": [], "lecturer": []}}
        )
        self.assertIsNone(out["mnemonic_suggestions"])

    def test_mnemonic_suggestions_valid_dict_passthrough(self) -> None:
        """유효 dict → 통째 보존 (R-09).

        [블록 1] 사용자 룰 #2 R-09 통째 보존 — dict 내부 nested 필드 그대로.
        attempts.py L1582-L1583: dict(item) shallow copy 후 통째 보존.
        """
        raw = {
            "mnemonic_suggestions": {
                "judge": [
                    {
                        "mnemonic_text": "[em1]일[/em1]·[em1]시[/em1]·[em1]불[/em1]",
                        "source": "민법.md#L499",
                        "extra_field_xyz": 123,
                        "nested": {"a": 1},
                    }
                ],
                "lecturer": [],
            }
        }
        out = attempts_mod._normalize_eval_notes(raw)
        ms = out["mnemonic_suggestions"]
        self.assertIsNotNone(ms)
        self.assertEqual(ms["judge"][0]["source"], "민법.md#L499")
        # R-09 통째 보존
        self.assertEqual(ms["judge"][0]["extra_field_xyz"], 123)
        # nested 보존
        self.assertEqual(ms["judge"][0]["nested"], {"a": 1})
        # 한쪽 빈 list 도 dict 형태로 보존 (다른 쪽 비어있지 않으므로)
        self.assertEqual(ms["lecturer"], [])

    def test_mnemonic_suggestions_cap_10(self) -> None:
        """15개 입력 → silent slice 10개 (사용자 피로 방지).

        [블록 1] 사용자 룰 #4 캡 10 검증.
        attempts.py L1588-L1589: judge_normalized[:10] / lecturer_normalized[:10].
        """
        items = [
            {"mnemonic_text": f"m{i}", "source": f"민법.md#L{i}"} for i in range(15)
        ]
        out = attempts_mod._normalize_eval_notes(
            {"mnemonic_suggestions": {"judge": items, "lecturer": []}}
        )
        self.assertEqual(len(out["mnemonic_suggestions"]["judge"]), 10)

    def test_mnemonic_suggestions_invalid_type_list_reject(self) -> None:
        """list 입력 → GradeInjectionError (dict 아님).

        [블록 1] 사용자 룰 #3 타입 strict 검증.
        attempts.py L1591-L1595: dict/None 아니면 reject.
        """
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes({"mnemonic_suggestions": ["bad"]})

    def test_mnemonic_suggestions_invalid_type_str_reject(self) -> None:
        """str 입력 → GradeInjectionError. attempts.py L1591-L1595."""
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes({"mnemonic_suggestions": "bad"})

    def test_mnemonic_suggestions_invalid_type_int_reject(self) -> None:
        """int 입력 → GradeInjectionError. attempts.py L1591-L1595."""
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes({"mnemonic_suggestions": 42})

    def test_mnemonic_suggestions_invalid_inner_type(self) -> None:
        """judge=str → GradeInjectionError (nested type strict).

        attempts.py L1577-L1581: judge/lecturer 각각 list 아니면 reject.
        """
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod._normalize_eval_notes(
                {"mnemonic_suggestions": {"judge": "bad", "lecturer": []}}
            )

    def test_mnemonic_suggestions_non_dict_items_skipped(self) -> None:
        """list 안 non-dict 항목 graceful skip.

        attempts.py L1582-L1583: `for item in judge_raw if isinstance(item, dict)`.
        """
        raw = {
            "mnemonic_suggestions": {
                "judge": [{"mnemonic_text": "ok"}, "bad", 123],
                "lecturer": [],
            }
        }
        out = attempts_mod._normalize_eval_notes(raw)
        # bad/123 skip → judge 1개만 살아남음
        self.assertEqual(len(out["mnemonic_suggestions"]["judge"]), 1)
        self.assertEqual(
            out["mnemonic_suggestions"]["judge"][0]["mnemonic_text"], "ok"
        )


if __name__ == "__main__":
    unittest.main()
