"""grader.py SYSTEM_PROMPT — 음성 인식 관용 + typo_corrections 출력 키 검증.

lawear-e571/typo-system (2026-05-19).
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grader as grader_mod  # noqa: E402
import typo_corrector as tc  # noqa: E402


class TestSystemPromptTypoTolerance(unittest.TestCase):
    """SYSTEM_PROMPT 음성 인식 관용 안내 포함 검증."""

    def test_system_prompt_mentions_voice_recognition(self):
        """SYSTEM_PROMPT 에 '음성 인식' 키워드 포함."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertIn("음성 인식 오타 관용", prompt)
        self.assertIn("STT", prompt)

    def test_system_prompt_lists_typo_examples(self):
        """대표 오타 예시 포함 (사용자 attempt 9 + 명시)."""
        prompt = grader_mod.SYSTEM_PROMPT
        # 사용자가 명시한 핵심 예시 중 최소 3개 포함
        examples = ["파산관제인", "통정표시", "선한간리주의", "아기"]
        hits = [e for e in examples if e in prompt]
        self.assertGreaterEqual(len(hits), 3,
                                f"기본 예시 3+ 권장. 실측 {hits}")

    def test_system_prompt_preserves_article_numbers(self):
        """조문 번호는 오타 인정 X 명시 — 절대 규칙."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertIn("조문 번호", prompt)
        # "오타 인정 X" 또는 동의어
        self.assertTrue(
            "오타 인정 X" in prompt or "오타 인정 안" in prompt or "절대" in prompt,
            "조문 번호 보호 명시 필요"
        )

    def test_system_prompt_mentions_typo_corrections_output(self):
        """JSON 출력 형식에 typo_corrections 키 포함."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertIn("typo_corrections", prompt)


class TestBuildPromptTypoIntegration(unittest.TestCase):
    """_build_prompt — SYSTEM_PROMPT 가 _build_prompt 응답에 반영."""

    def test_build_prompt_returns_system_with_typo_tolerance(self):
        """_build_prompt 의 system_prompt 가 음성 관용 포함."""
        case_meta = {
            "id": "test_case_1",
            "subject_kor": "민법",
            "category": "입문",
            "file": "test.md",
            "case_no": 1,
            "title": "테스트 케이스",
            "points": 30,
            "md_body": "테스트 본문",
        }
        system, user_msg = grader_mod._build_prompt(case_meta, "사용자 답안", {
            "mnem": 16, "color": 13, "under": 8, "outline": 10, "sem": 12,
            "rich": 15, "miss": 11, "articles": 10, "case_apply": 5,
        })
        self.assertIn("음성 인식 오타 관용", system)
        self.assertIn("typo_corrections", system)
        # user_message 는 본문 포함
        self.assertIn("테스트 본문", user_msg)

    def test_build_prompt_subq_returns_system_with_typo_tolerance(self):
        """_build_prompt_subq 도 SYSTEM_PROMPT 공유 — 캐시 적중."""
        case = {
            "id": "test_case_subq",
            "subject_kor": "민법",
            "category": "입문",
            "file": "subq.md",
            "case_no": 1,
            "title": "다중 설문 테스트",
        }
        subq = {"key": "설문 1", "label": "설문 1", "score_max": 10,
                "body": "문제 본문", "answer": "답안 본문"}
        system, user_msg = grader_mod._build_prompt_subq(case, subq, "사용자 카드 답안", [])
        self.assertIn("음성 인식 오타 관용", system)
        # 두 함수가 같은 SYSTEM_PROMPT 사용 — 캐시 적중
        self.assertEqual(system, grader_mod.SYSTEM_PROMPT)


class TestGraderTypoCorrectorIntegration(unittest.TestCase):
    """grade() 진입점이 typo_corrector 1차 패스를 적용."""

    def setUp(self) -> None:
        tc.clear_cache()

    def test_grade_mock_with_typo_in_answer_records_corrections(self):
        """mock 모드 + 답안에 오타 → eval_notes.typo_corrections 누적."""
        case_meta = {
            "id": "test_case_1",
            "subject_kor": "민법",
            "category": "입문",
            "file": "test.md",
            "case_no": 1,
            "title": "test",
            "points": 30,
            "md_body": "본문",
        }
        # 사전 오타 2건 포함
        user_answer = "파산관제인은 통정표시 행위를 추인할 수 있다."

        result = grader_mod.grade(
            case_meta, user_answer,
            weights={"mnem": 16, "color": 13, "under": 8, "outline": 10, "sem": 12,
                     "rich": 15, "miss": 11, "articles": 10, "case_apply": 5},
            force_mock=True,
        )
        self.assertIn("eval_notes", result)
        typo_corr = result["eval_notes"].get("typo_corrections")
        self.assertIsNotNone(typo_corr, "정적 사전 매칭 → typo_corrections 기록 필요")
        self.assertGreaterEqual(len(typo_corr), 2, f"2건 이상 누적, 실측 {len(typo_corr)}")
        # from 값 검증
        froms = [c["from"] for c in typo_corr]
        self.assertIn("파산관제인", froms)
        self.assertIn("통정표시", froms)

    def test_grade_mock_clean_answer_no_corrections(self):
        """오타 없는 답안 → typo_corrections=None."""
        case_meta = {
            "id": "test_case_clean",
            "subject_kor": "민법",
            "category": "입문",
            "file": "test.md",
            "case_no": 1,
            "title": "test",
            "points": 30,
            "md_body": "본문",
        }
        result = grader_mod.grade(
            case_meta, "민법 제103조에 따라 무효이다.",
            weights={"mnem": 16, "color": 13, "under": 8, "outline": 10, "sem": 12,
                     "rich": 15, "miss": 11, "articles": 10, "case_apply": 5},
            force_mock=True,
        )
        # 오타 없으면 None 또는 빈 list
        typo_corr = result["eval_notes"].get("typo_corrections")
        self.assertTrue(typo_corr is None or typo_corr == [],
                        f"오타 없는 답안 → None/빈 list, 실측 {typo_corr}")


class TestGraderPromptCacheStability(unittest.TestCase):
    """SYSTEM_PROMPT 가 _build_prompt / _build_prompt_subq 양쪽에서 *동일* 객체.

    Anthropic ephemeral cache 적중 조건 — system_prompt 가 같은 인스턴스/내용.
    """

    def test_system_prompt_identical_for_legacy_and_subq(self):
        """legacy + subq 양 함수가 같은 SYSTEM_PROMPT 사용."""
        case = {"id": "x", "subject_kor": "민법", "category": "입문",
                "file": "x.md", "case_no": 1, "title": "x", "points": 30,
                "md_body": "x"}
        sys_legacy, _ = grader_mod._build_prompt(case, "답", {
            "mnem": 16, "color": 13, "under": 8, "outline": 10, "sem": 12,
            "rich": 15, "miss": 11, "articles": 10, "case_apply": 5,
        })
        subq = {"key": "전체", "label": "전체", "score_max": 30, "body": "", "answer": ""}
        sys_subq, _ = grader_mod._build_prompt_subq(case, subq, "답", [])
        self.assertEqual(sys_legacy, sys_subq)


if __name__ == "__main__":
    unittest.main()
