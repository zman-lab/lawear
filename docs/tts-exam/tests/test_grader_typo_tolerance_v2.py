"""grader.py SYSTEM_PROMPT v2 — STT 오타 + 평문 키워드 관용 강화.

lawear-e571/grader-tune-fallback (2026-05-19).
사용자 명시:
  1. 오타 감점 절대 X — 음성 STT 입력이라 수정 힘듦. 자동 교정 후 남은 오타도
     의미 통하면 그대로 인정.
  2. 태그 감싸기 X 인정 — 사용자가 답안에 [red]/[blue]/[u] 태그를 박지 않아도,
     태그 안 키워드가 평문으로 언급되면 color/under/mnem 만점.
  3. 메인 시스템 메시지 "강조 태그 0개" 오해 유발 — 정정 필요.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grader as grader_mod  # noqa: E402


class TestSystemPromptToleranceV2(unittest.TestCase):
    """SYSTEM_PROMPT 가 v2 관용 룰 (STT + 평문) 을 포함하는지 검증."""

    def test_system_prompt_has_lenience_section(self):
        """[관용 룰 — 음성 STT + 평문 키워드 인정] 섹션 존재."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertIn("관용 룰", prompt)
        self.assertIn("평문 키워드 인정", prompt)

    def test_system_prompt_states_typo_no_penalty(self):
        """'오타 감점 절대 금지' 또는 동등 표현 명시."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertTrue(
            "오타 감점 절대 금지" in prompt or "오타 감점 X" in prompt,
            "오타 감점 금지 명시 필요"
        )

    def test_system_prompt_states_plain_text_keyword_acceptance(self):
        """평문 키워드 → color/under/mnem 만점 명시."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertIn("평문", prompt)
        # color/under/mnem 만점 인정 명시
        self.assertTrue(
            "color/under/mnem 만점" in prompt
            or "color/under/mnem **만점**" in prompt,
            "평문 키워드 만점 인정 명시 필요"
        )

    def test_system_prompt_states_tags_optional(self):
        """사용자 답안에 태그 박지 않음 — 정상 명시."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertTrue(
            "강조 태그" in prompt and (
                "박지 않" in prompt or "박지 않습니다" in prompt
                or "박지 마" in prompt
            ),
            "사용자가 태그 안 박는 게 정상이라는 명시 필요"
        )

    def test_system_prompt_tag_no_bonus(self):
        """태그 박아도 가점 X 명시 (오해 방지)."""
        prompt = grader_mod.SYSTEM_PROMPT
        # "태그를 박았다고 가점 X" 또는 동의어
        self.assertTrue(
            "태그를 박았다고 가점 X" in prompt
            or "태그 박힘은 점수 차이 없음" in prompt
            or "점수 차이 없음" in prompt,
            "태그 가점 X 명시 필요"
        )

    def test_criterion_mnem_mentions_plain_text(self):
        """mnem 기준에 '평문' + 만점 인정 명시."""
        prompt = grader_mod.SYSTEM_PROMPT
        # mnem 줄 근처에 평문 단어 (대략 위치 검증)
        # SYSTEM_PROMPT 의 mnem 줄을 찾아서 ~200자 범위 내 검사
        idx = prompt.find("mnem")
        self.assertGreater(idx, -1)
        # mnem 기준 줄 +200자 영역
        region = prompt[idx:idx + 400]
        self.assertIn("평문", region, "mnem 기준 설명에 '평문' 명시 필요")

    def test_criterion_color_mentions_plain_text(self):
        """color 기준에 '평문' + 만점 인정 명시."""
        prompt = grader_mod.SYSTEM_PROMPT
        idx = prompt.find("color")
        self.assertGreater(idx, -1)
        region = prompt[idx:idx + 400]
        self.assertIn("평문", region, "color 기준 설명에 '평문' 명시 필요")

    def test_criterion_under_mentions_plain_text(self):
        """under 기준에 '평문' + 만점 인정 명시."""
        prompt = grader_mod.SYSTEM_PROMPT
        idx = prompt.find("under")
        self.assertGreater(idx, -1)
        region = prompt[idx:idx + 400]
        self.assertIn("평문", region, "under 기준 설명에 '평문' 명시 필요")

    def test_misleading_message_disclaimer(self):
        """메인 메시지 '강조 태그 0개' 오해 유발 표현 무시 명시."""
        prompt = grader_mod.SYSTEM_PROMPT
        self.assertTrue(
            "오해 유발" in prompt or "무시할 것" in prompt or "강조 태그 0개" in prompt,
            "오해 유발 표현 무시 명시 필요"
        )

    def test_typo_strict_for_article_numbers(self):
        """조문 번호는 여전히 엄격 (오타 X)."""
        prompt = grader_mod.SYSTEM_PROMPT
        # "조문 번호" + "엄격" 또는 "오타 X" 인접 명시
        self.assertIn("조문 번호", prompt)
        # 조문 번호 보호 컨텍스트 (엄격 / 오타 X / 절대 / 모르는 것)
        # 핵심: 음성 STT 관용 룰에서도 조문 번호는 보호
        # 새 [관용 룰] 섹션의 1)-끝부분 텍스트 검증
        self.assertIn("엄격", prompt, "조문 번호 엄격 명시 필요")


class TestBuildPromptV2Integration(unittest.TestCase):
    """_build_prompt — 새 관용 룰이 system 에 포함."""

    def test_build_prompt_returns_lenience_section(self):
        """_build_prompt 의 system_prompt 가 관용 룰 포함."""
        case_meta = {
            "id": "test_v2",
            "subject_kor": "민법",
            "category": "입문",
            "file": "v2.md",
            "case_no": 1,
            "title": "V2 테스트",
            "points": 30,
            "md_body": "v2 본문",
        }
        weights = {
            "mnem": 16, "color": 13, "under": 8, "outline": 10, "sem": 12,
            "rich": 15, "miss": 11, "articles": 10, "case_apply": 5,
        }
        system, _ = grader_mod._build_prompt(case_meta, "답안", weights)
        self.assertIn("관용 룰", system)
        self.assertIn("평문", system)

    def test_build_prompt_subq_returns_lenience_section(self):
        """_build_prompt_subq 도 SYSTEM_PROMPT 공유 — 관용 룰 포함."""
        case = {
            "id": "test_v2_subq",
            "subject_kor": "민법",
            "category": "입문",
            "file": "v2.md",
            "case_no": 1,
            "title": "다중설문 v2",
        }
        subq = {
            "key": "설문 1", "label": "설문 1", "score_max": 10,
            "body": "본문", "answer": "답안지",
        }
        system, _ = grader_mod._build_prompt_subq(case, subq, "사용자 답안", [])
        self.assertIn("관용 룰", system)
        self.assertIn("평문 키워드 인정", system)


class TestGradeMockToleranceV2(unittest.TestCase):
    """grade() — 평문 키워드 + 음성 오타 답안 mock 채점 (스모크).

    실 API 호출 없는 mock 모드 — 시스템 프롬프트 통합 검증용.
    실제 의미 매칭 검증은 LLM 응답에 의존하므로 본 TC 는 채점 흐름이 정상 작동하는지만.
    """

    def test_grade_with_plain_text_keyword_answer(self):
        """태그 없는 평문 답안도 grade() 가 정상 처리 (예외 없음)."""
        case_meta = {
            "id": "v2_plain",
            "subject_kor": "민법",
            "category": "입문",
            "file": "test.md",
            "case_no": 1,
            "title": "평문 답안 TC",
            "points": 17,
            "md_body": (
                "## 원본\n"
                "사실관계: 갑은 채권자취소를 행사했다.\n"
                "## Lv.4\n"
                "[red]직접수익자[/red]에 대한 [u]상대적 효과[/u].\n"
            ),
        }
        # 사용자 답안은 태그 없는 평문 — 키워드 의미는 그대로 언급
        user_answer = (
            "갑은 채권자취소권을 행사했고, 직접수익자에 대한 상대적 효과로 청구가 인정된다."
        )
        result = grader_mod.grade(
            case_meta, user_answer,
            weights={
                "mnem": 10, "color": 8, "under": 5, "outline": 14, "sem": 15,
                "rich": 13, "miss": 13, "articles": 15, "case_apply": 7,
            },
            force_mock=True,
        )
        self.assertIn("eval_notes", result)
        self.assertIn("criteria", result)
        # mock 은 정확한 의미 매칭을 안 하지만 grade() 자체는 정상 작동.
        # criteria 9개 모두 정상
        self.assertEqual(len(result["criteria"]), 9)
        # is_mock 명시
        self.assertTrue(result["is_mock"])

    def test_grade_with_stt_typo_remaining_after_dict(self):
        """typo_dict 에 없는 STT 오타도 grade() 가 graceful 처리."""
        case_meta = {
            "id": "v2_stt",
            "subject_kor": "민법",
            "category": "입문",
            "file": "test.md",
            "case_no": 1,
            "title": "STT 오타 TC",
            "points": 17,
            "md_body": "## 원본\n표현대리 요건",
        }
        # 사전에 없는 변형 오타 (예: typo_dict 외 변형)
        # mock 은 어차피 점수 고정 → grade() 흐름만 정상 작동 확인
        user_answer = "표현대리 요건은 외관, 신뢰, 선의이다."
        result = grader_mod.grade(
            case_meta, user_answer,
            force_mock=True,
        )
        self.assertEqual(result["grade"] in ("A", "B", "C", "F"), True)


if __name__ == "__main__":
    unittest.main()
