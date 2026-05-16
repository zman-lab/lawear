#!/usr/bin/env python3
"""Reports 집계 단위 테스트 (Step 10).

cases / attempts / attempt_criteria 를 in-memory SQLite 에 시드해서
overall / by_subject / by_case 각 함수를 검증한다.

R-09 자의적 해석 금지: 시드 데이터는 결정적(deterministic).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from typing import Any

# 본 모듈 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reports as reports_mod  # noqa: E402


# ─── 헬퍼 ────────────────────────────────────────────────────────────────


SCHEMA_SQL = """
CREATE TABLE cases (
  id            TEXT    PRIMARY KEY,
  subject       TEXT    NOT NULL,
  subject_kor   TEXT    NOT NULL,
  category      TEXT    NOT NULL,
  file          TEXT    NOT NULL,
  file_kor      TEXT,
  case_no       TEXT    NOT NULL,
  title         TEXT    NOT NULL,
  path          TEXT    NOT NULL,
  pdf_path      TEXT,
  points        INTEGER NOT NULL,
  user_case     TEXT,
  synced_at     TEXT    NOT NULL,
  content_hash  TEXT    NOT NULL
);
CREATE TABLE attempts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id         TEXT    NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  answer_text     TEXT    NOT NULL,
  started_at      TEXT,
  submitted_at    TEXT    NOT NULL,
  status          TEXT    NOT NULL DEFAULT 'grading',
  score_total     REAL,
  score_max       REAL,
  score_pct       REAL,
  grade           TEXT,
  model           TEXT,
  weights_json    TEXT    NOT NULL,
  eval_notes_json TEXT,
  diff_json       TEXT,
  raw_response    TEXT,
  error_code      TEXT,
  is_stale        INTEGER NOT NULL DEFAULT 0,
  completed_at  TEXT,
  error_message TEXT,
  elapsed_sec   REAL,
  is_mock       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE attempt_criteria (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id    INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  criterion_key TEXT    NOT NULL,
  score         REAL    NOT NULL,
  max_score     REAL    NOT NULL,
  weight        REAL    NOT NULL,
  comment       TEXT
);
CREATE TABLE bookmarks (
  case_id       TEXT    PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
  bookmarked_at TEXT    NOT NULL
);
CREATE TABLE settings (
  key         TEXT PRIMARY KEY,
  value_json  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


def _seed_case(
    conn: sqlite3.Connection,
    case_id: str,
    *,
    subject: str = "minbeop",
    subject_kor: str = "민법",
    category: str = "입문",
    file: str = "미케01",
    case_no: str = "01",
    title: str = "테스트 케이스",
    points: int = 17,
) -> None:
    conn.execute(
        """
        INSERT INTO cases (id, subject, subject_kor, category, file, case_no, title,
                           path, points, synced_at, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            subject,
            subject_kor,
            category,
            file,
            case_no,
            title,
            f"{category}_{subject_kor}/{case_id}.md",
            points,
            "2026-05-16T08:00:00Z",
            "hash" + case_id[-6:],
        ),
    )


def _seed_attempt(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    score_pct: float | None = None,
    grade: str | None = None,
    submitted_at: str | None = None,
    completed_at: str | None = None,
    status: str = "done",
    score_total: float | None = None,
    score_max: float | None = None,
    is_stale: int = 0,
    is_mock: int = 0,
    eval_notes: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> int:
    submitted = submitted_at or "2026-05-16T09:00:00Z"
    eval_notes_json = json.dumps(eval_notes, ensure_ascii=False) if eval_notes else None
    cur = conn.execute(
        """
        INSERT INTO attempts (
            case_id, answer_text, submitted_at, status, score_total, score_max,
            score_pct, grade, model, weights_json, eval_notes_json,
            completed_at, error_code, error_message, is_stale, is_mock
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            "answer",
            submitted,
            status,
            score_total,
            score_max,
            score_pct,
            grade,
            "mock",
            '{"mnem":16,"color":13,"under":8,"outline":10,"sem":12,"rich":20,"miss":11,"articles":10}',
            eval_notes_json,
            completed_at or submitted,
            error_code,
            error_message,
            is_stale,
            is_mock,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_criteria(conn: sqlite3.Connection, attempt_id: int, vals: dict[str, tuple[float, float, float]]) -> None:
    """vals: {criterion_key: (score, max, weight)}"""
    for key, (s, m, w) in vals.items():
        conn.execute(
            "INSERT INTO attempt_criteria (attempt_id, criterion_key, score, max_score, weight, comment) VALUES (?,?,?,?,?,?)",
            (attempt_id, key, s, m, w, f"mock {key}"),
        )
    conn.commit()


# ─── 테스트 케이스 ──────────────────────────────────────────────────────


class TestOverallEmpty(unittest.TestCase):
    def test_empty_db(self) -> None:
        conn = _conn()
        result = reports_mod.overall(conn)
        self.assertEqual(result["kpi"]["submitted"], 0)
        self.assertIsNone(result["kpi"]["avg_score_pct"])
        self.assertEqual(result["kpi"]["high_error_cases"], 0)
        self.assertEqual(result["kpi"]["long_pending_cases"], 0)
        self.assertEqual(result["trend"], [])
        self.assertEqual(result["recent"], [])
        self.assertTrue(result["empty"])

    def test_no_attempts_only_cases(self) -> None:
        conn = _conn()
        _seed_case(conn, "case-a")
        _seed_case(conn, "case-b", subject="minso", subject_kor="민소")
        result = reports_mod.overall(conn)
        self.assertEqual(result["kpi"]["submitted"], 0)
        self.assertTrue(result["empty"])


class TestOverallBasic(unittest.TestCase):
    def test_with_attempts(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1")
        _seed_case(conn, "c2", case_no="02")
        _seed_case(conn, "c3", case_no="03")
        # 3 done + 1 error
        now = _dt.datetime.now(_dt.timezone.utc)
        for i, (cid, pct, grade) in enumerate(
            [("c1", 82.0, "B"), ("c2", 91.0, "A"), ("c1", 45.0, "F"), ("c3", 55.0, "C")]
        ):
            ts = (now - _dt.timedelta(hours=i + 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            _seed_attempt(
                conn,
                case_id=cid,
                score_pct=pct,
                grade=grade,
                submitted_at=ts,
                score_total=pct / 5.0,
                score_max=20.0,
            )
        result = reports_mod.overall(conn)
        # submitted = 4 (all done)
        self.assertEqual(result["kpi"]["submitted"], 4)
        # avg = (82+91+45+55)/4 = 68.25
        self.assertAlmostEqual(result["kpi"]["avg_score_pct"], 68.25, places=2)
        # high_error: c1 의 가장 최근은 82 (먼저 입력) 아닌 45 (i=2). c3 의 가장 최근은 55. 둘 다 < 60.
        # 하지만 시드 순서 i=0:c1 82, i=2:c1 45 → c1 의 MAX(submitted_at) 은 i=0(가장 큰 ts).
        # i=0 ts = now - 1h, i=2 ts = now - 3h → i=0 더 최신. c1 최근 = 82 (≥60) → high err X.
        # c3 의 최근 = 55 < 60 → high err.
        self.assertEqual(result["kpi"]["high_error_cases"], 1)
        # trend 4건
        self.assertEqual(len(result["trend"]), 4)
        # recent 4건 (DESC)
        self.assertEqual(len(result["recent"]), 4)
        self.assertFalse(result["empty"])

    def test_high_error_threshold(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1")
        _seed_attempt(conn, case_id="c1", score_pct=59.9, grade="C")
        result = reports_mod.overall(conn)
        self.assertEqual(result["kpi"]["high_error_cases"], 1)
        # 정확히 60.0 은 high error 아님 (< 만)
        conn2 = _conn()
        _seed_case(conn2, "c1")
        _seed_attempt(conn2, case_id="c1", score_pct=60.0, grade="C")
        result2 = reports_mod.overall(conn2)
        self.assertEqual(result2["kpi"]["high_error_cases"], 0)

    def test_long_pending(self) -> None:
        conn = _conn()
        _seed_case(conn, "old-case")
        _seed_case(conn, "fresh-case", case_no="02")
        # old: 100일 전, fresh: 오늘
        old_ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=100)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        fresh_ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _seed_attempt(conn, case_id="old-case", score_pct=80.0, submitted_at=old_ts)
        _seed_attempt(conn, case_id="fresh-case", score_pct=80.0, submitted_at=fresh_ts)
        result = reports_mod.overall(conn, stale_threshold_days=14)
        self.assertEqual(result["kpi"]["long_pending_cases"], 1)
        # threshold 200일 → 둘 다 stale 아님
        result2 = reports_mod.overall(conn, stale_threshold_days=200)
        self.assertEqual(result2["kpi"]["long_pending_cases"], 0)

    def test_error_attempt_in_recent(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1")
        _seed_attempt(
            conn,
            case_id="c1",
            status="error",
            error_code="anthropic_bad_gateway",
            error_message="upstream 502",
        )
        result = reports_mod.overall(conn)
        # submitted 카운트엔 error 포함 (1)
        self.assertEqual(result["kpi"]["submitted"], 1)
        # avg 는 None (done 없음)
        self.assertIsNone(result["kpi"]["avg_score_pct"])
        # recent 에 error attempt
        self.assertEqual(len(result["recent"]), 1)
        self.assertEqual(result["recent"][0]["status"], "error")
        self.assertEqual(result["recent"][0]["error_code"], "anthropic_bad_gateway")

    def test_grading_excluded(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1")
        _seed_attempt(conn, case_id="c1", status="grading", score_pct=None, grade=None)
        result = reports_mod.overall(conn)
        # grading 은 submitted 카운트에 X
        self.assertEqual(result["kpi"]["submitted"], 0)


# ─── By Subject ──────────────────────────────────────────────────────────


class TestBySubject(unittest.TestCase):
    def test_subject_not_exists(self) -> None:
        conn = _conn()
        result = reports_mod.by_subject(conn, "nonexist")
        self.assertFalse(result["subject_exists"])
        self.assertEqual(result["kpi"]["cases"], 0)
        self.assertTrue(result["empty"])

    def test_subject_no_attempts(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1", subject="minbeop", subject_kor="민법")
        _seed_case(conn, "c2", subject="minbeop", subject_kor="민법", case_no="02")
        result = reports_mod.by_subject(conn, "minbeop")
        self.assertTrue(result["subject_exists"])
        self.assertEqual(result["kpi"]["cases"], 2)
        self.assertEqual(result["kpi"]["submitted"], 0)
        self.assertEqual(result["kpi"]["covered_cases"], 0)
        self.assertIsNone(result["kpi"]["avg_score_pct"])
        self.assertEqual(result["kpi"]["coverage_pct"], 0.0)
        self.assertEqual(len(result["cases"]), 2)
        self.assertTrue(result["empty"])

    def test_subject_with_attempts(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1", subject="minbeop", subject_kor="민법")
        _seed_case(conn, "c2", subject="minbeop", case_no="02")
        _seed_case(conn, "c3", subject="minso", subject_kor="민소")
        # minbeop attempts
        _seed_attempt(conn, case_id="c1", score_pct=82.0)
        _seed_attempt(conn, case_id="c2", score_pct=70.0)
        # minso attempt (compare 에만 등장해야 함)
        _seed_attempt(conn, case_id="c3", score_pct=50.0)

        result = reports_mod.by_subject(conn, "minbeop")
        self.assertTrue(result["subject_exists"])
        self.assertEqual(result["kpi"]["cases"], 2)
        self.assertEqual(result["kpi"]["submitted"], 2)
        self.assertEqual(result["kpi"]["covered_cases"], 2)
        self.assertAlmostEqual(result["kpi"]["avg_score_pct"], 76.0, places=1)
        self.assertEqual(result["kpi"]["coverage_pct"], 100.0)
        # comparison 두 subject
        self.assertEqual(len(result["comparison"]), 2)
        # top error topic: 가장 낮은 점수의 케이스 = c2 (70.0)
        self.assertEqual(result["kpi"]["top_error_case_id"], "c2")
        # cases 리스트
        self.assertEqual(len(result["cases"]), 2)

    def test_top_error_topic_selection(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1", title="높은점수")
        _seed_case(conn, "c2", case_no="02", title="낮은점수")
        _seed_attempt(conn, case_id="c1", score_pct=90.0)
        _seed_attempt(conn, case_id="c2", score_pct=40.0)
        result = reports_mod.by_subject(conn, "minbeop")
        self.assertEqual(result["kpi"]["top_error_case_id"], "c2")
        self.assertEqual(result["kpi"]["top_error_topic"], "낮은점수")
        self.assertAlmostEqual(result["kpi"]["top_error_pct"], 40.0)


# ─── By Case ─────────────────────────────────────────────────────────────


class TestByCase(unittest.TestCase):
    def test_case_not_exists(self) -> None:
        conn = _conn()
        result = reports_mod.by_case(conn, "nonexist")
        self.assertFalse(result["case_exists"])
        self.assertEqual(result["kpi"]["attempts"], 0)
        self.assertTrue(result["empty"])

    def test_case_no_attempts(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1", title="Test")
        result = reports_mod.by_case(conn, "c1")
        self.assertTrue(result["case_exists"])
        self.assertEqual(result["kpi"]["attempts"], 0)
        self.assertIsNone(result["kpi"]["last_pct"])
        self.assertIsNone(result["kpi"]["best_pct"])
        self.assertEqual(result["trend"], [])
        self.assertEqual(result["history"], [])
        # criteria 는 9기준 0/0 fill (Step 21 v5 — case_apply 신설)
        self.assertEqual(len(result["criteria"]), 9)
        for c in result["criteria"]:
            self.assertEqual(c["n"], 0)
        self.assertTrue(result["empty"])

    def test_case_with_attempts(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1", title="Test Case")
        # 3 done attempts
        ids = []
        for i, pct in enumerate([60.0, 80.0, 70.0]):
            ts = f"2026-05-{16-i:02d}T09:00:00Z"
            aid = _seed_attempt(
                conn,
                case_id="c1",
                score_pct=pct,
                grade="A" if pct >= 80 else "B",
                score_total=pct / 5.0,
                score_max=20.0,
                submitted_at=ts,
                completed_at=ts,
            )
            ids.append(aid)
            # criteria 추가 (Step 21 v5 — case_apply 추가, 9기준)
            _seed_criteria(
                conn,
                aid,
                {
                    "mnem": (3.0, 4.0, 16),
                    "color": (10.0, 12.0, 13),
                    "under": (2.0, 2.0, 8),
                    "outline": (2.5, 3.0, 10),
                    "sem": (8.0, 10.0, 12),
                    "rich": (11.0, 15.0, 15),
                    "miss": (-1.0, 0.0, 11),
                    "articles": (4.0, 5.0, 10),
                    "case_apply": (3.0, 5.0, 5),
                },
            )

        result = reports_mod.by_case(conn, "c1")
        self.assertTrue(result["case_exists"])
        self.assertEqual(result["case_title"], "Test Case")
        self.assertEqual(result["kpi"]["attempts"], 3)
        # latest = 05-14 (i=2) pct=70.0 (ASC 순으로 마지막)
        # 하지만 submitted_at DESC LIMIT 1 → 05-16 (i=0) = 60.0
        self.assertAlmostEqual(result["kpi"]["last_pct"], 60.0, places=1)
        self.assertAlmostEqual(result["kpi"]["best_pct"], 80.0, places=1)
        # trend: ASC, 3건
        self.assertEqual(len(result["trend"]), 3)
        self.assertEqual(result["trend"][0]["attempt_num"], 1)
        self.assertEqual(result["trend"][2]["attempt_num"], 3)
        # criteria 9기준 (Step 21 v5 — case_apply 신설)
        self.assertEqual(len(result["criteria"]), 9)
        # mnem 평균 3.0/4.0
        mnem = next(c for c in result["criteria"] if c["criterion_key"] == "mnem")
        self.assertAlmostEqual(mnem["avg_score"], 3.0, places=1)
        self.assertAlmostEqual(mnem["avg_max"], 4.0, places=1)
        self.assertAlmostEqual(mnem["avg_pct"], 75.0, places=1)
        self.assertEqual(mnem["n"], 3)
        # miss 의 avg_pct 는 None (max=0)
        miss = next(c for c in result["criteria"] if c["criterion_key"] == "miss")
        self.assertIsNone(miss["avg_pct"])
        # history 3건
        self.assertEqual(len(result["history"]), 3)
        self.assertFalse(result["empty"])

    def test_persistent_errors(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1")
        # 4건 동일 missing → persistent (threshold=3 기본)
        for i in range(4):
            _seed_attempt(
                conn,
                case_id="c1",
                score_pct=60.0,
                eval_notes={
                    "strength": "ok",
                    "caution": "ok",
                    "missing": "증명책임 분배 미언급",
                },
                submitted_at=f"2026-05-{16-i:02d}T09:00:00Z",
            )
        # 1건 다른 missing
        _seed_attempt(
            conn,
            case_id="c1",
            score_pct=55.0,
            eval_notes={"strength": "x", "caution": "y", "missing": "다른 누락"},
            submitted_at="2026-05-10T09:00:00Z",
        )
        result = reports_mod.by_case(conn, "c1", persistent_threshold=3)
        self.assertEqual(result["persistent_errors"]["count"], 1)
        self.assertEqual(
            result["persistent_errors"]["items"][0]["text"], "증명책임 분배 미언급"
        )
        self.assertEqual(result["persistent_errors"]["items"][0]["occurrences"], 4)

    def test_main_miss_extraction(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1")
        aid = _seed_attempt(
            conn,
            case_id="c1",
            score_pct=70.0,
            eval_notes={
                "strength": "good",
                "caution": "warning",
                "missing": "첫번째 문장입니다. 두번째 문장.",
            },
        )
        result = reports_mod.by_case(conn, "c1")
        self.assertEqual(len(result["history"]), 1)
        # 마침표 첫 문장만
        self.assertEqual(result["history"][0]["main_miss"], "첫번째 문장입니다.")

    def test_error_attempt_main_miss(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1")
        _seed_attempt(
            conn,
            case_id="c1",
            status="error",
            error_code="anthropic_502",
            error_message="upstream gateway",
        )
        result = reports_mod.by_case(conn, "c1")
        self.assertEqual(len(result["history"]), 1)
        # error 시도의 main_miss = error_message
        self.assertIn("upstream gateway", result["history"][0]["main_miss"])


# ─── Pickers ─────────────────────────────────────────────────────────────


class TestPickers(unittest.TestCase):
    def test_subjects_empty(self) -> None:
        conn = _conn()
        result = reports_mod.list_subjects(conn)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["subjects"], [])

    def test_subjects_multi(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1", subject="minbeop", subject_kor="민법")
        _seed_case(conn, "c2", subject="minbeop", case_no="02")
        _seed_case(conn, "c3", subject="minso", subject_kor="민소")
        result = reports_mod.list_subjects(conn)
        self.assertEqual(result["count"], 2)
        subj_ids = [s["subject"] for s in result["subjects"]]
        self.assertIn("minbeop", subj_ids)
        self.assertIn("minso", subj_ids)

    def test_cases_for_picker_filter(self) -> None:
        conn = _conn()
        _seed_case(conn, "c1", subject="minbeop")
        _seed_case(conn, "c2", subject="minbeop", case_no="02")
        _seed_case(conn, "c3", subject="minso")
        _seed_attempt(conn, case_id="c1", score_pct=80.0)
        result_all = reports_mod.list_cases_for_picker(conn)
        self.assertEqual(result_all["count"], 3)
        result_minbeop = reports_mod.list_cases_for_picker(conn, subject="minbeop")
        self.assertEqual(result_minbeop["count"], 2)
        # 시도 카운트 검증
        c1 = next(c for c in result_minbeop["cases"] if c["case_id"] == "c1")
        self.assertEqual(c1["attempts"], 1)
        c2 = next(c for c in result_minbeop["cases"] if c["case_id"] == "c2")
        self.assertEqual(c2["attempts"], 0)


if __name__ == "__main__":
    unittest.main()
