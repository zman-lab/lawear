#!/usr/bin/env python3
"""Grader 엄격 룰 v3 — 사용자 데이터 기반 5룰 (lawear-e571, 2026-05-19).

[배경]
- 사용자 자체 채점이 AI 채점보다 더 엄격 (att 20: 80→39, att 21: 83.3→56 정정).
- 엄격 룰 v3 5개를 SYSTEM_PROMPT 에 추가:
    1) N요건 명시 누락 (outline -5pt 이상 / sem -5pt 이상)
    2) 조문 0개 인용 (articles ≤ max × 0.20)
    3) 변경판례 결론 한 줄만 매칭 + N요건 근거 누락 (sem ≤ max × 0.60)
    4) 법리 흐름 누락 (sem -5pt 이상 / outline -3pt 이상)
    5) 사안 적용에서 결론만 (case_apply ≤ max × 0.50)

[검증 포인트]
- SYSTEM_PROMPT 의 엄격 룰 v3 섹션 존재 + 5룰 모두 명시
- 각 룰별 키워드/임계값 명시 (예시 케이스, 점수 한도)
- mock 응답이 엄격 룰 v3 반영 (articles 0.20, case_apply 0.30, sem 0.50, outline 0.50)
- 사용자 정책 보존 (오타/태그/판례번호 X — 기존 룰 유지)

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_grader_strict_v3.py -v
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


# ─── SYSTEM_PROMPT — 엄격 룰 v3 섹션 존재 + 5룰 명시 ─────────────────


class SystemPromptStrictV3SectionTest(unittest.TestCase):
    """SYSTEM_PROMPT 에 엄격 룰 v3 섹션 + 5룰이 모두 명시되어 있는가."""

    def test_strict_v3_section_header_exists(self) -> None:
        """엄격화 v3 섹션 헤더 명시."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("엄격화 v3", sp)
        self.assertIn("사용자 데이터 기반", sp)
        # 추가 일자 명시
        self.assertIn("2026-05-19", sp)

    def test_strict_v3_rule1_n_requirements(self) -> None:
        """룰 1: N요건 명시 누락 (outline/sem -5pt 이상)."""
        sp = grader_mod.SYSTEM_PROMPT
        # 요건 명시 키워드
        self.assertIn("N요건", sp)
        self.assertIn("요건사실", sp)
        # 예시 케이스 4종 (양수금/이행불능/변경판례/부당이득)
        self.assertIn("양수금", sp)
        self.assertIn("이행불능", sp)
        self.assertIn("변경판례", sp)
        self.assertIn("부당이득", sp)
        # 점수 차감 명시
        self.assertTrue(
            "-5점" in sp or "-5 점" in sp or "-5pt" in sp,
            "요건 누락 -5점 차감 문구 누락",
        )

    def test_strict_v3_rule2_zero_articles(self) -> None:
        """룰 2: 조문 0개 인용 — articles max 20% 엄격."""
        sp = grader_mod.SYSTEM_PROMPT
        # "조문 0개" + "20%" 임계 명시
        self.assertIn("조문 0개", sp)
        self.assertIn("20%", sp)
        # 후하게 주지 말라는 문구
        self.assertTrue(
            "절대 금지" in sp or "한도 엄수" in sp,
            "조문 0개 후하게 주지 말라는 엄격 문구 누락",
        )
        # 구체 예시 (max=15 → 3)
        self.assertIn("max=15", sp)
        self.assertTrue(
            "최대 3" in sp or "score 최대 3" in sp,
            "max=15 → score 3 한도 예시 누락",
        )

    def test_strict_v3_rule3_changed_precedent(self) -> None:
        """룰 3: 변경판례 결론만 + N요건 근거 누락 (sem ≤ 60%)."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("변경판례", sp)
        # "결론만" 키워드
        self.assertTrue(
            "결론만" in sp or "결론 한 줄" in sp,
            "변경판례 결론만 매칭 키워드 누락",
        )
        # 60% 임계
        self.assertIn("60%", sp)
        # N요건 근거 명시
        self.assertTrue(
            "N요건 근거" in sp or "4요건 근거" in sp or "요건 근거" in sp,
            "변경판례 N요건 근거 키워드 누락",
        )

    def test_strict_v3_rule4_legal_flow(self) -> None:
        """룰 4: 법리 흐름 누락 (sem -5pt / outline -3pt)."""
        sp = grader_mod.SYSTEM_PROMPT
        # 법리 흐름 키워드
        self.assertIn("법리 흐름", sp)
        # 원칙/단서 구조 명시
        self.assertTrue(
            "원칙" in sp and "단서" in sp,
            "원칙/단서 구조 키워드 누락",
        )
        # 차감 점수
        self.assertTrue(
            "-3점" in sp or "-3 점" in sp or "-3pt" in sp,
            "법리 흐름 누락 -3점 차감 문구 누락",
        )

    def test_strict_v3_rule5_case_application(self) -> None:
        """룰 5: 사안 적용 결론만 (case_apply ≤ 50%)."""
        sp = grader_mod.SYSTEM_PROMPT
        # 사안 적용 결론만 키워드
        self.assertIn("사안 적용", sp)
        # 50% 임계
        self.assertIn("50%", sp)
        # case_apply 키 + 한도 예시 (max 7 → 3.5)
        self.assertIn("case_apply", sp)
        self.assertTrue(
            "max 7" in sp or "max=7" in sp,
            "case_apply max 7 임계 예시 누락",
        )

    def test_strict_v3_all_5_rules_numbered(self) -> None:
        """엄격 룰 v3 섹션에 1)~5) 5개 룰 번호 모두 명시."""
        sp = grader_mod.SYSTEM_PROMPT
        # 섹션 추출 (v3 헤더 ~ 출력 형식 직전)
        v3_start = sp.find("엄격화 v3")
        self.assertGreater(v3_start, -1, "엄격화 v3 섹션 헤더 미발견")
        v3_end = sp.find("[출력 형식", v3_start)
        self.assertGreater(v3_end, v3_start, "엄격화 v3 섹션 종결 미발견")
        v3_section = sp[v3_start:v3_end]
        # 1)~5) 모두 등장
        for n in ("1)", "2)", "3)", "4)", "5)"):
            self.assertIn(n, v3_section, f"룰 번호 {n} 누락")


# ─── mock 응답 — 엄격 룰 v3 반영 ────────────────────────────────


class MockStrictV3Test(unittest.TestCase):
    """_mock_response 가 엄격 룰 v3 임계를 반영하는가."""

    def setUp(self) -> None:
        self.case = {
            "id": "strict_v3_test",
            "subject_kor": "민법",
            "category": "테스트",
            "file": "test",
            "case_no": "01",
            "title": "Strict V3 Test",
            "points": 10,
            "md_body": "## 원본\n양수금 3요건 — 채권 성립, 양도계약, 대항요건.",
        }

    def _grade_mock(self) -> dict:
        return grader_mod.grade(self.case, "테스트 답안 (결론만)", force_mock=True)

    def test_mock_articles_at_or_below_20_pct(self) -> None:
        """mock articles score 가 max 의 20% 이하 (룰 2)."""
        result = self._grade_mock()
        articles = next(c for c in result["criteria"] if c["key"] == "articles")
        self.assertLessEqual(
            articles["score"],
            articles["max"] * 0.20 + 0.05,  # rounding 허용
            f"articles {articles['score']}/{articles['max']} 가 20% 초과",
        )

    def test_mock_case_apply_at_or_below_50_pct(self) -> None:
        """mock case_apply score 가 max 의 50% 이하 (룰 5)."""
        result = self._grade_mock()
        cap = next(c for c in result["criteria"] if c["key"] == "case_apply")
        self.assertLessEqual(
            cap["score"],
            cap["max"] * 0.50 + 0.05,
            f"case_apply {cap['score']}/{cap['max']} 가 50% 초과",
        )

    def test_mock_sem_conservative(self) -> None:
        """mock sem score 가 max 의 60% 이하 (룰 3 — 결론만 가정)."""
        result = self._grade_mock()
        sem = next(c for c in result["criteria"] if c["key"] == "sem")
        self.assertLessEqual(
            sem["score"],
            sem["max"] * 0.60 + 0.05,
            f"sem {sem['score']}/{sem['max']} 가 60% 초과 (변경판례 결론만 가정)",
        )

    def test_mock_outline_conservative(self) -> None:
        """mock outline score 가 max 의 60% 이하 (룰 1 — 요건 누락 가정)."""
        result = self._grade_mock()
        outline = next(c for c in result["criteria"] if c["key"] == "outline")
        self.assertLessEqual(
            outline["score"],
            outline["max"] * 0.60 + 0.05,
            f"outline {outline['score']}/{outline['max']} 가 60% 초과",
        )

    def test_mock_criteria_count_unchanged(self) -> None:
        """엄격 v3 반영 후에도 9 criteria 유지."""
        result = self._grade_mock()
        self.assertEqual(len(result["criteria"]), 9)
        keys = [c["key"] for c in result["criteria"]]
        for required in (
            "mnem",
            "color",
            "under",
            "outline",
            "sem",
            "rich",
            "miss",
            "articles",
            "case_apply",
        ):
            self.assertIn(required, keys)


# ─── 사용자 정책 보존 검증 (기존 룰 미훼손) ──────────────────────


class UserPolicyPreservationTest(unittest.TestCase):
    """기존 사용자 정책이 엄격 v3 추가 후에도 유지되는가."""

    def test_typo_tolerance_preserved(self) -> None:
        """오타 관용 (음성 STT 한정) 정책 유지."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("오타", sp)
        self.assertIn("STT", sp)
        # 오타 감점 금지 명시
        self.assertTrue(
            "오타 감점 절대 금지" in sp or "감점 X" in sp,
            "오타 감점 금지 문구 누락",
        )

    def test_tag_tolerance_preserved(self) -> None:
        """강조 태그 평문 인정 정책 유지 (태그 0개 OK)."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("강조 태그", sp)
        self.assertIn("평문", sp)
        # 평문 만점 인정 문구
        self.assertTrue(
            "평문 만점 인정" in sp or "평문으로 언급되면" in sp,
            "강조 태그 평문 인정 문구 누락",
        )

    def test_precedent_number_tolerance_preserved(self) -> None:
        """판례번호 평문 인정 (판례번호 미명시 감점 X) 정책 유지."""
        sp = grader_mod.SYSTEM_PROMPT
        self.assertIn("판례번호", sp)
        # 판례번호 미명시 missing_critical 금지
        self.assertTrue(
            "판례번호 미명시" in sp or "감점 X" in sp,
            "판례번호 감점 금지 문구 누락",
        )

    def test_phase2_strict_section_preserved(self) -> None:
        """기존 Phase 2 엄격화 (articles 임계 + 누락 핵심 4건) 보존."""
        sp = grader_mod.SYSTEM_PROMPT
        # Phase 2 articles 임계 섹션
        self.assertIn("articles 채점 임계", sp)
        # 누락 핵심 4건 섹션 (비법인사단/권리능력/제126조/증명책임)
        self.assertIn("누락 핵심 4건", sp)
        self.assertIn("비법인사단", sp)
        self.assertIn("제126조", sp)


# ─── 엄격 룰 v3 의도 검증 (사용자 데이터 매칭) ──────────────────


class StrictV3IntentTest(unittest.TestCase):
    """엄격 v3 가 실제 사용자 데이터(att 20/21) 패턴을 반영하는가."""

    def test_att20_pattern_n_requirements(self) -> None:
        """att 20 패턴 (3요건/4요건 사례 — N요건 명시 누락) 반영."""
        sp = grader_mod.SYSTEM_PROMPT
        # 양수금 3요건 + 이행불능 4요건 모두 명시
        self.assertIn("3요건", sp)
        self.assertIn("4요건", sp)

    def test_att21_pattern_changed_precedent(self) -> None:
        """att 21 패턴 (변경판례 결론만 매칭) 반영."""
        sp = grader_mod.SYSTEM_PROMPT
        # 변경판례 + 결론만 키워드
        self.assertIn("변경판례", sp)
        self.assertTrue(
            "결론만" in sp or "결론 한 줄" in sp,
            "변경판례 결론만 매칭 키워드 누락",
        )

    def test_zero_articles_pattern_explicit(self) -> None:
        """조문 0개 패턴 — 후하게 4~8점 주는 패턴 차단 명시."""
        sp = grader_mod.SYSTEM_PROMPT
        # "조문 0개" + "한도 엄수" 또는 "절대 금지" + "4~8점" 또는 "후하게"
        self.assertIn("조문 0개", sp)
        self.assertTrue(
            "한도 엄수" in sp or "절대 금지" in sp or "후하게" in sp,
            "조문 0개 후하게 주는 패턴 차단 문구 누락",
        )


if __name__ == "__main__":
    unittest.main()
