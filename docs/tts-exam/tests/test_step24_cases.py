#!/usr/bin/env python3
"""Step 24-2 — cases.parse_md_subqs + 정규식 3종 단위 테스트.

dev-design archive #48 §5-1~5-3 / dev-impl-plan §B Step 24-2 1:1.

검증 범위:
1. ``_SUBQ_HEADER_RE`` 3종 (A/B/C) — 8 .md 14 subq 헤더 전수 100% 매칭.
2. ``_SUBQ_ANSWER_HEADER_RE`` — 답안 헤더 매칭 + ``_SUBQ_HEADER_RE`` 오탐 0건.
3. ``_FACTS_HEADER_RE`` 4종 — 사실관계 prefix(공통된/기본적/변형된/없음).
4. ``normalize_subq_key`` — 패턴 A/B/C 정규화.
5. ``parse_md_subqs`` 다중 7건 + 단일 fallback 1건.
6. ``parse_md_subqs`` 가/나 독립 카드 (패턴 C).
7. ``parse_md_toc`` + ``parse_md_mnemonic`` 기본 동작.

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step24_cases.py -v
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
#
# 주의: 다른 테스트(test_step13/14/17/etc.)가 `cases.BASE_PATH` 를 임시 디렉토리로
# 변경한 상태로 본 모듈이 import 될 수 있다 (pytest-randomly 영향). 따라서
# `cases.BASE_PATH` 를 직접 쓰지 않고 본 파일 기준 상대 경로(`../../tts-new`)로
# 샘플 .md 를 찾는다. 워크트리/메인 양쪽 동일 트리 보장.
_REPO_ROOT = Path(__file__).resolve().parents[3]  # .../lawear[-...] 레포 root
_MD_BASE: Path = _REPO_ROOT / "docs" / "tts-new"


def _load(rel: str) -> str:
    """샘플 .md 본문 로드.

    Raises:
        unittest.SkipTest: 샘플 파일이 디스크에 없을 때 (예: tts-new 미동기화 환경).
    """
    p = _MD_BASE / rel
    if not p.is_file():
        raise unittest.SkipTest(f"sample md not found: {p}")
    return p.read_text(encoding="utf-8")


# ─── 1. 정규식 3종 헤더 매트릭스 검증 ────────────────────────────────


class TestSubqHeaderRegex(unittest.TestCase):
    """`_SUBQ_HEADER_RE` 3종 (A/B/C) — 8 .md 14 헤더 전수 매칭 100%."""

    # dev-design archive #48 5-2 표의 헤더 매트릭스 그대로 (14건)
    MULTI_HEADERS_A = [
        # 패턴 A: ### 설문 N (NN점)
        ("### 설문 1 (20점)", "설문 1", None, "20"),
        ("### 설문 2 (15점)", "설문 2", None, "15"),
        ("### 설문 1 (13점)", "설문 1", None, "13"),
        ("### 설문 2 (13점)", "설문 2", None, "13"),
        ("### 설문 3 (12점)", "설문 3", None, "12"),
        ("### 설문 4 (12점)", "설문 4", None, "12"),
    ]
    MULTI_HEADERS_B = [
        # 패턴 B: ### 설문 (N) (NN점)
        ("### 설문 (1) (12점)", "설문 (1)", None, "12"),
        ("### 설문 (2) (15점)", "설문 (2)", None, "15"),
        ("### 설문 (3) (8점)",  "설문 (3)", None, "8"),
        ("### 설문 (4) (15점)", "설문 (4)", None, "15"),
    ]
    MULTI_HEADERS_C = [
        # 패턴 C: ### 설문 N 가/나 (NN점)
        ("### 설문 1 가 (12점)", "설문 1", "가", "12"),
        ("### 설문 1 나 (10점)", "설문 1", "나", "10"),
        ("### 설문 2 가 (12점)", "설문 2", "가", "12"),
        ("### 설문 2 나 (16점)", "설문 2", "나", "16"),
    ]

    def test_subq_header_re_3patterns_8md_100percent(self):
        """8 .md 의 14 헤더 전수 — A/B/C 3종 모두 매칭 100%."""
        all_headers = (
            self.MULTI_HEADERS_A
            + self.MULTI_HEADERS_B
            + self.MULTI_HEADERS_C
        )
        self.assertEqual(len(all_headers), 14, "14 헤더 매트릭스 (8 .md 실측)")

        for header_line, exp_g1, exp_g2, exp_score in all_headers:
            with self.subTest(header=header_line):
                m = cases_mod._SUBQ_HEADER_RE.match(header_line)
                self.assertIsNotNone(m, f"MATCH FAIL: {header_line!r}")
                self.assertEqual(m.group(1), exp_g1)
                self.assertEqual(m.group(2), exp_g2)
                self.assertEqual(m.group(3), exp_score)

    def test_subq_header_re_rejects_answer_headers(self):
        """답안 헤더 `### 설문 N 답안` / `### 설문 N 가 답안` 은 매칭 X (오탐 방지)."""
        answer_headers = [
            "### 설문 1 답안",
            "### 설문 2 답안",
            "### 설문 (1) 답안",
            "### 설문 (3) 답안",
            "### 설문 1 가 답안",
            "### 설문 2 나 답안",
        ]
        for h in answer_headers:
            with self.subTest(header=h):
                self.assertIsNone(
                    cases_mod._SUBQ_HEADER_RE.match(h),
                    f"답안 헤더 오탐: {h!r}",
                )

    def test_subq_answer_header_re_matches_all(self):
        """`_SUBQ_ANSWER_HEADER_RE` 는 답안 헤더 6종 모두 매칭."""
        cases_to_test = [
            ("### 설문 1 답안",       "설문 1",     None),
            ("### 설문 (1) 답안",     "설문 (1)",   None),
            ("### 설문 1 가 답안",    "설문 1",     "가"),
            ("### 설문 2 나 답안",    "설문 2",     "나"),
            ("### 설문 (3) 답안",     "설문 (3)",   None),
            ("### 설문 (4) 답안",     "설문 (4)",   None),
        ]
        for header_line, exp_g1, exp_g2 in cases_to_test:
            with self.subTest(header=header_line):
                m = cases_mod._SUBQ_ANSWER_HEADER_RE.match(header_line)
                self.assertIsNotNone(m, f"답안 매칭 실패: {header_line!r}")
                self.assertEqual(m.group(1), exp_g1)
                self.assertEqual(m.group(2), exp_g2)


class TestFactsHeaderRegex(unittest.TestCase):
    """`_FACTS_HEADER_RE` 4종 — prefix(공통된/기본적/변형된/없음)."""

    def test_facts_header_re_4patterns(self):
        """4종 사실관계 헤더 매칭 + prefix 캡처."""
        cases_to_test = [
            ("### 사실관계",          None),
            ("### 공통된 사실관계",   "공통된"),
            ("### 기본적 사실관계",   "기본적"),
            ("### 변형된 사실관계",   "변형된"),
        ]
        for header_line, exp_prefix in cases_to_test:
            with self.subTest(header=header_line):
                m = cases_mod._FACTS_HEADER_RE.match(header_line)
                self.assertIsNotNone(m, f"facts 매칭 실패: {header_line!r}")
                self.assertEqual(m.group(1), exp_prefix)

    def test_facts_header_re_rejects_non_facts(self):
        """비-사실관계 헤더 거부 (오탐 방지)."""
        non_facts = [
            "### 문제",
            "### 답안",
            "### 결론",
            "### 목차",
            "### 설문 1 (20점)",
        ]
        for h in non_facts:
            with self.subTest(header=h):
                self.assertIsNone(cases_mod._FACTS_HEADER_RE.match(h))


# ─── 2. normalize_subq_key 정규화 ──────────────────────────────────


class TestNormalizeSubqKey(unittest.TestCase):
    """`normalize_subq_key` 패턴 A/B/C 정규화."""

    def test_normalize_subq_key_pattern_a(self):
        """패턴 A — `### 설문 1 (20점)` → `설문 1`."""
        self.assertEqual(cases_mod.normalize_subq_key("설문 1", None), "설문 1")
        self.assertEqual(cases_mod.normalize_subq_key("설문 3", None), "설문 3")

    def test_normalize_subq_key_pattern_b_parens_removed(self):
        """패턴 B — `### 설문 (1) (12점)` → `설문 1` (괄호 제거)."""
        self.assertEqual(cases_mod.normalize_subq_key("설문 (1)", None), "설문 1")
        self.assertEqual(cases_mod.normalize_subq_key("설문 (4)", None), "설문 4")

    def test_normalize_subq_key_pattern_c_ga_na(self):
        """패턴 C — `### 설문 1 가 (12점)` → `설문 1 가`."""
        self.assertEqual(cases_mod.normalize_subq_key("설문 1", "가"), "설문 1 가")
        self.assertEqual(cases_mod.normalize_subq_key("설문 2", "나"), "설문 2 나")

    def test_normalize_subq_key_pattern_b_plus_c_future_safe(self):
        """패턴 B+C 결합 (미래 대비) — `### 설문 (1) 가` → `설문 1 가`."""
        self.assertEqual(cases_mod.normalize_subq_key("설문 (1)", "가"), "설문 1 가")


# ─── 3. parse_md_subqs — 다중 설문 분해 ────────────────────────────


class TestParseMdSubqsMulti(unittest.TestCase):
    """`parse_md_subqs` — 7건 다중 설문 .md 각각 카드 N 개 분해."""

    # 8 .md 중 다중 설문 7건 (모고01_02 fallback 제외)
    EXPECTED = [
        # (rel_path, pattern, exp_count, exp_keys, exp_scores)
        ("예비_민법/2026_minbeop_yebi_모고01_01.md",
         "A", 2, ["설문 1", "설문 2"], [20, 15]),
        ("예비_민법/2026_minbeop_yebi_모고02_01.md",
         "C", 2, ["설문 1 가", "설문 1 나"], [12, 10]),
        ("예비_민법/2026_minbeop_yebi_모고02_02.md",
         "C", 2, ["설문 2 가", "설문 2 나"], [12, 16]),
        ("예비_민소/2026_minso_yebi_모고01_01.md",
         "B", 2, ["설문 1", "설문 2"], [12, 15]),
        ("예비_민소/2026_minso_yebi_모고01_02.md",
         "B", 2, ["설문 3", "설문 4"], [8, 15]),
        ("예비_민소/2026_minso_yebi_모고02_01.md",
         "A", 2, ["설문 1", "설문 2"], [13, 13]),
        ("예비_민소/2026_minso_yebi_모고02_02.md",
         "A", 2, ["설문 3", "설문 4"], [12, 12]),
    ]

    def test_parse_md_subqs_multi(self):
        """7 .md 각각 — subq_count + key 라벨 + score_max 모두 일치."""
        for rel, pattern, exp_count, exp_keys, exp_scores in self.EXPECTED:
            with self.subTest(file=rel, pattern=pattern):
                md = _load(rel)
                cards = cases_mod.parse_md_subqs(md)
                self.assertEqual(
                    len(cards), exp_count,
                    f"{rel}: subq_count={len(cards)} (expected {exp_count})"
                )
                self.assertEqual(
                    [c["key"] for c in cards], exp_keys,
                    f"{rel}: keys 불일치",
                )
                self.assertEqual(
                    [c["score_max"] for c in cards], exp_scores,
                    f"{rel}: score_max 불일치",
                )

    def test_parse_md_subqs_body_answer_nonempty(self):
        """7 .md — 모든 카드의 body / answer 본문이 비어있지 않음."""
        for rel, _, _, _, _ in self.EXPECTED:
            with self.subTest(file=rel):
                md = _load(rel)
                cards = cases_mod.parse_md_subqs(md)
                for c in cards:
                    self.assertTrue(
                        c["body"].strip(),
                        f"{rel} card[{c['key']}].body 비어있음",
                    )
                    self.assertTrue(
                        c["answer"].strip(),
                        f"{rel} card[{c['key']}].answer 비어있음",
                    )


class TestParseMdSubqsSingleFallback(unittest.TestCase):
    """`parse_md_subqs` — 단일 설문 .md 는 빈 list (legacy fallback)."""

    def test_parse_md_subqs_single_fallback(self):
        """모고01_02 (단일 설문, ### 설문 N 헤더 0개) → []."""
        md = _load("예비_민법/2026_minbeop_yebi_모고01_02.md")
        cards = cases_mod.parse_md_subqs(md)
        self.assertEqual(cards, [], "단일 설문 fallback 은 빈 list 반환")

    def test_parse_md_subqs_empty_input(self):
        """빈 본문 → []."""
        self.assertEqual(cases_mod.parse_md_subqs(""), [])

    def test_parse_md_subqs_no_subq_headers(self):
        """`### 설문 N` 헤더 전혀 없는 본문 → []."""
        md = "## 원본 (10점)\n\n### 사실관계\n본문\n\n### 결론\n결론\n"
        self.assertEqual(cases_mod.parse_md_subqs(md), [])


class TestParseMdSubqsGaNa(unittest.TestCase):
    """`parse_md_subqs` — 가/나 별도 카드 (패턴 C 대응)."""

    def test_parse_md_subqs_ga_na_minbeop_모고02_01(self):
        """민법 모고02_01 — 설문 1 가 + 설문 1 나 독립 카드 2개."""
        md = _load("예비_민법/2026_minbeop_yebi_모고02_01.md")
        cards = cases_mod.parse_md_subqs(md)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["key"], "설문 1 가")
        self.assertEqual(cards[1]["key"], "설문 1 나")
        self.assertEqual(cards[0]["score_max"], 12)
        self.assertEqual(cards[1]["score_max"], 10)

    def test_parse_md_subqs_ga_na_minbeop_모고02_02(self):
        """민법 모고02_02 — 설문 2 가 + 설문 2 나 독립 카드 2개."""
        md = _load("예비_민법/2026_minbeop_yebi_모고02_02.md")
        cards = cases_mod.parse_md_subqs(md)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["key"], "설문 2 가")
        self.assertEqual(cards[1]["key"], "설문 2 나")

    def test_parse_md_subqs_ga_na_body_answer_paired(self):
        """가/나 카드 — body ↔ answer 짝 매칭 (key 로 인덱싱)."""
        md = _load("예비_민법/2026_minbeop_yebi_모고02_01.md")
        cards = cases_mod.parse_md_subqs(md)
        # 가 답안에 "I. 결론" 포함, 나 답안에 "병은 을의 청구를 거절" 포함
        ga = next(c for c in cards if c["key"] == "설문 1 가")
        na = next(c for c in cards if c["key"] == "설문 1 나")
        self.assertIn("I. 결론", ga["answer"])
        self.assertIn("적법하게 해제", ga["answer"])
        self.assertIn("I. 결론", na["answer"])
        self.assertIn("을의 청구", na["answer"])


# ─── 4. parse_md_toc / parse_md_mnemonic ────────────────────────────


class TestParseMdToc(unittest.TestCase):
    """`parse_md_toc` — `### 목차` 본문 추출."""

    def test_parse_md_toc_multi(self):
        """다중 설문 — 목차 본문에 설문 1 / 설문 2 라벨 포함."""
        md = _load("예비_민법/2026_minbeop_yebi_모고01_01.md")
        toc = cases_mod.parse_md_toc(md)
        self.assertIn("설문 1", toc)
        self.assertIn("설문 2", toc)
        self.assertIn("시효소멸", toc)

    def test_parse_md_toc_ga_na(self):
        """가/나 — 목차에 `설문 1 가` / `설문 1 나` 포함."""
        md = _load("예비_민법/2026_minbeop_yebi_모고02_01.md")
        toc = cases_mod.parse_md_toc(md)
        self.assertIn("설문 1 가", toc)
        self.assertIn("설문 1 나", toc)

    def test_parse_md_toc_fallback_returns_body(self):
        """단일 설문 — `### 목차` 본문 (설문 N prefix 없어도 OK)."""
        md = _load("예비_민법/2026_minbeop_yebi_모고01_02.md")
        toc = cases_mod.parse_md_toc(md)
        self.assertTrue(toc.strip(), "단일 설문 .md 에도 목차는 존재")

    def test_parse_md_toc_no_header_returns_empty(self):
        """`### 목차` 헤더 없으면 빈 문자열."""
        self.assertEqual(cases_mod.parse_md_toc("## 본문\n다른 내용"), "")


class TestParseMdMnemonic(unittest.TestCase):
    """`parse_md_mnemonic` — 전체 .md ``[blank2]X[/blank2]`` 콘텐츠만 추출.

    2026-05-17 lawear-a519 Step 25 사용자 피드백:
        - 기존 Lv.4 번호 목록 추출 = **정답 본문 노출** → 폐기.
        - 새 정책: ``[blank2]`` 태그 글자만 (정답 X).
        - 두문자 없으면 (= blank2 0건) 빈 list.

    풀 커버리지는 ``test_step24_blank2.py`` 참조. 본 클래스는 회귀 sanity 만.
    """

    def test_parse_md_mnemonic_blank2_only(self):
        """blank2 태그 → 콘텐츠 추출."""
        md = "본문에 [blank2]무[/blank2]와 [blank2]기[/blank2] 단서."
        self.assertEqual(cases_mod.parse_md_mnemonic(md), ["무", "기"])

    def test_parse_md_mnemonic_no_blank2_returns_empty(self):
        """blank2 없으면 빈 list (Lv.4 번호 목록 X)."""
        self.assertEqual(cases_mod.parse_md_mnemonic("## 원본\n본문"), [])

    def test_parse_md_mnemonic_lv4_number_list_ignored(self):
        """Lv.4 번호 목록만 있고 blank2 없으면 빈 list (기존 동작 폐기)."""
        md = "## Lv.4 암기노트\n\n1. 결론.\n2. 둘째.\n"
        self.assertEqual(cases_mod.parse_md_mnemonic(md), [])


if __name__ == "__main__":
    unittest.main()
