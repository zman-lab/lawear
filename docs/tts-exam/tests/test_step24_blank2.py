#!/usr/bin/env python3
"""Step 24 후속 — Lv.2 힌트 ``[blank2]`` 태그 추출 단위 테스트.

배경 (2026-05-17 lawear-a519 Step 25 사용자 피드백):
- 기존 Lv.2 힌트 = Lv.4 번호 목록 노출 → **정답 본문 노출** → 폐기.
- 새 정책: ``[blank2]X[/blank2]`` 태그 안 콘텐츠만 콤마 join 으로 노출.
- 두문자 없는 .md (= [blank2] 0건) → 아무것도 노출 X.

검증 범위:
1. ``_extract_blank2_chars`` — 정규식 단위 (basic / multiple / empty).
2. ``parse_md_subqs`` — 각 subq dict 에 ``mnemonic`` 필드 정확 추출.
3. ``parse_md_mnemonic`` — 전체 .md ``[blank2]`` 추출 (기존 Lv.4 본문 X).

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step24_blank2.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent.resolve()
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import cases as cases_mod  # noqa: E402

# .md 샘플 경로 (워크트리/메인 양쪽 동일 docs/tts-new 트리).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MD_BASE: Path = _REPO_ROOT / "docs" / "tts-new"


def _load(rel: str) -> str:
    p = _MD_BASE / rel
    if not p.is_file():
        raise unittest.SkipTest(f"sample md not found: {p}")
    return p.read_text(encoding="utf-8")


# ─── 1. _extract_blank2_chars (정규식 단위) ─────────────────────────


class TestExtractBlank2Chars(unittest.TestCase):
    """``_extract_blank2_chars`` — ``[blank2]X[/blank2]`` 콘텐츠 추출."""

    def test_extract_blank2_chars_basic(self):
        """단일 글자 태그 — `[blank2]무[/blank2]` → ['무']."""
        self.assertEqual(cases_mod._extract_blank2_chars("[blank2]무[/blank2]"), ["무"])

    def test_extract_blank2_chars_multiple(self):
        """다중 태그 — 미케03_27.md 117라인 패턴 → 4건 순서 보존."""
        text = (
            "채[blank2]무[/blank2]자의 이행지체, 상당한 [blank2]기[/blank2]간, "
            "[blank2]최[/blank2]고기간내 불이행, 해제 의사표시 [blank2]도[/blank2]달"
        )
        self.assertEqual(cases_mod._extract_blank2_chars(text), ["무", "기", "최", "도"])

    def test_extract_blank2_chars_multi_letter(self):
        """글자 2+ 토큰 — `[blank2]묵시[/blank2]` 또는 `[blank2]단체[/blank2]` 같은 다글자."""
        text = "[blank2]묵시[/blank2]적으로도, [blank2]단체[/blank2] 존속"
        self.assertEqual(cases_mod._extract_blank2_chars(text), ["묵시", "단체"])

    def test_extract_blank2_chars_empty(self):
        """blank2 없는 본문 → 빈 list."""
        self.assertEqual(cases_mod._extract_blank2_chars("그냥 평문, [red]색[/red] 만 있음"), [])

    def test_extract_blank2_chars_none(self):
        """None / 빈 문자열 → 빈 list (NPE 방지)."""
        self.assertEqual(cases_mod._extract_blank2_chars(""), [])
        self.assertEqual(cases_mod._extract_blank2_chars(None), [])  # type: ignore[arg-type]

    def test_extract_blank2_chars_non_greedy(self):
        """non-greedy — 두 태그를 하나로 묶지 않음."""
        text = "[blank2]A[/blank2]중간[blank2]B[/blank2]"
        self.assertEqual(cases_mod._extract_blank2_chars(text), ["A", "B"])

    def test_extract_blank2_chars_real_md_single_blank2(self):
        """실제 .md 단일 매치 — 미케01_07.md 91라인 ['묵시']."""
        md = _load("입문_민법/2026_minbeop_immun_미케01_07.md")
        chars = cases_mod._extract_blank2_chars(md)
        self.assertEqual(chars, ["묵시"])


# ─── 2. parse_md_subqs subq.mnemonic 필드 ─────────────────────────


class TestParseMdSubqsMnemonic(unittest.TestCase):
    """``parse_md_subqs`` — 각 subq dict 에 ``mnemonic`` 필드 추출."""

    def test_parse_md_subqs_mnemonic_field_exists(self):
        """다중 설문 .md — 모든 subq 에 `mnemonic` 키 존재 (str 타입)."""
        md = _load("예비_민법/2026_minbeop_yebi_모고01_01.md")
        cards = cases_mod.parse_md_subqs(md)
        self.assertTrue(len(cards) > 0, "다중 설문 카드 있어야 함")
        for c in cards:
            self.assertIn("mnemonic", c)
            self.assertIsInstance(c["mnemonic"], str)

    def test_parse_md_subqs_mnemonic_empty_when_no_blank2(self):
        """blank2 없는 다중 설문 .md — subq.mnemonic 모두 ''."""
        md = _load("예비_민법/2026_minbeop_yebi_모고01_01.md")
        cards = cases_mod.parse_md_subqs(md)
        for c in cards:
            self.assertEqual(c["mnemonic"], "", f"key={c['key']} 에 blank2 없는데 mnemonic 비어있어야 함")

    def test_parse_md_subqs_mnemonic_synthetic_with_blank2(self):
        """합성 .md — subq body+answer 안 blank2 → mnemonic 콤마 join."""
        md = (
            "### 설문 1 (10점)\n"
            "본문에 [blank2]보[/blank2]증 키워드.\n\n"
            "### 설문 1 답안\n"
            "I. 결론\n"
            "[blank2]필[/blank2]수, [blank2]불[/blank2]가, [blank2]대[/blank2]항.\n\n"
            "### 설문 2 (5점)\n"
            "blank2 없음.\n\n"
            "### 설문 2 답안\n"
            "그냥 평문.\n"
        )
        cards = cases_mod.parse_md_subqs(md)
        self.assertEqual(len(cards), 2)
        by_key = {c["key"]: c for c in cards}
        self.assertEqual(by_key["설문 1"]["mnemonic"], "보,필,불,대")
        self.assertEqual(by_key["설문 2"]["mnemonic"], "")

    def test_parse_md_subqs_preserves_existing_fields(self):
        """회귀 — 기존 키 (key/score_max/body/answer) 보존."""
        md = (
            "### 설문 1 (10점)\n"
            "본문\n\n"
            "### 설문 1 답안\n"
            "답안\n"
        )
        cards = cases_mod.parse_md_subqs(md)
        self.assertEqual(len(cards), 1)
        c = cards[0]
        self.assertEqual(c["key"], "설문 1")
        self.assertEqual(c["score_max"], 10)
        self.assertIn("본문", c["body"])
        self.assertIn("답안", c["answer"])
        self.assertIn("mnemonic", c)


# ─── 3. parse_md_mnemonic 전체 .md blank2 추출 ─────────────────────


class TestParseMdMnemonicBlank2(unittest.TestCase):
    """``parse_md_mnemonic`` — 전체 .md ``[blank2]`` 추출 (Lv.4 본문 X)."""

    def test_parse_md_mnemonic_only_blank2_basic(self):
        """단일 blank2 .md — 미케01_07.md → ['묵시']."""
        md = _load("입문_민법/2026_minbeop_immun_미케01_07.md")
        items = cases_mod.parse_md_mnemonic(md)
        self.assertEqual(items, ["묵시"])

    def test_parse_md_mnemonic_only_blank2_multi(self):
        """다중 blank2 .md — 미케03_27.md (Lv.4 4개) + 미케03_27 다른 라인 검증."""
        md = _load("입문_민법/2026_minbeop_immun_미케03_27.md")
        items = cases_mod.parse_md_mnemonic(md)
        # 117 라인 답안: 무, 기, 최, 도 (4건) + 118 라인 (성립 요건): 무, 도, 가, 귀, 법 (5건)
        self.assertTrue(len(items) >= 4, f"미케03_27 blank2 매칭 최소 4건 (실측 {len(items)})")
        self.assertIn("무", items)
        self.assertIn("기", items)
        self.assertIn("최", items)
        self.assertIn("도", items)

    def test_parse_md_mnemonic_no_blank2_returns_empty(self):
        """blank2 없는 .md (모고01_01.md) → []."""
        md = _load("예비_민법/2026_minbeop_yebi_모고01_01.md")
        items = cases_mod.parse_md_mnemonic(md)
        self.assertEqual(items, [])

    def test_parse_md_mnemonic_lv4_number_list_not_extracted(self):
        """회귀 — Lv.4 번호 목록 (`1. ...`) 만 있는 본문 → [] (기존 동작 폐기)."""
        md = (
            "## Lv.4 암기노트\n"
            "1. 결론 첫번째.\n"
            "2. 결론 두번째.\n"
            "3. 결론 세번째.\n"
        )
        self.assertEqual(cases_mod.parse_md_mnemonic(md), [])

    def test_parse_md_mnemonic_blank2_outside_lv4(self):
        """Lv.4 섹션 밖 (예: 원본) 의 blank2 도 추출 — 전체 .md 스캔."""
        md = (
            "## 원본 (10점)\n"
            "본문에 [blank2]테스트[/blank2] 태그.\n\n"
            "## Lv.4 암기노트\n"
            "1. 결론.\n"
        )
        items = cases_mod.parse_md_mnemonic(md)
        self.assertEqual(items, ["테스트"])

    def test_parse_md_mnemonic_empty_md(self):
        """빈 .md → []."""
        self.assertEqual(cases_mod.parse_md_mnemonic(""), [])


if __name__ == "__main__":
    unittest.main()
