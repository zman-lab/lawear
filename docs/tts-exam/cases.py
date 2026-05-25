#!/usr/bin/env python3
"""케이스 API 비즈니스 로직 (Step 4).

dev-design archive #48 §4-2 (DB) / dev-impl-plan #51 Step 4 1:1.

핵심:
- `list_cases(conn, filters)`         : `GET /api/cases`     (필터링 + 메타 집계)
- `get_case(conn, case_id)`           : `GET /api/cases/{id}` (메타 + .md 파일 파싱)
- `parse_md_file(md_text)`            : .md → {origin, lv1, lv4} 섹션 분리
                                        (R-28 강조 태그 [red][blue][bold][u][blank][blank2] 보존)

설계 결정:
- BASE_PATH: dev-impl-plan §5 Q21 A 결정 — `/Users/nhn/zman-lab/lawear/docs/tts-new` 디스크 직접 read
  (env LAWEAR_TTS_BASE 우선)
- 필터: dev-design #48 §3-1 endpoint 2 — `?filter=all|err|stale|book` + 확장 `subject/category/file/search`
  (dev-impl-plan #51 Step 4 표 '+filter (all/err/stale/book)' 기반, search 는 title LIKE)
- 섹션 분리: `^## ` 헤더 기준 split.
  - `## 원본 (NN점)` → origin
  - `## Lv.1 빠른복습`  → lv1
  - `## Lv.4 암기노트` → lv4 (괄호 안 설명 무관, 'Lv.4' 접두만 매칭)
  - `## 메타` → meta (선택)
- 강조 태그는 텍스트에 raw 로 포함 (브라우저/클라이언트가 파싱).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

# ─── 설정 (env 우선) ───────────────────────────────────────────────
BASE_PATH: Path = Path(
    os.environ.get("LAWEAR_TTS_BASE", "/Users/nhn/zman-lab/lawear/docs/tts-new")
).resolve()

# 법제처 조문명 캐시 (부등법 [case] 태그 → 법/규칙 + 조문명 lookup)
# - lawArticles.json: title + path (주된 소스, 21개 법령)
# - law_titles_cache.json: title (fallback, 13개 법령)
# 둘 다 본문 body 미보유 → R-09 강제로 조문명만 표시 (본문 인용 금지).
_LAW_ARTICLES_PATH = Path(
    os.environ.get(
        "LAWEAR_LAW_ARTICLES_JSON",
        "/Users/nhn/zman-lab/lawear/web/src/data/lawArticles.json",
    )
)
_LAW_TITLES_PATH = Path(
    os.environ.get(
        "LAWEAR_LAW_TITLES_JSON",
        "/Users/nhn/zman-lab/lawear/docs/lawear-7ad6_input_mode_3subjects/law_titles_cache.json",
    )
)
# 모듈 레벨 캐시 (lazy 로드, 1회만)
_LAW_TITLE_INDEX: dict[str, dict[str, str]] | None = None

# 필터 enum (dev-design #48 §3-1)
# 'book' = dev-design 정본, 'bookmarked' = 사용자 사양 alias (Step 9 wire)
ALLOWED_FILTERS = {"all", "err", "stale", "book", "bookmarked"}

# alias 정규화: 클라이언트가 보낸 값 → 내부 정규형
_FILTER_ALIASES = {
    "bookmarked": "book",
}


class CaseNotFoundError(Exception):
    """케이스 ID 미존재 (HTTP 404 매핑)."""


class CaseFileMissingError(Exception):
    """cases.path 가 가리키는 .md 파일이 디스크에 없음 (HTTP 500)."""


# ─── .md 파싱 ──────────────────────────────────────────────────────

# `^## (헤더명)` 매칭 — 헤더명 캡쳐. 헤더 줄 자체는 결과에 포함하지 않음.
_HEADER_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


# 점수 추출 정규식 2종 (lawear-c63e-sub4 2026-05-21 게시판 #2138 §Sub4):
#
# 1) `## 원본 (NN점)` 헤더 패턴 — 괄호 안 합산표시 OK (닫는 괄호 의존 X).
#    예: `원본 (17점)` / `원본 (20점 + 보충 10점)` / `원본 (20점 (설문 1=13점, ...))`
# 2) `- 점수: NN점` 메타 라인 패턴 — fallback 용 (헤더에서 추출 실패 시).
#    예: `- 점수: 50점 (13+12+10+15)` / `- 점수: 20점 + 보충문제 75점 = 95점`
#
# R-09: 첫 번째 `\d+점` 토큰만 추출 — 합산/보충 등 추가 표시는 무시 (자의 해석 X).
_SCORE_HEADER_RE = re.compile(r"\((\d+)\s*점")
_SCORE_META_RE = re.compile(r"^-\s*점수:\s*(\d+)\s*점", re.MULTILINE)


# `[blank2]X[/blank2]` 인라인 강조 태그 매칭 (글자 단위, non-greedy).
# 예: `[blank2]무[/blank2]` → group1 = "무"
#     `[blank2]단체[/blank2]` → group1 = "단체"
# R-09: 자의적 해석 X — 태그 안 글자 그대로 추출, 정답 노출 방지를 위해 다른 텍스트는 사용 X.
_BLANK2_TAG_RE = re.compile(r"\[blank2\]([\s\S]+?)\[/blank2\]")

# `[blank]X[/blank]` cloze 빈칸 태그 매칭 (lawear-23d9 — 17896 민사서류 1라운드).
# `[blank2]` 와는 별개 — `[blank]` 는 7글자 (`[`,`b`,`l`,`a`,`n`,`k`,`]`), `[blank2]` 는 8글자.
# 정규식 \[blank\] 는 정확히 `[blank]` 7글자만 매칭. `[blank2]` 와 자동 분리됨 (글자 길이 다름).
# 예: `[blank]연대하여[/blank]` → group1 = "연대하여"
#     `[blank]2022. 7. 1.[/blank]` → group1 = "2022. 7. 1." (정답이 숫자로 시작해도 OK)
# R-09 (자의 해석 금지): 태그 내부 문자 그대로 추출. AI 보강 X.
_BLANK_TAG_RE = re.compile(r"\[blank\]([\s\S]+?)\[/blank\]")


def _extract_blank2_chars(text: str) -> list[str]:
    """`[blank2]X[/blank2]` 태그 안 글자(들)만 순서대로 추출.

    Args:
        text: 검색 대상 본문 (str). None/빈 문자열 OK.

    Returns:
        매칭된 태그 콘텐츠 list (순서 보존, 중복 제거 X).
        예: ``"[blank2]무[/blank2]...[blank2]기[/blank2]"`` → ``["무", "기"]``
        매칭 0건이면 빈 list.

    R-09 (자의적 해석 금지): 태그 사이 raw 글자 그대로 — 두문자 줄임/추측 X.
    Lv.2 힌트 노출에 사용 (정답 본문은 노출 X, 태그 콘텐츠만 시각 단서).
    """
    if not text:
        return []
    return [m.group(1) for m in _BLANK2_TAG_RE.finditer(text)]


def extract_blank_answers(text: str) -> tuple[dict[str, str], str, int]:
    """`[blank]X[/blank]` cloze 정답 추출 + UI placeholder 치환 (lawear-23d9 17896 민사서류).

    Args:
        text: 검색 대상 본문 (보통 subq.body — 청구취지 cloze 본문).

    Returns:
        ``(blanks, body_with_placeholders, blank_count)``:

        - ``blanks``: ``{"blank_1": "연대하여", "blank_2": "2022.7.1.", ...}``
          정답값 (인덱스 1부터, [bold]/[b]/[em1] 토큰 보존 — grader 가중치 판정용).
        - ``body_with_placeholders``: 본문에서 ``[blank]X[/blank]`` →
          ``<input type="text" data-blank-idx="N" data-card-blank>`` 치환된 HTML 문자열.
          UI 렌더 시 그대로 innerHTML 가능 (이미 HTML 형식).
        - ``blank_count``: 추출된 [blank] 개수 (정수).

        매칭 0건이면 ``({}, text, 0)`` (변경 X).

    R-09 (자의 해석 금지):
        - 정답값은 태그 안 raw 그대로 (가공/요약 X).
        - placeholder 치환은 UI 입력 컴포넌트 자리 표시만 — 정답 노출 X.

    예:
        >>> extract_blank_answers("피고들은 [blank]연대하여[/blank] 지급하라.")
        ({"blank_1": "연대하여"},
         '피고들은 <input type="text" data-blank-idx="1" data-card-blank> 지급하라.',
         1)
    """
    if not text:
        return {}, text or "", 0
    blanks: dict[str, str] = {}
    idx_counter = [0]  # 클로저용 mutable

    def _replace(m: "re.Match") -> str:
        idx_counter[0] += 1
        n = idx_counter[0]
        blanks[f"blank_{n}"] = m.group(1)
        # UI placeholder — input.data-blank-idx 로 식별, 채점 시 카드 안 input 전체 수집
        return f'<input type="text" data-blank-idx="{n}" data-card-blank class="cloze-blank-input" />'

    new_text = _BLANK_TAG_RE.sub(_replace, text)
    return blanks, new_text, idx_counter[0]


# ─── Step 24-2 다중 설문 정규식 3종 (8 .md 14 헤더 전수 100% 매칭) ───
#
# 패턴 A: `### 설문 1 (20점)`              — 민법 모고01_01, 민소 모고02_01/02
# 패턴 B: `### 설문 (1) (12점)`            — 민소 모고01_01/02 (괄호 안 숫자)
# 패턴 C: `### 설문 1 가 (12점)`           — 민법 모고02_01/02 (가/나 하위)
#
# `### 설문 N 답안` / `### 설문 N 가 답안` 은 `_SUBQ_HEADER_RE` 에 매칭 X
# (정규식 끝의 `\s*$` 가 "답안" 잔여를 거부).
_SUBQ_HEADER_RE = re.compile(
    r"^### (설문\s+(?:\(\d+\)|\d+))(?:\s+([가-힣]))?\s*(?:\((\d+)\s*점\))?\s*$",
    re.MULTILINE,
)

# `### 설문 N 답안` / `### 설문 (N) 답안` / `### 설문 N 가 답안` 등 답안 헤더.
_SUBQ_ANSWER_HEADER_RE = re.compile(
    r"^### (설문\s+(?:\(\d+\)|\d+))(?:\s+([가-힣]))?\s+답안\s*$",
    re.MULTILINE,
)

# `### 사실관계` / `### 공통된 사실관계` / `### 기본적 사실관계` / `### 변형된 사실관계`.
# group1=prefix(공통된|기본적|변형된) 또는 None(prefix 없음).
_FACTS_HEADER_RE = re.compile(
    r"^### (공통된|기본적|변형된)?\s*사실관계\s*$",
    re.MULTILINE,
)

# lawear-23d9 (2026-05-25) — 17896 민사서류 cloze .md H2 문제 헤더.
# 예: `## 문제 1. 연대하여 — 연대채무 (2인 연대채무자)`
#     `## 문제 5. 공동하여 — 공동불법행위 (손괴)`
# group1 = 문제 번호 ("1", "5"), group2 = 제목 (옵션).
_CLOZE_PROBLEM_HEADER_RE = re.compile(
    r"^## 문제\s+(\d+)\.\s*(.*?)\s*$",
    re.MULTILINE,
)

# cloze .md 청구취지 헤더 (`### 청구취지 (cloze)` 또는 `### 청구취지`).
_CLOZE_TARGET_HEADER_RE = re.compile(
    r"^### 청구취지(?:\s*\(cloze\))?\s*$",
    re.MULTILINE,
)

# cloze .md 힌트 헤더 (`### 힌트 (5단계)` 또는 `### 힌트`).
_CLOZE_HINT_HEADER_RE = re.compile(
    r"^### 힌트(?:\s*\([^)]*\))?\s*$",
    re.MULTILINE,
)

# cloze 힌트 라인 — `- **hint_1 (라벨)**: 내용` 또는 `- **hint_2.5 (...)**: ...`.
# group1 = 단계 ("1", "2", "2.5", "3", "4", "5"), group2 = 내용.
_CLOZE_HINT_LINE_RE = re.compile(
    r"^-\s*\*\*hint_([\d.]+)\s*(?:\([^)]*\))?\*\*:\s*(.+?)\s*$",
    re.MULTILINE,
)


def parse_md_file(md_text: str) -> dict[str, str | None]:
    """.md 본문을 섹션별로 분리.

    Returns:
        {
          "origin":   "## 원본 (17점)\n\n### 사실관계\n..." (raw, 헤더 포함),
          "origin_points": 17 (None 가능),
          "lv1":      "## Lv.1 빠른복습\n\n### 문제\n...",
          "lv4":      "## Lv.4 암기노트 (사용자 스타일)\n결론...",
          "toc":      "1. 결론\n2. 이유" (## 목차 H2 본문, 헤더 제외, strip),
          "meta":     "## 메타\n- PDF: ...",
        }
        섹션 없으면 해당 키 None.
    """
    # 헤더 위치 모음
    headers: list[tuple[int, str]] = [(m.start(), m.group(1)) for m in _HEADER_RE.finditer(md_text)]
    if not headers:
        return {"origin": None, "origin_points": None, "lv1": None, "lv4": None, "toc": None, "meta": None}

    # 다음 헤더 시작 위치 = 현재 섹션의 끝
    sections: dict[str, str] = {}
    for i, (start, name) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(md_text)
        sections[name] = md_text[start:end].rstrip()

    # 분류
    origin = None
    origin_points = None
    lv1 = None
    lv4 = None
    toc = None
    meta = None

    for name, body in sections.items():
        # 부등법 alias: '## 문제' → origin / '## 답안' → lv4
        # lawear-0d65: subject_type='problem_answer' (부동산등기법) 분기
        # 헤더 alias로 처리하면 기존 attempt/UI 흐름 그대로 작동.
        if name.startswith("원본") or name.startswith("문제"):
            origin = body
            # "원본 (17점)" / "원본 (20점 + 보충 10점)" / "문제 (30점)" 등에서 첫 NN점 추출
            # (lawear-c63e-sub4 #2138 §Sub4: 닫는 괄호 의존 X)
            m = _SCORE_HEADER_RE.search(name)
            if m:
                try:
                    origin_points = int(m.group(1))
                except ValueError:
                    origin_points = None
        elif name.startswith("Lv.1"):
            lv1 = body
        elif name.startswith("Lv.4") or name.startswith("답안"):
            # 부등법 '## 답안' → lv4 (reference answer로 활용)
            lv4 = body
        elif name.startswith("목차"):
            # lawear-23d9 (P2-a, 2026-05-25): 부등법 ## 목차 H2 본문 → 답안 박스 인덱스용
            # 17895 merge.html user-toc 박스 패턴 mirror (commit 66f854b).
            # body 는 "## 목차\n\n1. 결론\n2. 이유" 형태 — 헤더 라인 제거하고 본문만 노출.
            # R-09: 원문 verbatim (요약/가공 X). 헤더 줄만 떼고 strip.
            body_lines = body.split("\n", 1)
            toc = body_lines[1].strip() if len(body_lines) > 1 else ""
            if not toc:
                toc = None
        elif name.startswith("메타"):
            meta = body

    # fallback: 원본 헤더에서 점수 추출 실패 시 메타 섹션 `- 점수: NN점` 매칭
    # (lawear-c63e-sub4 #2138 §Sub4: `- 점수: 50점 (13+12+10+15)` 등 합산표시 OK)
    if origin_points is None and meta:
        m_meta = _SCORE_META_RE.search(meta)
        if m_meta:
            try:
                origin_points = int(m_meta.group(1))
            except ValueError:
                origin_points = None

    return {
        "origin": origin,
        "origin_points": origin_points,
        "lv1": lv1,
        "lv4": lv4,
        "toc": toc,
        "meta": meta,
    }


# ─── Step 24-2 다중 설문 파싱 헬퍼 ───────────────────────────────────


def normalize_subq_key(group1: str, group2: str | None) -> str:
    """정규식 캡처 그룹 → 정규화된 subq key (`설문 N` / `설문 N 가`).

    Args:
        group1: `_SUBQ_HEADER_RE` 의 group1 (예: ``"설문 1"`` 또는 ``"설문 (1)"``).
        group2: `_SUBQ_HEADER_RE` 의 group2 (예: ``"가"``, ``"나"`` 또는 None).

    Returns:
        패턴 A `### 설문 1 (20점)`  + group2=None → ``"설문 1"``
        패턴 B `### 설문 (1) (12점)` + group2=None → ``"설문 1"`` (괄호 제거)
        패턴 C `### 설문 1 가 (12점)`+ group2="가"  → ``"설문 1 가"``
        패턴 B+C `### 설문 (1) 가 (12점)` (미래 대비) → ``"설문 1 가"``

    정규화 정책 (dev-design archive #48 G-1 Q6 A 결정):
        - DB attempt_criteria.subq_key TEXT + API JSON dict key 일관성 보장.
        - 표기 변형(괄호/공백 N개)은 통일 — R-09 자의가 아니라 키 매칭용.
    """
    # group1 예: "설문 1" / "설문 (1)" — 공백으로 split 후 [1] 가 숫자 토큰
    parts = group1.split()
    if len(parts) < 2:
        # 안전장치 (실제로는 정규식이 \s+ 강제하므로 도달 불가)
        num_part = group1.strip()
    else:
        num_part = parts[1].strip("()")  # "(1)" → "1"
    if group2:
        return f"설문 {num_part} {group2}"
    return f"설문 {num_part}"


def _extract_section_body(md_text: str, header_line_pos: int, header_match_end: int) -> str:
    """주어진 헤더 위치부터 다음 `^### ` 또는 `^## ` 헤더 전까지의 본문 추출.

    Args:
        md_text:           전체 .md 본문.
        header_line_pos:   header match 의 `start()` (= 줄 시작).
        header_match_end:  header match 의 `end()`.

    Returns:
        헤더 줄을 제외한 본문 (양옆 공백 strip).
    """
    # 다음 `### ` 또는 `## ` 헤더 찾기 (header_match_end 부터)
    # `^### ` 우선 — `^## ` 도 동시 검사 (Lv 섹션 시작이면 종료)
    next_h3 = re.search(r"^### ", md_text[header_match_end:], re.MULTILINE)
    next_h2 = re.search(r"^## ", md_text[header_match_end:], re.MULTILINE)
    candidates = []
    if next_h3:
        candidates.append(header_match_end + next_h3.start())
    if next_h2:
        candidates.append(header_match_end + next_h2.start())
    body_end = min(candidates) if candidates else len(md_text)
    return md_text[header_match_end:body_end].strip()


def parse_md_subqs_cloze(md_content: str) -> list[dict]:
    """17896 민사서류 cloze .md → subq 카드 N개 분해 (lawear-23d9 2026-05-25).

    cloze .md 구조 (cloze_simple/skeleton/full 공통):
        ## 문제 1. 제목 (h2)
        ### 조건 (h3)
        본문...
        ### 청구취지 (cloze) (h3)
        본문에 [blank]X[/blank] 포함
        ### 힌트 (5단계) (h3)
        - **hint_1 (...)**: ...
        - **hint_2 (...)**: ...
        - **hint_2.5 (...)**: ...
        ...

    Returns:
        list[dict] — 각 카드:
            ``{"key": "문제 1", "score_max": 1, "body": str, "answer": str,
              "mnemonic": str, "blanks": dict, "body_with_placeholders": str,
              "blank_count": int, "hints": dict, "is_cloze": True}``

        - ``body``: 조건 + 청구취지 (cloze) 본문 (R-09 raw verbatim).
        - ``answer``: 청구취지 정답 본문 ([blank] 제거 후 정답값 inline) — 채점 reference.
        - ``hints``: ``{"hint_1": "내용", "hint_2": "...", "hint_2.5": "..."}`` 사전 추출.
        - ``blanks``: extract_blank_answers 결과 (cloze 채점 정답값).
        - ``body_with_placeholders``: UI 렌더용 <input> 치환된 HTML.
        - ``blank_count``: 빈칸 개수.

    R-09 (자의 해석 금지): 원본 .md verbatim. 정답값/힌트 가공 X.

    매칭 0건이면 빈 list (호출자가 다른 parser 시도).
    """
    if not md_content:
        return []
    headers = list(_CLOZE_PROBLEM_HEADER_RE.finditer(md_content))
    if not headers:
        return []
    cards: list[dict] = []
    for i, m in enumerate(headers):
        num = m.group(1)
        title = m.group(2).strip()
        key = f"문제 {num}"
        # 현재 문제 ~ 다음 문제 직전 본문
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(md_content)
        block = md_content[start:end]

        # 조건 + 청구취지 본문 → body
        # 청구취지 (cloze) 헤더 위치 (블록 안)
        target_m = _CLOZE_TARGET_HEADER_RE.search(block)
        hint_m = _CLOZE_HINT_HEADER_RE.search(block)
        if target_m:
            # body = 헤더 전 (조건) + target 본문 (cloze)
            body_pre = block[:target_m.start()].strip()
            # target 본문 = target 헤더 끝 ~ 힌트 헤더 직전
            target_body_start = target_m.end()
            target_body_end = hint_m.start() if hint_m else len(block)
            target_body = block[target_body_start:target_body_end].strip()
            # 본문 합성 — UI에 cloze 본문이 표시되어야 하므로 그대로 보존
            body = (body_pre + "\n\n### 청구취지 (cloze)\n\n" + target_body).strip()
        else:
            # 청구취지 헤더 없으면 전체를 body
            body = block.strip()
            target_body = block.strip()

        # cloze 정답 추출 + placeholder 치환 (target_body 영역만)
        blanks, target_with_placeholders, blank_count = extract_blank_answers(target_body)
        # body_with_placeholders — body 안 [blank] 토큰 치환 (조건 영역은 그대로)
        _, body_with_placeholders, _ = extract_blank_answers(body)

        # 정답 본문 (answer) — target_body 에서 [blank]X[/blank] → X (정답값 inline)
        # grader 가 reference 로 활용. UI 표시 시 [bold] 토큰 제거 별도.
        answer = _BLANK_TAG_RE.sub(lambda m: m.group(1), target_body)

        # 힌트 추출 (key=hint_N, value=내용) — 단계는 1/2/2.5/3/4/5
        hints: dict[str, str] = {}
        if hint_m:
            hint_block = block[hint_m.end():]
            for hm in _CLOZE_HINT_LINE_RE.finditer(hint_block):
                step = hm.group(1)
                content = hm.group(2)
                hints[f"hint_{step}"] = content

        # mnemonic — body+answer 안 [blank2] (보통 0, cloze 데이터엔 없음)
        mnemonic_chars = _extract_blank2_chars(body) + _extract_blank2_chars(answer)
        mnemonic = ",".join(mnemonic_chars)

        # score_max — 1라운드는 1점/카드 균등 (mode 별 가중치는 grader 에서 처리)
        score_max = 1

        cards.append({
            "key": key,
            "title": title,
            "score_max": score_max,
            "body": body,
            "answer": answer,
            "mnemonic": mnemonic,
            "blanks": blanks,
            "body_with_placeholders": body_with_placeholders,
            "blank_count": blank_count,
            "hints": hints,
            "is_cloze": True,
        })
    return cards


def parse_md_subqs_minsa_practice(md_content: str) -> list[dict]:
    """17896 민사서류 1순환 작성연습 .md → 단일 카드 4 슬롯 분해 (lawear-23d9 Track D 2026-05-25).

    1순환 .md 구조 (3건 공통: 01_금전 / 02_등기 / 03_인도):
        ## 문제
        본문...
        ## 답안
        ### 소장 표제부 / ### 당사자 칸 / ### 사건명 칸
        ### 청구취지 칸
        ### 청구원인 칸 (요건사실 위주)
        ### 증명방법·첨부서류 칸
        ### 작성일·제출자·관할법원 칸
        ### 별지 목록 (03 인도만)

    Returns:
        list[dict] — 단일 카드 1개, slots[] 안에 청구취지/청구원인/증명방법/첨부서류 4개 슬롯.
            ``{"key": "단일", "score_max": 30, "body": str (## 문제 본문),
              "answer": str (## 답안 전체 raw), "mnemonic": str,
              "slots": [{"label": str, "key": str, "exemplar_md": str}, ...],
              "is_minsa_practice": True}``

        - ``body``:        `## 문제` 헤더 다음 ~ `## 답안` 직전 (수험생에게 보여줄 문제).
        - ``answer``:      `## 답안` 전체 본문 (사이드패널/AI 비교용 raw).
        - ``slots[i]``:    4개 입력 슬롯 (사용자 요구: 청구취지/청구원인/입증서류/첨부서류).
            ``label``:       UI 표시명 ("청구취지", "청구원인", "증명방법", "첨부서류").
            ``key``:         data 키 (cheong_chwiji / cheong_wonin / jeungmyeong / cheombu).
            ``exemplar_md``: 해당 슬롯의 강사 답안 .md raw (ui-fold details 포함, renderMd 처리).

    매핑 (.md 헤더 → 슬롯):
        - 청구취지 ← `### 청구취지 칸` 본문
        - 청구원인 ← `### 청구원인 칸 (요건사실 위주)` 본문
        - 증명방법 ← `### 증명방법·첨부서류 칸` 본문 안 "증명방법" 텍스트 ~ "첨부서류" 직전
        - 첨부서류 ← `### 증명방법·첨부서류 칸` 본문 안 "첨부서류" 텍스트 ~ 다음 헤더 직전

    R-09 (자의 해석 금지): .md raw verbatim. ui-fold details 그대로 슬롯 본문에 포함.
                          매칭 안 되면 slots[i].exemplar_md = "" (빈 문자열 — 사용자 진단 대상).

    매칭 0건 (`## 답안` 헤더 없음) → 빈 list 반환 (호출자 fallback).
    """
    if not md_content:
        return []
    # `## 답안` 헤더 위치 (1순환 작성연습 식별자)
    answer_h2 = re.search(r"^## 답안\s*$", md_content, re.MULTILINE)
    if not answer_h2:
        return []
    # `## 문제` 헤더 → body
    problem_h2 = re.search(r"^## 문제\s*$", md_content, re.MULTILINE)
    if problem_h2:
        body = md_content[problem_h2.end():answer_h2.start()].strip()
    else:
        body = ""
    # `## 답안` 본문 = answer (사이드 + AI 비교용)
    # 다음 `## ` 또는 EOF 까지
    after_answer = md_content[answer_h2.end():]
    next_h2 = re.search(r"^## ", after_answer, re.MULTILINE)
    answer_block_end = answer_h2.end() + (next_h2.start() if next_h2 else len(after_answer))
    answer_raw = md_content[answer_h2.end():answer_block_end].strip()

    # H3 슬롯 매핑 — R-09 raw verbatim, exemplar_md 에 포함.
    def _h3_body(label_regex: str) -> str:
        m = re.search(rf"^### {label_regex}\s*$", answer_raw, re.MULTILINE)
        if not m:
            return ""
        return _extract_section_body(answer_raw, m.start(), m.end())

    cheong_chwiji_body = _h3_body(r"청구취지 칸")
    cheong_wonin_body = _h3_body(r"청구원인 칸.*")
    # 증명방법·첨부서류 칸 — 본문 split "증명방법" / "첨부서류"
    jm_cb_body = _h3_body(r"증명방법·첨부서류 칸")
    # split 시도 — "증명방법" 라인 ~ "첨부서류" 라인 직전 / "첨부서류" 라인 ~ 끝
    jeungmyeong_body = ""
    cheombu_body = ""
    if jm_cb_body:
        # "증명방법" / "첨부서류" 단독 라인 위치 (앞뒤 공백 허용)
        jm_match = re.search(r"^증명방법\s*$", jm_cb_body, re.MULTILINE)
        cb_match = re.search(r"^첨부서류\s*$", jm_cb_body, re.MULTILINE)
        if jm_match and cb_match:
            jeungmyeong_body = jm_cb_body[jm_match.end():cb_match.start()].strip()
            cheombu_body = jm_cb_body[cb_match.end():].strip()
        else:
            # 라인 단독 매칭 실패 → 통합 본문을 첫 슬롯에 넣고 두 번째는 빈값 (R-09: 자의 분할 X)
            jeungmyeong_body = jm_cb_body
            cheombu_body = ""

    slots = [
        {"label": "청구취지", "key": "cheong_chwiji", "exemplar_md": cheong_chwiji_body},
        {"label": "청구원인", "key": "cheong_wonin", "exemplar_md": cheong_wonin_body},
        {"label": "증명방법", "key": "jeungmyeong", "exemplar_md": jeungmyeong_body},
        {"label": "첨부서류", "key": "cheombu", "exemplar_md": cheombu_body},
    ]

    # mnemonic — body+answer 안 [blank2] (보통 0)
    mnemonic_chars = _extract_blank2_chars(body) + _extract_blank2_chars(answer_raw)
    mnemonic = ",".join(mnemonic_chars)

    return [{
        "key": "단일",
        "score_max": 30,
        "body": body,
        "answer": answer_raw,
        "mnemonic": mnemonic,
        "blanks": {},
        "body_with_placeholders": body,
        "blank_count": 0,
        "slots": slots,
        "is_minsa_practice": True,
    }]


def parse_md_subqs(md_content: str) -> list[dict]:
    """다중 설문 .md → subq 카드 N개 분해.

    Args:
        md_content: .md 본문 원문 (`read_md_for_case` 결과).

    Returns:
        list[dict] — 각 카드 한 건:
            ``{"key": str, "score_max": int | None, "body": str, "answer": str,
              "mnemonic": str}``

        - ``key``: 정규화 키 (``"설문 1"`` / ``"설문 1 가"``).
        - ``score_max``: 헤더 ``(NN점)`` 캡처 (없으면 None).
        - ``body``:  ``### 설문 N`` 헤더 다음 줄 ~ 다음 헤더 직전.
        - ``answer``: ``### 설문 N 답안`` 헤더 다음 줄 ~ 다음 헤더 직전.
                     매칭되는 답안 헤더가 없으면 빈 문자열.
        - ``mnemonic``: 해당 subq 의 body + answer 안 ``[blank2]X[/blank2]`` 콘텐츠
                       콤마 join (예: ``"무,기,최,도"``). 매칭 0건이면 빈 문자열 ``""``.
                       Lv.2 힌트 노출 전용 (정답 본문 노출 X, R-09 준수).

        **단일 설문 (legacy fallback)**: ``_SUBQ_HEADER_RE`` 매칭 0건 →
        빈 리스트 ``[]`` 반환. 호출자가 단일 설문 케이스로 판단.

    알고리즘:
        1. `_SUBQ_HEADER_RE.finditer` 로 모든 문제 헤더 위치 수집.
        2. `_SUBQ_ANSWER_HEADER_RE.finditer` 로 모든 답안 헤더 위치 수집.
        3. `normalize_subq_key` 결과를 key 삼아 문제 헤더 ↔ 답안 헤더 짝 매칭.
        4. 본문은 `_extract_section_body` 로 다음 헤더 직전까지 슬라이스.
        5. 0건이면 [] 반환 (legacy).

    8 .md 실측 분포 (dev-design #48 5-2):
        - 패턴 A (4건): 민법 모고01_01 / 민소 모고02_01/02
        - 패턴 B (2건): 민소 모고01_01/02
        - 패턴 C (2건): 민법 모고02_01/02 (가/나 독립 카드)
        - fallback (1건): 민법 모고01_02 (### 설문 N 헤더 0개)
    """
    # 1. 문제 헤더 수집
    subq_headers = list(_SUBQ_HEADER_RE.finditer(md_content))
    if not subq_headers:
        # legacy fallback — 호출자가 단일 설문으로 처리
        return []

    # 2. 답안 헤더를 key 로 인덱싱
    answer_by_key: dict[str, re.Match] = {}
    for m in _SUBQ_ANSWER_HEADER_RE.finditer(md_content):
        key = normalize_subq_key(m.group(1), m.group(2))
        answer_by_key[key] = m

    # 3. 카드 N개 생성
    cards: list[dict] = []
    for m in subq_headers:
        g1 = m.group(1)
        g2 = m.group(2)
        score_str = m.group(3)
        key = normalize_subq_key(g1, g2)
        score_max = int(score_str) if score_str else None
        body = _extract_section_body(md_content, m.start(), m.end())

        ans_match = answer_by_key.get(key)
        if ans_match:
            answer = _extract_section_body(md_content, ans_match.start(), ans_match.end())
        else:
            answer = ""

        # Lv.2 힌트 — body + answer 안 [blank2]X[/blank2] 콘텐츠만 콤마 join.
        # R-09: 정답 본문 노출 X, 태그 글자만.
        mnemonic_chars = _extract_blank2_chars(body) + _extract_blank2_chars(answer)
        mnemonic = ",".join(mnemonic_chars)

        # lawear-23d9 (2026-05-25) — 17896 민사서류 cloze 빈칸 추출.
        # `[blank]X[/blank]` 패턴은 청구취지 cloze 본문에 있음 (body) — answer 영역은 N/A.
        # 다른 과목/모드는 빈 dict 반환 (영향 0).
        # R-09: 정답값은 raw 그대로, body_with_placeholders 는 UI 렌더 전용 (정답 노출 X).
        blanks, body_with_placeholders, blank_count = extract_blank_answers(body)

        cards.append(
            {
                "key": key,
                "score_max": score_max,
                "body": body,
                "answer": answer,
                "mnemonic": mnemonic,
                # lawear-23d9 — 민사서류 cloze 1라운드 신규 필드 (다른 과목은 빈 dict / 원본 body / 0)
                "blanks": blanks,
                "body_with_placeholders": body_with_placeholders,
                "blank_count": blank_count,
            }
        )
    return cards


def parse_md_toc(md_content: str) -> str:
    """.md 본문에서 `### 목차` 섹션 본문 추출.

    Args:
        md_content: .md 본문 원문.

    Returns:
        ``### 목차`` 헤더 다음 줄 ~ 다음 헤더 직전 본문 (strip).
        헤더 없으면 빈 문자열.

    `### 목차` 는 Lv.1 빠른복습 안의 `### 문제` ~ `### 답안` 사이에 위치.
    """
    m = re.search(r"^### 목차\s*$", md_content, re.MULTILINE)
    if not m:
        return ""
    return _extract_section_body(md_content, m.start(), m.end())


def parse_md_mnemonic(md_content: str) -> list[str]:
    """.md 본문 전체에서 ``[blank2]X[/blank2]`` 콘텐츠만 추출 (Lv.2 힌트 단일 모드용).

    Args:
        md_content: .md 본문 원문.

    Returns:
        매칭된 태그 콘텐츠 list (순서 보존). 매칭 0건이면 빈 list.
        예: ``["무", "기", "최", "도"]`` (미케03_27.md 117라인 답안)
            ``["묵시"]`` (미케01_07.md 91라인)
            ``[]`` (blank2 없는 .md)

    사용자 피드백 (2026-05-17 lawear-a519 Step 25):
        - 기존 Lv.4 번호 목록 노출은 **정답 본문 노출** → 폐기.
        - Lv.2 힌트는 ``[blank2]`` 태그 콘텐츠만 시각 단서로 노출 (정답 X).
        - 두문자 없으면 (= blank2 0건) Lv.2 패널에 아무것도 표시 X.
        - 단일 설문 모드 fallback 으로 사용 — 다중 설문은 ``parse_md_subqs`` 의
          subq.mnemonic 필드를 직접 사용.

    R-09 (자의적 해석 금지): 태그 안 글자 그대로 (요약/줄임/추측 X).
    """
    return _extract_blank2_chars(md_content)


# ─── 법제처 조문명 캐시 lookup (부등법 [case] 태그용) ──────────────
#
# lawear-0d65 (2026-05-24): 부등법 17896 힌트 Lv.3 보강.
# - 답안 본문 [case] 태그 → 법/규칙 구분 + 조문명 lookup → UI 표시.
# - 본문(body) 인용은 캐시 미보유 → R-09 강제로 생략 (조문명만).
# - lazy 로드 + 모듈 레벨 캐시 (909KB lawArticles.json은 1회만 read).

# `[case]본문[/case]` 매칭 (본문에 `[` 포함 X 전제 — 부등법 .md 실측).
_CASE_TAG_RE = re.compile(r"\[case\]([^\[]+)\[/case\]")

# 조문 번호 추출 (예: "제15조", "제7조의2", "제29조 제2호")
# 그룹1: 번호 본체 ("15" / "7" / "29") — `조` 까지
# 그룹2: "의M" 접미 ("의2" / 없으면 None)
# 캐시 키 정규화: 그룹1 + (그룹2 ? "의" + M : "") → "15" / "7의2" / "139의4".
_ARTICLE_NUM_RE = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


def _load_law_title_index() -> dict[str, dict[str, str]]:
    """법제처 조문명 캐시 1회 로드 (lazy).

    Returns:
        ``{법명: {조번호: 조문명}}`` 통합 dict.
        예: ``{"부동산등기법": {"15": "물적 편성주의", ...}, "민법": {...}}``

    소스:
        1. lawArticles.json (statutes.{법명}.articles.{N}.title) — 주된 소스
        2. law_titles_cache.json (statutes.{법명}.{N}: title) — 보조 (1에 없는 법령)

    R-09 (자의 해석 금지): 캐시 미존재 법령/조번호 → lookup None 반환.
    """
    global _LAW_TITLE_INDEX
    if _LAW_TITLE_INDEX is not None:
        return _LAW_TITLE_INDEX

    index: dict[str, dict[str, str]] = {}

    # 1. lawArticles.json — articles.{N}.title 구조
    try:
        with _LAW_ARTICLES_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        for law_name, law_data in (data.get("statutes") or {}).items():
            articles = (law_data or {}).get("articles") or {}
            law_idx: dict[str, str] = {}
            for art_num, art_data in articles.items():
                title = (art_data or {}).get("title") if isinstance(art_data, dict) else None
                if title:
                    law_idx[str(art_num)] = title
            if law_idx:
                index[law_name] = law_idx
    except (OSError, json.JSONDecodeError):
        # 캐시 누락은 fatal X — fallback 으로 진행
        pass

    # 2. law_titles_cache.json — statutes.{법명}.{N}: title 평면 구조 (보충)
    try:
        with _LAW_TITLES_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        for law_name, law_data in (data.get("statutes") or {}).items():
            if not isinstance(law_data, dict):
                continue
            existing = index.setdefault(law_name, {})
            for art_num, title in law_data.items():
                if not title:
                    continue
                # 1차 캐시 우선 (덮어쓰기 X)
                existing.setdefault(str(art_num), title)
    except (OSError, json.JSONDecodeError):
        pass

    _LAW_TITLE_INDEX = index
    return index


def _classify_case_law_type(text: str, default_subject_kor: str | None = None) -> tuple[str, str | None]:
    """[case] 본문 prefix 분석 → (law_type, law_name).

    Args:
        text: [case] 태그 안 본문 (예: "민법 제200조 권리의 적법의 추정").
        default_subject_kor: 부등법이면 "부동산등기법" 등 — `제N조` 단독 시 기본 법명.

    Returns:
        (law_type, law_name):
          - law_type: "법" | "규칙" | "민법" | "신탁법" | "상법" | "건축법" |
                      "선례" | "예규" | "판례" | "기타"
          - law_name: 캐시 lookup 키 (없으면 None).

    R-09: prefix 매칭만 사용. 자연어 [case]는 "기타" 분류 + law_name None.
    """
    s = text.strip()
    # 규칙 prefix — 부동산등기규칙 (case가 부등법 컨텍스트일 때만)
    if s.startswith("규칙 제") or s.startswith("규칙제"):
        return "규칙", "부동산등기규칙"
    if s.startswith("같은 규칙"):
        return "규칙", "부동산등기규칙"
    # 민법 / 민사소송법 / 상법 / 신탁법 / 건축법 등 명시
    # 매칭 우선순위: 긴 이름 먼저 (예: 민사소송법 → 민법 보다 먼저).
    for law_name in ("민사소송법", "민사집행법", "민법",
                     "형사소송법", "형법",
                     "상법", "신탁법", "건축법", "공탁법",
                     "주택임대차보호법", "상가건물 임대차보호법",
                     "집합건물의 소유 및 관리에 관한 법률",
                     "부동산등기특별조치법"):
        if s.startswith(law_name + " 제") or s.startswith(law_name + "제"):
            return law_name, law_name
    # 선례/예규/판례
    if s.startswith("선례") or s.startswith("등기선례"):
        return "선례", None
    if s.startswith("예규") or s.startswith("등기예규"):
        return "예규", None
    if "대법원" in s[:10] or s.startswith("판례"):
        return "판례", None
    # 같은 법 / 법 제 / 제N조 (단독) → default_subject_kor (보통 부동산등기법)
    if s.startswith("같은 법") or s.startswith("법 제") or s.startswith("법제"):
        return "법", default_subject_kor or "부동산등기법"
    if s.startswith("제") and _ARTICLE_NUM_RE.match(s):
        return "법", default_subject_kor or "부동산등기법"
    return "기타", None


def extract_case_tags(md_text: str, default_subject_kor: str | None = None) -> list[dict]:
    """답안 .md 본문에서 ``[case]...[/case]`` 태그 추출 + 법/규칙 구분 + 캐시 lookup.

    Args:
        md_text: .md 본문 원문 (body+answer 등).
        default_subject_kor: case의 subject_kor (예: "부동산등기법").
            "제N조" 단독 표기 시 기본 법명으로 사용.

    Returns:
        list[dict] — 각 [case] 태그 한 건:
            ``{"raw": str, "law_type": str, "law_name": str | None,
              "article_num": str | None, "article_title": str | None,
              "source": "cache" | "raw"}``

        - ``raw``: [case] 태그 안 본문 그대로 (UI fallback 표시용).
        - ``law_type``: "법" | "규칙" | "민법" | "신탁법" | "상법" | "건축법" |
                        "선례" | "예규" | "판례" | "기타".
        - ``law_name``: 캐시 lookup 키 (선례/예규/판례/기타는 None).
        - ``article_num``: 조 번호 ("15" / "7의2"). 추출 실패 시 None.
        - ``article_title``: 캐시 조문명. 미캐시면 None (R-09).
        - ``source``: "cache" (조문명 lookup 성공) | "raw" (실패 — raw 표시).

    R-09 (자의 해석 금지):
        - 캐시 미존재 조문 → article_title=None, source="raw".
        - LLM 추정 절대 X — UI에서 "(조문명 미캐시)" 표시.
        - 중복 제거 X (등장 순서 보존).
    """
    if not md_text:
        return []
    index = _load_law_title_index()
    results: list[dict] = []
    for m in _CASE_TAG_RE.finditer(md_text):
        raw_inner = m.group(1).strip()
        if not raw_inner:
            continue
        law_type, law_name = _classify_case_law_type(raw_inner, default_subject_kor)
        # 조문 번호 추출 — 그룹1=본체, 그룹2=의X 접미
        num_match = _ARTICLE_NUM_RE.search(raw_inner)
        article_num: str | None = None
        article_title: str | None = None
        source = "raw"
        if num_match:
            base = num_match.group(1)
            suffix = num_match.group(2)
            article_num = f"{base}의{suffix}" if suffix else base
        # 캐시 lookup (law_name 있고 article_num 있을 때만)
        if law_name and article_num and law_name in index:
            cached_title = index[law_name].get(article_num)
            if cached_title:
                article_title = cached_title
                source = "cache"
        results.append(
            {
                "raw": raw_inner,
                "law_type": law_type,
                "law_name": law_name,
                "article_num": article_num,
                "article_title": article_title,
                "source": source,
            }
        )
    return results


def _resolve_md_path(case_path: str) -> Path:
    """cases.path (예: '입문_민법/2026_minbeop_immun_미케01_01.md') → 절대 경로."""
    p = BASE_PATH / case_path
    # 보안: BASE_PATH 밖으로 escape 금지
    try:
        p.resolve().relative_to(BASE_PATH)
    except ValueError as e:
        raise CaseFileMissingError(f"path_escape: {case_path}") from e
    return p


def read_md_for_case(case_path: str) -> str:
    """디스크 .md 본문 read (UTF-8)."""
    p = _resolve_md_path(case_path)
    if not p.is_file():
        raise CaseFileMissingError(f"md_not_found: {p}")
    return p.read_text(encoding="utf-8")


def parse_year_from_id(case_id: str | None) -> str | None:
    """case_id 첫 4자리에서 연도 추출 (lawear-2e42 2026-05-20).

    Example:
        '2026_minbeop_immun_mike01_01' → '2026'
        '2026_index_minbeop' → '2026' (library type 도 동일 패턴)
        '' or None → None

    R-09 (자의 해석 금지): id에 명시된 연도만 반환. 추정 X.
    """
    if not case_id or len(case_id) < 5:
        return None
    prefix = case_id[:4]
    if prefix.isdigit() and case_id[4] == "_":
        return prefix
    return None


def parse_year_from_path(path: str | None) -> str | None:
    """case path 첫 토큰에서 연도 추출 — id 파싱 실패 시 fallback (lawear-0d65 2026-05-24).

    Example:
        '2026_사용자_부동산등기법/1순환/01_모의고사_01.md' → '2026'
        '2025_사용자_부동산등기법/2순환/05_모의고사_01.md' → '2025'
        'misc/foo.md' → None

    R-09 (자의 해석 금지): path 첫 4자리가 숫자 + '_' 패턴일 때만. 추정 X.
    """
    if not path:
        return None
    first = path.split("/", 1)[0]
    if len(first) >= 5 and first[:4].isdigit() and first[4] == "_":
        return first[:4]
    return None


# ─── 케이스 메타 집계 ───────────────────────────────────────────────


def _case_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """cases row → dict (subjectKor/fileKor 카멜케이스 호환).

    lawear-2e42 (2026-05-20): year 필드 추가 (id 첫 4자리 파싱, 다년도 지원).
    """
    return {
        "id": row["id"],
        "subject": row["subject"],
        "subject_kor": row["subject_kor"],
        "category": row["category"],
        "file": row["file"],
        "file_kor": row["file_kor"],
        "case_no": row["case_no"],
        "title": row["title"],
        "path": row["path"],
        "pdf_path": row["pdf_path"],
        "points": row["points"],
        "user_case": row["user_case"],
        "synced_at": row["synced_at"],
        "content_hash": row["content_hash"],
        # lawear-0d65: migration 008 신규 컬럼 노출
        # subject_type: 'lv1234' (민법/민소) | 'problem_answer' (부등법 등)
        # outline_category: 부등법 만능목차 4분류 (기본/첨부서면/등기절차/부수절차/unknown)
        "subject_type": (row["subject_type"] if "subject_type" in row.keys() else "lv1234") or "lv1234",
        "outline_category": (row["outline_category"] if "outline_category" in row.keys() else None),
        # lawear-0d65: year fallback — id 첫 4자리 실패 시 path에서 추출
        # (예: '01_모의고사_01' id는 연도 없음 → path '2026_사용자_부동산등기법/...'에서 '2026' 추출)
        "year": parse_year_from_id(row["id"]) or parse_year_from_path(row["path"]),
    }


def _enrich_case_with_stats(conn: sqlite3.Connection, case: dict[str, Any]) -> dict[str, Any]:
    """case 에 bookmarked / attempt_count / last_score_pct / has_error / has_stale 추가.

    dev-design #48 §3-2 Case 응답 메시지의 누적 필드.
    """
    cid = case["id"]
    # bookmarked
    cur = conn.execute("SELECT 1 FROM bookmarks WHERE case_id = ?", (cid,))
    case["bookmarked"] = cur.fetchone() is not None

    # attempts 집계 (count / last score / error / stale)
    cur = conn.execute(
        """
        SELECT
          COUNT(*)                                          AS cnt,
          SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END) AS err_cnt,
          SUM(CASE WHEN is_stale = 1       THEN 1 ELSE 0 END) AS stale_cnt
        FROM attempts WHERE case_id = ?
        """,
        (cid,),
    )
    row = cur.fetchone()
    case["attempt_count"] = int(row["cnt"]) if row and row["cnt"] is not None else 0
    case["has_error"] = bool(row["err_cnt"]) if row and row["err_cnt"] is not None else False
    case["has_stale"] = bool(row["stale_cnt"]) if row and row["stale_cnt"] is not None else False

    # 최근 done attempt 의 score_pct
    cur = conn.execute(
        """
        SELECT score_pct FROM attempts
        WHERE case_id = ? AND status = 'done' AND score_pct IS NOT NULL
        ORDER BY submitted_at DESC LIMIT 1
        """,
        (cid,),
    )
    last = cur.fetchone()
    case["last_score_pct"] = float(last["score_pct"]) if last and last["score_pct"] is not None else None

    # points fallback (lawear-c63e-sub4 #2138 §Sub4):
    # cases 테이블 points == 0 인데 .md 본문에 `## 원본 (NN점)` 또는 `- 점수: NN점`
    # 메타가 있으면 .md 값으로 응답 보강 (사이드패널 표시용, DB 변경 X).
    # 라이브러리 type (subject='index'/'pdf_raw') 은 origin 없음 → fallback 스킵.
    if (
        not case.get("points")
        and case.get("subject") not in ("index", "pdf_raw")
        and case.get("path")
    ):
        try:
            md_text = read_md_for_case(case["path"])
            fallback_pts = parse_md_file(md_text).get("origin_points")
            if fallback_pts:
                case["points"] = fallback_pts
        except CaseFileMissingError:
            # 파일 없으면 0 유지 (백워드 호환)
            pass

    return case


# ─── 공용 API ──────────────────────────────────────────────────────


def list_cases(
    conn: sqlite3.Connection,
    *,
    filter_name: str = "all",
    subject: str | None = None,
    category: str | None = None,
    file_name: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """케이스 목록 조회 (필터 + 집계).

    Args:
        filter_name: 'all' | 'err' | 'stale' | 'book'
        subject:     subject 코드 (예: 'minbeop')
        category:    카테고리 (예: '입문' / '예비')
        file_name:   파일 코드 (예: '미케01')
        search:      title LIKE %search%

    Returns:
        Case dict 배열 (메타 + bookmarked + attempt_count + last_score_pct + has_error + has_stale).
        정렬: subject ASC, category ASC, file ASC, case_no ASC.
    """
    if filter_name not in ALLOWED_FILTERS:
        filter_name = "all"
    # alias 정규화 (bookmarked → book)
    filter_name = _FILTER_ALIASES.get(filter_name, filter_name)

    # 기본 쿼리 + 동적 WHERE
    where: list[str] = []
    params: list[Any] = []

    if subject:
        where.append("subject = ?")
        params.append(subject)
    if category:
        where.append("category = ?")
        params.append(category)
    if file_name:
        where.append("file = ?")
        params.append(file_name)
    if search:
        where.append("title LIKE ?")
        params.append(f"%{search}%")

    # filter=book → bookmarks JOIN
    if filter_name == "book":
        where.append("id IN (SELECT case_id FROM bookmarks)")
    elif filter_name == "err":
        where.append("id IN (SELECT case_id FROM attempts WHERE status = 'error')")
    elif filter_name == "stale":
        where.append("id IN (SELECT case_id FROM attempts WHERE is_stale = 1)")

    sql = "SELECT * FROM cases"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY subject ASC, category ASC, file ASC, case_no ASC"

    cur = conn.execute(sql, tuple(params))
    rows = cur.fetchall()
    cases = [_enrich_case_with_stats(conn, _case_row_to_dict(r)) for r in rows]
    return cases


def get_case(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    """단건 조회 (메타 + .md 파일 파싱 origin/lv1/lv4 + 집계).

    Raises:
        CaseNotFoundError: cases 테이블 미존재
        CaseFileMissingError: cases.path 의 .md 가 디스크에 없음
    """
    cur = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    row = cur.fetchone()
    if row is None:
        raise CaseNotFoundError(case_id)

    case = _case_row_to_dict(row)
    _enrich_case_with_stats(conn, case)

    # .md 파일 read + 파싱
    md_text = read_md_for_case(case["path"])
    sections = parse_md_file(md_text)

    case["origin"] = sections["origin"]
    case["origin_points"] = sections["origin_points"]
    case["lv1"] = sections["lv1"]
    case["lv4"] = sections["lv4"]
    # lawear-23d9 (P2-a, 2026-05-25): 부등법 ## 목차 H2 본문 (답안 컬럼 user-toc 박스용).
    # 17895 merge.html mirror — extractSection('목차') 패턴.
    case["toc_md"] = sections.get("toc")
    case["meta"] = sections["meta"]
    # 채점 시 레퍼런스로 쓰는 전체 .md raw (Step 6 grader 에서 활용)
    case["md_body"] = md_text

    # points fallback: cases 테이블 points 가 0 또는 None 인데
    # .md 파싱 origin_points 가 있으면 .md 값으로 보강 (사이드패널 표시용).
    # 백워드 호환: cases 테이블은 변경 X, 응답 dict 의 points 만 갱신.
    # (lawear-c63e-sub4 #2138 §Sub4: 79건 0점 중 라이브러리 type 제외 정상화)
    if (not case.get("points")) and sections.get("origin_points"):
        case["points"] = sections["origin_points"]

    # lawear-0d65 (2026-05-24): 부등법 힌트 Lv.3 — [case] 태그 → 조문명 lookup.
    # lawear-23d9 Track B (2026-05-25): 5과목 공통 적용 (사용자 피드백 — 과목별 다른 렌더 → 공통 함수).
    #   subject_kor → 기본 법명 매핑 (제N조 단독 표기 시 자과목 보충용, JS SUBJECT_KOR_TO_STATUTE mirror).
    #   민법/민소 도 [case]태그 있으면 articles_hint 채움 — 클라이언트는 articles_hint 비면 grep fallback.
    # R-09: 캐시 미존재 → article_title None (자의 해석 X).
    _SUBJECT_KOR_TO_STATUTE = {
        "형법": "형법",
        "형소": "형사소송법",
        "민법": "민법",
        "민소": "민사소송법",
        "부동산등기법": "부동산등기법",
        "부동산등기서류": "부동산등기법",
        "민사서류": "민법",
    }
    _subject_kor_val = case.get("subject_kor")
    _default_law = _SUBJECT_KOR_TO_STATUTE.get(_subject_kor_val) or "부동산등기법"
    # lawear-23d9 (2026-05-25): 본문 동일 조문 중복 인용 dedupe.
    # (law_name, article_num) 기준 — 같은 조는 1번만 (첫 등장 보존).
    # 항/호 차이는 무시 (사용자: "형소법 제8조 3번" → 1번으로).
    _raw_hints = extract_case_tags(md_text, default_subject_kor=_default_law)
    _seen_keys: set = set()
    _deduped: list = []
    for _h in _raw_hints:
        _key = (_h.get("law_name") or "", _h.get("article_num") or "", _h.get("law_type") or "")
        if _key not in _seen_keys:
            _seen_keys.add(_key)
            _deduped.append(_h)
    case["articles_hint"] = _deduped

    # lawear-23d9 (2026-05-25): 17896 민사서류 cloze .md → subqs 분기.
    # subject_type='civil_doc' 인 경우 cloze parser (H2 `## 문제 N`) 사용.
    # 기존 parse_md_subqs (`### 설문 N` H3) 와 호환 — 둘 다 빈 list 면 단일 모드.
    # R-09: cloze 데이터 verbatim, [blank] 토큰만 정답 추출 + UI placeholder 치환.
    if case.get("subject_type") == "civil_doc":
        cloze_subqs = parse_md_subqs_cloze(md_text)
        if cloze_subqs:
            case["subqs"] = cloze_subqs
            # 청구원인 placeholder 표시 — UI 가 카드 placeholder 표출 시 사용
            case["has_cause_section"] = True
            # cloze 모드 메타 — 채점 + UI 분기용
            case["cloze_mode"] = True

    # lawear-23d9 Track D (2026-05-25): 17896 민사서류 1순환 작성연습 분기.
    # subject='minsaseoryu' + category='1순환' (lv1234) — 4슬롯 단일 카드.
    # 사용자 요구 (2026-05-25): 청구취지/청구원인/증명방법/첨부서류 4개 입력칸 + 접펼.
    # R-09: parse_md_subqs_minsa_practice 가 .md raw verbatim 분해 — 슬롯별 exemplar_md 그대로.
    if (
        case.get("subject") == "minsaseoryu"
        and case.get("category") == "1순환"
        and not case.get("cloze_mode")
    ):
        practice_subqs = parse_md_subqs_minsa_practice(md_text)
        if practice_subqs:
            case["subqs"] = practice_subqs
            case["minsa_practice_mode"] = True

    return case
