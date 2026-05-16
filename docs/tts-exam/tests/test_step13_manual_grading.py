#!/usr/bin/env python3
"""Step 13 — manual 채점 모드 단위 테스트.

- settings.grading_mode (load/save/validate)
- attempts.create_attempt 모드 분기 (manual → pending_grade, auto → grading)
- attempts.inject_grade (외부 채점 결과 주입)
- ANTHROPIC_API_KEY 미설정 시 auto → manual fallback

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step13_manual_grading.py -v
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# 본 모듈 import (tests/ → 부모 docs/tts-exam)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 테스트 격리: cases 의 BASE_PATH 를 임시 디렉토리로 강제.
# (cases.py 가 import 시점에 BASE_PATH 를 굳히므로 import 이전에 env 세팅).
_TEST_BASE = tempfile.mkdtemp(prefix="lawear_step13_base_")
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
import settings as settings_mod  # noqa: E402

# import 이전 BASE_PATH 캐싱 안전화: cases 모듈이 이미 import 됐다면 BASE_PATH 재계산
if str(cases_mod.BASE_PATH) != _TEST_BASE:
    cases_mod.BASE_PATH = Path(_TEST_BASE).resolve()


# ─── 픽스처 ──────────────────────────────────────────────────────────


def _build_db(db_path: str) -> None:
    """공식 마이그(v1+v2+v3)로 DB 초기화 + 케이스 1건 시드."""
    db_mod.init_db(db_path)
    with db_mod.get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO cases
              (id, subject, subject_kor, category, file, case_no, title, path, points, synced_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TC_CASE",
                "minbeop",
                "민법",
                "입문",
                "미케01",
                "01",
                "테스트 케이스",
                "_test/dummy.md",  # _TEST_BASE 안의 더미 파일 (위에서 생성)
                17,
                "2026-05-16T00:00:00Z",
                "deadbeef",
            ),
        )
        conn.commit()


def _full_grade_payload(**overrides) -> dict:
    """PUT /grade 입력 — 9기준 + total/max/pct + grade + eval_notes (Step 21 v5).

    가중치 합: 16+13+8+10+12+15+11+10+5 = 100
    """
    base = {
        "criteria": [
            {"key": "mnemonics", "score": 3, "weight_applied": 16, "comment": "두문자 일부 반영"},
            {"key": "color", "score": 11, "weight_applied": 13, "comment": "색강조 OK"},
            {"key": "underline", "score": 2, "weight_applied": 8, "comment": "밑줄 OK"},
            {"key": "outline", "score": 3, "weight_applied": 10, "comment": "목차 일치"},
            {"key": "semantic", "score": 8, "weight_applied": 12, "comment": "의미 일치"},
            {"key": "richness", "score": 11, "weight_applied": 15, "comment": "원본 대비 풍부함"},
            {"key": "missing", "score": -2, "weight_applied": 11, "comment": "증명책임 누락"},
            {"key": "articles", "score": 8, "weight_applied": 10, "comment": "제397조 명시"},
            {"key": "case_apply", "score": 3, "weight_applied": 5, "comment": "사안 적용 양호 (Step 21)"},
        ],
        "total_score": 14.78,
        "max_score": 17.0,
        "score_pct": 82.47,
        "grade": "B",
        "eval_notes": {
            "strength": "목차 OK",
            "caution": "두문자 풀이형 누락",
            "missing": "증명책임 분배",
        },
        "diff_segments": [
            {"type": "match", "text": "재건축조합"},
            {"type": "miss", "text": "단체"},
        ],
    }
    base.update(overrides)
    return base


def _cleanup_env() -> None:
    """환경 변수 정리 — 테스트 격리."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["LAWEAR_GRADER_MOCK"] = "1"  # auto 분기 시 mock 채점만 시도


# ─── settings.grading_mode ───────────────────────────────────────────


class SettingsGradingModeTest(unittest.TestCase):
    """settings 모듈의 grading_mode 로드/저장/검증."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_default_grading_mode_is_manual(self) -> None:
        """마이그 v3 초기 INSERT → 'manual'."""
        with db_mod.get_conn(self.tmp.name) as conn:
            mode = settings_mod.load_grading_mode(conn)
        self.assertEqual(mode, "manual")

    def test_load_all_includes_grading_mode(self) -> None:
        """GET /api/settings 응답에 grading_mode 포함."""
        with db_mod.get_conn(self.tmp.name) as conn:
            data = settings_mod.load_all(conn)
        self.assertIn("grading_mode", data)
        self.assertEqual(data["grading_mode"], "manual")

    def test_save_grading_mode_auto(self) -> None:
        """PUT /api/settings {grading_mode: 'auto'} → 저장됨."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = settings_mod.save_settings(conn, grading_mode="auto")
            self.assertEqual(out["grading_mode"], "auto")
            mode = settings_mod.load_grading_mode(conn)
        self.assertEqual(mode, "auto")

    def test_validate_grading_mode_rejects_unknown(self) -> None:
        """허용 외 값 → SettingsValidationError(bad_request)."""
        with self.assertRaises(settings_mod.SettingsValidationError) as ctx:
            settings_mod.validate_grading_mode("hybrid")
        self.assertEqual(ctx.exception.error_code, "bad_request")

    def test_validate_grading_mode_rejects_non_string(self) -> None:
        """int 등 비문자열 → bad_request."""
        with self.assertRaises(settings_mod.SettingsValidationError):
            settings_mod.validate_grading_mode(42)

    def test_validate_grading_mode_accepts_manual_and_auto(self) -> None:
        self.assertEqual(settings_mod.validate_grading_mode("manual"), "manual")
        self.assertEqual(settings_mod.validate_grading_mode("auto"), "auto")
        # whitespace 허용
        self.assertEqual(settings_mod.validate_grading_mode("  manual  "), "manual")

    def test_load_corrupt_value_falls_back_to_default(self) -> None:
        """비-허용 값이 DB 에 있어도 디폴트 'manual' 반환 (R-09 안전)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            conn.execute(
                "UPDATE settings SET value_json = ? WHERE key = ?",
                (json.dumps("hybrid"), "grading_mode"),
            )
            conn.commit()
            mode = settings_mod.load_grading_mode(conn)
        self.assertEqual(mode, "manual")


# ─── attempts.create_attempt 모드 분기 ─────────────────────────────────


class CreateAttemptModeBranchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        # 환경 격리
        self._saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        self._saved_mock = os.environ.pop("LAWEAR_GRADER_MOCK", None)
        os.environ["LAWEAR_GRADER_MOCK"] = "1"  # auto 분기에서도 mock 채점

    def tearDown(self) -> None:
        if self._saved_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = self._saved_key
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        if self._saved_mock is not None:
            os.environ["LAWEAR_GRADER_MOCK"] = self._saved_mock
        else:
            os.environ.pop("LAWEAR_GRADER_MOCK", None)
        os.unlink(self.tmp.name)

    def test_manual_mode_inserts_pending_grade_status(self) -> None:
        """manual → status='pending_grade', thread X."""
        with db_mod.get_conn(self.tmp.name) as conn:
            result = attempts_mod.create_attempt(
                conn,
                self.tmp.name,
                case_id="TC_CASE",
                answer_text="manual 답안 본문",
                grading_mode="manual",
            )
            self.assertEqual(result["status"], "pending_grade")
            self.assertEqual(result["grading_mode"], "manual")
            self.assertNotIn("warning", result)

            row = conn.execute(
                "SELECT status, answer_text FROM attempts WHERE id = ?",
                (result["attempt_id"],),
            ).fetchone()
        self.assertEqual(row["status"], "pending_grade")
        self.assertEqual(row["answer_text"], "manual 답안 본문")

    def test_auto_mode_with_no_api_key_falls_back_to_manual(self) -> None:
        """auto + ANTHROPIC_API_KEY 미설정 → manual 강등 + warning."""
        with db_mod.get_conn(self.tmp.name) as conn:
            result = attempts_mod.create_attempt(
                conn,
                self.tmp.name,
                case_id="TC_CASE",
                answer_text="auto fallback",
                grading_mode="auto",
            )
        self.assertEqual(result["status"], "pending_grade")
        self.assertEqual(result["grading_mode"], "manual")
        self.assertIn("warning", result)
        self.assertIn("api_key_missing", result["warning"])

    def test_auto_mode_with_key_uses_grading_status(self) -> None:
        """auto + 키 있음 → status='grading' (백그라운드 mock 채점)."""
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-dummy"
        try:
            with db_mod.get_conn(self.tmp.name) as conn:
                result = attempts_mod.create_attempt(
                    conn,
                    self.tmp.name,
                    case_id="TC_CASE",
                    answer_text="auto 답안",
                    grading_mode="auto",
                )
            # 즉시 응답은 grading (백그라운드 thread 진행 중)
            self.assertEqual(result["grading_mode"], "auto")
            self.assertIn(result["status"], ("grading", "completed"))
            self.assertNotIn("warning", result)
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_manual_response_does_not_include_warning_field(self) -> None:
        """manual 정상 응답에는 warning 키 자체가 없음."""
        with db_mod.get_conn(self.tmp.name) as conn:
            result = attempts_mod.create_attempt(
                conn,
                self.tmp.name,
                case_id="TC_CASE",
                answer_text="x",
                grading_mode="manual",
            )
        self.assertNotIn("warning", result)


# ─── attempts.inject_grade (PUT /api/attempts/{id}/grade) ──────────────


class InjectGradeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        _cleanup_env()
        # pending_grade attempt 1건 생성
        with db_mod.get_conn(self.tmp.name) as conn:
            self.attempt_id = attempts_mod.create_attempt(
                conn,
                self.tmp.name,
                case_id="TC_CASE",
                answer_text="검토 의견 본문",
                grading_mode="manual",
            )["attempt_id"]

    def tearDown(self) -> None:
        os.environ.pop("LAWEAR_GRADER_MOCK", None)
        os.unlink(self.tmp.name)

    def test_inject_grade_marks_attempt_completed(self) -> None:
        """정상 입력 → status='done' (client 라벨 'completed', Step 21 v5 9기준)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())
            self.assertEqual(out["status"], "completed")
            self.assertEqual(out["grade"], "B")
            # Step 20 v4: 소수점 2자리 (실제 시험 형식)
            self.assertAlmostEqual(out["score_total"], 14.78, places=2)
            self.assertEqual(len(out["criteria"]), 9)

            # 8기준 모두 DB 에 row 존재 (Step 20 v4 — articles 신설)
            rows = conn.execute(
                "SELECT criterion_key FROM attempt_criteria WHERE attempt_id = ?",
                (self.attempt_id,),
            ).fetchall()
        keys = sorted(r["criterion_key"] for r in rows)
        self.assertEqual(keys, sorted(["mnem", "color", "under", "outline", "sem", "rich", "miss", "articles", "case_apply"]))

    def test_inject_grade_404_for_unknown_attempt(self) -> None:
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.AttemptNotFoundError):
                attempts_mod.inject_grade(conn, 999999, _full_grade_payload())

    def test_inject_grade_409_when_already_done(self) -> None:
        """이미 'done' 상태 → AttemptAlreadyGradedError."""
        with db_mod.get_conn(self.tmp.name) as conn:
            attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())
            with self.assertRaises(attempts_mod.AttemptAlreadyGradedError):
                attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())

    def test_inject_grade_400_missing_criteria_key(self) -> None:
        """8기준 중 'missing' 누락 → GradeInjectionError (Step 20 v4)."""
        payload = _full_grade_payload()
        payload["criteria"] = [c for c in payload["criteria"] if c["key"] != "missing"]
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
                attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertIn("missing keys", str(ctx.exception))

    def test_inject_grade_400_missing_articles_key(self) -> None:
        """Step 20 v4: 'articles' 누락 → GradeInjectionError (v3 호환 데이터 거부)."""
        payload = _full_grade_payload()
        payload["criteria"] = [c for c in payload["criteria"] if c["key"] != "articles"]
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
                attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertIn("articles", str(ctx.exception))

    def test_inject_grade_400_unknown_criteria_alias(self) -> None:
        """잘못된 key (예: 'foo') → GradeInjectionError."""
        payload = _full_grade_payload()
        payload["criteria"][0]["key"] = "foo"
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError):
                attempts_mod.inject_grade(conn, self.attempt_id, payload)

    def test_inject_grade_accepts_short_aliases(self) -> None:
        """grader.CRITERION_KEYS 짧은 이름 직접 입력도 OK (Step 21 v5 — case_apply 포함)."""
        payload = _full_grade_payload()
        # 모든 키를 짧은 이름으로 치환
        long_to_short = {
            "mnemonics": "mnem", "color": "color", "underline": "under",
            "outline": "outline", "semantic": "sem", "richness": "rich",
            "missing": "miss",
            "articles": "articles",  # Step 20 v4 — long/short 동일
            "case_apply": "case_apply",  # Step 21 v5 — long/short 동일
        }
        for c in payload["criteria"]:
            c["key"] = long_to_short[c["key"]]
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertEqual(out["status"], "completed")

    def test_inject_grade_400_missing_required_field(self) -> None:
        """eval_notes 누락 → GradeInjectionError."""
        payload = _full_grade_payload()
        del payload["eval_notes"]
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError) as ctx:
                attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertIn("eval_notes", str(ctx.exception))

    def test_inject_grade_400_invalid_grade_enum(self) -> None:
        """grade='X' (허용 외) → bad_request."""
        payload = _full_grade_payload()
        payload["grade"] = "X"
        with db_mod.get_conn(self.tmp.name) as conn:
            with self.assertRaises(attempts_mod.GradeInjectionError):
                attempts_mod.inject_grade(conn, self.attempt_id, payload)

    def test_inject_grade_default_model_label(self) -> None:
        """model 미지정 시 'claude-code-opus' 디폴트."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())
        self.assertEqual(out["model"], "claude-code-opus")

    def test_inject_grade_eval_notes_normalization(self) -> None:
        """eval_notes 의 3키만 저장, 불필요 키는 무시."""
        payload = _full_grade_payload()
        payload["eval_notes"] = {"strength": "S", "caution": "C", "missing": "M", "extra": "ignored"}
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertEqual(out["eval_notes"]["strength"], "S")
        self.assertEqual(out["eval_notes"]["caution"], "C")
        self.assertEqual(out["eval_notes"]["missing"], "M")
        self.assertNotIn("extra", out["eval_notes"])

    def test_inject_grade_diff_html_generated(self) -> None:
        """diff_segments → diff_html span 변환."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())
        self.assertIn("<span", out["diff_html"])
        self.assertIn('class="match"', out["diff_html"])
        self.assertIn('class="miss"', out["diff_html"])

    def test_inject_grade_missing_diff_segments_ok(self) -> None:
        """diff_segments 미제공 → 빈 배열로 처리."""
        payload = _full_grade_payload()
        del payload["diff_segments"]
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.inject_grade(conn, self.attempt_id, payload)
        self.assertEqual(out["diff_segments"], [])
        self.assertEqual(out["diff_html"], "")


# ─── pending_grade 조회 응답에 answer_text 포함 ────────────────────────


class PendingGradeListingTest(unittest.TestCase):
    """list_attempts(status='pending_grade') + get_attempt 모두 answer_text 노출."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        _cleanup_env()
        with db_mod.get_conn(self.tmp.name) as conn:
            self.attempt_id = attempts_mod.create_attempt(
                conn,
                self.tmp.name,
                case_id="TC_CASE",
                answer_text="외부 채점용 답안 본문 — 전체 길이 그대로",
                grading_mode="manual",
            )["attempt_id"]

    def tearDown(self) -> None:
        os.environ.pop("LAWEAR_GRADER_MOCK", None)
        os.unlink(self.tmp.name)

    def test_list_attempts_filter_status_pending_grade(self) -> None:
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.list_attempts(conn, status="pending_grade")
        items = out["attempts"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "pending_grade")
        # Step 13 — answer_text 노출 (외부 채점 자료)
        self.assertEqual(items[0]["answer_text"], "외부 채점용 답안 본문 — 전체 길이 그대로")
        self.assertEqual(items[0]["case_id"], "TC_CASE")
        self.assertIsNotNone(items[0]["submitted_at"])

    def test_get_attempt_pending_includes_answer_text(self) -> None:
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.get_attempt(conn, self.attempt_id)
        self.assertEqual(out["status"], "pending_grade")
        self.assertIn("answer_text", out)
        self.assertEqual(out["answer_text"], "외부 채점용 답안 본문 — 전체 길이 그대로")


# ─── 마이그레이션 v3 ───────────────────────────────────────────────────


class MigrationV3Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def tearDown(self) -> None:
        os.unlink(self.tmp.name)

    def test_init_db_reaches_v3(self) -> None:
        """Step 21 v5 (2026-05-17): TARGET_SCHEMA_VERSION=5 (함수명은 호환 유지)."""
        version = db_mod.init_db(self.tmp.name)
        self.assertEqual(version, 5)

    def test_status_check_constraint_accepts_pending_grade(self) -> None:
        """attempts.status='pending_grade' INSERT 가능."""
        db_mod.init_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO cases
                  (id, subject, subject_kor, category, file, case_no, title, path, points, synced_at, content_hash)
                VALUES ('C', 's', 'S', 'C', 'F', '01', 'T', 'p', 0, 't', 'h')
                """
            )
            conn.execute(
                """
                INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json)
                VALUES ('C', 'x', 't', 'pending_grade', '{}')
                """
            )
            conn.commit()
            n = conn.execute("SELECT count(*) FROM attempts WHERE status='pending_grade'").fetchone()[0]
        self.assertEqual(n, 1)

    def test_status_check_constraint_rejects_unknown(self) -> None:
        """미허용 status (예: 'queued') 는 CHECK 위반."""
        db_mod.init_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO cases
                  (id, subject, subject_kor, category, file, case_no, title, path, points, synced_at, content_hash)
                VALUES ('C', 's', 'S', 'C', 'F', '01', 'T', 'p', 0, 't', 'h')
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json)
                    VALUES ('C', 'x', 't', 'queued', '{}')
                    """
                )

    def test_settings_has_grading_mode_row(self) -> None:
        db_mod.init_db(self.tmp.name)
        with db_mod.get_conn(self.tmp.name) as conn:
            row = conn.execute(
                "SELECT value_json FROM settings WHERE key='grading_mode'"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(json.loads(row["value_json"]), "manual")


if __name__ == "__main__":
    unittest.main()
