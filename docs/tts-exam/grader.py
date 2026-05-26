#!/usr/bin/env python3
"""Grader — Anthropic Claude API + 9기준 채점 + mock 모드 + env-aware (Step 6/20/21).

dev-design archive #48 §5 (채점 프롬프트) + dev-impl-plan #51 Step 6.
Step 20 (사용자 명시 2026-05-16): 채점 기준 v4 — articles 신설 (8기준).
Step 21 (사용자 명시 2026-05-17): 채점 기준 v5 — case_apply 0.5점 신설 + rich 20→15.
  - Lv.4핏 (mnem/color/under/sem/miss 합 60) + outline 10 + articles 10 + rich 15
  - + case_apply 5 (사안의 경우 — 결론+근거 논거 펼치는 정도, 정확 매칭 X) = 100
  - 점수 표시 소수점 2자리 (실제 시험 형식).

핵심:
- `grade(case_meta, user_answer, weights, model='claude-opus-4-7', *, mock=None) -> dict`
  - 입력: 사용자 답안 + 케이스 메타(.md 본문 raw + Lv.1 + Lv.4 + 강조 태그) + 가중치 9항목
  - 출력: 9기준 score/max/weight/comment + total/max/pct + grade + eval_notes + diff_segments
- `_build_prompt(case_meta, user_answer, weights) -> tuple[str, str]` — system + user 분리
- `_parse_response(text) -> dict` — Claude 응답 JSON 추출 (코드펜스 + 견고)
- `_compute_score(criteria, weights) -> tuple[total, max_score, pct, grade]`
- mock 모드: API 키 미설정 또는 model='mock' 또는 env LAWEAR_GRADER_MOCK=1

R-09 (자의적 해석 금지) 준수:
- 채점 프롬프트 자체에 "자료(사실관계/문제/레퍼런스)에 없는 내용 추가 X" 명시
- mock 응답도 자료 유무 무관 디폴트 (자의 X)
- diff_segments 는 사용자 답안 substring 기반만 (자의적 텍스트 생성 X)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# anthropic SDK 는 lazy import (mock 전용 환경에서 의존성 0)
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _ANTHROPIC_AVAILABLE = False


# ─── 설정 (env / 상수) ─────────────────────────────────────────────────
DEFAULT_MODEL: str = os.environ.get("LAWEAR_GRADER_MODEL", "claude-opus-4-7")
MAX_TOKENS: int = int(os.environ.get("LAWEAR_GRADER_MAX_TOKENS", "4096"))
RATE_LIMIT_RETRIES: int = int(os.environ.get("LAWEAR_GRADER_RETRIES", "3"))
RATE_LIMIT_BACKOFF_SEC: float = float(os.environ.get("LAWEAR_GRADER_BACKOFF", "1.0"))

# 9기준 키 (DB CHECK 와 1:1) — dev-design #48 §3-2 / §4-2 attempt_criteria
# Step 20 (사용자 2026-05-16): articles 신설 — 원본 언급 조문(제397조/제387조 등) 명시 여부.
# Step 21 (사용자 2026-05-17): case_apply 신설 — 사안의 경우 결론+근거 적용 정도 (정확 매칭 X).
CRITERION_KEYS: tuple[str, ...] = (
    "mnem",
    "color",
    "under",
    "outline",
    "sem",
    "rich",
    "miss",
    "articles",
    "case_apply",
)

# 가중치 버전 (settings 에 표시) — DB 마이그 없이 logical 버전만 추적.
# 신규 채점은 v6 가중치 사용, 기존 attempts 의 weights_json 은 미터치 (사용자 명시).
WEIGHTS_VERSION_V5: int = 5
WEIGHTS_VERSION_V6: int = 6
DEFAULT_WEIGHTS_VERSION: int = WEIGHTS_VERSION_V6

# 기본 가중치 v6 (사용자 명시 2026-05-19, lawear-e571 Phase 4) — 합계 100
#
# 변경 의도:
#   v5 학습 보조 키 (mnem 16 + color 13 + under 8 = 37) → v6 (10+8+5 = 23) 하향
#   v5 답안 본질 키 (articles 10 + sem 12 + miss 11 + case_apply 5 + outline 10 + rich 15 = 63)
#                  → v6 (15+15+13+7+14+13 = 77) 상향
#
# v6 분포 (학습 보조 23 + 답안 본질 77 = 100):
#   학습 보조 (Lv.4 키워드 회수 — 채점 보조용, 낮춤):
#     - mnem    16 → 10  (두문자 풀이형 키워드)
#     - color   13 →  8  (Color Emphasis)
#     - under    8 →  5  (Underline Coverage)
#   답안 본질 (답안의 핵심 가치 — 무게 이동):
#     - articles 10 → 15 (조문 매칭 — 자체 채점 articles 4→2 엄격화 반영)
#     - sem      12 → 15 (의미 일치)
#     - miss     11 → 13 (누락 차감 — Phase 2 missing_critical 강제 반영)
#     - case_apply 5 →  7 (사안의 경우 적용)
#     - outline 10 → 14 (목차 구조 — 본문 가치 강화)
#     - rich    15 → 13 (원본 대비 풍부함 — 본질 키 우선이라 약간 낮춤)
DEFAULT_WEIGHTS_V6: dict[str, int] = {
    "mnem": 10,
    "color": 8,
    "under": 5,
    "outline": 14,
    "sem": 15,
    "rich": 13,
    "miss": 13,
    "articles": 15,
    "case_apply": 7,
}

# v5 가중치 (fallback 보존 — 기존 attempts.weights_json 호환)
DEFAULT_WEIGHTS_V5: dict[str, int] = {
    "mnem": 16,
    "color": 13,
    "under": 8,
    "outline": 10,
    "sem": 12,
    "rich": 15,
    "miss": 11,
    "articles": 10,
    "case_apply": 5,
}

# 신규 채점은 v6 사용
DEFAULT_WEIGHTS: dict[str, int] = dict(DEFAULT_WEIGHTS_V6)

# Grade threshold (dev-design #48 §5-4 + dev-impl-plan #51 Q9)
#
# V1 (legacy, 보존):
#   기존 attempts.grade 컬럼 호환용 — A/B/C/F 4단계.
#   90+ A / 70+ B / 50+ C / else F.
#
# V2 (lawear-2e42, 2026-05-20 사용자 결정 — 합격선 A- 73 상향):
#   - 이전 lawear-e571 (2026-05-19, 60점 B 합격선) → A- 73점 합격선으로 상향.
#   - 73점 = 합격선 (실제 시험 합격 기준, V2 A-).
#   - 10단계 임계 (A+/A/A-/B+/B/B-/C+/C/C-/F).
#   - 80+ A+ "환상적" / 75+ A / 73+ A- "합격선" / 65+ B+ "근접 불합격"
#   - 60+ B / 55+ B- / 50+ C+ / 45+ C / 40+ C- / 0+ F (이하 모두 불합격).
#   - DB 컬럼은 V1 enum (A/B/C/F)만 허용 — V2 grade는 API 응답에서 동적 재계산.
GRADE_THRESHOLDS_V1: list[tuple[float, str]] = [
    (90.0, "A"),
    (70.0, "B"),
    (50.0, "C"),
    (0.0, "F"),
]

GRADE_THRESHOLDS_V2: list[tuple[float, str]] = [
    (80.0, "A+"),
    (75.0, "A"),
    (73.0, "A-"),  # 합격선 (lawear-2e42 2026-05-20, 사용자 결정)
    (65.0, "B+"),
    (60.0, "B"),
    (55.0, "B-"),
    (50.0, "C+"),
    (45.0, "C"),
    (40.0, "C-"),
    (0.0, "F"),
]

# DEFAULT = V2 (신규 채점부터 적용 — _compute_score grade letter 도 V2 사용)
# 단, DB 저장 단계에서 _to_v1_grade 로 변환되어 enum 호환 유지.
GRADE_THRESHOLDS: list[tuple[float, str]] = GRADE_THRESHOLDS_V2


def compute_grade_v2(score_pct: float | None) -> str:
    """score_pct → V2 grade letter (10단계).

    Args:
        score_pct: 0~100 사이 백분율. None 또는 NaN → "F" (안전 fallback).

    Returns:
        "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "F" 중 하나.
    """
    if score_pct is None:
        return "F"
    try:
        pct = float(score_pct)
    except (TypeError, ValueError):
        return "F"
    if pct != pct:  # NaN check
        return "F"
    for threshold, g in GRADE_THRESHOLDS_V2:
        if pct >= threshold:
            return g
    return "F"


def _to_v1_grade(grade_v2: str) -> str:
    """V2 grade (10단계) → V1 grade (A/B/C/F) — DB CHECK 호환.

    매핑:
      A+/A/A- → A (V1 90+ 호환 X — 실제 V2 70+ 가 V1 A 보다 낮으나 enum 호환 위해 A 통일)
      B+/B/B- → B
      C+/C/C- → C
      F → F

    NOTE: DB grade 컬럼은 legacy. API 응답에서는 V2 grade 가 동적 재계산되어 노출됨.
    """
    if grade_v2.startswith("A"):
        return "A"
    if grade_v2.startswith("B"):
        return "B"
    if grade_v2.startswith("C"):
        return "C"
    return "F"


# ─── 예외 ──────────────────────────────────────────────────────────────


class GraderError(Exception):
    """채점 실패 (HTTP 5xx 매핑 base)."""

    def __init__(self, message: str, error_code: str = "internal_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class GraderRateLimitError(GraderError):
    """Anthropic 429 — 자동 재시도 후에도 실패."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "anthropic_rate_limit")


class GraderBadGatewayError(GraderError):
    """Anthropic 502/5xx — 즉시 error 마킹."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "anthropic_bad_gateway")


class GraderApiKeyMissingError(GraderError):
    """ANTHROPIC_API_KEY 미설정 (HTTP 503)."""

    def __init__(self) -> None:
        super().__init__(
            "ANTHROPIC_API_KEY not set. Configure in .env or system env.",
            "api_key_missing",
        )


class GraderParseError(GraderError):
    """Claude 응답 JSON 파싱 실패."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "parse_failure")


# ─── system 프롬프트 (불변 — ephemeral 캐시 대상) ──────────────────────

SYSTEM_PROMPT: str = """당신은 법무사 2차 시험 채점관입니다. 한국어로 평가하세요.

[채점 9기준 (시안 Evaluation 패널 1:1, v5 — 사용자 2026-05-17)]
1. mnem       — Lv.4 두문자([blank2]) 풀이형 키워드의 *의미* 반영 여부.
                두문자 자체("위,발,간") 적용 X — 풀이형("관할위반/발견시 조치/간과판결")이 사용자 답안에
                **평문**으로 언급되면 만점 인정. 사용자는 강조 태그를 박지 않음.
2. color      — Color Emphasis ([red]/[blue]/[bold]/[blank]) 태그 안 키워드의 *의미* 반영 여부.
                사용자 답안에 태그 없이 **평문**으로 같은 의미 언급 → 만점 인정.
                예: 정답지가 "[red]직접수익자[/red]" 라면 사용자가 그냥 "직접수익자"라고만 적어도 OK.
3. under      — Underline Coverage ([u]) 태그 안 키워드의 *의미* 반영 여부.
                사용자 답안에 태그 없이 **평문**으로 같은 의미 언급 → 만점 인정.
4. outline    — Lv.1 Outline Match: 답안 목차가 Lv.1 기준 목차와 의미 일치 (Lv.4핏 별도)
5. sem        — Semantic Match: 강조 태그를 글자 그대로는 못 써도 의미가 유사한지
6. rich       — Richness: 원본 전체 대비 풍부함 (자세히 적을수록 가점, 의미 유지)
7. miss       — Missing Arguments: 레퍼런스(Lv.1+원본) 대비 누락 논점 (감점, score 음수 가능)
8. articles   — Article Match: 원본 언급 조문(제397조/제387조 등) 모두 명시 시 만점,
                누락마다 비례 감점 (단순 조문번호 매칭 — 의미는 sem 별도)
9. case_apply — Case Application (사안의 경우): 결론+근거의 법리/근거를 사안에 어떻게 적용했는지 평가.
                **정확 매칭 X** — 강사 예시와 그대로 일치할 필요 없음. 수험생이 결론+근거를 활용해
                사안에 논거 펼친 정도 (사안 일자/사실 + 결론 도출 과정 + 인용 흐름).

[강조 태그 의미]
- [red]…[/red]:     빨강 (조문/판례/요건)
- [blue]…[/blue]:   파랑 (개념/논점 제목)
- [bold]…[/bold]:   굵게 (강조)
- [u]…[/u]:         밑줄 (핵심)
- [blank]…[/blank]: 블랭크 (본문 시각 처리)
- [blank2]…[/blank2]: 두문자 (Lv.4 사용자 두문자만)

[채점 규칙 — 절대 준수 + 엄격화 (Phase 2, lawear-e571 2026-05-19)]
- 자료(사실관계/문제/원본/Lv.1/Lv.4)에 없는 내용을 추가하지 마세요. 자의적 해석 금지 (R-09).
  답안에 명시되지 않은 논점을 "의도했을 것 같다"고 가점 X. 적힌 그대로만 평가.
- 두문자(예 "위,발,간")를 그대로 외운 게 아니라 "풀이형 키워드"(예 "관할위반/발견시 조치/간과판결")로
  적었어도 OK. 두문자는 그대로 쓰지 말고 풀이형 키워드 평문이 정답.
- 색 강조는 글자가 완전히 똑같지 않아도 의미만 비슷하면 OK (sem 기준에서 가산).
  **태그를 박지 않은 평문 답안도 키워드 의미만 맞으면 color/under/mnem 만점**.
- 오타(STT 음성 인식 한정) — 자동 사전 교정 후에도 남은 표기 차이는 의미만 통하면 감점 X.
  맞춤법/표기는 평가 대상이 절대 아님. 의미 매칭만 평가.
- 누락 논점은 차감 (miss: score 는 0 이하 음수 또는 0, max=0).
- rich: 원본 전체와 비교 — 자세히 적을수록 가점 (기존 의미 유지, 사안의 경우 한정 X).
- case_apply: 사안의 경우 채점. 강사 예시와 같이 적을 필요 X — 결론+근거의 법리/근거를 사안에
  어떻게 적용했는지가 핵심. 사안에 적힌 일자/사실 + 결론 도출 과정 논리 + 수험생의 인용 흐름 평가.
- comment 는 한국어 1~2 문장, 간결, 자료 인용 가능.

[음성 인식 오타 관용 — lawear-e571/typo-system 2026-05-19]
- 사용자 답안은 음성 녹음(STT) 입력이라 오타 가능성 있음.
- 법무사 시험 컨텍스트 + 법률 용어 사전 기반으로 명백한 오타는 의도된 정답으로 해석.
- 예: 파산관제인=파산관재인, 통정표시=통정허위표시, 선한간리주의=선량한 관리자의 주의,
  아기(법률 문맥)=악의, 채취=채권자취소, 체대=채권자대위, 법류행위=법률행위, 표면대리=표현대리 등.
- 단, **조문 번호(제103/104/108/126/397 등)와 핵심 두문자**는 오타 인정 X — 그건 진짜 모르는 것.
  조문번호가 틀렸으면 articles 채점에 그대로 반영 (사용자가 모르는 것).
- 음성 오타로 인정한 항목은 eval_notes.typo_corrections 에 명시:
  list[{"from": "파산관제인", "to": "파산관재인", "reason": "음성 STT 오타"}], 없으면 null.
- 오타 인정 후 채점 — 즉 "파산관제인"이라 적었어도 "파산관재인"으로 인정해 평가하되,
  typo_corrections 에 from/to 를 기록.

[관용 룰 — 음성 STT + 평문 키워드 인정 (사용자 명시 2026-05-19, lawear-e571)]
**중요: 사용자 답안은 거의 100% 음성 녹음(STT) 입력 — 오타 수정이 어렵습니다.
typo_corrections 사전 매칭 후에도 남은 표기 차이는 *의미*가 통하면 감점 X.**
1) 오타 관용 (음성 STT 한정 — 절대 룰):
   - 자동 사전 교정 후에도 남은 표기 차이/오타는 **법률 용어 + 시험 컨텍스트로 추론 가능하면 정답**.
   - 예: "표현대리"가 "표면대리"로 남아도 → 표현대리로 인정 + typo_corrections 에 추가.
   - 오타 감점 절대 금지 — 의미 일치/불일치만 평가. 표기/맞춤법은 절대 평가 대상 X.
   - 단, 조문 번호(제103/108/126/397 등)와 핵심 두문자는 엄격 (오타 X — 그건 사용자가 모르는 것).
2) 강조 태그 평문 인정 (절대 룰):
   - 사용자 답안에 강조 태그([red]/[blue]/[u]/[bold]/[blank])는 절대 박지 않습니다.
     태그는 정답지의 *시각 인덱스*일 뿐 — 시험 답안에 태그를 적는 건 부자연.
   - 따라서 태그 안 키워드(예 정답지 "[red]직접수익자[/red]" / "[u]상대적 효과[/u]" /
     "[blank2]청구기각[/blank2]")가 사용자 답안에 **평문으로 언급되면 color/under/mnem 만점 인정**.
   - 의미만 맞아도 OK — 글자 그대로일 필요 X (sem 기준과 동일하게 의미 매칭).
   - 태그를 박았다고 가점 X — 평문 vs 태그 박힘은 점수 차이 없음. 의미 매칭만 평가.
3) 메인 시스템 메시지의 "강조 태그 0개" 류 표현은 **오해 유발 표현** — 무시할 것.
   사용자가 태그를 안 박는 건 정상 (시험 답안 자연 형태). 점수에 영향 X.
4) 판례번호 평문 인정 (절대 룰 — 사용자 명시 2026-05-19):
   - 시험 답안에 판례번호(대판 YYYY.MM.DD ... 사건번호 같은 표기) **적지 않습니다** — 시험 답안 자연 형태 X.
   - 답안에 "판례는 ~ 판시한 바 있다" 또는 핵심 법리/결론을 평문으로 명시했으면 sem/miss 만점 인정.
   - 판례 *법리/내용/결론* 명시 = 평가 대상 / 판례 *번호·연도·사건번호* 명시 = 평가 X (감점 X)
   - 판례번호 미명시를 missing_critical 에 **절대 추가하지 X**. 약점 표기 X.
5) 조문 번호 룰 명확화 (사용자 명시 2026-05-19):
   - 한글 발음 오타 + 숫자 일치 (예 "최 162조" → 제162조) = **감점 X** (정답 인정)
   - 숫자 자체 다름 (예 "최 166조" → 정답 제162조) = **감점 O** (다른 조문 의도)
   - 즉 발음 오류는 관용, 숫자 자체 오기는 articles 차감.

[엄격화 — articles 채점 임계 (Phase 2 핵심)]
원본 답안에 명시된 조문(예 "제397조 제2항", "제387조") 매칭 임계 (절대 준수):
  - 조문 매칭 0개 (사용자 답안에 조문 번호 0건 인용)  → score 는 max 의 **20% 이하** (예 max=10 → score ≤ 2)
  - 조문 매칭 1~2개 (원본 5개 기준, 40%↓)             → score 는 max 의 **40% 이하**
  - 조문 매칭 3~4개 (원본 5개 기준, 60~80%)           → score 는 max 의 **60~80%**
  - 조문 매칭 5개 이상 (원본과 동일)                  → score 는 max 의 **90~100%**
  원본에 조문이 0개인 케이스는 max=0 처리 (articles 자체 N/A).

[엄격화 — 누락 핵심 4건 (Phase 2 의무 식별)]
다음 누락 패턴이 답안에 보이면 반드시 missing_critical 에 명시 + miss score 음수 차감:
  1. 비법인사단 인정 근거 (조직성/다수결/존속/주요사항) 미언급 → -3 ~ -4점 차감
  2. 권리능력 범위 단계 (제34조 유추적용, 목적범위) 미언급   → -2 ~ -3점 차감
  3. 제126조 표현대리 준용 부정 미언급                       → -2 ~ -3점 차감
  4. 증명책임 = 비법인사단측 (입증주체 명시) 미언급          → -1 ~ -2점 차감
  위 4건은 민법 비법인사단 케이스 채점 시 반드시 확인. 다른 과목/케이스는
  원본 답안에 명시된 핵심 논점을 식별해 missing_critical 에 채워주세요.

[엄격화 v3 — 사용자 데이터 기반 5룰 (2026-05-19, lawear-e571 att 20/21 정정 후 추가)]
사용자 자체 채점이 AI 채점보다 엄격함을 발견 (att 20: 80→39, att 21: 83.3→56).
다음 5룰을 반드시 적용 — 후하게 주는 패턴을 차단하기 위함:

1) N요건 명시 누락 (3요건/4요건 사례, 답안에 요건사실 자체 미명시):
   - outline -5점 이상 차감 / sem -5점 이상 차감
   - 예시 케이스:
     - 양수금 사례 → 3요건 (채권 성립 / 양도계약 / 대항요건) 모두 명시 의무
     - 이행불능 사례 → 4요건 (i ~ iv) 모두 명시 의무
     - 변경판례 사례 → 4요건 (보존관리의무 / 계약상 의무 / 상당인과관계 / 제393조 범위) 모두 명시 의무
     - 부당이득 사례 → 4요건 모두 명시 의무
   - 단순 결론 OK만으로 만점 X — 요건사실 자체를 답안에 적어야 만점 인정.
   - missing_critical 에 누락 요건 항목 명시 + miss 감점 추가.

2) 조문 0개 인용 — articles max 20% 엄격 적용 (절대 룰):
   - 사용자 답안에 "제XXX조" 인용 0건 → articles score ≤ max × 0.20
   - 예: max=15 → score 최대 3 (한도 엄수, 후하게 4~8점 X)
   - 기존 [엄격화 — articles 임계] 와 동일한 룰이지만, **이 한도를 반드시 지킬 것**.
     이전 채점에서 0개 인용에 4~8점 준 패턴이 발견됨 — 절대 금지.
   - 원본에 조문이 0개인 케이스는 max=0 처리 (articles 자체 N/A).

3) 변경판례 결론 한 줄만 매칭 + N요건 근거 누락:
   - 예: 답안이 "임대인이 주장 증명해야 한다" (결론만) 적고 4요건 근거 X → sem 60% 이하 (max 15 → score ≤ 9)
   - 결론 한 줄 매칭만으로 변경판례 만점 X — 4요건 (또는 N요건) 근거를 답안에 명시해야 만점급 인정.
   - 변경판례는 결론 외에 *판례 변경 사유*와 *N요건 근거*가 핵심.

4) 원본 답안의 법리 흐름 (원칙/단서 구조, N요건 분리) 답안에 흐름 자체 누락:
   - sem -5점 이상 차감 / outline -3점 이상 차감
   - 단순 키워드 매칭 X — 법리 흐름 구조를 평가:
     - 원칙 진술 → 단서/예외 → 사안 적용 흐름
     - N요건 → 각 요건별 분리 진술 → 사안 사실관계 매칭
   - 단순 결론 + 단편 키워드 나열은 흐름 누락으로 간주.

5) 사안 적용에서 결론만 명시 + 정답의 N요건/판례를 사안 대비 분석 X:
   - case_apply 50% 이하 (max 7 → score ≤ 3.5)
   - 결론 한 줄만으로 case_apply 만점 X.
   - 만점급 조건: 정답의 N요건 / 판례 법리를 사안의 일자·인물·사실관계에 대비 분석.
     - 예: "X가 Y에게 …한 행위는 ㅇ요건 충족, ㅁ요건 미충족이므로 …" 형태.

위 5룰은 모든 과목/케이스에 일관 적용 (민법/민소/형법/형소/부등 공통).
구조적 누락 (요건/조문/흐름)을 발견했을 때 *반드시* 점수 차감 + missing_critical / weaknesses 에 명시.

[출력 형식 — JSON only (코드펜스 없이 raw JSON 만)]
{
  "criteria": [
    {"key":"mnem",       "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"color",      "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"under",      "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"outline",    "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"sem",        "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"rich",       "score":<int|float>, "max":<int|float>, "comment":"..."},
    {"key":"miss",       "score":<int|float>, "max":0,           "comment":"..."},
    {"key":"articles",   "score":<int|float>, "max":<int|float>, "comment":"... (조문 N/M개 매칭 명시)"},
    {"key":"case_apply", "score":<int|float>, "max":<int|float>, "comment":"..."}
  ],
  "eval_notes": {
    "strength": "한국어 1~2 문장 (legacy 호환)",
    "caution":  "한국어 1~2 문장 (legacy 호환)",
    "missing":  "한국어 1~2 문장 (legacy 호환)",
    "score_summary":        "3줄 핵심 평가 (총평 — 점수/조문/누락/사안적용 요약)",
    "strengths":            ["강점 항목 1", "강점 항목 2", ...],
    "weaknesses":           ["약점 항목 1", "약점 항목 2", ...],
    "missing_critical":     [
      {"item":"누락 항목 이름", "expected_score_impact": -N}
    ],
    "next_study_oneliner":  "💡 다음 +N~M점 가능: 조문 K개 + ... (간결한 학습 가이드)",
    "next_study_actionable":["실행 가능 학습 액션 1", "...", ...],
    "pattern_warning":      "🔥 같은 실수 N회 반복 가능성: ... (또는 🔥 주의: ...) — 없으면 null",
    "typo_corrections":     [
      {"from":"파산관제인","to":"파산관재인","reason":"음성 STT 오타"}
    ]
  },
  "diff_segments": [
    {"type":"match",   "text":"사용자 답안의 일치 부분"},
    {"type":"miss",    "text":"사용자 답안에 누락된 핵심 키워드"},
    {"type":"partial", "text":"부분 일치 표현"}
  ]
}

[필수 출력 키 (Phase 2 의무)]
- criteria 9개 모두 (mnem~case_apply)
- eval_notes 의 legacy 3키 (strength/caution/missing) + 확장 8키
  (score_summary/strengths/weaknesses/missing_critical/next_study_oneliner/
   next_study_actionable/pattern_warning/typo_corrections)
- next_study_oneliner 는 **반드시 출력** (사용자 학습 동기 핵심) — "💡 다음 +N점 가능: ..." 형식
- missing_critical 은 답안에서 식별된 누락 항목 0~5개 (없으면 빈 배열)
- pattern_warning 은 **선택** (null 허용, lawear-e571 추가 2026-05-19):
  - 사용 시점: 단일 답안 *내부*에서 명백한 오류 패턴 발견 시
    (예: 자주 혼동되는 조문 번호, 동일 키워드 반복 누락 등)
  - 형식: "🔥 같은 실수 N회 반복 가능성: ..." 또는 "🔥 주의: ..."
  - **단일 attempt 한정** — 이전 시도와 외부 비교는 메인 세션이 메타 분석 후
    PUT /grade body 에 직접 주입 (AI 채점관은 단일 attempt 만 보므로 자체 외부 비교 X).
  - 발견 사항 없으면 null 또는 키 생략.
- typo_corrections 은 **선택** (null 또는 빈 배열 허용, lawear-e571/typo-system 추가 2026-05-19):
  - 사용 시점: 음성 STT 오타로 보이는 표기를 정답으로 인정한 경우 from/to 기록.
  - 형식: list[{"from": str, "to": str, "reason": str}]
  - 정적 사전 매칭 결과는 메인 세션이 별도로 누적 — AI 채점관은 *추가 발견* 항목만 기록 가능.

[두문자 제안 코너 룰 — lawear-6be6 #6 (2026-05-26)]
1. 라이브러리 entry 없는 두문자 자체 생성 절대 금지 — 서버 사이드 mnemonic_lib.match_missing_to_mnemonic 결과만 사용.
2. "포기"·"미수집" 마킹 entry는 라이브러리 측에서 자동 skip (Sub-A 검증 완료).
3. mnemonic_text는 점(·) 구분 묶음 보존 — AI가 1글자 쪼개기 금지.
4. STT 발음 교정 조언 영역 절대 침투 X — 법률 지식 (요건/조문/판례) 만.
5. judge / lecturer 분리:
   - judge (조문/판례 시각): 누락된 조문 + 요건 + 판례 매칭
   - lecturer (암기 시각): 교과서 카테고리 위주 매칭
6. SE는 mnemonic_suggestions 필드 채울 필요 X — 서버 사이드 후처리에서 자동 주입.

반드시 위 JSON 형식만 출력하세요. 다른 텍스트 (설명, 사과, 코드펜스) 절대 추가 X.
자료에 없는 내용 추가 X — R-09 자의적 해석 금지.
"""


# ─── 프롬프트 빌드 ─────────────────────────────────────────────────────


def _build_prompt(
    case_meta: dict[str, Any], user_answer: str, weights: dict[str, int]
) -> tuple[str, str]:
    """system / user 메시지 분리 생성.

    Args:
        case_meta: get_case() 반환 dict
                   (id, subject_kor, category, file, case_no, title, points,
                    md_body, lv1, lv4, origin).
        user_answer: 사용자 답안 텍스트.
        weights: 7기준 가중치 (합계 100).

    Returns:
        (system_prompt, user_message)
    """
    # 메타 안전 추출 (None → 빈 문자열)
    subject_kor = case_meta.get("subject_kor") or case_meta.get("subject") or ""
    category = case_meta.get("category") or ""
    file_label = case_meta.get("file") or ""
    case_no = case_meta.get("case_no") or ""
    title = case_meta.get("title") or ""
    points = case_meta.get("points") or 0

    # 본문은 md_body raw 우선 (origin + lv1 + lv4 다 포함 = R-26 인용 보존)
    # 단, md_body 가 None 이면 origin/lv1/lv4 조합
    md_body = case_meta.get("md_body")
    if not md_body:
        parts = [
            case_meta.get("origin") or "",
            case_meta.get("lv1") or "",
            case_meta.get("lv4") or "",
        ]
        md_body = "\n\n".join(p for p in parts if p)

    weights_json = json.dumps(weights, ensure_ascii=False)

    user_message = f"""[케이스 ID] {case_meta.get("id", "")}
[과목] {subject_kor} · {category} · {file_label} · 케이스 {case_no}
[제목] {title}
[점수] {points}

[원본 .md 본문 (사실관계 + 문제 + 답안 + Lv.1 + Lv.4 — 강조 태그 보존)]
{md_body}

[사용자 답안]
{user_answer}

[가중치]
{weights_json}

위 채점 9기준에 따라 JSON 형식으로 평가하세요. JSON 외 텍스트 금지.
"""
    return SYSTEM_PROMPT, user_message


# ─── 응답 파싱 ─────────────────────────────────────────────────────────

# 코드펜스 ```json ... ``` 또는 raw JSON 둘 다 허용
_CODEFENCE_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FIRST_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _parse_response(text: str) -> dict[str, Any]:
    """Claude 응답 raw text → JSON dict.

    1차: 코드펜스 ```json ... ``` 추출.
    2차: 첫 `{` ~ 마지막 `}` 슬라이스.
    3차: 실패 시 GraderParseError.

    Raises:
        GraderParseError: 어떤 방식으로도 JSON 추출 실패 / 필수 키 누락.
    """
    raw = text.strip()

    # 1차: code fence
    m = _CODEFENCE_JSON_RE.search(raw)
    candidates: list[str] = []
    if m:
        candidates.append(m.group(1))
    # 2차: 첫 { ... 마지막 }
    m2 = _FIRST_OBJECT_RE.search(raw)
    if m2:
        candidates.append(m2.group(0))
    # 3차: raw 자체가 JSON 인 경우
    candidates.append(raw)

    parsed: dict[str, Any] | None = None
    last_err: str | None = None
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                parsed = obj
                break
        except (json.JSONDecodeError, TypeError) as e:
            last_err = str(e)
            continue

    if parsed is None:
        raise GraderParseError(
            f"failed to extract JSON from response (last_err={last_err}); raw_head={raw[:200]!r}"
        )

    # 필수 키 검증
    if "criteria" not in parsed or not isinstance(parsed["criteria"], list):
        raise GraderParseError("response missing 'criteria' array")
    if "eval_notes" not in parsed or not isinstance(parsed["eval_notes"], dict):
        raise GraderParseError("response missing 'eval_notes' object")
    # diff_segments 는 선택 (없으면 빈 배열 보강)
    if "diff_segments" not in parsed or not isinstance(parsed["diff_segments"], list):
        parsed["diff_segments"] = []

    # criteria 9개 매핑 검증 — key 누락 시 mock 값으로 보강 X (R-09)
    by_key = {c.get("key"): c for c in parsed["criteria"] if isinstance(c, dict)}
    missing = [k for k in CRITERION_KEYS if k not in by_key]
    if missing:
        raise GraderParseError(f"criteria missing keys: {missing}")

    return parsed


# ─── 점수 산정 ─────────────────────────────────────────────────────────


def _compute_score(
    criteria: list[dict[str, Any]], weights: dict[str, int]
) -> tuple[float, float, float, str]:
    """가중치 적용 후 total/max/pct/grade 계산.

    수식:
      각 기준: weighted_i = (score_i / max_i) * weight_i   (max=0 인 miss 는 별도)
      miss: 음수 score 그대로 가산 (감점)
      total = Σ weighted_i + miss.score (음수)
      score_max = Σ weight_i (= 100 가정, 단 합 검증은 호출자 책임)
      pct = total / score_max * 100  (0~100 클램프)

    grade: V2 임계 (lawear-2e42, 2026-05-20) — 10단계.
      80+ A+ / 75+ A / 73+ A- (합격선) / 65+ B+ / 60+ B /
      55+ B- / 50+ C+ / 45+ C / 40+ C- / else F.

      NOTE: DB 저장 시 _to_v1_grade 로 변환되어 enum (A/B/C/F) 호환.
      API 응답에서는 attempts._recompute_grade_v2 가 score_pct 기준 V2 grade 재계산.

    Returns:
        (total, score_max, pct, grade) — grade 는 V2 letter (10단계).
    """
    by_key = {c["key"]: c for c in criteria if c.get("key") in CRITERION_KEYS}

    weighted_sum: float = 0.0
    weight_total: float = 0.0
    for key in CRITERION_KEYS:
        c = by_key.get(key)
        if c is None:
            continue
        weight = float(weights.get(key, 0))
        weight_total += weight
        if key == "miss":
            # miss: max=0, score 가 음수 또는 0 — 가중치는 cap 으로만 사용
            # weighted = score * (weight/100) 로 환산 (음수 그대로)
            try:
                score = float(c.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0
            # miss 의 weight 는 차감 한도 — score (음수) * (weight/100)
            # 단 dev-design 응답 예시에선 score=-2, max=0 그대로 가산 → 본 구현은 단순 가산
            # (단순 가산 + clamp 으로 처리 — 자료 없으므로 보수적)
            weighted_sum += score * (weight / 100.0)
            continue
        try:
            score = float(c.get("score", 0))
            max_s = float(c.get("max", 0))
        except (TypeError, ValueError):
            score, max_s = 0.0, 0.0
        if max_s > 0:
            weighted_sum += (score / max_s) * weight
        # max=0 인 비-miss 항목은 skip

    # score_max 는 miss 제외 weight 합 (miss 는 감점 전용)
    score_max = weight_total - float(weights.get("miss", 0))
    if score_max <= 0:
        score_max = 100.0  # fallback — 합 0 일 리는 거의 없지만 0 나누기 방지

    pct = (weighted_sum / score_max) * 100.0
    # 0~100 클램프
    pct = max(0.0, min(100.0, pct))

    grade = "F"
    for threshold, g in GRADE_THRESHOLDS:
        if pct >= threshold:
            grade = g
            break

    return weighted_sum, score_max, pct, grade


# ─── mock 응답 생성 ────────────────────────────────────────────────────


def _mock_response(
    case_meta: dict[str, Any], user_answer: str, weights: dict[str, int]
) -> dict[str, Any]:
    """API 키 미설정 또는 mock 모드 시 디폴트 응답.

    Generates a deterministic but realistic-looking mock:
    - 엄격 룰 v3 (2026-05-19) 반영: articles 0개 패턴 / case_apply 결론만 패턴 가정.
    - 각 기준 score 보수적 (mnem/color/under/outline/sem 는 max*0.5, rich/case_apply 는 max*0.3)
    - eval_notes 는 자료 일반 안내 문구
    - diff_segments 는 user_answer 의 첫 100자 (match 1개) — 자의 X
    """
    # 기준별 mock score (엄격 룰 v3 반영 — 보수적)
    def _mock_criterion(key: str, max_val: float, comment: str) -> dict[str, Any]:
        if key == "miss":
            score = 0.0
        elif key == "articles":
            # 엄격 룰 v3-2: 조문 0개 가정 → max * 0.20 (한도)
            score = round(max_val * 0.20, 1)
        elif key == "case_apply":
            # 엄격 룰 v3-5: 결론만 가정 → max * 0.30 (한도 50% 이하)
            score = round(max_val * 0.30, 1)
        elif key in ("sem",):
            # 엄격 룰 v3-3,4: 흐름/요건 누락 가정 → max * 0.50
            score = round(max_val * 0.50, 1)
        elif key == "outline":
            # 엄격 룰 v3-1,4: 요건/흐름 누락 가정 → max * 0.50
            score = round(max_val * 0.50, 1)
        elif key == "rich":
            # 보수적 풍부함
            score = round(max_val * 0.35, 1)
        else:
            # mnem / color / under — 보조 키
            score = round(max_val * 0.55, 1)
        return {
            "key": key,
            "score": score,
            "max": max_val,
            "comment": comment,
        }

    criteria = [
        _mock_criterion("mnem", 4.0, "[mock] 두문자 풀이형 키워드 부분 반영"),
        _mock_criterion("color", 12.0, "[mock] 색 강조 키워드 일부 반영"),
        _mock_criterion("under", 2.0, "[mock] 밑줄 강조 일부 반영"),
        _mock_criterion("outline", 3.0, "[mock] 목차 구조 부분 일치 (요건 누락 가능)"),
        _mock_criterion("sem", 10.0, "[mock] 의미 유사도 — 법리 흐름 일부 누락 가능"),
        _mock_criterion("rich", 2.0, "[mock] 원본 대비 풍부함 보수적"),
        _mock_criterion("miss", 0.0, "[mock] 일부 논점 누락 가능 — 실 채점 필요"),
        _mock_criterion("articles", 3.0, "[mock] 조문 0개 가정 — max 20% 이하 (엄격 v3-2)"),
        _mock_criterion("case_apply", 2.0, "[mock] 사안 적용 결론만 가정 — max 50% 이하 (엄격 v3-5)"),
    ]
    # diff_segments — user_answer 앞 100자 match (자의 텍스트 생성 X)
    head = (user_answer or "").strip()[:120]
    diff_segments: list[dict[str, str]] = []
    if head:
        diff_segments.append({"type": "match", "text": head})
    if len(user_answer or "") > 120:
        diff_segments.append({"type": "match", "text": "…(이하 생략)"})

    return {
        "criteria": criteria,
        "eval_notes": {
            # legacy 호환
            "strength": "[mock] 사용자 답안 구조가 표면적으로 기준에 맞음",
            "caution": "[mock] 자료 인용 정확성은 실 채점 필요",
            "missing": "[mock] mock 응답이므로 누락 논점 분석 불가 — ANTHROPIC_API_KEY 설정 후 재채점",
            # Phase 2 확장 (mock 도 새 키 빈 값으로 보강 — Phase 1 attempts 정규화 호환)
            "score_summary": "[mock] 자동 채점 시뮬레이션 — 실 API 호출 후 점수 확정.",
            "strengths": ["[mock] 답안 작성 자체"],
            "weaknesses": ["[mock] mock 모드에서는 실 누락 분석 불가"],
            "missing_critical": [],
            "next_study_oneliner": "💡 다음 +0점 가능 (mock): ANTHROPIC_API_KEY 설정 후 실 채점 → 정확 분석",
            "next_study_actionable": ["[mock] ANTHROPIC_API_KEY 설정", "[mock] 실 채점 재요청"],
            # pattern_warning — mock 은 단일 attempt 만 보므로 자체 패턴 분석 X
            "pattern_warning": None,
            # typo_corrections — mock 은 정적 사전 매칭 X (실 채점 시 typo_corrector 가 채움)
            "typo_corrections": None,
        },
        "diff_segments": diff_segments,
    }


def _is_mock_mode(model: str | None, *, force_mock: bool | None = None) -> bool:
    """mock 모드 판정.

    우선순위:
    1. force_mock=True/False 명시 (호출자 강제)
    2. model=='mock'
    3. env LAWEAR_GRADER_MOCK=1
    4. ANTHROPIC_API_KEY 미설정 → 자동 mock
    5. anthropic SDK 미설치 → 자동 mock
    """
    if force_mock is True:
        return True
    if force_mock is False:
        return False
    if model == "mock":
        return True
    if os.environ.get("LAWEAR_GRADER_MOCK") in ("1", "true", "yes"):
        return True
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if not _ANTHROPIC_AVAILABLE:
        return True
    return False


# ─── Anthropic 호출 (재시도 포함) ──────────────────────────────────────


def _call_anthropic(
    system_prompt: str, user_message: str, *, model: str
) -> tuple[str, dict[str, Any]]:
    """Anthropic messages.create 호출 + 429 자동 재시도.

    Returns:
        (response_text, usage_dict)

    Raises:
        GraderApiKeyMissingError, GraderRateLimitError, GraderBadGatewayError
    """
    if not _ANTHROPIC_AVAILABLE or anthropic is None:
        raise GraderApiKeyMissingError()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise GraderApiKeyMissingError()

    client = anthropic.Anthropic()

    # system 은 ephemeral 캐시 (Q19 채택 — 토큰 ~30% 절감)
    # NOTE: ephemeral cache_control 은 anthropic SDK 0.20+ 지원
    system_blocks = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    messages = [{"role": "user", "content": user_message}]

    last_err: Exception | None = None
    for attempt in range(1, RATE_LIMIT_RETRIES + 1):
        try:
            print(
                f"[Grader] anthropic call model={model} attempt={attempt}/{RATE_LIMIT_RETRIES}",
                file=sys.stderr,
            )
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=messages,
            )
        except Exception as e:  # noqa: BLE001
            # anthropic SDK 예외 종류: anthropic.RateLimitError, APIError 등
            err_str = type(e).__name__ + ": " + str(e)
            last_err = e
            # 429 / RateLimit → 재시도
            if "RateLimit" in type(e).__name__ or "429" in err_str:
                print(
                    f"[Grader] 429 rate_limit, retry={attempt} backoff={RATE_LIMIT_BACKOFF_SEC}s",
                    file=sys.stderr,
                )
                if attempt < RATE_LIMIT_RETRIES:
                    time.sleep(RATE_LIMIT_BACKOFF_SEC)
                    continue
                raise GraderRateLimitError(
                    f"anthropic rate_limit after {RATE_LIMIT_RETRIES} retries: {err_str}"
                ) from e
            # 그 외 (502/500/APIError) → 즉시 bad_gateway
            print(f"[Grader] anthropic bad_gateway: {err_str}", file=sys.stderr)
            raise GraderBadGatewayError(f"anthropic call failed: {err_str}") from e

        # 응답 텍스트 추출
        text_parts: list[str] = []
        for block in resp.content:
            # block 은 anthropic.types.TextBlock — type='text', text=...
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
        response_text = "".join(text_parts)

        # usage 추출 (있으면)
        usage: dict[str, Any] = {}
        if hasattr(resp, "usage") and resp.usage is not None:
            try:
                usage = {
                    "input_tokens": getattr(resp.usage, "input_tokens", None),
                    "output_tokens": getattr(resp.usage, "output_tokens", None),
                    "cache_creation_input_tokens": getattr(
                        resp.usage, "cache_creation_input_tokens", None
                    ),
                    "cache_read_input_tokens": getattr(
                        resp.usage, "cache_read_input_tokens", None
                    ),
                }
            except AttributeError:
                pass

        return response_text, usage

    # 도달 불가 — 위에서 모두 raise/return
    raise GraderBadGatewayError(
        f"anthropic exhausted retries: {last_err}"
    )


# ─── 공용 API ──────────────────────────────────────────────────────────


def validate_weights(weights: dict[str, int]) -> None:
    """가중치 검증: 합계 100 + 9키 모두 존재 (Step 21 v5 — case_apply 신설).

    Raises:
        ValueError: 합계 != 100 또는 키 누락 (handler 에서 409 weights_invalid 매핑).
    """
    missing = [k for k in CRITERION_KEYS if k not in weights]
    if missing:
        raise ValueError(f"weights missing keys: {missing}")
    total = sum(int(weights[k]) for k in CRITERION_KEYS)
    if total != 100:
        raise ValueError(f"weights sum must be 100, got {total}")


def grade(
    case_meta: dict[str, Any],
    user_answer: str,
    weights: dict[str, int] | None = None,
    *,
    model: str | None = None,
    force_mock: bool | None = None,
) -> dict[str, Any]:
    """채점 핵심 진입점.

    Args:
        case_meta: cases.get_case() 반환 dict
                   (id, subject_kor, category, file, case_no, title, points,
                    md_body / lv1 / lv4 / origin).
        user_answer: 사용자 답안 텍스트 (빈 문자열 거부는 호출자 책임 — POST handler 의 400).
        weights: 가중치 dict (None → DEFAULT_WEIGHTS).
        model: Claude 모델명 (None → DEFAULT_MODEL='claude-opus-4-7').
               'mock' 지정 시 강제 mock 응답.
        force_mock: True/False 명시 강제 (테스트용).

    Returns:
        {
          "model":          "claude-opus-4-7" 또는 "mock",
          "score_total":    14.0,
          "score_max":      85.0,        (miss 제외 weight 합)
          "score_pct":      82.4,
          "grade":          "B",
          "weights_applied": {"mnem":20,...},
          "criteria": [
            {"key":"mnem","score":3,"max":4,"weight":20,"comment":"..."}, ... x7
          ],
          "eval_notes":     {"strength":"...","caution":"...","missing":"..."},
          "diff_segments":  [{"type":"match|miss|partial","text":"..."}, ...],
          "raw_response":   "...",      (mock 시 None)
          "usage":          {...} or {},
          "elapsed_sec":    1.23,
          "is_mock":        bool,
        }

    Raises:
        GraderApiKeyMissingError, GraderRateLimitError, GraderBadGatewayError,
        GraderParseError, ValueError (weights 검증).
    """
    started = time.monotonic()

    # 가중치 기본값 + 검증
    if weights is None:
        weights = dict(DEFAULT_WEIGHTS)
    validate_weights(weights)

    # 모델
    selected_model = model or DEFAULT_MODEL

    # mock 판정
    is_mock = _is_mock_mode(selected_model, force_mock=force_mock)
    if selected_model == "mock":
        # 명시 mock 호출 시 model 라벨도 'mock'
        model_label = "mock"
    elif is_mock:
        # 환경 미설정으로 자동 mock 시도 — 라벨에 명시
        model_label = f"mock(auto:no_api_key)" if not os.environ.get("ANTHROPIC_API_KEY") else "mock"
    else:
        model_label = selected_model

    # lawear-e571/typo-system (2026-05-19) — 정적 사전 1차 패스
    # 음성 STT 오타 교정 (조문 번호 인접은 보호). 교정본을 grader 에게 전달.
    typo_corrections_static: list[dict[str, Any]] = []
    user_answer_for_grader = user_answer or ""
    try:
        import typo_corrector as _tc
        corrected, typo_corrections_static = _tc.correct(user_answer_for_grader)
        if typo_corrections_static:
            user_answer_for_grader = corrected
    except Exception as e:  # noqa: BLE001 — 사전 미존재/파싱 실패 graceful
        print(f"[Grader] typo_corrector skipped: {type(e).__name__}: {e}", file=sys.stderr)

    # 프롬프트 빌드 (교정본 사용 — AI 가 오타에 끌리지 않도록)
    system_prompt, user_message = _build_prompt(case_meta, user_answer_for_grader, weights)

    raw_response: str | None = None
    usage: dict[str, Any] = {}

    if is_mock:
        print(f"[Grader] MOCK mode (model_label={model_label}) case_id={case_meta.get('id')}", file=sys.stderr)
        parsed = _mock_response(case_meta, user_answer, weights)
    else:
        # 실 API 호출
        try:
            raw_response, usage = _call_anthropic(
                system_prompt, user_message, model=selected_model
            )
        except (GraderApiKeyMissingError, GraderRateLimitError, GraderBadGatewayError):
            raise
        # JSON 파싱
        parsed = _parse_response(raw_response)

    # lawear-6be6 #6 — 두문자 제안 후처리 (dismiss-only, mnemonic_lib 자동 주입)
    # 부장판사 QA P0 fix: dev-design 명세 필드명 변환 (mnemonic_text/expansion/source/
    #   applicable_missing_critical/role) + dict 구조 {judge, lecturer} 유지.
    try:
        import mnemonic_lib as _ml
        subject_kor = case_meta.get("subject_kor") or ""
        missing_critical = parsed.get("eval_notes", {}).get("missing_critical") or []

        judge_typed: list[dict] = []
        lecturer_typed: list[dict] = []
        for mc in missing_critical:
            item_text = (mc.get("item") if isinstance(mc, dict) else str(mc)) or ""
            if not item_text.strip():
                continue
            raw_judge = _ml.match_missing_to_mnemonic(
                [{"item": item_text}], subject_kor, role="judge", limit=3
            )
            raw_lecturer = _ml.match_missing_to_mnemonic(
                [{"item": item_text}], subject_kor, role="lecturer", limit=3
            )
            for r in raw_judge:
                judge_typed.append({"_raw": r, "item_text": item_text})
            for r in raw_lecturer:
                lecturer_typed.append({"_raw": r, "item_text": item_text})

        def _to_spec(typed_list: list[dict], role: str) -> list[dict]:
            """mnemonic_lib raw → dev-design 명세 필드명 변환 + dedup by source_entry + cap 3."""
            out: list[dict] = []
            seen: set[str] = set()
            for entry in typed_list:
                r = entry["_raw"]
                item_text = entry["item_text"]
                source = r.get("source_entry") or ""
                if not source or source in seen:
                    continue
                seen.add(source)
                letters = r.get("suggested_letters") or []
                keywords = r.get("suggested_keywords") or ""
                mnemonic_text = "[em1]" + "[/em1]·[em1]".join(letters) + "[/em1]" if letters else ""
                # expansion 우선순위: suggested_keywords (str/list) > 빈 문자열
                # (lib_section은 H2 prefix "1" 같은 무의미 값일 수 있어 fallback 제외)
                if isinstance(keywords, str):
                    expansion = keywords.strip()
                elif isinstance(keywords, list):
                    expansion = ", ".join(str(k) for k in keywords if k)
                else:
                    expansion = ""
                out.append({
                    "mnemonic_text": mnemonic_text,
                    "expansion": expansion,
                    "source": source,
                    "applicable_missing_critical": item_text,
                    "role": role,
                })
                if len(out) >= 3:
                    break
            return out

        judge_final = _to_spec(judge_typed, "judge")
        lecturer_final = _to_spec(lecturer_typed, "lecturer")

        if judge_final or lecturer_final:
            parsed.setdefault("eval_notes", {})["mnemonic_suggestions"] = {
                "judge": judge_final,
                "lecturer": lecturer_final,
            }
    except Exception as e:
        print(f"[Grader] mnemonic_lib skipped: {type(e).__name__}: {e}", file=sys.stderr)

    # 점수 산정
    total, score_max, pct, grade_letter = _compute_score(parsed["criteria"], weights)

    # criteria 에 weight 주입 (응답엔 없음)
    criteria_with_weight: list[dict[str, Any]] = []
    for c in parsed["criteria"]:
        key = c.get("key")
        if key not in CRITERION_KEYS:
            continue
        criteria_with_weight.append(
            {
                "key": key,
                "score": c.get("score"),
                "max": c.get("max"),
                "weight": int(weights.get(key, 0)),
                "comment": c.get("comment", ""),
            }
        )

    elapsed = time.monotonic() - started

    # lawear-e571/typo-system — eval_notes.typo_corrections 누적
    # AI 가 발견한 추가 항목 + 정적 사전 매칭 결과를 합산 (중복 from 키 제거).
    eval_notes_out = dict(parsed["eval_notes"])
    ai_corrections_raw = eval_notes_out.get("typo_corrections")
    ai_corrections: list[dict[str, Any]] = []
    if isinstance(ai_corrections_raw, list):
        for item in ai_corrections_raw:
            if isinstance(item, dict) and item.get("from"):
                ai_corrections.append(item)
    # 정적 사전 결과를 우선 (이미 매칭), AI 추가는 from 기준 중복 제거
    seen_from: set[str] = {c.get("from") for c in typo_corrections_static if c.get("from")}
    merged: list[dict[str, Any]] = list(typo_corrections_static)
    for ai_c in ai_corrections:
        f = ai_c.get("from")
        if f and f not in seen_from:
            merged.append(ai_c)
            seen_from.add(f)
    eval_notes_out["typo_corrections"] = merged if merged else None

    result = {
        "model": model_label,
        "score_total": round(total, 2),
        "score_max": round(score_max, 2),
        "score_pct": round(pct, 2),
        "grade": grade_letter,
        "weights_applied": dict(weights),
        "criteria": criteria_with_weight,
        "eval_notes": eval_notes_out,
        "diff_segments": parsed.get("diff_segments", []),
        "raw_response": raw_response,
        "usage": usage,
        "elapsed_sec": round(elapsed, 3),
        "is_mock": is_mock,
    }

    print(
        f"[Grader] done case_id={case_meta.get('id')} score={result['score_total']}/"
        f"{result['score_max']} pct={result['score_pct']} grade={grade_letter} "
        f"time={elapsed:.2f}s mock={is_mock}",
        file=sys.stderr,
    )
    return result


# ─── Step 24-4: 다중 설문 D안 카드별 채점 ──────────────────────────────


def _build_prompt_subq(
    case: dict[str, Any],
    subq: dict[str, Any],
    user_answer: str,
    hints_used_steps: list[int] | None = None,
) -> tuple[str, str]:
    """카드별(하위 설문) 채점 프롬프트 빌드.

    dev-design archive §3-7 + dev-impl-plan Phase 1 Step 24-4.

    Step 24-4 핵심:
    - 다중 설문 .md → ``cases.parse_md_subqs`` 결과 카드 1건 = 1 prompt.
    - 사용자 답안 textarea_i 와 답안지(`### 설문 N 답안` body) 를 1:1 매칭.
    - 힌트 단계는 **메타** (점수 영향 X) — 프롬프트에 "참고: 사용자가 N단계 힌트 사용"
      문구만 첨부. R-09 (자의적 해석 금지) 준수 — 단계별 페널티 없음.

    Args:
        case: 전체 케이스 dict (id, subject_kor, category, file, case_no, title,
              points, md_body, common_facts 등). subq 가 부분 정보만 가져
              상위 메타는 case 에서 보완.
        subq: 카드 1건 — ``cases.parse_md_subqs`` 항목 구조:
              ``{"key": str, "score_max": int|None, "body": str, "answer": str}``
              (확장 키 ``facts_body``/``label`` 도 허용).
        user_answer: 사용자가 textarea_i 에 입력한 답안 텍스트.
        hints_used_steps: 해당 카드에서 노출된 힌트 단계 list (1~5). 빈 list / None 허용.

    Returns:
        (system_prompt, user_message) — system 은 SYSTEM_PROMPT 동일 (캐시 적중).
    """
    # 메타 안전 추출
    subject_kor = case.get("subject_kor") or case.get("subject") or ""
    category = case.get("category") or ""
    file_label = case.get("file") or ""
    case_no = case.get("case_no") or ""
    title = case.get("title") or ""
    case_id = case.get("id", "")

    # 카드 메타
    subq_key = subq.get("key") or "전체"
    subq_label = subq.get("label") or subq_key
    score_max = subq.get("score_max") or subq.get("points") or 0
    facts_body = subq.get("facts_body") or case.get("common_facts") or ""
    question_body = subq.get("body") or subq.get("question_body") or ""
    answer_body = subq.get("answer") or subq.get("answer_body") or ""

    # 힌트 메타 — 점수 영향 X, 프롬프트에 정보 제공만
    hints_used_steps = hints_used_steps or []
    if hints_used_steps:
        # 1~5 범위 유효한 step 만 정렬
        valid_steps = sorted({int(s) for s in hints_used_steps if isinstance(s, (int, float)) and 1 <= int(s) <= 5})
        if valid_steps:
            steps_str = ", ".join(str(s) for s in valid_steps)
            hint_note = (
                f"\n[힌트 사용 메타 (점수 영향 X — 참고만)]\n"
                f"이 카드에서 사용자가 노출한 힌트 단계: {steps_str}\n"
                f"(1=목차 / 2=두문자 / 3=조문+키워드 / 4=결론+근거 / 5=전체답안)\n"
                f"힌트 사용은 채점에 영향을 주지 마세요. R-09 자의적 해석 금지.\n"
            )
        else:
            hint_note = ""
    else:
        hint_note = ""

    # user_message — 카드 1건의 본문/답안 + 사용자 답안
    user_message = f"""[케이스 ID] {case_id}
[과목] {subject_kor} · {category} · {file_label} · 케이스 {case_no}
[제목] {title}
[하위 설문] {subq_label} (배점 {score_max}점)

[공통 사실관계 (모든 카드 공유)]
{facts_body or "(없음)"}

[이 카드의 문제 본문]
{question_body or "(없음)"}

[이 카드의 답안지 (정답 — 강조 태그 보존)]
{answer_body or "(없음)"}
{hint_note}
[사용자 답안 (이 카드)]
{user_answer}

위 채점 9기준에 따라 **이 카드에 대해서만** JSON 형식으로 평가하세요.
다른 카드(설문)는 별도로 채점됩니다 — 이 prompt 에서는 무관.
JSON 외 텍스트 금지.
"""
    return SYSTEM_PROMPT, user_message


def grade_attempt_subq(
    case: dict[str, Any],
    attempt: dict[str, Any],
    weights: dict[str, int] | None = None,
    *,
    model: str | None = None,
    force_mock: bool | None = None,
) -> dict[str, Any]:
    """다중 설문 D안 — 카드별 채점 + 부분 매칭 합산.

    dev-design archive §3-3 / §3-4 / §3-7 + dev-impl-plan Phase 1 Step 24-4.

    Step 24-4 핵심:
    - ``attempt["answer_subq"]`` (dict) 각 카드 → grader API 1회 호출 (총 N회).
    - 카드별 9기준 채점 결과를 ``criteria_subq`` dict 로 묶음.
    - **부분 매칭** (사용자 결정 Q10):
        - 풀린 카드 (빈 문자열 아닌 답안) 만 합산.
        - 빈 카드 (textarea empty) 는 score_max 합산에서 제외.
    - hints_used 는 카드별 메타 — 프롬프트에 첨부, 점수 영향 X.

    Args:
        case: 전체 케이스 dict (id, subject_kor, ..., subqs?, common_facts).
              ``subqs`` 가 있으면 cards 로 사용, 없으면 ``answer_subq`` 키 만 카드로 처리
              (테스트 / fallback 호환).
        attempt: dict — 최소 키 ``answer_subq``. 옵션 ``hints_used`` / ``subq_elapsed``.
            - ``answer_subq``: ``{subq_key: 답안 텍스트}``
            - ``hints_used``: ``{subq_key: list[int]}`` (1~5 step). 없으면 ``{}``.
        weights: 9기준 가중치 (None → DEFAULT_WEIGHTS). 모든 카드에 동일 적용.
        model: 모델명 (None → DEFAULT_MODEL).
        force_mock: True/False 명시 강제 (테스트용).

    Returns:
        {
          "model":           "claude-opus-4-7" 또는 "mock(auto:...)",
          "score_total":     float,             부분 매칭 합산 가중치 기준 점수
          "score_max":       float,             풀린 카드의 score_max 합 (빈 카드 제외)
          "score_pct":       float,             0~100 클램프
          "grade":           "A"|"B"|"C"|"F",
          "weights_applied": dict[str, int],
          "criteria_subq":   {subq_key: [9 criteria]},
          "eval_notes_subq": {subq_key: {strength, caution, missing}},
          "diff_subq":       {subq_key: [diff_segments]},
          "solved_cards":    list[str],        실제로 풀이된 카드 키
          "skipped_cards":   list[str],        빈 카드 키
          "subq_count":      int,              풀린 카드 수
          "is_mock":         bool,
          "elapsed_sec":     float,
        }

    Raises:
        ValueError: weights 검증 실패 / answer_subq 누락.
        GraderApiKeyMissingError, GraderRateLimitError, GraderBadGatewayError,
        GraderParseError: 단일 카드 채점 실패 시 그대로 전파 (호출자가 처리).
    """
    started = time.monotonic()

    # 가중치 검증
    if weights is None:
        weights = dict(DEFAULT_WEIGHTS)
    validate_weights(weights)

    answer_subq = attempt.get("answer_subq")
    if not isinstance(answer_subq, dict) or not answer_subq:
        raise ValueError("attempt.answer_subq must be non-empty dict for grade_attempt_subq")

    hints_used = attempt.get("hints_used") or {}
    if not isinstance(hints_used, dict):
        hints_used = {}

    # 카드 정보 인덱싱 (case.subqs 가 있으면 사용, 없으면 answer_subq 키 그대로)
    subq_index: dict[str, dict[str, Any]] = {}
    case_subqs = case.get("subqs") if isinstance(case.get("subqs"), list) else None
    if case_subqs:
        for sq in case_subqs:
            if isinstance(sq, dict) and sq.get("key"):
                subq_index[sq["key"]] = sq

    # 모델 + mock 판정 (한번만 결정)
    selected_model = model or DEFAULT_MODEL
    is_mock = _is_mock_mode(selected_model, force_mock=force_mock)
    if selected_model == "mock":
        model_label = "mock"
    elif is_mock:
        model_label = "mock(auto:no_api_key)" if not os.environ.get("ANTHROPIC_API_KEY") else "mock"
    else:
        model_label = selected_model

    criteria_subq: dict[str, list[dict[str, Any]]] = {}
    eval_notes_subq: dict[str, dict[str, str]] = {}
    diff_subq: dict[str, list[dict[str, str]]] = {}
    solved_cards: list[str] = []
    skipped_cards: list[str] = []

    # 부분 점수 합산 — 풀린 카드만 sum(weighted) / sum(score_max_per_card)
    total_weighted_sum: float = 0.0
    total_score_max_sum: float = 0.0

    # lawear-e571/typo-system (2026-05-19) — 다중 설문 typo_corrections 누적
    # 모든 카드의 정적 사전 매칭 + AI 발견 항목을 카드별 dict 로 합산.
    typo_corrections_per_card: dict[str, list[dict[str, Any]]] = {}
    try:
        import typo_corrector as _tc  # 카드 외부 1회 import
        _typo_dict = _tc.load_typo_dict()
    except Exception as e:  # noqa: BLE001
        _tc = None
        _typo_dict = None
        print(f"[Grader] typo_corrector skipped (subq): {type(e).__name__}: {e}", file=sys.stderr)

    # 카드 순회 — answer_subq 의 키 순서 유지 (Python 3.7+ dict 보존)
    for subq_key, user_answer in answer_subq.items():
        # 빈 카드는 skip (부분 매칭 — score_max 합산에서 제외)
        if not isinstance(user_answer, str) or not user_answer.strip():
            skipped_cards.append(subq_key)
            continue

        # 카드 메타 추출 (case.subqs 우선, 없으면 키만 가진 stub)
        subq_meta = subq_index.get(subq_key, {"key": subq_key, "score_max": None, "body": "", "answer": ""})

        # 힌트 메타 (카드별)
        steps = hints_used.get(subq_key) or []
        if not isinstance(steps, list):
            steps = []

        # 음성 STT 정적 사전 1차 패스 (카드별)
        user_answer_for_grader = user_answer
        if _tc is not None and _typo_dict is not None:
            try:
                corrected, card_corrections = _tc.apply_static_replacements(user_answer, _typo_dict)
                if card_corrections:
                    typo_corrections_per_card[subq_key] = card_corrections
                    user_answer_for_grader = corrected
            except Exception as e:  # noqa: BLE001
                print(f"[Grader] typo_corrector card={subq_key} skipped: {type(e).__name__}: {e}", file=sys.stderr)

        # 프롬프트 생성 (교정본 사용)
        system_prompt, user_message = _build_prompt_subq(case, subq_meta, user_answer_for_grader, steps)

        # 채점 호출 (mock 또는 실 API)
        raw_resp: str | None = None
        if is_mock:
            print(
                f"[Grader] MOCK subq case_id={case.get('id')} subq={subq_key!r}",
                file=sys.stderr,
            )
            parsed = _mock_response(case, user_answer, weights)
        else:
            raw_resp, _usage = _call_anthropic(system_prompt, user_message, model=selected_model)
            parsed = _parse_response(raw_resp)

        # 카드별 점수 계산 (각 카드 max=89 기준이지만 부분 점수는 weight 비율로 sum)
        card_weighted, card_max, _card_pct, _card_grade = _compute_score(parsed["criteria"], weights)
        total_weighted_sum += card_weighted
        total_score_max_sum += card_max

        # criteria 에 weight 주입 (응답엔 없음)
        criteria_with_weight: list[dict[str, Any]] = []
        for c in parsed["criteria"]:
            key = c.get("key")
            if key not in CRITERION_KEYS:
                continue
            criteria_with_weight.append({
                "key": key,
                "score": c.get("score"),
                "max": c.get("max"),
                "weight": int(weights.get(key, 0)),
                "comment": c.get("comment", ""),
            })

        # CRITERION_KEYS 순서로 정렬
        by_key = {c["key"]: c for c in criteria_with_weight}
        ordered = [by_key[k] for k in CRITERION_KEYS if k in by_key]

        criteria_subq[subq_key] = ordered
        card_eval_notes = dict(parsed.get("eval_notes") or {})
        # 카드별 정적 사전 typo_corrections + AI 발견 항목 합산
        static_corr = typo_corrections_per_card.get(subq_key, [])
        ai_corr_raw = card_eval_notes.get("typo_corrections")
        ai_corr: list[dict[str, Any]] = []
        if isinstance(ai_corr_raw, list):
            for it in ai_corr_raw:
                if isinstance(it, dict) and it.get("from"):
                    ai_corr.append(it)
        seen: set[str] = {c.get("from") for c in static_corr if c.get("from")}
        merged_card: list[dict[str, Any]] = list(static_corr)
        for ai_c in ai_corr:
            f = ai_c.get("from")
            if f and f not in seen:
                merged_card.append(ai_c)
                seen.add(f)
        card_eval_notes["typo_corrections"] = merged_card if merged_card else None
        eval_notes_subq[subq_key] = card_eval_notes
        diff_subq[subq_key] = parsed.get("diff_segments", []) or []
        solved_cards.append(subq_key)

    # 부분 매칭 — 풀린 카드 합산 기준 pct
    if total_score_max_sum > 0:
        pct = (total_weighted_sum / total_score_max_sum) * 100.0
    else:
        # 모든 카드가 빈 답안 — 0점 처리
        pct = 0.0
    pct = max(0.0, min(100.0, pct))

    grade_letter = "F"
    for threshold, g in GRADE_THRESHOLDS:
        if pct >= threshold:
            grade_letter = g
            break

    elapsed = time.monotonic() - started

    # 전체 typo_corrections flat 요약 (eval_notes 로 노출 — _normalize_subq_grades 호환)
    flat_typo: list[dict[str, Any]] = []
    seen_flat: set[str] = set()
    for sk in solved_cards:
        for c in (eval_notes_subq.get(sk, {}).get("typo_corrections") or []):
            f = c.get("from") if isinstance(c, dict) else None
            if f and f not in seen_flat:
                flat_typo.append(c)
                seen_flat.add(f)

    result = {
        "model": model_label,
        "score_total": round(total_weighted_sum, 2),
        "score_max": round(total_score_max_sum, 2),
        "score_pct": round(pct, 2),
        "grade": grade_letter,
        "weights_applied": dict(weights),
        "criteria_subq": criteria_subq,
        "eval_notes_subq": eval_notes_subq,
        "diff_subq": diff_subq,
        "solved_cards": solved_cards,
        "skipped_cards": skipped_cards,
        "subq_count": len(solved_cards),
        "typo_corrections_flat": flat_typo if flat_typo else None,
        "is_mock": is_mock,
        "elapsed_sec": round(elapsed, 3),
    }

    print(
        f"[Grader] subq done case_id={case.get('id')} cards={len(solved_cards)}/"
        f"{len(answer_subq)} skipped={len(skipped_cards)} "
        f"score={result['score_total']}/{result['score_max']} pct={pct:.2f} "
        f"grade={grade_letter} time={elapsed:.2f}s mock={is_mock}",
        file=sys.stderr,
    )
    return result


def _normalize_subq_grades(grade_dict: dict[str, Any]) -> dict[str, Any]:
    """legacy grade() 결과와 subq grade 결과를 통일 형식으로 정규화.

    dev-design archive §3-4 (_attempt_row_to_dict 응답 호환).

    legacy ``grade()`` 결과 (1차원 criteria) → ``criteria_subq = {"전체": criteria}`` wrap.
    grade_attempt_subq() 결과 (이미 criteria_subq) → 그대로 두고 legacy ``criteria`` 키
    1차원 array 도 보강 (단일 카드 케이스에서 호환).

    한글 카드 키는 보존 (ensure_ascii=False).

    Args:
        grade_dict: ``grade()`` 또는 ``grade_attempt_subq()`` 반환 dict.

    Returns:
        통일된 형식:
          - "criteria_subq":   dict (필수 — 단일이라도 {"전체": [...] } wrap)
          - "eval_notes_subq": dict
          - "diff_subq":       dict
          - "criteria":        list (단일 카드 호환, 첫 카드 또는 "전체")
          - "eval_notes":      dict (첫 카드 또는 "전체")
          - 기존 메타키 (score_total/max/pct/grade/weights_applied/is_mock/elapsed_sec) 보존
    """
    if not isinstance(grade_dict, dict):
        raise ValueError(f"grade_dict must be dict, got {type(grade_dict).__name__}")

    out = dict(grade_dict)  # shallow copy — 원본 안 건드림

    # 이미 criteria_subq 가 있으면 (grade_attempt_subq 결과) → criteria/eval_notes 도 호환 보강
    if "criteria_subq" in out and isinstance(out["criteria_subq"], dict):
        subq_map = out["criteria_subq"]
        # 단일 카드면 legacy criteria 키도 채워 호환 (첫 카드)
        if len(subq_map) == 1:
            first_key = next(iter(subq_map))
            if "criteria" not in out:
                out["criteria"] = list(subq_map[first_key])
            # eval_notes 호환
            if "eval_notes" not in out:
                notes_subq = out.get("eval_notes_subq", {})
                if isinstance(notes_subq, dict) and first_key in notes_subq:
                    out["eval_notes"] = notes_subq[first_key]
            # diff_segments 호환
            if "diff_segments" not in out:
                diff_subq_map = out.get("diff_subq", {})
                if isinstance(diff_subq_map, dict) and first_key in diff_subq_map:
                    out["diff_segments"] = diff_subq_map[first_key]
        return out

    # legacy grade() 결과 → criteria_subq = {"전체": criteria} wrap
    legacy_criteria = out.get("criteria")
    if isinstance(legacy_criteria, list):
        out["criteria_subq"] = {"전체": list(legacy_criteria)}
    else:
        out["criteria_subq"] = {}

    legacy_notes = out.get("eval_notes")
    if isinstance(legacy_notes, dict):
        out["eval_notes_subq"] = {"전체": dict(legacy_notes)}
    else:
        out["eval_notes_subq"] = {}

    legacy_diff = out.get("diff_segments")
    if isinstance(legacy_diff, list):
        out["diff_subq"] = {"전체": list(legacy_diff)}
    else:
        out["diff_subq"] = {}

    return out


def grade_attempt(
    case: dict[str, Any],
    attempt: dict[str, Any],
    weights: dict[str, int] | None = None,
    *,
    model: str | None = None,
    force_mock: bool | None = None,
) -> dict[str, Any]:
    """Step 24-4 attempt 채점 분기 진입점 (legacy + 다중 설문 자동 라우팅).

    dev-design archive §3-2 + dev-impl-plan Phase 1 Step 24-4.

    분기:
    - ``attempt["answer_subq"]`` 가 non-empty dict → ``grade_attempt_subq()`` 위임.
    - 그 외 (None / 빈 dict) → 기존 ``grade()`` 로직 (legacy answer_text 단일 모드).

    Args:
        case:    cases.get_case() 결과 dict (id, subject_kor, ..., md_body, subqs?).
        attempt: attempt dict — ``answer_text`` (legacy) 또는 ``answer_subq`` (신규 D안).
                 옵션 ``hints_used``/``subq_elapsed``.
        weights: 9기준 가중치 (None → DEFAULT_WEIGHTS).
        model:   Claude 모델명 (None → DEFAULT_MODEL).
        force_mock: 테스트용 강제 mock.

    Returns:
        legacy 분기 시: ``grade()`` 결과 그대로 (criteria/eval_notes/diff_segments 1차원).
        다중 분기 시:  ``grade_attempt_subq()`` 결과 그대로 (criteria_subq dict).
        호출자에서 통일 형식이 필요하면 ``_normalize_subq_grades()`` 추가 호출.

    Raises:
        ValueError: weights 또는 attempt 검증 실패.
        Grader*Error: 채점 실패 (legacy 와 동일하게 전파).
    """
    if not isinstance(attempt, dict):
        raise ValueError(f"attempt must be dict, got {type(attempt).__name__}")

    answer_subq = attempt.get("answer_subq")
    if isinstance(answer_subq, dict) and answer_subq:
        # 다중 설문 분기
        return grade_attempt_subq(
            case, attempt, weights, model=model, force_mock=force_mock
        )

    # legacy 분기 — answer_text 추출
    answer_text = attempt.get("answer_text") or ""
    return grade(case, answer_text, weights, model=model, force_mock=force_mock)


# ─── CLI (수동 실 호출 테스트용) ────────────────────────────────────────


def main() -> int:
    """CLI: python3 grader.py --case CASE_ID [--answer-file PATH] [--mock]

    실 API 호출 또는 mock 시뮬레이션. 결과 JSON 을 stdout 으로 출력.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Lawear Grader CLI (단위 테스트/디버그용)")
    parser.add_argument("--case", help="case_id (DB 조회). 없으면 --case-json 사용")
    parser.add_argument(
        "--case-json", help="case_meta JSON 파일 경로 (DB 없이 직접 주입)"
    )
    parser.add_argument(
        "--answer",
        default="테스트 답안: A조합은 비법인사단으로 권리능력 범위 내에서 도급계약을 체결하였다.",
        help="사용자 답안 텍스트",
    )
    parser.add_argument("--answer-file", help="답안 파일 (--answer 우선)")
    parser.add_argument("--mock", action="store_true", help="mock 모드 강제")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"모델 (기본 {DEFAULT_MODEL})")
    args = parser.parse_args()

    # env 로드 (있으면)
    try:
        from env_loader import load_env
        load_env()
    except ImportError:
        pass

    # case_meta 로드
    case_meta: dict[str, Any]
    if args.case_json:
        with open(args.case_json, encoding="utf-8") as f:
            case_meta = json.load(f)
    elif args.case:
        # DB 조회
        import db as db_mod
        import cases as cases_mod

        db_path = os.environ.get(
            "LAWEAR_EXAM_DB",
            str(Path(__file__).parent.resolve() / "exam.db"),
        )
        with db_mod.get_conn(db_path) as conn:
            case_meta = cases_mod.get_case(conn, args.case)
    else:
        # 더미 case_meta (mock 테스트)
        case_meta = {
            "id": "test_case_dummy",
            "subject_kor": "민법",
            "category": "테스트",
            "file": "test01",
            "case_no": "01",
            "title": "더미 케이스",
            "points": 17,
            "md_body": "## 원본\n사실관계 + 문제 + 답안 dummy\n## Lv.1\n목차 dummy",
        }

    # 답안 파일 우선
    if args.answer_file:
        with open(args.answer_file, encoding="utf-8") as f:
            user_answer = f.read()
    else:
        user_answer = args.answer

    # mock 강제
    force_mock = True if args.mock else None
    model = "mock" if args.mock else args.model

    result = grade(case_meta, user_answer, model=model, force_mock=force_mock)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
