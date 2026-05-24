"""17896 민사서류 cloze 채점 테스트 (lawear-23d9 2026-05-25).

근거: docs/민사서류_작성연습_설계/design_mvp1.md v2 결정 5.

TC:
  - test_cloze_simple_perfect: cloze_simple 1문 정상 정답 → 100점
  - test_cloze_normalize_match: 공백/구두점 차이 → normalize 만점 (1점, 100점)
  - test_cloze_half_miss: 빈칸 절반 오답 → 약 50점 (가중치에 따라)
  - test_bold_weight: bold 빈칸은 1.5배 가중 (정답이면 점수 더 큼)
  - test_hint_penalty: 힌트 사용 시 감점 (1단계 -5%, 2.5단계 -15%)
  - test_parse_md_subqs_cloze: cases.py cloze parser — 데이터 1문 정상 분해
  - test_extract_blank_answers: [blank] 토큰 추출 + placeholder 치환
"""
from __future__ import annotations

import json
import os
import sys
import unittest

# 테스트 디렉토리에서 상위(docs/tts-exam) import 가능하도록 path 추가
_HERE = os.path.dirname(os.path.abspath(__file__))
_TTS_EXAM = os.path.dirname(_HERE)
if _TTS_EXAM not in sys.path:
    sys.path.insert(0, _TTS_EXAM)


class TestCivilDocGrader(unittest.TestCase):
    """청구취지 cloze diff 채점 — design v2 결정 5 검증."""

    def setUp(self):
        # 표준 case_meta — 빈칸 2개 (1개 bold = 1.5x, 1개 normal = 1.0x)
        self.case_meta = {
            "id": "2026_civildoc_test_01",
            "subject_type": "civil_doc",
            "subqs": [
                {
                    "key": "문제 1",
                    "score_max": 1,
                    "blanks": {
                        "blank_1": "[bold]연대하여[/bold]",  # bold = 1.5x
                        "blank_2": "다 갚는 날까지",          # normal = 1.0x
                    },
                },
            ],
        }

    def test_cloze_simple_perfect(self):
        """TC1: cloze_simple 1문 정상 정답 → 100점 + grade=A."""
        import minsaseoryu_grader as g
        user_blanks = {"blank_1": "연대하여", "blank_2": "다 갚는 날까지"}
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        result = g.grade(self.case_meta, answer_text, hints_used=None)
        self.assertAlmostEqual(result["pct"], 100.0, places=1)
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["criteria"][0]["key"], "cloze_match")

    def test_cloze_normalize_match(self):
        """TC2: 공백/구두점 차이 → normalize 만점 (R-09 부장판사 권고 D)."""
        import minsaseoryu_grader as g
        # "연대하여" vs "연대 하여" — 공백만 다름. normalize 후 동일.
        # "다 갚는 날까지" vs "다갚는날까지" — 공백 제거 후 동일.
        user_blanks = {"blank_1": "연대 하여", "blank_2": "다갚는날까지"}
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        result = g.grade(self.case_meta, answer_text, hints_used=None)
        self.assertAlmostEqual(result["pct"], 100.0, places=1, msg="normalize 만점 — 둘 다 정답")
        # blank_results 의 match_type 'normalized' 확인
        subq_result = result["subqs_results"][0]
        normalized_count = sum(1 for br in subq_result["blank_results"] if br["match_type"] == "normalized")
        self.assertGreaterEqual(normalized_count, 1, "최소 1개는 normalized match")

    def test_cloze_half_miss(self):
        """TC3: 빈칸 절반 오답 — bold(1.5) miss + normal(1.0) hit → 1.0/2.5 = 40%.

        normal 빈칸만 맞고 bold 오답 → weighted = 1.0, max = 2.5 → 40%.
        """
        import minsaseoryu_grader as g
        user_blanks = {
            "blank_1": "공동하여",       # 오답 (정답은 연대하여, bold 1.5x)
            "blank_2": "다 갚는 날까지",  # 정답 (normal 1.0x)
        }
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        result = g.grade(self.case_meta, answer_text, hints_used=None)
        self.assertAlmostEqual(result["pct"], 40.0, places=1, msg="1.0 / 2.5 = 40%")

    def test_bold_weight(self):
        """TC4: bold 빈칸이 정답일 때 점수 가중치 1.5배 확인.

        bold 정답 + normal 오답 → 1.5/2.5 = 60%.
        """
        import minsaseoryu_grader as g
        user_blanks = {
            "blank_1": "연대하여",   # 정답 (bold 1.5x)
            "blank_2": "다 갚는",     # 오답
        }
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        result = g.grade(self.case_meta, answer_text, hints_used=None)
        self.assertAlmostEqual(result["pct"], 60.0, places=1, msg="1.5 / 2.5 = 60% (bold 가중치 적용)")

    def test_hint_penalty(self):
        """TC5: 힌트 사용 시 감점 (1단계 -5%, 2.5단계 -15%).

        100점 - (5% + 15%) = 80점 → 100 * 0.80 = 80.
        """
        import minsaseoryu_grader as g
        user_blanks = {"blank_1": "연대하여", "blank_2": "다 갚는 날까지"}
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        hints_used = {"문제 1": [1, 2.5]}  # -5% + -15% = -20%
        result = g.grade(self.case_meta, answer_text, hints_used=hints_used)
        self.assertAlmostEqual(result["pct"], 80.0, places=1, msg="100% × (1 - 0.20) = 80%")

    def test_all_miss(self):
        """TC6: 전부 오답 → 0점."""
        import minsaseoryu_grader as g
        user_blanks = {"blank_1": "X", "blank_2": "Y"}
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        result = g.grade(self.case_meta, answer_text, hints_used=None)
        self.assertAlmostEqual(result["pct"], 0.0, places=1)
        self.assertEqual(result["grade"], "F")

    def test_empty_answer(self):
        """TC7: 빈 답안 → 0점 (오답 처리)."""
        import minsaseoryu_grader as g
        user_blanks = {}
        answer_text = json.dumps({"format": "cloze", "blanks": user_blanks}, ensure_ascii=False)
        result = g.grade(self.case_meta, answer_text, hints_used=None)
        self.assertAlmostEqual(result["pct"], 0.0, places=1)

    def test_normalize_for_compare(self):
        """공백/구두점 normalize 함수 단위 테스트."""
        import minsaseoryu_grader as g
        self.assertEqual(g.normalize_for_compare("연대 하여"), "연대하여")
        self.assertEqual(g.normalize_for_compare("연대하여"), "연대하여")
        self.assertEqual(g.normalize_for_compare("2022. 7. 1."), "2022.7.1.")
        self.assertEqual(g.normalize_for_compare(""), "")
        self.assertEqual(g.normalize_for_compare(None), "")

    def test_is_bold_blank(self):
        """bold 토큰 검출 함수 단위 테스트."""
        import minsaseoryu_grader as g
        self.assertTrue(g.is_bold_blank("[bold]연대하여[/bold]"))
        self.assertTrue(g.is_bold_blank("[b]각[/b]"))
        self.assertTrue(g.is_bold_blank("[em1]강조[/em1]"))
        self.assertFalse(g.is_bold_blank("연대하여"))
        self.assertFalse(g.is_bold_blank(""))


class TestCasesParserCloze(unittest.TestCase):
    """cases.py parse_md_subqs_cloze + extract_blank_answers 검증."""

    def test_extract_blank_answers_single(self):
        """[blank]X[/blank] 단일 토큰 추출 + placeholder 치환."""
        import cases
        text = "피고들은 [blank]연대하여[/blank] 원고에게 지급하라."
        blanks, body, count = cases.extract_blank_answers(text)
        self.assertEqual(count, 1)
        self.assertEqual(blanks, {"blank_1": "연대하여"})
        self.assertIn('data-blank-idx="1"', body)
        self.assertIn('data-card-blank', body)
        # 정답 노출 없음
        self.assertNotIn("연대하여", body)

    def test_extract_blank_answers_multiple(self):
        """[blank] 토큰 다중 — 인덱스 1~N 순차 부여."""
        import cases
        text = "피고는 [blank]연대하여[/blank] 100원 및 이에 대하여 [blank]2022.7.1.[/blank]부터 지급하라."
        blanks, body, count = cases.extract_blank_answers(text)
        self.assertEqual(count, 2)
        self.assertEqual(blanks["blank_1"], "연대하여")
        self.assertEqual(blanks["blank_2"], "2022.7.1.")
        self.assertIn('data-blank-idx="1"', body)
        self.assertIn('data-blank-idx="2"', body)

    def test_extract_blank_answers_with_bold(self):
        """[blank][bold]X[/bold][/blank] 중첩 토큰 — 정답값에 [bold] 보존 (grader 가중치 판정용)."""
        import cases
        text = "[blank][bold]연대하여[/bold][/blank] 지급"
        blanks, body, count = cases.extract_blank_answers(text)
        self.assertEqual(count, 1)
        # [bold] 토큰은 정답값에 유지 (grader 가 strip 후 비교)
        self.assertEqual(blanks["blank_1"], "[bold]연대하여[/bold]")

    def test_extract_blank2_unchanged(self):
        """[blank2] 토큰은 추출 대상 아님 (별개 — 두문자 시각 단서)."""
        import cases
        text = "본문 [blank2]무[/blank2] 다음"
        blanks, body, count = cases.extract_blank_answers(text)
        self.assertEqual(count, 0)
        self.assertEqual(blanks, {})
        # 원본 본문 보존
        self.assertEqual(body, text)

    def test_parse_md_subqs_cloze(self):
        """cloze .md → subq 카드 분해 — 데이터 파일 1문 정상."""
        import cases
        md = """# 테스트 cloze

## 문제 1. 연대하여 — 연대채무 (테스트)

### 조건
甲과 乙이 원고에게 10,000,000원의 연대채무를 부담.

### 청구취지 (cloze)

피고들은 [blank]연대하여[/blank] 원고에게 10,000,000원을 지급하라.

### 힌트 (5단계)

- **hint_1 (청구 유형)**: 금전지급 청구
- **hint_2 (청구취지 골격)**: 피고들은 ___ 원고에게 10,000,000원을 지급하라.
- **hint_3 (연결어 후보)**: 연대하여 / 공동하여 / 각
- **hint_4 (적용 룰)**: 연대채무 = "연대하여"
- **hint_5 (정답 일부)**: 연결어 = "연대하여"
"""
        cards = cases.parse_md_subqs_cloze(md)
        self.assertEqual(len(cards), 1)
        c = cards[0]
        self.assertEqual(c["key"], "문제 1")
        self.assertTrue(c["is_cloze"])
        self.assertEqual(c["blank_count"], 1)
        self.assertEqual(c["blanks"], {"blank_1": "연대하여"})
        # 힌트 추출 — hint_1 ~ hint_5
        self.assertIn("hint_1", c["hints"])
        self.assertIn("hint_5", c["hints"])
        self.assertIn("금전지급 청구", c["hints"]["hint_1"])
        # body_with_placeholders — input 마커
        self.assertIn('data-blank-idx="1"', c["body_with_placeholders"])


class TestMinsaseoryuModes(unittest.TestCase):
    """minsaseoryu_modes 메타 검증."""

    def test_active_modes_3(self):
        """1라운드 active mode 3종 (cloze_shuffle 제외)."""
        import minsaseoryu_modes as m
        active = m.get_active_modes()
        self.assertEqual(len(active), 3)
        self.assertEqual(set(active), {"cloze_simple", "cloze_skeleton", "cloze_full"})

    def test_get_mode_invalid(self):
        """잘못된 mode → ValueError."""
        import minsaseoryu_modes as m
        with self.assertRaises(ValueError):
            m.get_mode("invalid_mode_xx")

    def test_hint_penalty_accumulation(self):
        """힌트 단계별 감점 누적 — 중복 무시."""
        import minsaseoryu_modes as m
        self.assertAlmostEqual(m.get_hint_penalty([]), 0.0)
        self.assertAlmostEqual(m.get_hint_penalty([1]), 0.05)
        self.assertAlmostEqual(m.get_hint_penalty([1, 2]), 0.15)
        self.assertAlmostEqual(m.get_hint_penalty([1, 2, 2.5]), 0.30)
        # 중복 step 은 1회만
        self.assertAlmostEqual(m.get_hint_penalty([1, 1, 1]), 0.05)
        # 전 단계 = 100% (1.0 clamp)
        full = m.get_hint_penalty([1, 2, 2.5, 3, 4, 5])
        self.assertGreater(full, 0.99)

    def test_get_modes_for_subject(self):
        """get_modes_for_subject('civil_doc') → 3개 dict."""
        import minsaseoryu_modes as m
        modes = m.get_modes_for_subject("civil_doc")
        self.assertEqual(len(modes), 3)
        self.assertEqual(modes[0]["name"][:5], "연결어 4"[:5])
        # 다른 과목 → 빈 list
        self.assertEqual(m.get_modes_for_subject("essay"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
