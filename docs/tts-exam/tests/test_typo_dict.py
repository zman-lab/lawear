"""정적 사전 (typo_dict.json) 로딩 + 매칭 검증.

lawear-e571/typo-system (2026-05-19).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import typo_corrector as tc  # noqa: E402


class TestLoadTypoDict(unittest.TestCase):
    """typo_dict.json 로딩."""

    def setUp(self) -> None:
        tc.clear_cache()

    def test_load_default_dict_returns_static_replacements(self):
        """기본 typo_dict.json 로드 — 30+건 (사용자 명시)."""
        d = tc.load_typo_dict()
        self.assertIn("static_replacements", d)
        self.assertIsInstance(d["static_replacements"], dict)
        # 사용자 명시 초기 사전 30~50건
        self.assertGreaterEqual(len(d["static_replacements"]), 30,
                                f"static dict 30+ 권장, 실측 {len(d['static_replacements'])}")

    def test_load_default_dict_contains_user_examples(self):
        """사용자가 명시한 핵심 오타 (attempt 9 발견) 포함."""
        d = tc.load_typo_dict()
        m = d["static_replacements"]
        self.assertEqual(m.get("파산관제인"), "파산관재인")
        self.assertEqual(m.get("통정표시"), "통정허위표시")
        self.assertEqual(m.get("선한간리주의"), "선량한 관리자의 주의")
        self.assertEqual(m.get("아기"), "악의")

    def test_load_missing_file_returns_empty(self):
        """존재 안 하는 경로 → 빈 사전 graceful."""
        result = tc.load_typo_dict("/nonexistent/path/typo_dict.json", force_reload=True)
        self.assertEqual(result["static_replacements"], {})
        self.assertEqual(result["version"], "0.0")

    def test_load_corrupted_json_returns_empty(self):
        """파싱 실패 → 빈 사전 graceful."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            tmp_path = f.name
        try:
            result = tc.load_typo_dict(tmp_path, force_reload=True)
            self.assertEqual(result["static_replacements"], {})
        finally:
            os.unlink(tmp_path)

    def test_load_dict_caches_result(self):
        """같은 경로 재로드 시 캐시 — 같은 인스턴스."""
        d1 = tc.load_typo_dict()
        d2 = tc.load_typo_dict()
        self.assertIs(d1, d2)

    def test_force_reload_invalidates_cache(self):
        """force_reload=True 시 캐시 무시."""
        d1 = tc.load_typo_dict()
        d2 = tc.load_typo_dict(force_reload=True)
        # 캐시 무시 후 다시 캐시되어 같음
        self.assertIsNotNone(d1)
        self.assertIsNotNone(d2)

    def test_env_var_override(self):
        """LAWEAR_TYPO_DICT_PATH 환경변수 override."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({
                "version": "test",
                "static_replacements": {"테스트": "TEST"},
                "context_patterns": [],
                "preserve_terms": []
            }, f, ensure_ascii=False)
            tmp_path = f.name
        try:
            os.environ["LAWEAR_TYPO_DICT_PATH"] = tmp_path
            tc.clear_cache()
            d = tc.load_typo_dict()
            self.assertEqual(d["static_replacements"], {"테스트": "TEST"})
            self.assertEqual(d["version"], "test")
        finally:
            os.environ.pop("LAWEAR_TYPO_DICT_PATH", None)
            tc.clear_cache()
            os.unlink(tmp_path)


class TestApplyStaticReplacements(unittest.TestCase):
    """apply_static_replacements — 정적 사전 매칭 적용."""

    def setUp(self) -> None:
        tc.clear_cache()

    def test_replace_파산관제인_returns_corrected(self):
        """파산관제인 → 파산관재인."""
        d = tc.load_typo_dict()
        text = "파산관제인이 채권자에게 통지했다."
        corrected, corrections = tc.apply_static_replacements(text, d)
        self.assertIn("파산관재인", corrected)
        self.assertNotIn("파산관제인", corrected)
        self.assertEqual(len(corrections), 1)
        self.assertEqual(corrections[0]["from"], "파산관제인")
        self.assertEqual(corrections[0]["to"], "파산관재인")
        self.assertEqual(corrections[0]["source"], "static_dict")

    def test_replace_multiple_typos_accumulates(self):
        """여러 오타 동시 — 각각 list 항목 누적."""
        d = tc.load_typo_dict()
        text = "통정표시는 무효이며, 선한간리주의 의무를 부담한다."
        corrected, corrections = tc.apply_static_replacements(text, d)
        self.assertIn("통정허위표시", corrected)
        self.assertIn("선량한 관리자의 주의", corrected)
        self.assertEqual(len(corrections), 2)
        froms = [c["from"] for c in corrections]
        self.assertIn("통정표시", froms)
        self.assertIn("선한간리주의", froms)

    def test_replace_empty_text_returns_empty(self):
        """빈 텍스트 → 빈 결과."""
        d = tc.load_typo_dict()
        corrected, corrections = tc.apply_static_replacements("", d)
        self.assertEqual(corrected, "")
        self.assertEqual(corrections, [])

    def test_replace_none_text_returns_empty(self):
        """None → 빈 결과 graceful."""
        d = tc.load_typo_dict()
        corrected, corrections = tc.apply_static_replacements(None, d)  # type: ignore[arg-type]
        self.assertEqual(corrected, "")
        self.assertEqual(corrections, [])

    def test_no_typo_text_returns_original(self):
        """오타 없는 텍스트 → 원본 그대로."""
        d = tc.load_typo_dict()
        text = "민법 제103조에 따른 반사회질서의 법률행위는 무효이다."
        corrected, corrections = tc.apply_static_replacements(text, d)
        self.assertEqual(corrected, text)
        self.assertEqual(corrections, [])

    def test_replace_preserves_조문번호_context(self):
        """조문 번호 인접 영역 보호 — preserve_terms 적용."""
        d = tc.load_typo_dict()
        # 제103조 인접에 "아기" 가 있어도 보호되어 그대로 (preserve_terms 매칭)
        text = "제103조 아기 무효"
        corrected, corrections = tc.apply_static_replacements(text, d)
        # preserve_terms (제103조) 가 ±5자 윈도우에 있어 보호
        self.assertEqual(corrected, text)
        self.assertEqual(corrections, [])

    def test_replace_longest_key_first(self):
        """긴 키 우선 매칭 — '통정 허위 표시' (사전에는 키로 등록) > '통정'."""
        # 커스텀 사전 — 부분 충돌 시나리오
        custom = {
            "version": "test",
            "static_replacements": {
                "통정": "WRONG",  # 짧은 키
                "통정 허위 표시": "통정허위표시",  # 긴 키 (우선)
            },
            "context_patterns": [],
            "preserve_terms": [],
        }
        text = "통정 허위 표시는 무효."
        corrected, corrections = tc.apply_static_replacements(text, custom)
        self.assertIn("통정허위표시", corrected)
        self.assertNotIn("WRONG", corrected)

    def test_empty_dict_returns_original_text(self):
        """빈 사전 → 원본 그대로 (corrections 0)."""
        empty = {"static_replacements": {}, "context_patterns": [], "preserve_terms": []}
        text = "아무거나 텍스트"
        corrected, corrections = tc.apply_static_replacements(text, empty)
        self.assertEqual(corrected, text)
        self.assertEqual(corrections, [])

    def test_correct_helper_uses_default_dict(self):
        """correct() 1-shot helper — 기본 사전 로드."""
        corrected, corrections = tc.correct("파산관제인이 왔다")
        self.assertIn("파산관재인", corrected)
        self.assertEqual(len(corrections), 1)


class TestBuildTypoToleranceNote(unittest.TestCase):
    """grader prompt 보조 — 음성 인식 관용 안내문 빌드."""

    def setUp(self) -> None:
        tc.clear_cache()

    def test_note_contains_voice_recognition_hint(self):
        """안내문에 '음성 인식' 키워드 포함."""
        d = tc.load_typo_dict()
        note = tc.build_typo_tolerance_note(d)
        self.assertIn("음성", note)
        self.assertIn("법률 용어", note)
        self.assertIn("조문 번호", note)

    def test_note_contains_examples(self):
        """안내문에 사전 예시 포함."""
        d = tc.load_typo_dict()
        note = tc.build_typo_tolerance_note(d)
        # 사전 예시 키 중 하나라도 포함되어야 함
        self.assertTrue(any(k in note for k in ["파산관제인", "통정표시", "선한간리주의"]))

    def test_note_empty_dict_returns_empty(self):
        """빈 사전 → 빈 안내문 (호출자가 prompt 분기)."""
        empty = {"static_replacements": {}, "context_patterns": [], "preserve_terms": []}
        note = tc.build_typo_tolerance_note(empty)
        self.assertEqual(note, "")


class TestDictEntryCount(unittest.TestCase):
    """사전 항목 수 helper."""

    def setUp(self) -> None:
        tc.clear_cache()

    def test_default_dict_30_plus_entries(self):
        """기본 사전 30+ 항목 (사용자 명시)."""
        n = tc.dict_entry_count()
        self.assertGreaterEqual(n, 30, f"default dict 30+ entries 권장, 실측 {n}")

    def test_empty_dict_zero(self):
        """빈 사전 → 0."""
        empty = {"static_replacements": {}, "context_patterns": [], "preserve_terms": []}
        self.assertEqual(tc.dict_entry_count(empty), 0)


if __name__ == "__main__":
    unittest.main()
