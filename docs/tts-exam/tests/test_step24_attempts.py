#!/usr/bin/env python3
"""Step 24-3 — attempts.py 다중 설문 D안 + 힌트 메타 단위 테스트.

dev-design archive §5-4 / dev-impl-plan §B Step 24-3 1:1.

검증 범위:
1. `_serialize_subq_dicts` — 한글 키 ensure_ascii=False 보존 + None 입력 처리
2. `_deserialize_subq_dicts` — JSON → dict + NULL/invalid 안전 처리 + 라운드트립
3. `_compute_hint_meta` — 빈 dict / 다중 카드 / 잘못된 입력 처리
4. `create_attempt` — answer_text only / answer_subq only / both / neither
5. `create_attempt` 응답 — subq_count / hints_used_count / hint_steps_revealed_max
6. `get_attempt` — legacy NULL fallback + 다중 카드 노출
7. `get_attempt` criteria_subq — subq_key 별 그룹핑 노출
8. `list_attempts` — 히스토리 패널 메타 4종 노출
9. `inject_grade` — criteria_subq 다중 카드 INSERT (subq_key 채움)
10. `inject_grade` — legacy criteria 1차원 list (subq_key=NULL) 보존
11. `inject_grade` — criteria_subq 빈 dict / dict 아님 → reject
12. `inject_grade` — criteria / criteria_subq 둘 다 없으면 reject

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step24_attempts.py -v
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# tests/ → 부모 docs/tts-exam 를 sys.path 에 등록
_THIS_DIR = Path(__file__).parent.resolve()
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import attempts as attempts_mod  # noqa: E402
import cases as cases_mod  # noqa: E402
import db as db_mod  # noqa: E402
import grader as grader_mod  # noqa: E402


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _build_db(path: str) -> None:
    """v6 마이그까지 적용된 깨끗한 DB."""
    db_mod.init_db(path)


def _seed_case(conn: sqlite3.Connection, case_id: str = "tc24-3") -> None:
    """테스트용 케이스 1건 시드."""
    conn.execute(
        """
        INSERT OR IGNORE INTO cases (
            id, subject, subject_kor, category, file, case_no, title, path,
            points, synced_at, content_hash
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (case_id, "minbeop", "민법", "예비", "모고01", "01",
         "Step 24-3 TC 케이스", "/mock", 35, "2026-05-18T00:00:00Z", "deadbeef"),
    )
    conn.commit()


def _fake_case_meta(case_id: str = "tc24-3") -> dict:
    """cases.get_case 가 반환할 가짜 case_meta."""
    return {
        "id": case_id,
        "subject": "minbeop",
        "subject_kor": "민법",
        "category": "예비",
        "file": "모고01",
        "case_no": "01",
        "title": "Step 24-3 TC 케이스",
        "path": "/mock",
        "points": 35,
        "md_body": "## 원본\n\n### 사실관계\n test\n\n### 설문 1\n test\n",
    }


def _full_criteria_9(extra_score: float = 0.0) -> list[dict]:
    """9기준 채점 입력 (DEFAULT_WEIGHTS 합=100).

    score 합 = 65 + extra_score (legacy + 다중 카드 양쪽 재사용).
    """
    return [
        {"key": "mnem",       "score": 12 + extra_score, "weight_applied": 16, "comment": "두문자 OK"},
        {"key": "color",      "score": 11, "weight_applied": 13, "comment": "색강조"},
        {"key": "under",      "score": 6,  "weight_applied": 8,  "comment": "밑줄"},
        {"key": "outline",    "score": 8,  "weight_applied": 10, "comment": "목차"},
        {"key": "sem",        "score": 10, "weight_applied": 12, "comment": "의미"},
        {"key": "rich",       "score": 12, "weight_applied": 15, "comment": "풍부함"},
        {"key": "miss",       "score": -1, "weight_applied": 11, "comment": "누락"},
        {"key": "articles",   "score": 6,  "weight_applied": 10, "comment": "조문"},
        {"key": "case_apply", "score": 1,  "weight_applied": 5,  "comment": "사안 적용"},
    ]


def _full_eval_notes() -> dict:
    return {"strength": "강점", "caution": "주의", "missing": "누락"}


# ─── 1. 헬퍼 — _serialize_subq_dicts ─────────────────────────────────


class SerializeSubqDictsTest(unittest.TestCase):
    """_serialize_subq_dicts 한글 키 + None 보존 검증."""

    def test_serialize_subq_dicts_korean_keys(self):
        """한글 키 "설문 1" 등 ensure_ascii=False 로 escape 없이 직렬화."""
        ans, elap, hints = attempts_mod._serialize_subq_dicts(
            {"설문 1": "답안 본문 가나다", "설문 2": "답안 둘"},
            {"설문 1": 120, "설문 2": 180},
            {"설문 1": [1, 2], "설문 2": [1]},
        )
        # 한글 키가 \u 형식이 아니라 그대로 들어있어야 함
        self.assertIsNotNone(ans)
        self.assertIn("설문 1", ans)
        self.assertIn("설문 2", ans)
        self.assertIn("답안 본문 가나다", ans)
        self.assertNotIn("\\u", ans, "ensure_ascii=False 가 작동해야 함")
        # subq_elapsed / hints_used 도 마찬가지
        self.assertIn("설문 1", elap)
        self.assertIn("설문 1", hints)

    def test_serialize_subq_dicts_all_none_returns_none(self):
        """3개 모두 None 입력 → 3개 모두 None."""
        ans, elap, hints = attempts_mod._serialize_subq_dicts(None, None, None)
        self.assertIsNone(ans)
        self.assertIsNone(elap)
        self.assertIsNone(hints)

    def test_serialize_subq_dicts_empty_dicts_become_none(self):
        """빈 dict {} → None (DB NULL 효율)."""
        ans, elap, hints = attempts_mod._serialize_subq_dicts({}, {}, {})
        self.assertIsNone(ans)
        self.assertIsNone(elap)
        self.assertIsNone(hints)

    def test_serialize_subq_dicts_mixed(self):
        """일부만 제공 — 나머지는 None 유지."""
        ans, elap, hints = attempts_mod._serialize_subq_dicts(
            {"설문 1": "답안"}, None, None
        )
        self.assertIsNotNone(ans)
        self.assertIsNone(elap)
        self.assertIsNone(hints)

    def test_serialize_subq_dicts_ga_na_keys(self):
        """패턴 C 키 "설문 1 가" / "설문 1 나" 도 정상."""
        ans, _, _ = attempts_mod._serialize_subq_dicts(
            {"설문 1 가": "가 답안", "설문 1 나": "나 답안"}, None, None
        )
        loaded = json.loads(ans)
        self.assertIn("설문 1 가", loaded)
        self.assertIn("설문 1 나", loaded)


# ─── 2. 헬퍼 — _deserialize_subq_dicts ───────────────────────────────


class DeserializeSubqDictsTest(unittest.TestCase):
    """_deserialize_subq_dicts NULL / invalid / 라운드트립."""

    def test_deserialize_all_null_returns_none(self):
        """NULL 입력 → None."""
        ans, elap, hints = attempts_mod._deserialize_subq_dicts(None, None, None)
        self.assertIsNone(ans)
        self.assertIsNone(elap)
        self.assertIsNone(hints)

    def test_deserialize_empty_string_returns_none(self):
        """빈 문자열 → None (truthy 체크)."""
        ans, elap, hints = attempts_mod._deserialize_subq_dicts("", "", "")
        self.assertIsNone(ans)
        self.assertIsNone(elap)
        self.assertIsNone(hints)

    def test_deserialize_roundtrip_korean(self):
        """serialize → deserialize 라운드트립으로 한글 키 + 값 보존."""
        original_ans = {"설문 1": "답안 가나다", "설문 2": "답안 라마"}
        original_elap = {"설문 1": 90, "설문 2": 150}
        original_hints = {"설문 1": [1, 2, 3], "설문 2": [1]}

        ans_json, elap_json, hints_json = attempts_mod._serialize_subq_dicts(
            original_ans, original_elap, original_hints
        )
        ans_back, elap_back, hints_back = attempts_mod._deserialize_subq_dicts(
            ans_json, elap_json, hints_json
        )
        self.assertEqual(ans_back, original_ans)
        self.assertEqual(elap_back, original_elap)
        self.assertEqual(hints_back, original_hints)

    def test_deserialize_invalid_json_returns_none(self):
        """JSON 파싱 실패 → None (raise X)."""
        ans, elap, hints = attempts_mod._deserialize_subq_dicts(
            "{not valid json", "[broken", "also broken"
        )
        self.assertIsNone(ans)
        self.assertIsNone(elap)
        self.assertIsNone(hints)

    def test_deserialize_non_dict_json_returns_none(self):
        """dict 가 아닌 JSON (list/string) → None 으로 정규화."""
        ans, elap, hints = attempts_mod._deserialize_subq_dicts(
            json.dumps([1, 2, 3]),  # list
            json.dumps("hello"),    # string
            json.dumps(42),         # int
        )
        self.assertIsNone(ans)
        self.assertIsNone(elap)
        self.assertIsNone(hints)


# ─── 3. 헬퍼 — _compute_hint_meta ───────────────────────────────────


class ComputeHintMetaTest(unittest.TestCase):
    """_compute_hint_meta count + steps_max 산출."""

    def test_compute_hint_meta_none_returns_zero(self):
        """None 입력 → {count:0, steps_max:0}."""
        meta = attempts_mod._compute_hint_meta(None)
        self.assertEqual(meta, {"count": 0, "steps_max": 0})

    def test_compute_hint_meta_empty_dict(self):
        """빈 dict → 0/0."""
        meta = attempts_mod._compute_hint_meta({})
        self.assertEqual(meta, {"count": 0, "steps_max": 0})

    def test_compute_hint_meta_single_card(self):
        """단일 카드 — count + steps_max 정확."""
        meta = attempts_mod._compute_hint_meta({"설문 1": [1, 2, 3]})
        self.assertEqual(meta, {"count": 3, "steps_max": 3})

    def test_compute_hint_meta_multi_card_sums_count(self):
        """다중 카드 — count 합산, steps_max 최대값."""
        meta = attempts_mod._compute_hint_meta(
            {"설문 1": [1, 2, 3], "설문 2": [1, 2]}
        )
        # count = 3 + 2 = 5, max = 3 (둘 다 3 못 넘음)
        self.assertEqual(meta, {"count": 5, "steps_max": 3})

    def test_compute_hint_meta_steps_max_across_cards(self):
        """steps_max — 한쪽 카드에서만 5단계 도달해도 잡힘."""
        meta = attempts_mod._compute_hint_meta(
            {"설문 1": [1], "설문 2": [1, 2, 3, 4, 5]}
        )
        self.assertEqual(meta, {"count": 6, "steps_max": 5})

    def test_compute_hint_meta_invalid_step_range_ignored(self):
        """1~5 범위 밖 step 은 count + steps_max 모두에 무시."""
        meta = attempts_mod._compute_hint_meta(
            {"설문 1": [0, 6, 7, 99, -1]}
        )
        self.assertEqual(meta, {"count": 0, "steps_max": 0})

    def test_compute_hint_meta_invalid_value_types(self):
        """list 가 아닌 값 / int 아닌 step → 무시."""
        meta = attempts_mod._compute_hint_meta(
            {"설문 1": "not a list", "설문 2": [1, "string", None, 2]}
        )
        # 설문 1 전체 무시 / 설문 2 의 1, 2 만 카운트
        self.assertEqual(meta, {"count": 2, "steps_max": 2})

    def test_compute_hint_meta_not_dict_returns_zero(self):
        """dict 아닌 입력 (list / int / str) → 0/0 (방어 코드)."""
        self.assertEqual(
            attempts_mod._compute_hint_meta([1, 2, 3]),
            {"count": 0, "steps_max": 0},
        )
        self.assertEqual(
            attempts_mod._compute_hint_meta("string"),
            {"count": 0, "steps_max": 0},
        )


# ─── 4. create_attempt — 입력 호환 매트릭스 ───────────────────────────


class CreateAttemptCompatTest(unittest.TestCase):
    """create_attempt — legacy answer_text / 신규 answer_subq / 둘 다 / 둘 다 없음."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "tc24-3")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_create_attempt_legacy_answer_text_only(self):
        """legacy 단일 카드 — answer_text 만, answer_subq=None."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_text="레거시 단일 답안 본문",
                grading_mode="manual",
            )
        self.assertGreater(result["attempt_id"], 0)
        self.assertEqual(result["status"], "pending_grade")
        self.assertEqual(result["subq_count"], 0)  # answer_subq 없으면 0
        self.assertEqual(result["hints_used_count"], 0)
        self.assertEqual(result["hint_steps_revealed_max"], 0)

        # DB 직접 검증 — answer_subq NULL
        cur = self.conn.execute(
            "SELECT answer_text, answer_subq, subq_elapsed, hints_used "
            "FROM attempts WHERE id = ?",
            (result["attempt_id"],),
        )
        row = cur.fetchone()
        self.assertEqual(row["answer_text"], "레거시 단일 답안 본문")
        self.assertIsNone(row["answer_subq"])
        self.assertIsNone(row["subq_elapsed"])
        self.assertIsNone(row["hints_used"])

    def test_create_attempt_subq_multi_card(self):
        """신규 다중 카드 — answer_subq + subq_elapsed + hints_used."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_subq={"설문 1": "답안 1 본문", "설문 2": "답안 2 본문"},
                subq_elapsed={"설문 1": 120, "설문 2": 180},
                hints_used={"설문 1": [1, 2], "설문 2": [1]},
                grading_mode="manual",
            )
        self.assertEqual(result["subq_count"], 2)
        self.assertEqual(result["hints_used_count"], 3)  # 2 + 1
        self.assertEqual(result["hint_steps_revealed_max"], 2)

        # DB — answer_text 가 자동 join 으로 채워졌는지
        cur = self.conn.execute(
            "SELECT answer_text, answer_subq, subq_elapsed, hints_used "
            "FROM attempts WHERE id = ?",
            (result["attempt_id"],),
        )
        row = cur.fetchone()
        self.assertIn("[설문 1]", row["answer_text"])
        self.assertIn("답안 1 본문", row["answer_text"])
        self.assertIn("[설문 2]", row["answer_text"])

        # JSON 한글 보존
        ans_loaded = json.loads(row["answer_subq"])
        self.assertEqual(ans_loaded["설문 1"], "답안 1 본문")
        elap_loaded = json.loads(row["subq_elapsed"])
        self.assertEqual(elap_loaded["설문 1"], 120)
        hints_loaded = json.loads(row["hints_used"])
        self.assertEqual(hints_loaded["설문 1"], [1, 2])

    def test_create_attempt_both_provided(self):
        """answer_text + answer_subq 양쪽 — 양쪽 그대로 저장 (R-09)."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_text="legacy 답안",
                answer_subq={"설문 1": "신규 답안"},
                grading_mode="manual",
            )
        cur = self.conn.execute(
            "SELECT answer_text, answer_subq FROM attempts WHERE id = ?",
            (result["attempt_id"],),
        )
        row = cur.fetchone()
        # answer_text 가 제공됐으므로 join 으로 덮어쓰지 않음
        self.assertEqual(row["answer_text"], "legacy 답안")
        ans_loaded = json.loads(row["answer_subq"])
        self.assertEqual(ans_loaded["설문 1"], "신규 답안")

    def test_create_attempt_validation_both_none_raises(self):
        """answer_text + answer_subq 둘 다 빈 값 → AttemptValidationError."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            with self.assertRaises(attempts_mod.AttemptValidationError) as ctx:
                attempts_mod.create_attempt(
                    self.conn,
                    self.db_path,
                    "tc24-3",
                    grading_mode="manual",
                )
            self.assertEqual(ctx.exception.error_code, "subq_empty")

    def test_create_attempt_validation_empty_string_text(self):
        """answer_text 빈 문자열 + answer_subq=None → 거부."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            with self.assertRaises(attempts_mod.AttemptValidationError):
                attempts_mod.create_attempt(
                    self.conn,
                    self.db_path,
                    "tc24-3",
                    answer_text="   ",  # 공백만
                    grading_mode="manual",
                )

    def test_create_attempt_validation_empty_subq_values(self):
        """answer_subq dict 자체 있지만 모든 value 빈 문자열 → 거부."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            with self.assertRaises(attempts_mod.AttemptValidationError):
                attempts_mod.create_attempt(
                    self.conn,
                    self.db_path,
                    "tc24-3",
                    answer_subq={"설문 1": "", "설문 2": "   "},
                    grading_mode="manual",
                )

    def test_create_attempt_hints_meta_with_no_hints(self):
        """다중 카드인데 힌트 0 — count/steps_max 모두 0."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_subq={"설문 1": "답안", "설문 2": "답안"},
                grading_mode="manual",
            )
        self.assertEqual(result["hints_used_count"], 0)
        self.assertEqual(result["hint_steps_revealed_max"], 0)
        self.assertEqual(result["subq_count"], 2)


# ─── 5. get_attempt — legacy fallback / 다중 노출 ─────────────────────


class GetAttemptSubqTest(unittest.TestCase):
    """get_attempt 응답에 answer_subq/subq_elapsed/hints_used + 메타 노출."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "tc24-3")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_get_attempt_legacy_fallback(self):
        """legacy attempt (answer_subq NULL) → answer_subq=None + 메타 0."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_text="legacy 답안",
                grading_mode="manual",
            )
        got = attempts_mod.get_attempt(self.conn, result["attempt_id"])
        self.assertIsNone(got["answer_subq"])
        self.assertIsNone(got["subq_elapsed"])
        self.assertIsNone(got["hints_used"])
        self.assertEqual(got["hints_used_count"], 0)
        self.assertEqual(got["hint_steps_revealed_max"], 0)
        # answer_text 는 pending_grade 시 그대로 노출 (Step 13 호환)
        self.assertEqual(got["answer_text"], "legacy 답안")

    def test_get_attempt_multi_card(self):
        """다중 카드 — answer_subq/elapsed/hints 모두 dict 로 노출."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_subq={"설문 1": "답안 일", "설문 2": "답안 이"},
                subq_elapsed={"설문 1": 100, "설문 2": 200},
                hints_used={"설문 1": [1, 2], "설문 2": [1, 2, 3]},
                grading_mode="manual",
            )
        got = attempts_mod.get_attempt(self.conn, result["attempt_id"])
        self.assertEqual(got["answer_subq"], {"설문 1": "답안 일", "설문 2": "답안 이"})
        self.assertEqual(got["subq_elapsed"], {"설문 1": 100, "설문 2": 200})
        self.assertEqual(got["hints_used"], {"설문 1": [1, 2], "설문 2": [1, 2, 3]})
        self.assertEqual(got["hints_used_count"], 5)  # 2 + 3
        self.assertEqual(got["hint_steps_revealed_max"], 3)


# ─── 6. list_attempts — 히스토리 메타 노출 ────────────────────────────


class ListAttemptsHintsMetaTest(unittest.TestCase):
    """list_attempts 응답 list 각 item 에 메타 4종 노출."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "tc24-3")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_list_attempts_hints_count_meta(self):
        """다중 카드 attempt — list item 에 hints_used_count + steps_max + subq_count + total_solve_sec."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_subq={"설문 1": "답안", "설문 2": "답안"},
                subq_elapsed={"설문 1": 60, "설문 2": 120},
                hints_used={"설문 1": [1, 2, 3], "설문 2": [1]},
                grading_mode="manual",
            )
        out = attempts_mod.list_attempts(self.conn, case_id="tc24-3")
        self.assertEqual(len(out["attempts"]), 1)
        item = out["attempts"][0]
        self.assertEqual(item["subq_count"], 2)
        self.assertEqual(item["hints_used_count"], 4)  # 3 + 1
        self.assertEqual(item["hint_steps_revealed_max"], 3)
        self.assertEqual(item["total_solve_sec"], 180)  # 60 + 120

    def test_list_attempts_legacy_meta_zero(self):
        """legacy attempt — 메타 모두 0/None."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                answer_text="legacy 답안",
                grading_mode="manual",
            )
        out = attempts_mod.list_attempts(self.conn, case_id="tc24-3")
        self.assertEqual(len(out["attempts"]), 1)
        item = out["attempts"][0]
        self.assertEqual(item["subq_count"], 0)
        self.assertEqual(item["hints_used_count"], 0)
        self.assertEqual(item["hint_steps_revealed_max"], 0)
        self.assertIsNone(item["total_solve_sec"])


# ─── 7. inject_grade — criteria_subq + legacy 양립 ──────────────────


class InjectGradeSubqTest(unittest.TestCase):
    """inject_grade — criteria_subq 다중 카드 vs legacy criteria 단일."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "tc24-3")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _create_pending(self, **kw) -> int:
        """pending_grade attempt 생성 헬퍼."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn,
                self.db_path,
                "tc24-3",
                grading_mode="manual",
                **kw,
            )
        return result["attempt_id"]

    def test_inject_grade_legacy_no_subq_key(self):
        """legacy criteria 1차원 list → attempt_criteria.subq_key=NULL 9 row."""
        aid = self._create_pending(answer_text="legacy 단일")
        payload = {
            "criteria": _full_criteria_9(),
            "total_score": 65.0,
            "max_score": 100.0,
            "score_pct": 65.0,
            "grade": "C",
            "eval_notes": _full_eval_notes(),
        }
        attempts_mod.inject_grade(self.conn, aid, payload)

        cur = self.conn.execute(
            "SELECT criterion_key, subq_key FROM attempt_criteria "
            "WHERE attempt_id = ? ORDER BY id ASC",
            (aid,),
        )
        rows = cur.fetchall()
        self.assertEqual(len(rows), 9, "9기준 row 전부")
        for r in rows:
            self.assertIsNone(r["subq_key"], "legacy 모드는 subq_key=NULL")

    def test_inject_grade_with_subq_key(self):
        """criteria_subq dict → attempt_criteria.subq_key 채움 (다중 카드)."""
        aid = self._create_pending(
            answer_subq={"설문 1": "답안 일", "설문 2": "답안 이"}
        )
        payload = {
            "criteria_subq": {
                "설문 1": _full_criteria_9(),
                "설문 2": _full_criteria_9(extra_score=1.0),
            },
            "total_score": 132.0,
            "max_score": 200.0,
            "score_pct": 66.0,
            "grade": "C",
            "eval_notes": _full_eval_notes(),
        }
        attempts_mod.inject_grade(self.conn, aid, payload)

        cur = self.conn.execute(
            "SELECT criterion_key, subq_key FROM attempt_criteria "
            "WHERE attempt_id = ? ORDER BY subq_key, id ASC",
            (aid,),
        )
        rows = cur.fetchall()
        self.assertEqual(len(rows), 18, "9기준 × 2카드")
        subq_keys = {r["subq_key"] for r in rows}
        self.assertEqual(subq_keys, {"설문 1", "설문 2"})

    def test_inject_grade_subq_returns_criteria_subq(self):
        """get_attempt 응답에 criteria_subq dict 노출."""
        aid = self._create_pending(
            answer_subq={"설문 1": "답안 일", "설문 2": "답안 이"}
        )
        payload = {
            "criteria_subq": {
                "설문 1": _full_criteria_9(),
                "설문 2": _full_criteria_9(),
            },
            "total_score": 130.0,
            "max_score": 200.0,
            "score_pct": 65.0,
            "grade": "C",
            "eval_notes": _full_eval_notes(),
        }
        got = attempts_mod.inject_grade(self.conn, aid, payload)
        self.assertIn("criteria_subq", got)
        self.assertIn("설문 1", got["criteria_subq"])
        self.assertIn("설문 2", got["criteria_subq"])
        # 카드별 9 entries 정렬 (CRITERION_KEYS 순)
        self.assertEqual(len(got["criteria_subq"]["설문 1"]), 9)
        self.assertEqual(len(got["criteria_subq"]["설문 2"]), 9)
        self.assertEqual(
            [c["key"] for c in got["criteria_subq"]["설문 1"]],
            list(grader_mod.CRITERION_KEYS),
        )

    def test_inject_grade_legacy_no_criteria_subq_key(self):
        """legacy 단일 — get_attempt 응답에 criteria_subq 키 없음."""
        aid = self._create_pending(answer_text="legacy")
        payload = {
            "criteria": _full_criteria_9(),
            "total_score": 65.0,
            "max_score": 100.0,
            "score_pct": 65.0,
            "grade": "C",
            "eval_notes": _full_eval_notes(),
        }
        got = attempts_mod.inject_grade(self.conn, aid, payload)
        self.assertNotIn("criteria_subq", got)
        # legacy criteria 는 그대로 보존
        self.assertEqual(len(got["criteria"]), 9)

    def test_inject_grade_criteria_subq_empty_dict_raises(self):
        """criteria_subq 빈 dict → GradeInjectionError."""
        aid = self._create_pending(answer_subq={"설문 1": "답안"})
        payload = {
            "criteria_subq": {},
            "total_score": 0.0, "max_score": 100.0, "score_pct": 0.0,
            "grade": "F", "eval_notes": _full_eval_notes(),
        }
        with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
            attempts_mod.inject_grade(self.conn, aid, payload)
        self.assertEqual(ctx.exception.error_code, "criteria_subq_required")

    def test_inject_grade_criteria_subq_not_dict_raises(self):
        """criteria_subq 가 dict 아님 (list 등) → GradeInjectionError."""
        aid = self._create_pending(answer_subq={"설문 1": "답안"})
        payload = {
            "criteria_subq": [1, 2, 3],  # list — 잘못된 형식
            "total_score": 0.0, "max_score": 100.0, "score_pct": 0.0,
            "grade": "F", "eval_notes": _full_eval_notes(),
        }
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod.inject_grade(self.conn, aid, payload)

    def test_inject_grade_missing_both_criteria_raises(self):
        """criteria 도 criteria_subq 도 없음 → GradeInjectionError(criteria_subq_required)."""
        aid = self._create_pending(answer_text="ans")
        payload = {
            "total_score": 0.0, "max_score": 100.0, "score_pct": 0.0,
            "grade": "F", "eval_notes": _full_eval_notes(),
        }
        with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
            attempts_mod.inject_grade(self.conn, aid, payload)
        self.assertEqual(ctx.exception.error_code, "criteria_subq_required")

    def test_inject_grade_subq_invalid_key_type(self):
        """criteria_subq key 가 빈 문자열 / 비문자열 → 거부."""
        aid = self._create_pending(answer_subq={"설문 1": "답안"})
        payload = {
            "criteria_subq": {"": _full_criteria_9()},  # 빈 key
            "total_score": 0.0, "max_score": 100.0, "score_pct": 0.0,
            "grade": "F", "eval_notes": _full_eval_notes(),
        }
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod.inject_grade(self.conn, aid, payload)

    def test_inject_grade_subq_partial_criteria_missing_keys(self):
        """criteria_subq 한 카드의 criteria 가 9키 미달 → _normalize_criteria 에러."""
        aid = self._create_pending(answer_subq={"설문 1": "답안"})
        partial = _full_criteria_9()[:5]  # 5기준만
        payload = {
            "criteria_subq": {"설문 1": partial},
            "total_score": 0.0, "max_score": 100.0, "score_pct": 0.0,
            "grade": "F", "eval_notes": _full_eval_notes(),
        }
        with self.assertRaises(attempts_mod.GradeInjectionError):
            attempts_mod.inject_grade(self.conn, aid, payload)


# ─── 8. get_attempt — done + 다중 채점 criteria_subq 응답 ─────────────


class GetAttemptDoneSubqTest(unittest.TestCase):
    """채점 완료된 다중 attempt 의 criteria_subq + legacy criteria 호환."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        _build_db(self.db_path)
        self.conn = db_mod.get_conn(self.db_path)
        _seed_case(self.conn, "tc24-3")

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_get_attempt_done_legacy_single_criteria(self):
        """legacy 채점 — criteria 9 entries + criteria_subq 없음."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn, self.db_path, "tc24-3",
                answer_text="legacy", grading_mode="manual",
            )
        aid = result["attempt_id"]
        attempts_mod.inject_grade(self.conn, aid, {
            "criteria": _full_criteria_9(),
            "total_score": 65.0, "max_score": 100.0, "score_pct": 65.0,
            "grade": "C", "eval_notes": _full_eval_notes(),
        })
        got = attempts_mod.get_attempt(self.conn, aid)
        self.assertEqual(got["status"], "completed")
        self.assertEqual(len(got["criteria"]), 9)
        self.assertNotIn("criteria_subq", got)

    def test_get_attempt_done_multi_criteria_subq(self):
        """다중 채점 — criteria_subq dict + criteria (첫 카드, legacy 호환)."""
        with patch.object(cases_mod, "get_case", return_value=_fake_case_meta()):
            result = attempts_mod.create_attempt(
                self.conn, self.db_path, "tc24-3",
                answer_subq={"설문 1": "답안 일", "설문 2": "답안 이"},
                grading_mode="manual",
            )
        aid = result["attempt_id"]
        attempts_mod.inject_grade(self.conn, aid, {
            "criteria_subq": {
                "설문 1": _full_criteria_9(),
                "설문 2": _full_criteria_9(),
            },
            "total_score": 130.0, "max_score": 200.0, "score_pct": 65.0,
            "grade": "C", "eval_notes": _full_eval_notes(),
        })
        got = attempts_mod.get_attempt(self.conn, aid)
        self.assertIn("criteria_subq", got)
        self.assertEqual(set(got["criteria_subq"].keys()), {"설문 1", "설문 2"})
        # legacy criteria 는 첫 카드 entries (호환)
        self.assertEqual(len(got["criteria"]), 9)


if __name__ == "__main__":
    unittest.main()
