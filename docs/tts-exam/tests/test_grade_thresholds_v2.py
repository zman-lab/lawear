"""V2 grade thresholds (lawear-e571, 2026-05-19).

10단계 임계 (사용자 결정):
  80+ A+  / 75+ A  / 70+ A- / 65+ B+ / 60+ B (합격선) /
  55+ B-  / 50+ C+ / 45+ C  / 40+ C- / else F.

V1 → V2 호환:
  - 기존 attempts.grade DB 컬럼은 V1 enum (A/B/C/F) 유지.
  - API 응답에서 score_pct 기준 V2 grade 동적 재계산 (_recompute_grade_v2).
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grader  # noqa: E402


class TestGradeThresholdsV2Boundaries(unittest.TestCase):
    """V2 임계 경계 — 10단계 각 임계 정확히 확인."""

    def test_aplus_boundary_80(self) -> None:
        """80.0 → A+ (정확 경계)."""
        self.assertEqual(grader.compute_grade_v2(80.0), "A+")
        self.assertEqual(grader.compute_grade_v2(100.0), "A+")
        self.assertEqual(grader.compute_grade_v2(85.5), "A+")

    def test_a_boundary_75(self) -> None:
        """75.0 → A / 79.99 → A."""
        self.assertEqual(grader.compute_grade_v2(75.0), "A")
        self.assertEqual(grader.compute_grade_v2(79.99), "A")
        self.assertEqual(grader.compute_grade_v2(76.0), "A")
        # 80 직전
        self.assertEqual(grader.compute_grade_v2(79.999), "A")

    def test_aminus_boundary_70(self) -> None:
        """70.0 → A- / 74.99 → A-."""
        self.assertEqual(grader.compute_grade_v2(70.0), "A-")
        self.assertEqual(grader.compute_grade_v2(74.99), "A-")
        self.assertEqual(grader.compute_grade_v2(73.0), "A-")

    def test_bplus_boundary_65(self) -> None:
        """65.0 → B+ / 69.99 → B+."""
        self.assertEqual(grader.compute_grade_v2(65.0), "B+")
        self.assertEqual(grader.compute_grade_v2(69.99), "B+")

    def test_b_pass_line_60(self) -> None:
        """60.0 → B (합격선 정중앙) / 64.99 → B."""
        self.assertEqual(grader.compute_grade_v2(60.0), "B")
        self.assertEqual(grader.compute_grade_v2(64.99), "B")
        self.assertEqual(grader.compute_grade_v2(63.0), "B")  # att 6 예시

    def test_bminus_boundary_55(self) -> None:
        """55.0 → B- / 59.99 → B- (합격선 직전)."""
        self.assertEqual(grader.compute_grade_v2(55.0), "B-")
        self.assertEqual(grader.compute_grade_v2(59.99), "B-")
        self.assertEqual(grader.compute_grade_v2(56.7), "B-")  # att 17 예시

    def test_cplus_boundary_50(self) -> None:
        """50.0 → C+ / 54.99 → C+."""
        self.assertEqual(grader.compute_grade_v2(50.0), "C+")
        self.assertEqual(grader.compute_grade_v2(54.99), "C+")

    def test_c_boundary_45(self) -> None:
        """45.0 → C / 49.99 → C."""
        self.assertEqual(grader.compute_grade_v2(45.0), "C")
        self.assertEqual(grader.compute_grade_v2(49.99), "C")
        self.assertEqual(grader.compute_grade_v2(44.0), "C-")  # 45 직전

    def test_cminus_boundary_40(self) -> None:
        """40.0 → C- / 44.99 → C-."""
        self.assertEqual(grader.compute_grade_v2(40.0), "C-")
        self.assertEqual(grader.compute_grade_v2(44.99), "C-")

    def test_f_below_40(self) -> None:
        """39.99 → F / 0 → F."""
        self.assertEqual(grader.compute_grade_v2(39.99), "F")
        self.assertEqual(grader.compute_grade_v2(0.0), "F")
        self.assertEqual(grader.compute_grade_v2(0.1), "F")
        self.assertEqual(grader.compute_grade_v2(35.0), "F")


class TestGradeV2EdgeCases(unittest.TestCase):
    """V2 edge cases — None / NaN / 음수 / 100 초과 등."""

    def test_none_returns_f(self) -> None:
        self.assertEqual(grader.compute_grade_v2(None), "F")

    def test_nan_returns_f(self) -> None:
        nan = float("nan")
        self.assertEqual(grader.compute_grade_v2(nan), "F")

    def test_negative_returns_f(self) -> None:
        """음수 (이론적으로 score_pct 는 clamp 됐지만 안전).

        compute_grade_v2 자체는 임계 매칭만 함 — 음수는 0 임계 매칭하여 F.
        """
        self.assertEqual(grader.compute_grade_v2(-10.0), "F")

    def test_above_100_returns_aplus(self) -> None:
        """100 초과 → A+ (clamp 는 호출자 책임)."""
        self.assertEqual(grader.compute_grade_v2(150.0), "A+")

    def test_string_input_returns_f(self) -> None:
        """str 입력 → F (안전 fallback)."""
        self.assertEqual(grader.compute_grade_v2("abc"), "F")  # type: ignore

    def test_int_input_works(self) -> None:
        """int 도 정상 — float 변환."""
        self.assertEqual(grader.compute_grade_v2(75), "A")
        self.assertEqual(grader.compute_grade_v2(60), "B")


class TestUserScoreExamples(unittest.TestCase):
    """사용자 명시 예시 (att 6/14/17/18/19 등 — 백그라운드 정보).

    예시:
      att 19 (80)   → A+
      att 14 (76)   → A
      att 18 (73)   → A-
      att 6  (63)   → B
      att 17 (56.7) → B-
      att 11 (50)   → C+
    """

    def test_att19_80_aplus(self) -> None:
        self.assertEqual(grader.compute_grade_v2(80.0), "A+")

    def test_att14_76_a(self) -> None:
        self.assertEqual(grader.compute_grade_v2(76.0), "A")

    def test_att18_73_aminus(self) -> None:
        self.assertEqual(grader.compute_grade_v2(73.0), "A-")

    def test_att6_63_b(self) -> None:
        self.assertEqual(grader.compute_grade_v2(63.0), "B")

    def test_att17_56_bminus(self) -> None:
        self.assertEqual(grader.compute_grade_v2(56.7), "B-")

    def test_att11_50_cplus(self) -> None:
        self.assertEqual(grader.compute_grade_v2(50.0), "C+")


class TestV1V2Conversion(unittest.TestCase):
    """_to_v1_grade — DB CHECK 호환 (A/B/C/F enum)."""

    def test_aplus_a_aminus_to_a(self) -> None:
        self.assertEqual(grader._to_v1_grade("A+"), "A")
        self.assertEqual(grader._to_v1_grade("A"), "A")
        self.assertEqual(grader._to_v1_grade("A-"), "A")

    def test_bplus_b_bminus_to_b(self) -> None:
        self.assertEqual(grader._to_v1_grade("B+"), "B")
        self.assertEqual(grader._to_v1_grade("B"), "B")
        self.assertEqual(grader._to_v1_grade("B-"), "B")

    def test_cplus_c_cminus_to_c(self) -> None:
        self.assertEqual(grader._to_v1_grade("C+"), "C")
        self.assertEqual(grader._to_v1_grade("C"), "C")
        self.assertEqual(grader._to_v1_grade("C-"), "C")

    def test_f_to_f(self) -> None:
        self.assertEqual(grader._to_v1_grade("F"), "F")


class TestGradeThresholdsV2Constants(unittest.TestCase):
    """V2 상수 — 10단계 임계 정합성."""

    def test_v2_has_10_grades(self) -> None:
        """GRADE_THRESHOLDS_V2 — 10단계."""
        self.assertEqual(len(grader.GRADE_THRESHOLDS_V2), 10)

    def test_v2_thresholds_descending(self) -> None:
        """임계는 내림차순 (early-break 의도)."""
        thresholds = [t for t, _ in grader.GRADE_THRESHOLDS_V2]
        self.assertEqual(thresholds, sorted(thresholds, reverse=True))

    def test_default_thresholds_is_v2(self) -> None:
        """DEFAULT = V2 (신규 채점부터 V2 적용)."""
        self.assertEqual(grader.GRADE_THRESHOLDS, grader.GRADE_THRESHOLDS_V2)

    def test_v1_still_available(self) -> None:
        """V1 보존 (legacy 호환)."""
        self.assertEqual(len(grader.GRADE_THRESHOLDS_V1), 4)
        v1_grades = [g for _, g in grader.GRADE_THRESHOLDS_V1]
        self.assertEqual(v1_grades, ["A", "B", "C", "F"])


if __name__ == "__main__":
    unittest.main()
