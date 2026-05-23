"""부등법(부동산등기법) 5모드 채점 시스템 — weights_version=7

5개 채점 모드:
  1. judge          — 부장판사 안 (논리/근거 정확성 중심, sources 4종 통합)
  2. lecturer       — 강사 김기찬 안 (만능목차 골격 + 첨부정보 8칸 + 선례·예규 별도)
  3. hybrid         — 판사+강사 합의 (메인 종합, 위 두 안 best-of)
  4. main_opus      — 메인 Opus 독립 안 (학습자 관점 균형)
  5. strict_outline — 만능목차 엄격 준수 (outline 압도적 비중)

사용:
    from budeunglaw_modes import MODES, get_mode_weights, get_mode_prompt
    weights = get_mode_weights("hybrid")
    prompt = get_mode_prompt("hybrid")

DB:
  - weights_version='v7_budeunglaw_{mode}' (예: 'v7_budeunglaw_hybrid')
  - attempts.grading_mode 컬럼 (migrations/008 신설)
  - 한 답안 → 5 attempt (각 mode별) 또는 한 attempt에 5 mode 결과 JSON

근거: docs/lawear-0d65_budeunglaw_multimode/plan.md
"""
from __future__ import annotations

# ============================================================
# 부등법 채점 키 (11개) — DB CHECK 호환을 위해 기존 9키 superset
# ============================================================
# 기존 9키 (민법/민소 v6): mnem, color, under, outline, sem, rich, miss, articles, case_apply
# 신설 5키 (부등법 v7): attached, procedure, effect, richness, precedent, missing
#   - missing은 miss의 부등법 한정 alias (음수 차감 전용)
#   - richness는 rich의 부등법 한정 alias (조문 깊이 중심)
#
# 모든 mode가 같은 키 집합 사용. 가중치만 다름. max=0 키는 채점 skip.

BUDEUNGLAW_KEYS = [
    # outline 계열
    "outline",          # 만능목차 4분류 골격 일치 (기본/첨부/등기절차/부수)
    # 출처 계열
    "articles",         # 조문 + 규칙 인용 (法+規)
    "precedent",        # 선례 + 예규 인용 ([선례]+[예규])
    "sources_unified",  # 4종 통합 (judge 모드 전용, 다른 모드는 0)
    # 부등법 특유
    "attached",         # 첨부정보 8칸 카탈로그
    "procedure",        # 개시 → 신청 → 실행 절차 흐름
    "effect",           # 효력/효과 (직권말소/각하/이의) 정확성
    "case_apply",       # 사안의 적용
    # 풍부함/누락
    "richness",         # 풍부함 (원본 대비 분량 + 깊이)
    "sem",              # 의미 일치 (judge 모드 전용)
    "missing",          # 핵심 누락 차감 (음수 buffer, max=0)
    # 시각 보조 (judge 모드만 유지, 다른 모드는 0)
    "color",
    "under",
    "mnem",
]

# ============================================================
# 5개 모드별 가중치 — 합계는 모드별로 다를 수 있음 (env normalize)
# ============================================================

WEIGHTS = {
    # 모드 1: 부장판사 (sources 4종 통합, 시각 보조 유지)
    "judge": {
        "outline": 16,
        "articles": 0,           # sources_unified에 통합
        "precedent": 0,          # sources_unified에 통합
        "sources_unified": 15,   # 조문+규칙+선례+예규 4종 통합
        "attached": 0,           # miss에 통합
        "procedure": 10,
        "effect": 0,             # 별도 없음
        "case_apply": 10,
        "richness": 8,
        "sem": 13,               # judge만 sem 사용
        "missing": 13,           # judge는 양수 가중치 (음수 가능)
        "color": 6,
        "under": 4,
        "mnem": 5,
    },
    # 모드 2: 강사 (9~11키 + missing 음수, 첨부/효력 신설)
    "lecturer": {
        "outline": 17,
        "articles": 15,
        "precedent": 8,
        "sources_unified": 0,
        "attached": 13,
        "procedure": 12,
        "effect": 10,
        "case_apply": 11,
        "richness": 9,
        "sem": 0,
        "missing": -5,           # 차감 전용
        "color": 0,
        "under": 0,
        "mnem": 0,
    },
    # 모드 3: 하이브리드 (메인 종합, 강사 안 base + 판사 보강)
    "hybrid": {
        "outline": 17,
        "articles": 15,
        "precedent": 8,
        "sources_unified": 0,
        "attached": 13,
        "procedure": 12,
        "effect": 10,
        "case_apply": 11,
        "richness": 9,
        "sem": 0,
        "missing": -5,
        "color": 0,
        "under": 0,
        "mnem": 0,
    },
    # 모드 4: 메인 Opus 독립 안 (학습자 관점 균형 — outline 약간 ↓, case_apply ↑)
    "main_opus": {
        "outline": 14,
        "articles": 15,
        "precedent": 10,         # 선례·예규 학습 깊이 중시 ↑
        "sources_unified": 0,
        "attached": 12,
        "procedure": 11,
        "effect": 11,
        "case_apply": 13,        # 사안 적용 학습 효과 ↑
        "richness": 9,
        "sem": 0,
        "missing": -5,
        "color": 0,
        "under": 0,
        "mnem": 5,               # 만능목차 부수절차 "주객상방기범효업" 두문자
    },
    # 모드 5: 만능목차 엄격 준수 (outline 압도적, 골격 누락 곧 사망)
    "strict_outline": {
        "outline": 40,           # 압도적
        "articles": 20,
        "precedent": 3,
        "sources_unified": 0,
        "attached": 15,          # 첨부정보 8칸 누락도 골격 누락
        "procedure": 12,         # 절차 흐름도 골격 일부
        "effect": 5,
        "case_apply": 3,
        "richness": 2,
        "sem": 0,
        "missing": -10,          # 차감 강화
        "color": 0,
        "under": 0,
        "mnem": 0,
    },
}

MODE_LABELS = {
    "judge": "부장판사",
    "lecturer": "강사 (김기찬)",
    "hybrid": "하이브리드 합의",
    "main_opus": "메인 Opus 독립",
    "strict_outline": "만능목차 엄격",
}

MODE_ORDER = ["judge", "lecturer", "hybrid", "main_opus", "strict_outline"]


def get_mode_weights(mode: str) -> dict:
    """모드별 가중치 dict 반환."""
    if mode not in WEIGHTS:
        raise ValueError(f"Unknown mode: {mode}. Valid: {list(WEIGHTS.keys())}")
    return dict(WEIGHTS[mode])


def get_all_modes() -> list[str]:
    """5개 모드 리스트 (정렬 순서)."""
    return list(MODE_ORDER)


# ============================================================
# 모드별 SYSTEM_PROMPT 분기 (각 모드의 관점 강조)
# ============================================================

# 공통 부등법 base prompt — 모든 모드에 prepend
BASE_PROMPT_BUDEUNGLAW = """[부등법(부동산등기법) 채점 컨텍스트]
- 과목: 부동산등기법 (절차법 — 정형성 강함, 판례보다 조문/규칙/선례/예규 인용 비중 큼)
- 만능목차 4분류 (강사 김기찬 1순환 자료):
  1. 기본 목차: 서설(I) → 요건(II) → 적용범위(III) → 효과(IV)
  2. 첨부서면 목차: 서설(의의·요건·범위·효과·관련문제) → 제공여부 → 제공절차 → 심사
  3. 등기절차 목차: 서설 → 개시(공동/단독/촉탁/직권) → 신청절차(신청인·신청정보·첨부정보) → 실행절차(접수·조사·등기형식·통지) → 처분이의
  4. 부수절차 목차: 서설 → 절차(주·객·상·방·시·범·효·업무처리)
- 답안의 핵심 출처 4종: (1)조문 (2)규칙 (3)선례 (4)예규 — 모두 [case]태그로 인용됨
- 첨부정보 8칸 카탈로그: 등기필정보·인감증명·주소증명·번호증명·세금영수증·대장·지적도·기타
- 사안의 적용: 사례형 문제는 인물(甲·乙·X·Y)·일자·권리관계를 답안 결론 도출에 직접 적용

채점 기준 키 의미 (부등법 한정):
  - outline: 만능목차 4분류 골격 일치 (어느 tier 채택, 빠진 단계 없음)
  - articles: 조문 + 규칙 인용 매칭 (法+規, 0개=max 20% 컷)
  - precedent: 선례 + 예규 인용 매칭 ([선례][예규], 학습 깊이 증거)
  - attached: 첨부정보 8칸 중 사안 요구 N칸 매칭 (첨부 사안 한정)
  - procedure: 개시→신청→실행 단계 명시 (등기절차 사안 한정)
  - effect: 직권말소 범위/각하사유/이의신청 결론 정확성
  - case_apply: 사안 인물/사실 → 답안 결론 도출 (사례형 한정)
  - richness: 원본 대비 분량 + 조문 인용 깊이
  - missing: 핵심 누락 차감 (음수 가능, max=0)
  - sources_unified: (judge 모드 전용) 4종 출처 통합 매칭
  - sem/color/under/mnem: (judge 모드 전용 또는 main_opus 일부) 의미·시각 보조

사례형/약술형 분기:
  - 사례형 (사안 인물 있음): procedure/case_apply/effect/attached 모두 채점
  - 약술형 (단순 정의·설명): procedure/case_apply는 max=0 또는 비례 축소

R-09 (절대): 답안에 명시되지 않은 논점을 "의도했을 것 같다"고 가점 X. 적힌 그대로만 평가.
"""

# 모드별 추가 관점 prompt
MODE_PROMPTS = {
    "judge": """[모드: 부장판사 관점]
- 논리/근거 정확성 중심으로 채점
- sources_unified로 4종 출처를 통합 평가 (조문+규칙+선례+예규 한 묶음)
- sem(의미 매칭)을 살려 핵심 법리 의미 검증
- 시각 강조(color/under/mnem) 평문 인정 룰 그대로 (낮은 가중치)
- miss를 양수 가중치로 사용 (누락 식별 → 음수 score 가능)
""",
    "lecturer": """[모드: 강사 김기찬 관점]
- 만능목차 골격 일치 + 첨부정보 8칸 + 선례·예규 별도 평가 강조
- outline_skeleton 17점 (만점 비중 최대) — 골격 누락이 곧 점수 누락
- 시각 강조(color/under/mnem)는 부등법에서 평가 가치 X (학습 보조용)
- 선례·예규 인용 별도 평가 (학습 깊이 증거)
- missing은 음수 차감 전용 (max=0)
""",
    "hybrid": """[모드: 하이브리드 합의 (판사+강사 best-of)]
- 강사 안의 첨부/절차/효력 세분화 + 판사 안의 논리 정확성 강조 모두 살림
- 만능목차 4분류 골격 + 출처 분리 + 사례형/약술형 분기 균형
- 메인 종합 권장 모드 — 양쪽 강점 통합
""",
    "main_opus": """[모드: 메인 Opus 독립 관점]
- 학습자 효과 우선 — 사안의 적용(case_apply 13) + 선례·예규(precedent 10) 강조
- 만능목차 골격(outline 14)은 base이지만 압도적 X
- 두문자(mnem 5) 부수절차 "주객상방기범효업" 일부 인정
- 균형 잡힌 평가
""",
    "strict_outline": """[모드: 만능목차 엄격 준수]
- 만능목차 4분류 골격이 답안의 50% 점수 (outline 40 + attached 15 + procedure 12)
- 골격 누락 시 사실상 실격에 가까움 (missing -10 차감 강화)
- 조문 인용은 살리되 (articles 20), 다른 평가축은 최소화
- 표준 합격 답안 = 만능목차 그대로 작성. 창의적 풀이는 strict 모드에서 감점 위험
""",
}


def get_mode_prompt(mode: str) -> str:
    """모드별 system prompt 반환 (base + mode 특화)."""
    if mode not in MODE_PROMPTS:
        raise ValueError(f"Unknown mode: {mode}. Valid: {list(MODE_PROMPTS.keys())}")
    return BASE_PROMPT_BUDEUNGLAW + "\n" + MODE_PROMPTS[mode]


# ============================================================
# 만능목차 카테고리 매칭 (outline 채점 보조)
# ============================================================

# 답안 문제 메타에서 카테고리 추정 (제목 키워드 기반)
OUTLINE_CATEGORIES = {
    "기본": ["의의", "요건", "효과", "추정력", "유효요건", "물권변동"],
    "첨부서면": ["인감증명", "등기필정보", "주소증명", "번호증명", "세금영수증", "대장", "지적도", "허가", "동의", "승낙"],
    "등기절차": ["수용", "보존", "이전", "말소", "회복", "변경", "경정", "신청", "촉탁", "직권", "단독", "공동", "이의"],
    "부수절차": ["취하", "보정", "각하", "이의신청", "처분"],
}


def guess_outline_category(title: str, case: str = "") -> str:
    """답안 메타 제목/case에서 만능목차 카테고리 추정.

    Returns: "기본" | "첨부서면" | "등기절차" | "부수절차" | "unknown"
    """
    text = f"{title} {case}".lower()
    scores = {}
    for cat, keywords in OUTLINE_CATEGORIES.items():
        scores[cat] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


# ============================================================
# 약술형 감지 (procedure/case_apply 비례 축소 기준)
# ============================================================

def is_short_answer(points: int, problem_text: str = "") -> bool:
    """답안이 약술형인지 판단.

    기준:
      - points <= 10
      - 또는 problem_text에 "약술", "간략", "N줄", "한 줄" 키워드 포함
    """
    if points <= 10:
        return True
    keywords = ["약술", "간략", "줄로", "줄 내외", "한 줄", "두 줄", "세 줄"]
    return any(kw in problem_text for kw in keywords)


def is_attached_case(title: str, case: str = "") -> bool:
    """첨부서면 사안 여부 (attached 채점 활성화 조건)."""
    return guess_outline_category(title, case) == "첨부서면"


def is_procedure_case(title: str, case: str = "") -> bool:
    """등기절차 사안 여부 (procedure 채점 활성화 조건)."""
    return guess_outline_category(title, case) == "등기절차"


# ============================================================
# 가중치 동적 조정 (사례형/약술형 분기)
# ============================================================

def adjust_weights_for_case_type(
    weights: dict, points: int, title: str, case: str = "", problem_text: str = ""
) -> dict:
    """사안 유형에 따라 max 가중치 동적 조정.

    - 약술형 (points <= 10 등): procedure/case_apply 비례 축소
    - 첨부 사안 외: attached max=0
    - 등기절차 사안 외: procedure max=0 (단 단순 약술이 아니면 그대로)
    """
    w = dict(weights)
    if is_short_answer(points, problem_text):
        # 약술형 — outline 비례 축소, procedure/case_apply 약화
        w["procedure"] = int(w.get("procedure", 0) * 0.3)
        w["case_apply"] = int(w.get("case_apply", 0) * 0.3)
        w["attached"] = int(w.get("attached", 0) * 0.3)
        w["outline"] = int(w.get("outline", 0) * 0.5)
    else:
        # 사례형 — 카테고리에 맞게
        if not is_attached_case(title, case):
            w["attached"] = 0
        if not is_procedure_case(title, case):
            # 등기절차 사안 아니면 procedure 살짝 ↓
            w["procedure"] = int(w.get("procedure", 0) * 0.5)
    return w


# ============================================================
# 점수 환산 (사용자 요청: 10/50 (20/100) 형식)
# ============================================================

def format_score_display(raw_score: float, raw_max: float, problem_points: int) -> dict:
    """점수 표시 형식 변환.

    Args:
      raw_score: 채점 결과 100점 환산 점수 (예: 73.5)
      raw_max: 100 (가중치 합)
      problem_points: 문제 절대점수 (예: 50)

    Returns:
      {
        "absolute_score": 36 (10/50의 10),  # 사용자 요청 "10점 맞았다면"
        "absolute_max": 50,
        "absolute_str": "36/50",
        "pct_score": 73,
        "pct_str": "(73/100)",
        "combined": "36/50 (73/100)",
      }
    """
    pct = raw_score / raw_max * 100 if raw_max else 0
    absolute = int(round(pct / 100 * problem_points))
    return {
        "absolute_score": absolute,
        "absolute_max": problem_points,
        "absolute_str": f"{absolute}/{problem_points}",
        "pct_score": int(round(pct)),
        "pct_str": f"({int(round(pct))}/100)",
        "combined": f"{absolute}/{problem_points} ({int(round(pct))}/100)",
    }


# ============================================================
# 5모드 일괄 채점 결과 비교 helper
# ============================================================

def summarize_multi_mode_results(results: dict) -> dict:
    """5 mode 채점 결과 비교 요약.

    Args:
      results: {mode: {total, max, pct, grade, ...}}

    Returns:
      {
        "modes": [{mode, label, total, max, pct, grade, ...}],
        "highest_mode": "judge",
        "lowest_mode": "strict_outline",
        "spread_pct": 18.5,
        "consensus_grade": "B+",
      }
    """
    modes_list = []
    for mode in MODE_ORDER:
        if mode not in results:
            continue
        r = results[mode]
        modes_list.append({
            "mode": mode,
            "label": MODE_LABELS[mode],
            "total": r.get("total"),
            "max": r.get("max"),
            "pct": r.get("pct"),
            "grade": r.get("grade"),
        })
    if not modes_list:
        return {"modes": [], "highest_mode": None, "lowest_mode": None, "spread_pct": 0, "consensus_grade": None}
    pcts = [m["pct"] for m in modes_list if m["pct"] is not None]
    highest = max(modes_list, key=lambda m: m["pct"] or 0)
    lowest = min(modes_list, key=lambda m: m["pct"] or 0)
    spread = (highest["pct"] or 0) - (lowest["pct"] or 0)
    # consensus = 5개 중 가장 빈번한 grade (간단히 hybrid mode grade 선택)
    hybrid_result = next((m for m in modes_list if m["mode"] == "hybrid"), None)
    consensus = hybrid_result["grade"] if hybrid_result else modes_list[0]["grade"]
    return {
        "modes": modes_list,
        "highest_mode": highest["mode"],
        "lowest_mode": lowest["mode"],
        "spread_pct": spread,
        "consensus_grade": consensus,
    }


if __name__ == "__main__":
    # 자가 테스트
    print("=== 부등법 5모드 가중치 ===")
    for mode in MODE_ORDER:
        w = get_mode_weights(mode)
        total = sum(v for v in w.values() if v > 0)
        neg = sum(v for v in w.values() if v < 0)
        print(f"{mode:18s} | 양수합 {total:4d} | 음수 {neg:4d} | 키 수 {len([v for v in w.values() if v != 0])}")
    print()
    print("=== 점수 표시 예시 (사용자 요청 10/50 (20/100)) ===")
    print(format_score_display(20.0, 100.0, 50))
    print(format_score_display(73.0, 100.0, 30))
