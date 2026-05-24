"""17896 민사서류 작성연습 트랙 — cloze 3종 모드 정의 (1라운드 MVP).

근거: docs/민사서류_작성연습_설계/design_mvp1.md v2 결정 6.

3 modes (1라운드, 청구취지 cloze):
  1. cloze_simple   — 연결어 4종 12문 (자체 생성, 표준 정형)
  2. cloze_skeleton — 8대분류 골격 8문 (정리본 PDF Ⅰ~Ⅷ × 대표 1문)
  3. cloze_full     — 쪽지 문답 38문 전 빈칸 (bold span [blank] 토큰화)

cloze_shuffle (정리본 60패턴 + 숫자/날짜/이율 셔플)는 2라운드 이월 (강사 QA 권고 B).
청구원인 작성 + idea4 4단계 1~3은 2라운드 이월 (placeholder UI 만).

사용:
    from minsaseoryu_modes import MODES, get_mode, get_modes_for_subject
    meta = get_mode("cloze_simple")
    civil_doc_modes = get_modes_for_subject("civil_doc")  # 3개 dict list
"""
from __future__ import annotations

from typing import Any


# ============================================================
# 3 modes 메타 (1라운드 MVP)
# ============================================================

# 6단계 힌트 매핑 (design v2 결정 7) — 강사+부장판사 합의 권고 C 반영.
#   2.5 신설 — "사례 키워드 매칭" (연대보증/공동불법행위/분할채무 ↔ 연결어 매핑)
#   hint 5는 1택 한정 (연결어 OR 기산일) — 정답 누설 방지
HINT_STEPS_6 = [1, 2, 2.5, 3, 4, 5]
HINT_LABELS_6 = {
    1: "청구 유형",
    2: "청구취지 골격",
    2.5: "사례 키워드 매칭",
    3: "연결어 후보 / 기간·이율 룰",
    4: "기산일·이율 (약정<5% 시 법정이율 5%)",
    5: "key element 1개 (연결어 OR 기산일 1택)",
}

# 힌트 단계별 감점율 (budeunglaw 패턴 차용 — 1단계 -5%, ...).
# 2.5단계는 신설 — 0.075 (중간값).
HINT_PENALTY = {
    1: 0.05,    # -5%
    2: 0.10,    # -10%
    2.5: 0.15,  # -15% (사례 키워드 매칭 — 도움 큼)
    3: 0.20,    # -20%
    4: 0.30,    # -30%
    5: 0.50,    # -50% (key element 1개 노출)
}

# bold span 가중치 (design v2 결정 5)
#   - bold = 채점키워드 = 1.5배
#   - non-bold = 일반 빈칸 = 1.0배
BOLD_WEIGHT_DEFAULT = 1.5
NORMAL_WEIGHT_DEFAULT = 1.0


MODES: dict[str, dict[str, Any]] = {
    "cloze_simple": {
        "name": "연결어 4종 cloze (12문)",
        "name_en": "Cloze Simple (connector × 12)",
        "difficulty": "easy",
        "question_count": 12,
        "data_file_pattern": "2026_사용자_민사서류/cloze/cloze_simple/*.md",
        "blank_policy": "connector_only",  # 연결어 위치 1개만
        "hint_steps": HINT_STEPS_6,
        "hint_labels": HINT_LABELS_6,
        "hint_penalty": HINT_PENALTY,
        "weights": {
            "bold": BOLD_WEIGHT_DEFAULT,
            "normal": NORMAL_WEIGHT_DEFAULT,
        },
        "description": (
            "연결어 4종(연대하여/공동하여/각/연대보증인과 연대하여) 반복 학습. "
            "초반 성취감 확보 + spaced repetition."
        ),
        "round": 1,
    },
    "cloze_skeleton": {
        "name": "8대분류 골격 cloze (8문)",
        "name_en": "Cloze Skeleton (8 categories)",
        "difficulty": "medium",
        "question_count": 8,
        "data_file_pattern": "2026_사용자_민사서류/cloze/cloze_skeleton/*.md",
        "blank_policy": "connector_and_date_only",  # 연결어+기산일+종결어
        "hint_steps": HINT_STEPS_6,
        "hint_labels": HINT_LABELS_6,
        "hint_penalty": HINT_PENALTY,
        "weights": {
            "bold": BOLD_WEIGHT_DEFAULT,
            "normal": NORMAL_WEIGHT_DEFAULT,
        },
        "description": (
            "정리본 청구취지 PDF 8대분류(Ⅰ금전~Ⅷ기타) 대표 1문씩. "
            "골격 학습용 — 빈칸은 연결어+기산일 위치만 2~3개."
        ),
        "round": 1,
    },
    "cloze_full": {
        "name": "쪽지 전 빈칸 cloze (38문)",
        "name_en": "Cloze Full (38 questions)",
        "difficulty": "hard",
        "question_count": 38,  # 쪽지 문답01~03 합산 (1라운드는 우선 10문)
        "data_file_pattern": "2026_사용자_민사서류/cloze/cloze_full/*.md",
        "blank_policy": "all_bold",  # 답안 PDF bold span 전부 [blank]
        "hint_steps": HINT_STEPS_6,
        "hint_labels": HINT_LABELS_6,
        "hint_penalty": HINT_PENALTY,
        "weights": {
            "bold": BOLD_WEIGHT_DEFAULT,
            "normal": NORMAL_WEIGHT_DEFAULT,
        },
        "description": (
            "쪽지_청구취지_답01~03 PDF의 bold span 전부 [blank] 토큰화. "
            "어려움 — 정형 어휘 + 기산일 + 별지목록 마무리 등 종합."
        ),
        "round": 1,
    },
    # 2라운드 예고 (UI 안내용 — get_modes_for_subject 에서 제외)
    "cloze_shuffle": {
        "name": "정리본 셔플 cloze (60패턴, 2라운드)",
        "name_en": "Cloze Shuffle (60 patterns, round 2)",
        "difficulty": "advanced",
        "question_count": 60,
        "data_file_pattern": "2026_사용자_민사서류/cloze_2round/cloze_shuffle/*.md",
        "blank_policy": "shuffled_numerals",  # 금액/날짜/이율 셔플
        "hint_steps": HINT_STEPS_6,
        "hint_labels": HINT_LABELS_6,
        "hint_penalty": HINT_PENALTY,
        "weights": {
            "bold": BOLD_WEIGHT_DEFAULT,
            "normal": NORMAL_WEIGHT_DEFAULT,
        },
        "description": "정리본 8대분류 60패턴 + 숫자/날짜/이율 셔플 (강사 QA 권고 B로 2라운드 이월).",
        "round": 2,
    },
}

# 1라운드 active mode 목록 (UI 표시 + 선택)
ROUND1_MODES = ["cloze_simple", "cloze_skeleton", "cloze_full"]

MODE_ORDER = ["cloze_simple", "cloze_skeleton", "cloze_full", "cloze_shuffle"]

MODE_LABELS = {
    "cloze_simple": "연결어 cloze",
    "cloze_skeleton": "8대분류 골격",
    "cloze_full": "쪽지 전 빈칸",
    "cloze_shuffle": "셔플 (2라운드)",
}


def get_mode(name: str) -> dict[str, Any]:
    """모드 메타 반환 (없으면 ValueError).

    Args:
        name: cloze_simple / cloze_skeleton / cloze_full / cloze_shuffle

    Returns:
        MODES[name] dict.
    """
    if name not in MODES:
        raise ValueError(f"Unknown civil_doc mode: {name}. Valid: {list(MODES.keys())}")
    return dict(MODES[name])


def get_modes_for_subject(subject_type: str) -> list[dict[str, Any]]:
    """과목 타입별 mode list 반환.

    Args:
        subject_type: 'civil_doc' (민사서류) — 1라운드 3종 active.

    Returns:
        1라운드 active mode list (cloze_simple/skeleton/full).
        다른 subject_type 은 빈 list (확장 여지).
    """
    if subject_type == "civil_doc":
        return [dict(MODES[m]) for m in ROUND1_MODES]
    return []


def get_active_modes() -> list[str]:
    """1라운드 active mode 키 list (cloze_shuffle 제외)."""
    return list(ROUND1_MODES)


def is_round1_mode(name: str) -> bool:
    """1라운드 mode 여부 (UI 활성화 조건)."""
    return name in ROUND1_MODES


def get_hint_penalty(steps_used: list) -> float:
    """힌트 사용 단계별 감점율 합산 → 0.0 ~ 1.0 반환.

    Args:
        steps_used: ``[1, 2, 2.5, ...]`` 사용된 힌트 단계 list (중복 허용).

    Returns:
        총 감점율 (0.0 = 감점 없음, 1.0 = 100% 감점).
        중복 단계는 1회만 카운트 (set 변환).
    """
    if not isinstance(steps_used, list):
        return 0.0
    penalty = 0.0
    seen: set[float] = set()
    for s in steps_used:
        try:
            sf = float(s)
        except (TypeError, ValueError):
            continue
        if sf in seen:
            continue
        seen.add(sf)
        penalty += HINT_PENALTY.get(sf, 0.0)
    return min(1.0, penalty)


if __name__ == "__main__":
    # 자가 테스트
    print("=== minsaseoryu 1라운드 mode ===")
    for m in get_active_modes():
        meta = get_mode(m)
        print(f"  {m:18s} | {meta['question_count']:3d}문 | {meta['difficulty']:8s} | {meta['blank_policy']}")
    print()
    print("=== hint penalty 누적 ===")
    for steps in [[], [1], [1, 2], [1, 2, 2.5], [1, 2, 2.5, 3], [1, 2, 2.5, 3, 4, 5]]:
        print(f"  steps={steps} → penalty={get_hint_penalty(steps):.2%}")
