#!/usr/bin/env python3
"""Phase 2 — grader.py prompt 엄격화 TC (lawear-e571, 2026-05-19).

[배경]
사용자 자체 채점(58점, articles 4→2) 이 기존 채점(63점) 보다 더 엄격.
prompt 를 자체 채점 스타일로 강화 — articles 0개 max 2점 명시 + 누락 핵심 식별 강제.

[검증 포인트]
- SYSTEM_PROMPT 에 articles 임계 (조문 0개 → max 20% 이하) 명시
- SYSTEM_PROMPT 에 누락 핵심 4건 (비법인사단/권리능력/제126조/증명책임) 명시
- SYSTEM_PROMPT 에 next_study_oneliner 출력 강제 명시
- SYSTEM_PROMPT 에 missing_critical 출력 형식 명시
- mock 응답에 확장 6키 모두 포함

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_phase2_grader_strict.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent.resolve()
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import grader as grader_mod  # noqa: E402


# ─── SYSTEM_PROMPT 엄격화 검증 ────────────────────────────────────


class SystemPromptStrictTest(unittest.TestCase):
    """SYSTEM_PROMPT 의 엄격화 문구 확인 (Phase 2)."""

    def test_articles_threshold_explicit(self) -> None:
        """articles 조문 0개 = max 20% 이하 명시."""
        sp = grader_mod.SYSTEM_PROMPT
        # "조문 매칭 0개" 또는 "조문 번호 0건" 명시 + "20%" 명시
        self.assertIn("조문 매칭 0개", sp)
        self.assertIn("20%", sp)
        # 임계 4단계 모두 명시
        self.assertIn("조문 매칭 1~2개", sp)
        self.assertIn("조문 매칭 3~4개", sp)
        self.assertIn("조문 매칭 5개 이상", sp)

    def test_missing_critical_4_items_explicit(self) -> None:
        """누락 핵심 4건 (비법인사단/권리능력/제126조/증명책임) 명시."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("비법인사단", sp)
        self.assertIn("권리능력", sp)
        self.assertIn("제126조", sp)
        self.assertIn("증명책임", sp)
        # 차감 점수 범위도 명시 (구체화)
        self.assertIn("차감", sp)

    def test_next_study_oneliner_mandated(self) -> None:
        """next_study_oneliner 출력 강제 명시."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("next_study_oneliner", sp)
        # "반드시 출력" 표현 확인
        self.assertTrue(
            "반드시 출력" in sp or "의무" in sp,
            "next_study_oneliner 의무 출력 문구 누락",
        )

    def test_missing_critical_output_schema(self) -> None:
        """missing_critical 출력 스키마 명시 (item + expected_score_impact)."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("missing_critical", sp)
        self.assertIn("expected_score_impact", sp)
        # 빈 배열 허용 명시
        self.assertIn("빈 배열", sp)

    def test_strengths_weaknesses_in_schema(self) -> None:
        """strengths / weaknesses 출력 형식 명시."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("strengths", sp)
        self.assertIn("weaknesses", sp)
        self.assertIn("score_summary", sp)
        self.assertIn("next_study_actionable", sp)

    def test_r09_reinforced(self) -> None:
        """R-09 자의적 해석 금지 재강조."""
        sp = grader_mod.SYSTEM_PROMPT
        # R-09 키워드 + "자의" 키워드 둘 다 등장
        self.assertIn("R-09", sp)
        self.assertIn("자의", sp)
        # 의도 추정 가점 금지 명시 (Phase 2 핵심)
        self.assertTrue(
            "의도" in sp or "추정" in sp,
            "의도/추정 가점 금지 문구 누락",
        )

    def test_legacy_eval_notes_keys_preserved(self) -> None:
        """legacy strength/caution/missing 키도 그대로 명시 (호환)."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn('"strength"', sp)
        self.assertIn('"caution"', sp)
        self.assertIn('"missing"', sp)


# ─── mock 응답 확장 키 검증 ────────────────────────────────────────


class MockResponseExtKeysTest(unittest.TestCase):
    """_mock_response 가 확장 6키 모두 포함 (Phase 2)."""

    def test_mock_eval_notes_has_ext_keys(self) -> None:
        """mock 응답 eval_notes 에 확장 6키 모두 존재."""
        case = {
            "id": "phase2_test",
            "subject_kor": "민법",
            "category": "테스트",
            "file": "test",
            "case_no": "01",
            "title": "Phase2 Test",
            "points": 10,
            "md_body": "## 원본\n[red]제126조[/red] 표현대리.",
        }
        result = grader_mod.grade(case, "테스트 답안", force_mock=True)
        en = result["eval_notes"]
        # legacy 3
        self.assertIn("strength", en)
        self.assertIn("caution", en)
        self.assertIn("missing", en)
        # 확장 6
        self.assertIn("score_summary", en)
        self.assertIn("strengths", en)
        self.assertIn("weaknesses", en)
        self.assertIn("missing_critical", en)
        self.assertIn("next_study_oneliner", en)
        self.assertIn("next_study_actionable", en)

    def test_mock_eval_notes_types(self) -> None:
        """확장 키 타입 검증: str / list 일관성."""
        case = {"id": "x", "md_body": "."}
        result = grader_mod.grade(case, "답", force_mock=True)
        en = result["eval_notes"]
        # str 키
        self.assertIsInstance(en["score_summary"], str)
        self.assertIsInstance(en["next_study_oneliner"], str)
        # list 키
        self.assertIsInstance(en["strengths"], list)
        self.assertIsInstance(en["weaknesses"], list)
        self.assertIsInstance(en["missing_critical"], list)
        self.assertIsInstance(en["next_study_actionable"], list)

    def test_mock_next_study_oneliner_emoji(self) -> None:
        """mock 의 next_study_oneliner 도 '💡' 이모지로 시작 (스타일 일관)."""
        case = {"id": "x", "md_body": "."}
        result = grader_mod.grade(case, "답", force_mock=True)
        self.assertIn("💡", result["eval_notes"]["next_study_oneliner"])


# ─── 응답 파싱 — 확장 키 옵션 호환 ────────────────────────────────


class ParseResponseExtKeysTest(unittest.TestCase):
    """_parse_response 가 확장 키 있어도 / 없어도 OK (Phase 2 옵션 호환)."""

    def test_parse_response_with_ext_keys(self) -> None:
        """확장 키 포함된 응답 파싱 정상."""
        raw = '''
        {
          "criteria": [
            {"key":"mnem","score":1,"max":1,"comment":""},
            {"key":"color","score":1,"max":1,"comment":""},
            {"key":"under","score":1,"max":1,"comment":""},
            {"key":"outline","score":1,"max":1,"comment":""},
            {"key":"sem","score":1,"max":1,"comment":""},
            {"key":"rich","score":1,"max":1,"comment":""},
            {"key":"miss","score":0,"max":0,"comment":""},
            {"key":"articles","score":2,"max":10,"comment":"조문 0/5"},
            {"key":"case_apply","score":1,"max":1,"comment":""}
          ],
          "eval_notes": {
            "strength":"S","caution":"C","missing":"M",
            "score_summary":"3줄",
            "strengths":["s1"],
            "weaknesses":["w1"],
            "missing_critical":[{"item":"X","expected_score_impact":-3}],
            "next_study_oneliner":"💡 +6점",
            "next_study_actionable":["a1"]
          },
          "diff_segments": []
        }
        '''
        parsed = grader_mod._parse_response(raw)
        # 9 criteria
        self.assertEqual(len(parsed["criteria"]), 9)
        # eval_notes 확장 키 통과
        en = parsed["eval_notes"]
        self.assertEqual(en["score_summary"], "3줄")
        self.assertEqual(len(en["strengths"]), 1)
        self.assertEqual(len(en["missing_critical"]), 1)

    def test_parse_response_legacy_only_still_works(self) -> None:
        """legacy 3키만 있는 응답도 그대로 파싱 (호환)."""
        raw = '''
        {
          "criteria": [
            {"key":"mnem","score":1,"max":1,"comment":""},
            {"key":"color","score":1,"max":1,"comment":""},
            {"key":"under","score":1,"max":1,"comment":""},
            {"key":"outline","score":1,"max":1,"comment":""},
            {"key":"sem","score":1,"max":1,"comment":""},
            {"key":"rich","score":1,"max":1,"comment":""},
            {"key":"miss","score":0,"max":0,"comment":""},
            {"key":"articles","score":1,"max":1,"comment":""},
            {"key":"case_apply","score":1,"max":1,"comment":""}
          ],
          "eval_notes": {"strength":"S","caution":"C","missing":"M"},
          "diff_segments": []
        }
        '''
        parsed = grader_mod._parse_response(raw)
        self.assertEqual(parsed["eval_notes"]["strength"], "S")


if __name__ == "__main__":
    unittest.main()
