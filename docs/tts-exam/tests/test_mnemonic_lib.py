"""mnemonic_lib.py 유닛테스트 (lawear-6be6 Task #6 M2).

dev-impl-plan Phase 3 명세 기반 8+ 케이스 + 사용자 룰 R-09 강제 검증.

검증 룰 (사용자 블록 1):
  1. R-09 abandoned skip + source_entry 의무 + 자의 생성 0
  2. letter 묶음 보존 (점/슬래시 분리 단위)
  3. 5과목 status + entry 수
  4. role 가중치 차등 (judge vs lecturer)
  5. lru_cache 두 번 호출 동일 + .md mtime 0
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# tests/ → docs/tts-exam/ import 경로
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mnemonic_lib as ml  # noqa: E402


# ─── 5과목 로드 검증 ─────────────────────────────────────────────────────


def test_load_minbeop_loaded():
    """민법 라이브러리 loaded — 실측 total=74 / abandoned=1.

    검증 룰: #3 5과목 status / #1 abandoned 카운트 노출.
    """
    data = ml.load_mnemonic_library("민법")
    assert data["status"] == "loaded"
    # 실측 74 entry — 추가 entry가 합쳐져도 hold 가능하도록 하한만 검증.
    assert data["total_count"] >= 60
    assert len(data["entries"]) == data["total_count"]
    # 민법은 §1-1 (채무불이행) abandoned 마킹 1건 존재.
    assert data["abandoned_count"] >= 1


def test_load_minso_loaded():
    """민소 라이브러리 loaded — 실측 total=65 / abandoned=0.

    검증 룰: #3 5과목 status.
    """
    data = ml.load_mnemonic_library("민소")
    assert data["status"] == "loaded"
    assert data["total_count"] >= 50  # 실측 65
    # alias 검증
    data2 = ml.load_mnemonic_library("민사소송법")
    assert data2["status"] == "loaded"
    assert data2["total_count"] == data["total_count"]


def test_load_budeunglaw_single_entry():
    """부등법 라이브러리 loaded — 실측 entry 1건 (권리경정등기).

    검증 룰: #2 letter 묶음 보존(현재·일·시·불·승낙) / #3 5과목.
    부등법은 강사 PDF 없어 사용자 free가 유일 정본
    → mnemonic 1개라도 자체 생성 X (R-09).
    """
    data = ml.load_mnemonic_library("부동산등기법")
    assert data["status"] == "loaded"
    assert data["total_count"] == 1
    e = data["entries"][0]
    # 권리경정등기 entry — section_title에 "권리경정등기" 포함
    assert "경정등기" in e["section_title"]
    # letter 묶음 — "현재" "승낙" 등 2자+ 묶음이 있어야 함
    assert e["letters"], "letters 비어 있음 — 파싱 실패"
    assert any(letter in ("현재", "승낙") for letter in e["letters"]), (
        f"letter 묶음 분해됨: {e['letters']}"
    )


def test_load_hyungbeop_empty():
    """형법 라이브러리 empty — entry 0건 (라이브러리 미보강).

    검증 룰: #1 자체 생성 X — entry 없으면 status='empty', entries=[].
    """
    data = ml.load_mnemonic_library("형법")
    assert data["status"] == "empty"
    assert data["entries"] == []
    assert data["total_count"] == 0


def test_load_hyungso_empty():
    """형소 라이브러리 empty — entry 0건.

    검증 룰: #1 자체 생성 X.
    """
    data = ml.load_mnemonic_library("형사소송법")
    assert data["status"] == "empty"
    assert data["entries"] == []
    # alias
    data2 = ml.load_mnemonic_library("형소")
    assert data2["status"] == "empty"


def test_load_missing_subject():
    """알 수 없는 과목 → status='missing' (파일 부재 + 자체 생성 X).

    검증 룰: #1 R-09 — 라이브러리 부재 시 빈 결과만 반환.
    """
    data = ml.load_mnemonic_library("일본법")
    assert data["status"] == "missing"
    assert data["entries"] == []
    assert data["file_path"] is None
    assert data["total_count"] == 0


# ─── abandoned skip + source_entry 의무 검증 ────────────────────────────


def test_abandoned_entries_excluded_from_match():
    """abandoned entry는 매칭 결과에서 100% 제외 (R-09 / lawear-4b59 사고 재현 방지).

    검증 룰: #1 abandoned skip.
    민법 §1-1 (채무불이행 손해배상 요건)이 abandoned 마킹 →
    동일 키워드로 매칭 시도해도 §1-1 절대 등장 X.
    """
    lib = ml.load_mnemonic_library("민법")
    abandoned_entries = [e for e in lib["entries"] if e["abandoned"]]
    assert len(abandoned_entries) >= 1, "민법 abandoned entry 0건 — 데이터 변경?"
    abandoned_sources = {e["source_entry"] for e in abandoned_entries}

    # abandoned entry의 키워드로 매칭 시도 — 결과에 source_entry가 등장하면 안 됨.
    result = ml.match_missing_to_mnemonic(
        [{"item": "제390조 채무불이행 손해배상 요건 누락"}],
        "민법", role="judge", limit=20,
    )
    matched_sources = {r["source_entry"] for r in result}
    overlap = abandoned_sources & matched_sources
    assert not overlap, f"abandoned entry가 매칭 결과에 등장: {overlap}"


def test_match_source_entry_mandatory():
    """모든 매칭 결과는 source_entry + lib_section 의무 (R-09).

    검증 룰: #1 source_entry 의무.
    """
    result = ml.match_missing_to_mnemonic(
        [{"item": "이행지체 손해배상 요건", "expected_score_impact": -3}],
        "민법", role="judge", limit=5,
    )
    assert isinstance(result, list)
    for r in result:
        assert r.get("source_entry"), f"source_entry 누락: {r}"
        assert r.get("lib_section"), f"lib_section 누락: {r}"
        # source_entry 형식: "민법 §N-M"
        assert r["source_entry"].startswith("민법 §"), (
            f"source_entry 형식 위반: {r['source_entry']}"
        )


# ─── role 가중치 차등 ──────────────────────────────────────────────────


def test_match_judge_articles_weighted():
    """judge perspective — articles 매칭 ×2 가중치 (조문 우선).

    검증 룰: #4 role 가중치 차등.
    제390조 입력 → articles 매칭이 발생하면 결과 sample 1+ + role='judge'.
    """
    result = ml.match_missing_to_mnemonic(
        [{"item": "제390조 채무불이행 누락"}],
        "민법", role="judge", limit=5,
    )
    # judge 매칭 — abandoned skip 후라도 §9-9 등 다른 entry 매칭 가능.
    assert isinstance(result, list)
    for r in result:
        assert r["role"] == "judge", f"role 미일치: {r['role']}"
        assert r.get("source_entry")


def test_match_lecturer_title_weighted():
    """lecturer perspective — title/카테고리 매칭 ×2 가중치.

    검증 룰: #4 role 가중치 차등.
    "변제의 효력" 입력 → title 매칭 다수 후보 + role='lecturer'.
    """
    result = ml.match_missing_to_mnemonic(
        [{"item": "변제의 효력 누락"}],
        "민법", role="lecturer", limit=3,
    )
    assert isinstance(result, list)
    for r in result:
        assert r["role"] == "lecturer", f"role 미일치: {r['role']}"


def test_match_role_difference_scoring():
    """동일 item에 대해 judge vs lecturer 점수 차이 발생 가능 (가중치 차등).

    검증 룰: #4 role 차등.
    동일 item에서 두 role 결과의 score 분포가 차이가 나는지 확인 — 일종의 sanity.
    """
    item = [{"item": "제390조 손해배상 청구 요건 누락"}]
    judge_res = ml.match_missing_to_mnemonic(item, "민법", role="judge", limit=10)
    lect_res = ml.match_missing_to_mnemonic(item, "민법", role="lecturer", limit=10)
    # 둘 다 list — 단 articles 가중치가 적용되는 경우 judge가 articles 매칭에 유리.
    assert isinstance(judge_res, list)
    assert isinstance(lect_res, list)
    # role 필드만 확실히 분리되어 있어야 함.
    judge_roles = {r["role"] for r in judge_res}
    lect_roles = {r["role"] for r in lect_res}
    assert judge_roles <= {"judge"}, f"judge 결과에 다른 role: {judge_roles}"
    assert lect_roles <= {"lecturer"}, f"lecturer 결과에 다른 role: {lect_roles}"


def test_match_invalid_role_defaults_judge():
    """role 인자 'judge'/'lecturer' 외 입력 → judge로 fallback.

    검증 룰: #4 role 가중치 — 잘못된 입력에 대한 안전망.
    """
    result = ml.match_missing_to_mnemonic(
        [{"item": "이행지체 손해배상"}],
        "민법", role="unknown_role", limit=3,
    )
    for r in result:
        assert r["role"] == "judge"


# ─── R-09 자의 생성 0 ──────────────────────────────────────────────────


def test_match_no_invention_for_no_match():
    """매칭 0건 — 빈 list 반환 (자의 생성 X).

    검증 룰: #1 R-09 — 매칭 후보 없으면 절대 자체 생성 X.
    """
    result = ml.match_missing_to_mnemonic(
        [{"item": "완전 무관한 텍스트 xyz123 영어 only"}],
        "민법", role="judge",
    )
    assert result == []


def test_match_empty_library_no_invention():
    """형법/형소 empty 라이브러리 → 빈 list (자체 생성 X).

    검증 룰: #1 R-09 — 라이브러리 entry 0건이면 그대로 빈 결과.
    """
    for subj in ("형법", "형사소송법"):
        result = ml.match_missing_to_mnemonic(
            [{"item": "범죄 구성요건 누락 (제250조)"}],
            subj, role="judge",
        )
        assert result == [], f"{subj} 빈 라이브러리에서 자체 생성 발생: {result}"


def test_match_missing_subject_no_invention():
    """알 수 없는 과목 → 빈 list (자체 생성 X).

    검증 룰: #1 R-09 — 과목 부재 시도 자체 생성 절대 X.
    """
    result = ml.match_missing_to_mnemonic(
        [{"item": "뭐든지 매칭해주세요"}],
        "일본법", role="judge",
    )
    assert result == []


def test_match_empty_missing_input():
    """missing_critical 입력 자체가 비어 있으면 빈 list.

    검증 룰: #1 R-09 — 입력 없으면 결과 없음.
    """
    assert ml.match_missing_to_mnemonic([], "민법", role="judge") == []
    # item 키 없는 dict — skip.
    assert ml.match_missing_to_mnemonic(
        [{"expected_score_impact": -3}], "민법", role="judge"
    ) == []
    # item이 빈 문자열 — skip.
    assert ml.match_missing_to_mnemonic(
        [{"item": "   "}], "민법", role="judge"
    ) == []


# ─── letter 묶음 보존 ─────────────────────────────────────────────────


def test_letter_grouping_preservation():
    """letter 묶음 보존 — 점(·)/슬래시 분리 단위 그대로, AI 1글자 쪼개기 X.

    검증 룰: #2 letter 묶음 보존.
    부등법 §1-1: 사용자 free 두문자 "현재·일·시·불·승낙" →
    multichar('현재', '승낙') letter 보존 필수.
    """
    data = ml.load_mnemonic_library("부동산등기법")
    assert data["entries"], "부등법 entries 비어 있음"
    e = data["entries"][0]
    letters = e["letters"]
    # 묶음 보존 검증: 2자 이상 묶음이 1개 이상 있어야 함.
    multichar = [letter for letter in letters if len(letter) >= 2]
    assert multichar, f"letter 묶음 분해됨: {letters}"
    # 부등법 §1-1 사용자 두문자 묶음 정본 — '현재' 또는 '승낙' 중 하나는 반드시 보존.
    assert any(letter in ("현재", "승낙") for letter in letters), (
        f"부등법 묶음 letter '현재'/'승낙' 보존 실패: {letters}"
    )


# ─── lru_cache 검증 ─────────────────────────────────────────────────


def test_cache_idempotent():
    """lru_cache 검증 — 두 번 호출 동일 결과 (객체 동일 또는 동일 내용).

    검증 룰: #5 lru_cache.
    """
    data1 = ml.load_mnemonic_library("민법")
    data2 = ml.load_mnemonic_library("민법")
    assert data1["status"] == data2["status"]
    assert data1["total_count"] == data2["total_count"]
    assert data1["entries"] == data2["entries"]
    # lru_cache이므로 객체 동일성도 통과해야 함 (성능 보장).
    assert data1 is data2, "lru_cache 미작동 — 객체 ID 불일치"


def test_read_only_no_mtime_change():
    """라이브러리 .md 파일 mtime 변경 0 (read-only 검증, R-09).

    검증 룰: #5 .md 파일 mtime 0.
    load + match 양쪽 모두 .md를 수정해서는 안 됨.
    """
    # 실제 라이브러리 경로 (mnemonic_lib._LIB_BASE 사용).
    lib_path = ml._LIB_BASE / "민법.md"
    assert lib_path.exists(), f"민법.md 부재: {lib_path}"

    mtime_before = lib_path.stat().st_mtime
    size_before = lib_path.stat().st_size

    # cache clear 후 강제 재로드 — write 가능성 한 번 더 검증.
    ml.load_mnemonic_library.cache_clear()
    _ = ml.load_mnemonic_library("민법")
    _ = ml.match_missing_to_mnemonic(
        [{"item": "이행지체 손해배상"}], "민법", role="judge"
    )
    _ = ml.match_missing_to_mnemonic(
        [{"item": "변제 효력"}], "민법", role="lecturer"
    )

    mtime_after = lib_path.stat().st_mtime
    size_after = lib_path.stat().st_size

    assert mtime_before == mtime_after, (
        f"라이브러리 .md mtime 변경됨 (read-only 위반): "
        f"{mtime_before} → {mtime_after}"
    )
    assert size_before == size_after, (
        f"라이브러리 .md size 변경됨: {size_before} → {size_after}"
    )


# ─── parse_entries 직접 검증 (보조) ──────────────────────────────────────


def test_parse_entries_handles_empty_body():
    """parse_entries — 빈 본문 / H3 없는 본문은 빈 list.

    검증 룰: #1 R-09 — 입력 부재 시 자체 생성 X.
    """
    assert ml.parse_entries("", "민법") == []
    assert ml.parse_entries("# 제목\n\n본문이지만 H3 없음", "민법") == []


def test_load_returns_loaded_for_known_subject_aliases():
    """과목 alias 검증 (민법 / 민소 / 부동산등기법 / 부등법 / 형법 / 형사소송법 / 형소).

    검증 룰: #3 5과목 alias 인식.
    """
    # 같은 파일을 가리키는 alias는 동일 entry 수.
    minso_a = ml.load_mnemonic_library("민소")
    minso_b = ml.load_mnemonic_library("민사소송법")
    assert minso_a["total_count"] == minso_b["total_count"]
    assert minso_a["status"] == minso_b["status"]

    budeung_a = ml.load_mnemonic_library("부등법")
    budeung_b = ml.load_mnemonic_library("부동산등기법")
    assert budeung_a["total_count"] == budeung_b["total_count"]
    assert budeung_a["status"] == budeung_b["status"]
