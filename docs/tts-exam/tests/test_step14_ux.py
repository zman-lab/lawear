#!/usr/bin/env python3
"""Step 14 — 시안 UX 보강 단위 테스트.

본 단계는 주로 시안(index.html/JS) 변경이지만, 백엔드 회귀가 1건 있다:
- GET /api/attempts/{id} 의 done 응답에 `answer_text` 포함 (시안 Reference Diff
  2열 분할 "내 답안 vs Lv.1" 렌더링 자료).

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step14_ux.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 본 모듈 import (tests/ → 부모 docs/tts-exam)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 테스트 격리: cases 의 BASE_PATH 를 임시 디렉토리로 강제.
_TEST_BASE = tempfile.mkdtemp(prefix="lawear_step14_base_")
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
                "_test/dummy.md",
                17,
                "2026-05-16T00:00:00Z",
                "deadbeef",
            ),
        )
        conn.commit()


def _full_grade_payload(**overrides: object) -> dict:
    """PUT /grade 입력 — 9기준 + total/max/pct + grade + eval_notes (Step 21 v5).

    가중치 합: 16+13+8+10+12+15+11+10+5 = 100
    """
    base: dict = {
        "criteria": [
            {"key": "mnemonics", "score": 3, "weight_applied": 16, "comment": "두문자"},
            {"key": "color", "score": 11, "weight_applied": 13, "comment": "색강조"},
            {"key": "underline", "score": 2, "weight_applied": 8, "comment": "밑줄"},
            {"key": "outline", "score": 3, "weight_applied": 10, "comment": "목차"},
            {"key": "semantic", "score": 8, "weight_applied": 12, "comment": "의미"},
            {"key": "richness", "score": 11, "weight_applied": 15, "comment": "원본 대비 풍부함"},
            {"key": "missing", "score": -2, "weight_applied": 11, "comment": "누락"},
            {"key": "articles", "score": 8, "weight_applied": 10, "comment": "조문"},
            {"key": "case_apply", "score": 3, "weight_applied": 5, "comment": "사안 적용"},
        ],
        "total_score": 14.78,
        "max_score": 17.0,
        "score_pct": 82.47,
        "grade": "B",
        "eval_notes": {"strength": "S", "caution": "C", "missing": "M"},
        "diff_segments": [{"type": "match", "text": "재건축조합"}],
    }
    base.update(overrides)
    return base


# ─── Step 14-2 — done 응답에 answer_text 포함 (Reference Diff 2열용) ─────


class GetAttemptDoneAnswerTextTest(unittest.TestCase):
    """get_attempt(done) → answer_text 포함 (Step 14, 시안 2열 분할 자료)."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["LAWEAR_GRADER_MOCK"] = "1"
        # pending_grade attempt 1건 + inject_grade 로 done 전환
        with db_mod.get_conn(self.tmp.name) as conn:
            self.attempt_id = attempts_mod.create_attempt(
                conn,
                self.tmp.name,
                case_id="TC_CASE",
                answer_text="내 답안 본문 — Reference Diff 2열에서 좌측에 표시",
                grading_mode="manual",
            )["attempt_id"]
            attempts_mod.inject_grade(conn, self.attempt_id, _full_grade_payload())

    def tearDown(self) -> None:
        os.environ.pop("LAWEAR_GRADER_MOCK", None)
        os.unlink(self.tmp.name)

    def test_get_attempt_done_includes_answer_text(self) -> None:
        """done 상태에서도 answer_text 노출 (pending_grade 와 대칭)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.get_attempt(conn, self.attempt_id)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["db_status"], "done")
        self.assertIn("answer_text", out)
        self.assertEqual(
            out["answer_text"],
            "내 답안 본문 — Reference Diff 2열에서 좌측에 표시",
        )

    def test_get_attempt_done_answer_text_preserved_after_grading(self) -> None:
        """채점(inject_grade) 후에도 answer_text 원문 그대로 (R-09)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            # DB raw row 와 응답값 일치 확인
            row = conn.execute(
                "SELECT answer_text FROM attempts WHERE id = ?",
                (self.attempt_id,),
            ).fetchone()
            out = attempts_mod.get_attempt(conn, self.attempt_id)
        self.assertEqual(out["answer_text"], row["answer_text"])

    def test_get_attempt_done_response_shape(self) -> None:
        """done 응답에 기존 필드 + answer_text 모두 존재 (회귀 방지)."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.get_attempt(conn, self.attempt_id)
        # 기존 필드 — 회귀 X
        for key in (
            "id", "attempt_id", "case_id", "status", "db_status",
            "submitted_at", "completed_at",
            "score_total", "score_max", "score_pct", "grade", "model",
            "eval_notes", "diff_segments", "weights_applied", "diff_html",
            "criteria", "case_title", "case_short_id",
        ):
            self.assertIn(key, out, f"done 응답에 {key} 누락")
        # Step 14 새 필드
        self.assertIn("answer_text", out)


# ─── Step 14-3 — list_attempts(case_id, status='completed') 정렬/필터 회귀 ───


class ListAttemptsLatestCompletedTest(unittest.TestCase):
    """시안 케이스 선택 시 마지막 채점 자동 로드 — list_attempts 사양 회귀."""

    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        _build_db(self.tmp.name)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["LAWEAR_GRADER_MOCK"] = "1"
        # 3건 시드: 오래된→done, 중간→pending_grade, 최신→done
        with db_mod.get_conn(self.tmp.name) as conn:
            # 시간 순서: t1 < t2 < t3
            conn.execute(
                """
                INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json)
                VALUES ('TC_CASE', '오래된 done', '2026-05-16T00:01:00Z', 'done', '{}')
                """
            )
            conn.execute(
                """
                INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json)
                VALUES ('TC_CASE', '중간 pending', '2026-05-16T00:02:00Z', 'pending_grade', '{}')
                """
            )
            conn.execute(
                """
                INSERT INTO attempts (case_id, answer_text, submitted_at, status, weights_json,
                                       score_total, score_max, score_pct, grade, model, completed_at)
                VALUES ('TC_CASE', '최신 done', '2026-05-16T00:03:00Z', 'done', '{}',
                        12, 17, 70, 'C', 'm', '2026-05-16T00:04:00Z')
                """
            )
            conn.commit()

    def tearDown(self) -> None:
        os.environ.pop("LAWEAR_GRADER_MOCK", None)
        os.unlink(self.tmp.name)

    def test_filter_completed_returns_only_done_sorted_desc(self) -> None:
        """status='completed' + 정렬 submitted_at DESC."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.list_attempts(conn, case_id="TC_CASE", status="completed", limit=10)
        items = out["attempts"]
        # done 만 2건 (pending_grade 제외)
        self.assertEqual(len(items), 2)
        for it in items:
            self.assertEqual(it["status"], "completed")
        # 정렬: 최신이 먼저 (시안 케이스 선택 시 [0] = 마지막 채점)
        self.assertEqual(items[0]["answer_text"], "최신 done")
        self.assertEqual(items[1]["answer_text"], "오래된 done")

    def test_limit_1_returns_latest_completed(self) -> None:
        """limit=1 → 최신 1건만 — 시안의 `loadLastAttempt` 호출 패턴."""
        with db_mod.get_conn(self.tmp.name) as conn:
            out = attempts_mod.list_attempts(conn, case_id="TC_CASE", status="completed", limit=1)
        items = out["attempts"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["answer_text"], "최신 done")
        self.assertEqual(items[0]["grade"], "C")

    def test_no_completed_returns_empty(self) -> None:
        """완료된 시도 없는 케이스 → 빈 배열 (시안은 empty 상태 유지)."""
        # 새 케이스 시드 (시도 없음)
        with db_mod.get_conn(self.tmp.name) as conn:
            conn.execute(
                """
                INSERT INTO cases
                  (id, subject, subject_kor, category, file, case_no, title, path, points, synced_at, content_hash)
                VALUES ('TC2', 'minbeop', '민법', '입문', '미케01', '02', 't', '_test/dummy.md', 17, 't', 'h')
                """
            )
            conn.commit()
            out = attempts_mod.list_attempts(conn, case_id="TC2", status="completed", limit=1)
        self.assertEqual(out["attempts"], [])
        self.assertEqual(out["total"], 0)


if __name__ == "__main__":
    unittest.main()
