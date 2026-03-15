#!/usr/bin/env python3
"""
Phase 2: TTS 변환 배치 러너

Phase 1 JSON을 읽어 Opus 3인팀 프롬프트를 자동 생성하고,
에이전트 응답을 파싱하여 TTS 결과 JSON으로 저장한다.

Usage:
    python3 scripts/phase2_tts_batch.py generate --subject 민소 --file 미케01
    python3 scripts/phase2_tts_batch.py generate --subject 민소 --file 미케01 --case case01
    python3 scripts/phase2_tts_batch.py save --subject 민소 --file 미케01 --input result.txt
    python3 scripts/phase2_tts_batch.py save --subject 민소 --file 미케01 --case case01 --input result.txt
    python3 scripts/phase2_tts_batch.py status
    python3 scripts/phase2_tts_batch.py pending
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_TEXTS_DIR = PROJECT_ROOT / "pipeline" / "raw_texts"
TTS_TEXTS_DIR = PROJECT_ROOT / "pipeline" / "tts_texts"
PROGRESS_FILE = PROJECT_ROOT / "pipeline" / "progress.json"
LAW_ARTICLES_FILE = PROJECT_ROOT / "web" / "src" / "data" / "lawArticles.json"

# 과목 키 매핑 (한글 → 디렉토리명)
SUBJECT_ID_MAP = {
    "민소": "minso",
    "민법": "minbeop",
    "형법": "hyeongbeop",
    "형소": "hyeongso",
    "부등": "budeung",
}

# 과목별 관련 법령 (lawArticles.json의 키와 일치해야 함)
SUBJECT_LAWS = {
    "민소": ["민사소송법", "민사집행법"],
    "민법": ["민법", "상법"],
    "형법": ["형법"],
    "형소": ["형사소송법", "형법"],
    "부등": ["부동산등기법", "부동산 실권리자명의 등기에 관한 법률"],
}

RULES_VERSION = "R-01~R-22"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTS 규칙 요약 (프롬프트용 — 하드코딩, 토큰 절약)
# ---------------------------------------------------------------------------

TTS_RULES_SUMMARY = """\
## TTS 변환 규칙 (R-01~R-22)

### 텍스트 정제
- R-01: 판례번호 완전 제거 (대판 2018.7.19. 2018다22008 → 삭제)
- R-02: 날짜 → 상대적 시간 (5년 후 등). 시효/기간 계산 필수 날짜는 유지
- R-03: 괄호 A(B) → "A 혹은 B" (TTS가 괄호를 못 읽음)
- R-04: 호흡 조절 쉼표 삽입 (과다/부족 모두 금지)
- R-05: 콜론(:) → 쉼표(,)
- R-08: 특수기호 [] — : () / 제거 또는 자연어 변환
- R-14: 제+숫자 복합어 한글화 (제1심→제일심, 제3자→제삼자). 조문번호(제44조)는 그대로
- R-15: 문제 섹션 불필요 수식어 과감 제거. 금액 한글화 (1000만원→천만원)
- R-16: 조문 인용 시 제목 삽입 + 조문 앞배치 ("제397조 금전채무불이행에 대한 특칙에 의해")
- R-17: 문맥 유추 가능한 정보 생략 (당사자 두명뿐이면 이름 반복 줄이기)
- R-19: 조문 번호는 아라비아 숫자 그대로 (제250조). 한글 서수 변환 금지
- R-20: 목록 번호는 숫자 (1. 2. 3.). 첫째/둘째 금지. 로마숫자만 아라비아로 변환
- R-21: 금액 한글화O, 조문번호 한글화X, 목록번호 한글화X, 호실/주소 한글 읽기

### 구조
- R-06: 문제 → 목차 → 답안 순서
- R-07: 목차는 원문 그대로 (요약/재구성 금지)
- R-12: 문제 부분 간결화 (중복 표현/불필요 수식어 제거, 쉼표 과다 금지)
- R-13: 목차에서 "결론"/"이유" 단독 항목 제거 (구체적 내용 붙은 건 유지)

### 최상위 규칙
- R-09: AI 자의적 해석 금지 — 원본 정보만 사용. 의심스러우면 원본 표현 유지
- R-22: 모든 피드백은 전 과목 공통 (특정 과목 한정은 사용자가 명시한 경우만)

### 검증 (필수)
- R-10: diff 필수 제공 (원본 vs TTS 비교)
- R-11: 듣는 사람 입장 QA (구분/길이/혼동/정확성)
- R-18: diff 누락 시 작업 미완료"""


# ---------------------------------------------------------------------------
# 3인팀 프롬프트 템플릿
# ---------------------------------------------------------------------------

TEAM_PROMPT_TEMPLATE = """\
# TTS 변환 3인팀 — {subject} {file_label} {case_label}

당신은 법무사 2차 시험 TTS 변환 3인팀입니다.
하나의 에이전트 안에서 3단계를 순차 실행하세요.

{rules_summary}

## 과목별 특화
{subject_specific}

## 조문 매핑 (해당 과목 관련 법령)
아래 조문 매핑을 참고하여 R-16(조문 제목 삽입) 적용 시 사용하세요.
{law_articles_section}

## 원본 텍스트

### 문제 (problem)
{problem_text}

### 빈칸 정답
{blanks_text}

### 답안 (answer)
{answer_text}

## 3단계 실행

### Phase 1: 작가 (문장 다듬기)
- R-01~R-22 규칙 적용하여 TTS 텍스트 생성
- 문제: 대폭 간결화 (조사 최소화, 필러 제거, 질문 간소화)
- 답안: 번호 체계(1. 2. 3.), "~이다," 종결, "생각건대" 제거
- 목차: "결론"/"이유"/"사안의 해결" 단독 항목 제거, 핵심 쟁점만

### Phase 2: 수험생 리뷰어 (TTS 청취자 관점)
Phase 1 결과를 "귀로 듣는 사람" 입장에서 검토:
- 호흡/끊어읽기 자연스러운가?
- 문장이 너무 길어 암기 불가능하지 않은가?
- 날짜/인명 혼동 없는가?
- 쉼표 과다/부족 없는가?
- 목차 구조가 한번에 머리에 들어오는가?
→ 피드백 후 직접 수정

### Phase 3: 판사 QA (채점자 관점)
- 원본 대비 핵심 법리/키워드 누락 확인
- 핵심 쟁점 빠진 것 없는지
- 결론 정확한지
- R-09 위반 여부 (AI 자의적 해석 유무)
→ PASS / 수정필요 (사유 명시)

## 출력 형식 (반드시 아래 마커 사용)

[문제]
(TTS 변환된 문제 텍스트)

[목차]
1. 첫번째 목차 항목
2. 두번째 목차 항목
...

[답안]
(TTS 변환된 답안 텍스트)

[diff]
원본: ...
TTS: ...
규칙: R-XX
---
원본: ...
TTS: ...
규칙: R-XX
...

[Phase 2]
(수험생 리뷰어 피드백 및 수정 내역. 수정 없으면 "수정 없음")

[Phase 3]
판정: PASS 또는 수정필요
누락: (없으면 "없음")
R-09 위반: 없음 또는 위반 사유
사유: (수정필요인 경우 사유)
"""

# 과목별 특화 규칙
SUBJECT_SPECIFIC = {
    "민소": "- 빈칸 박스: 정답을 괄호 안에 삽입 (예: '(소각하 판결)')\n- 민사소송법/민사집행법 조문 참조",
    "민법": "- 빈칸 박스: 정답을 괄호 안에 삽입\n- 민법/상법 조문 참조",
    "형법": '- 별표(★★) → "중요" 변환\n- 중첩 괄호 단순화\n- 형법 조문 참조',
    "형소": '- 별표(★★) → "중요" 변환\n- 형사소송법/형법 조문 참조',
    "부등": '- "명문x" → "명문 규정 없음" 변환\n- 부동산등기법/실권리자명의법 조문 참조',
}


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def compute_text_hash(problem_tts: str, answer_tts: str) -> str:
    """problem_tts + answer_tts의 SHA-256 해시를 반환한다."""
    combined = (problem_tts + answer_tts).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


def load_law_articles() -> dict:
    """lawArticles.json을 로드한다."""
    if not LAW_ARTICLES_FILE.exists():
        log.warning("lawArticles.json 없음: %s", LAW_ARTICLES_FILE)
        return {}
    with open(LAW_ARTICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_law_articles_for_subject(subject: str, law_data: dict) -> str:
    """해당 과목의 관련 법령 조문을 프롬프트용 텍스트로 변환한다."""
    laws = SUBJECT_LAWS.get(subject, [])
    statutes = law_data.get("statutes", {})

    sections = []
    for law_name in laws:
        if law_name not in statutes:
            sections.append(f"### {law_name}\n(조문 매핑 없음)")
            continue

        articles = statutes[law_name].get("articles", {})
        if not articles:
            sections.append(f"### {law_name}\n(조문 없음)")
            continue

        # 조문 목록 (최대 표시 — 프롬프트 토큰 절약을 위해 번호: 제목 형태)
        lines = [f"### {law_name}"]
        for art_num, art_title in articles.items():
            lines.append(f"- 제{art_num}조: {art_title}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "(관련 법령 조문 매핑 없음)"


def find_raw_text_file(subject: str, file_label: str) -> Path | None:
    """Phase 1 JSON 파일을 찾는다. file_label(미케01 등)로 검색."""
    subject_id = SUBJECT_ID_MAP.get(subject)
    if not subject_id:
        return None

    raw_dir = RAW_TEXTS_DIR / subject_id
    if not raw_dir.exists():
        return None

    # 모든 JSON 파일에서 file 필드를 비교하여 찾기
    for json_file in raw_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("file") == file_label or data.get("fileId") == file_label:
                return json_file
        except (json.JSONDecodeError, KeyError):
            continue

    # 파일명으로 직접 매칭 시도
    for json_file in raw_dir.glob("*.json"):
        if file_label in json_file.stem:
            return json_file

    return None


def load_progress() -> dict:
    """progress.json을 로드한다."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"lastUpdated": "", "subjects": {}, "stats": {}}


def save_progress(progress: dict):
    """progress.json을 저장한다."""
    progress["lastUpdated"] = datetime.now(timezone.utc).isoformat()

    # 통계 재계산
    total_files = 0
    extracted_files = 0
    tts_done_files = 0
    total_cases = 0
    extracted_cases = 0

    for subj_data in progress["subjects"].values():
        files = subj_data.get("files", {})
        for file_data in files.values():
            total_files += 1
            status = file_data.get("status", "pending")
            case_count = file_data.get("cases", 0)
            total_cases += case_count

            if status in ("extracted", "tts_done", "reviewed"):
                extracted_files += 1
                extracted_cases += case_count
            if status in ("tts_done", "reviewed"):
                tts_done_files += 1

    progress["stats"] = {
        "totalFiles": total_files,
        "extractedFiles": extracted_files,
        "ttsDoneFiles": tts_done_files,
        "totalCases": total_cases,
        "extractedCases": extracted_cases,
    }

    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def format_answer_text(answer: dict) -> str:
    """answer 객체를 읽기 쉬운 텍스트로 변환한다."""
    parts = []
    if answer.get("conclusion"):
        parts.append(f"[결론]\n{answer['conclusion']}")

    for i, section in enumerate(answer.get("sections", []), 1):
        title = section.get("title", f"섹션 {i}")
        content = section.get("content", "")
        parts.append(f"[{i}. {title}]\n{content}")

    return "\n\n".join(parts) if parts else "(답안 없음)"


def format_blanks_text(blanks: dict) -> str:
    """빈칸 정답을 텍스트로 변환한다."""
    if not blanks:
        return "(빈칸 없음)"
    lines = []
    for num in sorted(blanks.keys(), key=lambda x: int(x)):
        lines.append(f"빈칸 {num}: {blanks[num]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 기능 1: 프롬프트 생성
# ---------------------------------------------------------------------------

def generate_prompt(case_data: dict, subject: str, file_label: str, law_articles: dict) -> str:
    """
    Phase 1 JSON의 case 1개에 대해 Opus 3인팀 프롬프트를 생성한다.

    Args:
        case_data: Phase 1 JSON의 case 1개
        subject: 과목명 (민소, 민법, 형법 등)
        file_label: 파일 라벨 (미케01 등)
        law_articles: lawArticles.json 전체 데이터

    Returns:
        Opus 3인팀 프롬프트 문자열
    """
    case_label = case_data.get("label", case_data.get("id", ""))

    # 원본 텍스트
    problem_text = case_data.get("problem", "(문제 없음)")
    answer_text = format_answer_text(case_data.get("answer", {}))
    blanks_text = format_blanks_text(case_data.get("blanks", {}))

    # 과목별 조문 매핑
    law_articles_section = get_law_articles_for_subject(subject, law_articles)

    # 과목별 특화 규칙
    subject_specific = SUBJECT_SPECIFIC.get(subject, "(과목별 특화 규칙 없음)")

    prompt = TEAM_PROMPT_TEMPLATE.format(
        subject=subject,
        file_label=file_label,
        case_label=case_label,
        rules_summary=TTS_RULES_SUMMARY,
        subject_specific=subject_specific,
        law_articles_section=law_articles_section,
        problem_text=problem_text,
        blanks_text=blanks_text,
        answer_text=answer_text,
    )

    return prompt


def cmd_generate(args):
    """generate 커맨드: 프롬프트 생성."""
    subject = args.subject
    file_label = args.file

    if subject not in SUBJECT_ID_MAP:
        log.error("알 수 없는 과목: %s (가능: %s)", subject, ", ".join(SUBJECT_ID_MAP.keys()))
        sys.exit(1)

    # Phase 1 JSON 찾기
    raw_file = find_raw_text_file(subject, file_label)
    if not raw_file:
        log.error("Phase 1 JSON 없음: %s/%s", subject, file_label)
        sys.exit(1)

    log.info("Phase 1 JSON 로드: %s", raw_file)
    with open(raw_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # 조문 매핑 로드
    law_articles = load_law_articles()

    cases = raw_data.get("cases", [])
    if not cases:
        log.error("Case가 없습니다: %s/%s", subject, file_label)
        sys.exit(1)

    # --case 필터
    if args.case:
        cases = [c for c in cases if c.get("id") == args.case]
        if not cases:
            log.error("Case를 찾지 못함: %s", args.case)
            sys.exit(1)

    # 프롬프트 출력 디렉토리
    prompt_dir = TTS_TEXTS_DIR / SUBJECT_ID_MAP[subject] / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    for case_data in cases:
        case_id = case_data.get("id", "unknown")
        prompt = generate_prompt(case_data, subject, file_label, law_articles)

        # 프롬프트를 파일로 저장
        file_id = raw_data.get("fileId", file_label)
        prompt_file = prompt_dir / f"{file_id}_{case_id}.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        log.info("프롬프트 생성: %s (%d chars)", prompt_file.name, len(prompt))

    log.info("")
    log.info("=" * 50)
    log.info("프롬프트 생성 완료: %d개 Case", len(cases))
    log.info("출력: %s", prompt_dir)
    log.info("=" * 50)


# ---------------------------------------------------------------------------
# 기능 2: 결과 파싱
# ---------------------------------------------------------------------------

def parse_tts_result(agent_output: str) -> dict:
    """
    Opus 에이전트의 텍스트 응답을 파싱하여 구조화된 dict로 변환한다.

    마커: [문제], [목차], [답안], [diff], [Phase 2], [Phase 3]

    Returns:
        {
            "problem_tts": "...",
            "toc": [...],
            "answer_tts": "...",
            "diff": [...],
            "phase2_review": "...",
            "phase3_qa": {"pass": bool, "missing": [], "r09_violation": bool, "reason": ""},
            "textHash": "sha256hex..."
        }
    """
    result = {
        "problem_tts": "",
        "toc": [],
        "answer_tts": "",
        "diff": [],
        "phase2_review": "",
        "phase3_qa": {
            "pass": False,
            "missing": [],
            "r09_violation": False,
            "reason": "",
        },
        "textHash": "",
    }

    # 마커 기반 섹션 분리
    markers = ["[문제]", "[목차]", "[답안]", "[diff]", "[Phase 2]", "[Phase 3]"]
    sections = _split_by_markers(agent_output, markers)

    # 문제 TTS
    result["problem_tts"] = sections.get("[문제]", "").strip()

    # 목차
    toc_text = sections.get("[목차]", "").strip()
    result["toc"] = _parse_toc(toc_text)

    # 답안 TTS
    result["answer_tts"] = sections.get("[답안]", "").strip()

    # diff
    diff_text = sections.get("[diff]", "").strip()
    result["diff"] = _parse_diff(diff_text)

    # Phase 2 수험생 리뷰
    result["phase2_review"] = sections.get("[Phase 2]", "").strip()

    # Phase 3 판사 QA
    phase3_text = sections.get("[Phase 3]", "").strip()
    result["phase3_qa"] = _parse_phase3(phase3_text)

    # textHash
    result["textHash"] = compute_text_hash(
        result["problem_tts"], result["answer_tts"]
    )

    return result


def _split_by_markers(text: str, markers: list[str]) -> dict[str, str]:
    """마커로 텍스트를 섹션별로 분리한다."""
    sections = {}
    # 마커 위치 찾기
    positions = []
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            positions.append((idx, marker))

    positions.sort(key=lambda x: x[0])

    for i, (pos, marker) in enumerate(positions):
        start = pos + len(marker)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        sections[marker] = text[start:end]

    return sections


def _parse_toc(toc_text: str) -> list[dict]:
    """목차 텍스트를 파싱한다."""
    toc = []
    if not toc_text:
        return toc

    for line in toc_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # "1. 제목" 또는 "  1-1. 하위제목" 패턴
        indent = 0
        # 들여쓰기 레벨 감지
        stripped = line.lstrip()
        leading_spaces = len(line) - len(stripped)
        if leading_spaces >= 4:
            indent = 2
        elif leading_spaces >= 2:
            indent = 1

        # 번호와 텍스트 분리
        number_match = re.match(r"^(\d+(?:-\d+)?(?:\.\d+)?)\.\s*(.*)", stripped)
        if number_match:
            toc.append({
                "number": number_match.group(1),
                "text": number_match.group(2).strip(),
                "indent": indent,
            })
        else:
            # 번호 없는 항목
            toc.append({
                "number": "",
                "text": stripped,
                "indent": indent,
            })

    return toc


def _parse_diff(diff_text: str) -> list[dict]:
    """diff 텍스트를 파싱한다."""
    diffs = []
    if not diff_text:
        return diffs

    # "---" 구분자로 분할
    entries = re.split(r"\n---\n", diff_text)

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        diff_item = {"original": "", "tts": "", "rule": ""}

        for line in entry.split("\n"):
            line = line.strip()
            if line.startswith("원본:"):
                diff_item["original"] = line[len("원본:"):].strip()
            elif line.startswith("TTS:"):
                diff_item["tts"] = line[len("TTS:"):].strip()
            elif line.startswith("규칙:"):
                diff_item["rule"] = line[len("규칙:"):].strip()

        if diff_item["original"] or diff_item["tts"]:
            diffs.append(diff_item)

    return diffs


def _parse_phase3(phase3_text: str) -> dict:
    """Phase 3 QA 결과를 파싱한다."""
    qa = {
        "pass": False,
        "missing": [],
        "r09_violation": False,
        "reason": "",
    }

    if not phase3_text:
        return qa

    for line in phase3_text.split("\n"):
        line = line.strip()
        if line.startswith("판정:"):
            verdict = line[len("판정:"):].strip()
            qa["pass"] = verdict.upper() == "PASS"
        elif line.startswith("누락:"):
            missing_text = line[len("누락:"):].strip()
            if missing_text and missing_text != "없음":
                qa["missing"] = [m.strip() for m in missing_text.split(",")]
        elif line.startswith("R-09 위반:"):
            violation_text = line[len("R-09 위반:"):].strip()
            qa["r09_violation"] = violation_text != "없음"
        elif line.startswith("사유:"):
            qa["reason"] = line[len("사유:"):].strip()

    return qa


def cmd_save(args):
    """save 커맨드: 에이전트 응답을 파싱하여 TTS 결과 JSON으로 저장."""
    subject = args.subject
    file_label = args.file
    input_path = args.input

    if subject not in SUBJECT_ID_MAP:
        log.error("알 수 없는 과목: %s (가능: %s)", subject, ", ".join(SUBJECT_ID_MAP.keys()))
        sys.exit(1)

    # Phase 1 JSON 찾기 (메타데이터용)
    raw_file = find_raw_text_file(subject, file_label)
    if not raw_file:
        log.error("Phase 1 JSON 없음: %s/%s", subject, file_label)
        sys.exit(1)

    with open(raw_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    file_id = raw_data.get("fileId", file_label)
    subject_id = SUBJECT_ID_MAP[subject]

    # 기존 TTS 결과 로드 (있으면 병합)
    tts_out_dir = TTS_TEXTS_DIR / subject_id
    tts_out_dir.mkdir(parents=True, exist_ok=True)
    tts_out_file = tts_out_dir / f"{file_id}.json"

    existing_tts = None
    if tts_out_file.exists():
        with open(tts_out_file, "r", encoding="utf-8") as f:
            existing_tts = json.load(f)

    # 에이전트 응답 로드
    # input_path가 "-"이면 stdin에서 읽기
    if input_path == "-":
        raw_content = sys.stdin.read()
    else:
        input_file = Path(input_path)
        if not input_file.exists():
            log.error("입력 파일 없음: %s", input_path)
            sys.exit(1)
        with open(input_file, "r", encoding="utf-8") as f:
            raw_content = f.read()

    # JSON Lines 형식인 경우 assistant 응답 텍스트 추출
    agent_output = extract_agent_text(raw_content)
    if agent_output is raw_content:
        log.info("일반 텍스트 입력으로 처리")
    else:
        log.info("JSON Lines 형식 감지: assistant 응답 추출 완료 (%d chars)", len(agent_output))

    # --case 필터: 단일 Case 결과 저장
    if args.case:
        target_cases = [c for c in raw_data.get("cases", []) if c.get("id") == args.case]
        if not target_cases:
            log.error("Case를 찾지 못함: %s", args.case)
            sys.exit(1)

        case_meta = target_cases[0]
        parsed = parse_tts_result(agent_output)

        case_result = {
            "id": case_meta.get("id"),
            "label": case_meta.get("label"),
            "subtitle": case_meta.get("subtitle", ""),
            **parsed,
        }

        # 기존 파일에 병합 또는 새로 생성
        if existing_tts:
            tts_data = existing_tts
            # 기존 cases에서 같은 id 교체 또는 추가
            case_ids = {c["id"]: i for i, c in enumerate(tts_data.get("cases", []))}
            if case_result["id"] in case_ids:
                tts_data["cases"][case_ids[case_result["id"]]] = case_result
                log.info("기존 Case 교체: %s", case_result["id"])
            else:
                tts_data["cases"].append(case_result)
                log.info("새 Case 추가: %s", case_result["id"])
            tts_data["generatedAt"] = datetime.now(timezone.utc).isoformat()
        else:
            tts_data = {
                "subject": subject,
                "file": file_label,
                "fileId": file_id,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "rulesVersion": RULES_VERSION,
                "cases": [case_result],
            }
    else:
        # 전체 파일 결과: 에이전트 응답에 여러 Case가 있을 수 있음
        # Case 구분: "## Case XX" 또는 "# Case XX" 마커로 분리
        case_outputs = _split_multi_case_output(agent_output, raw_data.get("cases", []))

        cases_results = []
        for case_meta, case_text in case_outputs:
            parsed = parse_tts_result(case_text)
            cases_results.append({
                "id": case_meta.get("id"),
                "label": case_meta.get("label"),
                "subtitle": case_meta.get("subtitle", ""),
                **parsed,
            })

        tts_data = {
            "subject": subject,
            "file": file_label,
            "fileId": file_id,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "rulesVersion": RULES_VERSION,
            "cases": cases_results,
        }

    # JSON 저장
    with open(tts_out_file, "w", encoding="utf-8") as f:
        json.dump(tts_data, f, ensure_ascii=False, indent=2)

    log.info("TTS 결과 저장: %s (%d cases)", tts_out_file, len(tts_data["cases"]))

    # progress.json 업데이트
    progress = load_progress()
    if subject_id in progress.get("subjects", {}):
        files = progress["subjects"][subject_id].get("files", {})
        if file_id in files:
            # 모든 Case가 완료되었는지 확인
            total_cases = files[file_id].get("cases", 0)
            done_cases = len(tts_data.get("cases", []))
            if done_cases >= total_cases:
                files[file_id]["status"] = "tts_done"
                log.info("진행 상태 업데이트: %s/%s → tts_done", subject_id, file_id)
            else:
                log.info(
                    "진행 중: %s/%s (%d/%d cases)",
                    subject_id, file_id, done_cases, total_cases,
                )
    save_progress(progress)


def extract_agent_text(raw_content: str) -> str:
    """
    에이전트 응답 파일에서 실제 텍스트를 추출한다.

    지원 형식:
    1. JSON Lines (.output 파일): 마지막 assistant 메시지의 content[].text 추출
    2. 일반 텍스트: 그대로 반환
    """
    stripped = raw_content.strip()
    if not stripped.startswith("{"):
        return raw_content

    # JSON Lines 형식 시도
    lines = stripped.split("\n")
    assistant_text = ""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get("message", {})
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        content_items = msg.get("content", [])
        if isinstance(content_items, list):
            parts = []
            for item in content_items:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            if parts:
                assistant_text = "\n".join(parts)
                break
        elif isinstance(content_items, str):
            assistant_text = content_items
            break

    return assistant_text if assistant_text else raw_content


def _split_multi_case_output(
    agent_output: str, cases_meta: list[dict]
) -> list[tuple[dict, str]]:
    """
    여러 Case가 포함된 에이전트 응답을 Case별로 분리한다.

    지원 마커 (우선순위 순):
    1. "=== CASE: caseXX ===" (에이전트 출력 표준 마커)
    2. "## Case XX", "# Case XX", "--- Case XX ---"
    """
    # 우선: "=== CASE: caseXX ===" 마커 패턴
    case_id_pattern = re.compile(
        r"===\s*CASE:\s*(case\d+)\s*===",
        re.IGNORECASE,
    )
    id_matches = list(case_id_pattern.finditer(agent_output))

    if id_matches:
        results = []
        for i, match in enumerate(id_matches):
            case_id = match.group(1).lower()
            start = match.end()
            end = id_matches[i + 1].start() if i + 1 < len(id_matches) else len(agent_output)
            case_text = agent_output[start:end]

            meta = next(
                (c for c in cases_meta if c.get("id") == case_id),
                {"id": case_id, "label": case_id, "subtitle": ""},
            )
            results.append((meta, case_text))
        return results

    # 폴백: "## Case XX" / "# Case XX" 등 숫자 기반 마커
    case_pattern = re.compile(
        r"(?:^|\n)(?:#{1,3}\s*)?(?:Case\s*(\d+)|case(\d+))",
        re.IGNORECASE,
    )
    matches = list(case_pattern.finditer(agent_output))

    if not matches:
        # Case 구분 마커가 없으면 전체를 첫 번째 Case로 간주
        if cases_meta:
            return [(cases_meta[0], agent_output)]
        return []

    results = []
    for i, match in enumerate(matches):
        case_num = match.group(1) or match.group(2)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(agent_output)
        case_text = agent_output[start:end]

        # 메타데이터 매칭 (case_num으로)
        case_id = f"case{int(case_num):02d}"
        meta = next(
            (c for c in cases_meta if c.get("id") == case_id),
            {"id": case_id, "label": f"Case {case_num}", "subtitle": ""},
        )
        results.append((meta, case_text))

    return results


# ---------------------------------------------------------------------------
# 기능 3: 상태 확인
# ---------------------------------------------------------------------------

def cmd_status(args):
    """status 커맨드: 진행 상황 표시."""
    progress = load_progress()
    stats = progress.get("stats", {})

    print("\n=== Phase 2 TTS 변환 진행 현황 ===\n")
    print(f"총 파일: {stats.get('totalFiles', 0)}개")
    print(f"추출 완료: {stats.get('extractedFiles', 0)}개")
    print(f"TTS 완료: {stats.get('ttsDoneFiles', 0)}개")
    print(f"총 Cases: {stats.get('totalCases', 0)}개")
    print()

    # 과목별 상세
    subject_names = {v: k for k, v in SUBJECT_ID_MAP.items()}
    for subj_id, subj_data in sorted(progress.get("subjects", {}).items()):
        subj_name = subject_names.get(subj_id, subj_id)
        files = subj_data.get("files", {})

        extracted = sum(1 for f in files.values() if f.get("status") == "extracted")
        tts_done = sum(1 for f in files.values() if f.get("status") == "tts_done")
        total = len(files)

        print(f"[{subj_name}] 파일 {total}개: 추출 {extracted} / TTS {tts_done}")

        for file_id, file_data in sorted(files.items()):
            status = file_data.get("status", "pending")
            cases = file_data.get("cases", 0)
            label = file_data.get("label", file_id)
            status_icon = {"extracted": "[ ]", "tts_done": "[v]", "pending": "[-]"}.get(
                status, "[?]"
            )
            print(f"  {status_icon} {label} ({file_id}): {cases} cases — {status}")
        print()


def cmd_pending(args):
    """pending 커맨드: 미처리 파일 목록."""
    progress = load_progress()

    print("\n=== 미처리 파일 (TTS 변환 대기) ===\n")

    subject_names = {v: k for k, v in SUBJECT_ID_MAP.items()}
    pending_count = 0

    for subj_id, subj_data in sorted(progress.get("subjects", {}).items()):
        subj_name = subject_names.get(subj_id, subj_id)
        files = subj_data.get("files", {})

        for file_id, file_data in sorted(files.items()):
            if file_data.get("status") == "extracted":
                cases = file_data.get("cases", 0)
                label = file_data.get("label", file_id)
                print(f"  [{subj_name}] {label} ({file_id}): {cases} cases")
                pending_count += 1

    if pending_count == 0:
        print("  (미처리 파일 없음)")
    else:
        print(f"\n총 {pending_count}개 파일 대기 중")
    print()


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: TTS 변환 배치 러너"
    )
    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령")

    # generate
    gen_parser = subparsers.add_parser(
        "generate", help="TTS 변환 프롬프트 생성"
    )
    gen_parser.add_argument(
        "--subject", required=True, help="과목 (민소, 민법, 형법, 형소, 부등)"
    )
    gen_parser.add_argument(
        "--file", required=True, help="파일 라벨 (예: 미케01, 예비01)"
    )
    gen_parser.add_argument(
        "--case", help="특정 Case만 (예: case01)"
    )

    # save
    save_parser = subparsers.add_parser(
        "save", help="에이전트 응답을 TTS 결과 JSON으로 저장"
    )
    save_parser.add_argument(
        "--subject", required=True, help="과목"
    )
    save_parser.add_argument(
        "--file", required=True, help="파일 라벨"
    )
    save_parser.add_argument(
        "--case", help="특정 Case만 저장"
    )
    save_parser.add_argument(
        "--input", required=True, help="에이전트 응답 파일 경로 (- 이면 stdin)"
    )

    # status
    subparsers.add_parser("status", help="진행 상황 확인")

    # pending
    subparsers.add_parser("pending", help="미처리 파일 목록")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "save":
        cmd_save(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "pending":
        cmd_pending(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
