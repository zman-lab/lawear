#!/usr/bin/env python3
"""
Phase 1: PDF 텍스트 추출 스크립트

PDF 디렉토리를 스캔하여 과목별로 텍스트를 추출하고,
Case/문제 단위로 분리하여 JSON으로 저장한다.

Usage:
    python3 scripts/extract_pdf_text.py                          # 전체 추출
    python3 scripts/extract_pdf_text.py --subject 민소           # 특정 과목
    python3 scripts/extract_pdf_text.py --subject 민소 --file 미케02  # 특정 파일
    python3 scripts/extract_pdf_text.py --list                   # 대상 파일 목록만 출력
"""

import argparse
import json
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF가 필요합니다: pip install PyMuPDF", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

PDF_BASE = os.path.expanduser("~/Downloads/2026_USB/2026_박문각_피뎁")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "pipeline" / "raw_texts"
PROGRESS_FILE = PROJECT_ROOT / "pipeline" / "progress.json"

# 과목 매핑
SUBJECT_MAP = {
    "민소": {
        "id": "minso",
        "name": "민사소송법",
        "dirs": [
            {"path": "예비_민소", "prefix": "yebi"},
            {"path": "입문_민소", "prefix": "immun"},
        ],
        "case_pattern": r"Case\s*(\d+)",
        "file_types": {
            "미케": {"pattern": r"미케_(\d+)", "type": "mike"},
            "모고": {
                "pattern": r"모고_(\d+)",
                "type": "mogo",
                "case_pattern": r"제\s*(\d+)\s*문",  # 모고는 "제 X 문" 패턴
            },
        },
    },
    "민법": {
        "id": "minbeop",
        "name": "민법",
        "dirs": [
            {"path": "예비_민법", "prefix": "yebi"},
            {"path": "입문_민법", "prefix": "immun"},
        ],
        "case_pattern": r"Case\s*(\d+)",
        "file_types": {
            "미케": {"pattern": r"미케_(\d+)", "type": "mike"},
            "모고": {
                "pattern": r"모고_(\d+)",
                "type": "mogo",
                "case_pattern": r"제\s*(\d+)\s*문",  # 모고는 "제 X 문" 패턴
            },
        },
    },
    "형법": {
        "id": "hyeongbeop",
        "name": "형법",
        "dirs": [
            {"path": "예비_형법", "prefix": "yebi"},
            {"path": "입문_형법", "prefix": "immun"},
        ],
        "case_pattern": r"【문\s*(\d+)】",
        "split_files": True,  # 문제/답안 PDF 분리
        "file_types": {
            "예비": {
                "problem_pattern": r"예비_형법_(\d+)_문\.pdf",
                "answer_pattern": r"예비_형법_(\d+)_답\.pdf",
                "type": "yebi",
            },
            "입문": {
                "problem_pattern": r"형법_입문_(\d+)_문제\.pdf",
                "answer_pattern": r"형법_입문_(\d+)_해설\.pdf",
                "type": "immun",
            },
        },
    },
    "형소": {
        "id": "hyeongso",
        "name": "형사소송법",
        "dirs": [
            {"path": "예비_형소", "prefix": "yebi"},
        ],
        "case_pattern": r"\[제(\d+)문\]",
        "file_types": {
            "모고": {"pattern": r"모고_(\d+)\.pdf", "type": "mogo"},
        },
    },
    "부등": {
        "id": "budeung",
        "name": "부동산등기법",
        "dirs": [
            {"path": "입문_부등", "prefix": "immun"},
        ],
        "case_pattern": r"【문\s*[○○]】",
        "split_files": True,
        "file_types": {
            "입문": {
                "problem_pattern": r"부등법_입문_\d+_예상문제\.pdf",
                "answer_pattern": r"부등법_입문_\d+_예상답안\.pdf",
                "type": "immun",
            },
        },
    },
}

# TTS 대상에서 제외할 키워드
EXCLUDE_KEYWORDS = [
    "강의계획", "두문자", "보충자료", "추심명령", "청구_분쟁",
    "답안작성방법", "출제예상쟁점", "최판연습", "개정내용",
    "모범답안", "최고답안", "채점평", "쪽지시험",
    "강의추가자료", "동영상참고자료",
    "등기서류", "등기신청서", "등기사항증명서", "첨부서면",
    "등기신청서양식", "주요논점", "조문연습법", "조문.",
    "강의계획서",
]

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF 텍스트 추출
# ---------------------------------------------------------------------------

def extract_pdf_pages(pdf_path: str) -> list[dict]:
    """PDF에서 페이지별 텍스트를 추출한다."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        pages.append({"page_num": i + 1, "text": text})
    doc.close()
    return pages


def clean_page_header(text: str) -> str:
    """페이지 헤더/푸터 패턴을 제거한다."""
    # "- N -" 페이지 번호 패턴
    text = re.sub(r"^-\s*\d+\s*-\s*\n", "", text, flags=re.MULTILINE)
    # "N/N" 페이지 번호 (형법 답안)
    text = re.sub(r"^\d+/\d+\s+.*?연습문제\s+해설.*?\n", "", text, flags=re.MULTILINE)
    # 과목 헤더 라인 제거
    text = re.sub(
        r"^.*법무사.*?(예비순환|입문|모의고사).*?\n",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^.*부동산등기법.*?(예상문제|예상답안).*?\n",
        "",
        text,
        flags=re.MULTILINE,
    )
    return text


# ---------------------------------------------------------------------------
# 빈칸 정답 추출
# ---------------------------------------------------------------------------

def extract_blanks_from_text(text: str) -> dict[str, str]:
    """
    페이지 텍스트에서 빈칸 정답을 추출한다.
    패턴: ① 소각하 판결  ② 주장 자체  ③ 등기의무자
    """
    blanks = {}
    # 원문자 번호 매핑
    circled_nums = {
        "①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5",
        "⑥": "6", "⑦": "7", "⑧": "8", "⑨": "9", "⑩": "10",
        "⑪": "11", "⑫": "12", "⑬": "13", "⑭": "14", "⑮": "15",
    }

    # "① xxx ② yyy ③ zzz" 패턴의 라인 찾기
    # 빈칸 정답 라인은 보통 페이지 첫 부분이나 Case 경계 직전에 나온다
    pattern = r"([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])\s*([^①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮\n]+)"
    lines = text.split("\n")

    for line in lines:
        matches = re.findall(pattern, line)
        # 빈칸 정답 라인은 보통 2개 이상의 원문자 번호가 있는 짧은 라인
        if len(matches) >= 2:
            for circled, answer in matches:
                num = circled_nums.get(circled)
                if num:
                    blanks[num] = answer.strip()

    return blanks


# ---------------------------------------------------------------------------
# Case 분리 (민소/민법 — Case XX 패턴)
# ---------------------------------------------------------------------------

def split_cases_by_case_pattern(
    pages: list[dict], case_pattern: str, id_prefix: str = "case", label_prefix: str = "Case"
) -> list[dict]:
    """Case XX 또는 제 X 문 패턴으로 문제를 분리한다."""
    cases = []
    current_case = None
    current_text_lines = []
    current_pages = []
    all_blanks = {}

    # split용 패턴: 캡처 그룹을 비캡처로 바꿔서 사용
    # case_pattern에 (\d+)가 있으므로, 전체 매치만 캡처하는 래퍼 사용
    split_pattern = case_pattern.replace("(", "(?:")  # 내부 캡처 -> 비캡처
    split_pattern = f"({split_pattern})"  # 전체를 캡처로 감싸기

    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page_num"]

        # 이 페이지의 빈칸 정답 추출 (Case 시작 전에 있는 것들)
        page_blanks = extract_blanks_from_text(text)

        # 페이지 헤더 제거
        cleaned = clean_page_header(text)

        # Case 경계로 분할
        parts = re.split(split_pattern, cleaned)

        i = 0
        while i < len(parts):
            part = parts[i]

            # Case 번호 패턴 매치 (원본 캡처 패턴으로 번호 추출)
            case_match = re.match(case_pattern, part)
            if case_match:
                # 이전 Case 저장
                if current_case is not None:
                    cases.append(
                        _build_case(
                            current_case, current_text_lines, current_pages, all_blanks,
                            id_prefix=id_prefix, label_prefix=label_prefix,
                        )
                    )
                    all_blanks = {}

                case_num = case_match.group(1)
                current_case = case_num
                current_text_lines = []
                current_pages = [page_num]

                # Case 번호 다음의 텍스트
                if i + 1 < len(parts):
                    next_part = parts[i + 1]
                    current_text_lines.append(next_part)
                    i += 2
                else:
                    i += 1
            else:
                if current_case is not None:
                    current_text_lines.append(part)
                    if page_num not in current_pages:
                        current_pages.append(page_num)
                i += 1

        # 이 페이지의 빈칸 정답을 현재 Case에 할당
        if page_blanks:
            all_blanks.update(page_blanks)

    # 마지막 Case
    if current_case is not None:
        cases.append(
            _build_case(
                current_case, current_text_lines, current_pages, all_blanks,
                id_prefix=id_prefix, label_prefix=label_prefix,
            )
        )

    return cases


def _build_case(
    case_num: str,
    text_lines: list[str],
    pages: list[int],
    blanks: dict,
    id_prefix: str = "case",
    label_prefix: str = "Case",
) -> dict:
    """Case 데이터를 구성한다."""
    full_text = "\n".join(text_lines).strip()
    # Case 패턴 뒤의 선행 마침표/공백 제거
    full_text = re.sub(r"^\s*[.\s]*", "", full_text)

    # 빈칸 정답 라인 제거 (본문에서)
    # 원문자만 있는 라인이나 "① xxx ② yyy" 형태의 정답 라인 제거
    lines = full_text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # 원문자만 단독으로 있는 라인 제거
        if re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\s*$", stripped):
            continue
        # 빈칸 정답 라인 제거 (원문자 2개 이상 + 텍스트)
        circled_count = len(re.findall(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]", stripped))
        if circled_count >= 2 and len(stripped) < 200:
            # 정답 라인은 보통 짧다
            words = stripped.split()
            if all(
                re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]", w) or len(w) < 30
                for w in words
            ):
                continue
        cleaned_lines.append(line)

    full_text = "\n".join(cleaned_lines).strip()

    # 문제/답안 분리
    problem, answer_sections = _parse_problem_answer(full_text)

    # Case 라벨
    label = f"{label_prefix} {int(case_num):02d}"

    # subtitle 추출 (판례번호 등)
    subtitle_match = re.search(r"【(.+?)】", full_text)
    subtitle = subtitle_match.group(1) if subtitle_match else ""

    # 배점 추출
    points_match = re.search(r"\((\d+)점\)", full_text)
    points = int(points_match.group(1)) if points_match else None

    case_data = {
        "id": f"{id_prefix}{int(case_num):02d}",
        "label": label,
        "subtitle": subtitle,
        "pages": pages,
        "problem": problem,
        "answer": answer_sections,
        "blanks": blanks if blanks else {},
    }
    if points:
        case_data["metadata"] = {"points": points}
    if subtitle:
        case_data["metadata"] = case_data.get("metadata", {})
        case_data["metadata"]["caseRef"] = subtitle

    return case_data


def _parse_problem_answer(text: str) -> tuple[str, dict]:
    """문제와 답안을 분리한다."""
    # 구조: <기본적 사실관계> + <문제> + Ⅰ. 결론 + Ⅱ. 근거 + ...
    problem = ""
    answer = {"conclusion": "", "sections": []}

    # 결론/근거 경계 찾기
    conclusion_match = re.search(r"Ⅰ\.\s*결\s*론", text)
    reason_match = re.search(r"Ⅱ\.\s*근\s*거", text)

    if conclusion_match:
        problem = text[: conclusion_match.start()].strip()

        if reason_match:
            conclusion_text = text[
                conclusion_match.end() : reason_match.start()
            ].strip()
            answer["conclusion"] = conclusion_text
            reason_text = text[reason_match.end() :].strip()
        else:
            reason_text = text[conclusion_match.end() :].strip()
            answer["conclusion"] = ""

        # 소제목 파싱 (1. xxx, 2. xxx, (1) xxx 등)
        answer["sections"] = _parse_sections(reason_text)
    else:
        problem = text

    return problem, answer


def _parse_sections(text: str) -> list[dict]:
    """답안 텍스트에서 섹션을 파싱한다."""
    sections = []
    # "1. 제목", "2. 제목" 패턴으로 분할
    parts = re.split(r"(\d+\.\s+[^\n]+)", text)

    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if not part:
            i += 1
            continue

        title_match = re.match(r"(\d+)\.\s+(.+)", part)
        if title_match:
            title = title_match.group(2).strip()
            content = ""
            if i + 1 < len(parts):
                content = parts[i + 1].strip()
                i += 2
            else:
                i += 1
            sections.append({"title": title, "content": content})
        else:
            # 제목 없는 텍스트
            if sections:
                sections[-1]["content"] += "\n" + part
            i += 1

    return sections


# ---------------------------------------------------------------------------
# Case 분리 (형법 — 문/답 분리 파일)
# ---------------------------------------------------------------------------

def split_cases_hyeongbeop(
    problem_pages: list[dict], answer_pages: list[dict], case_pattern: str, num: str
) -> list[dict]:
    """형법 문제/답안 분리 PDF를 병합하여 Case를 만든다."""
    # 문제 전체 텍스트
    prob_text = "\n".join(
        clean_page_header(p["text"]) for p in problem_pages
    ).strip()
    prob_pages = [p["page_num"] for p in problem_pages]

    # 답안 전체 텍스트
    ans_text = "\n".join(
        clean_page_header(p["text"]) for p in answer_pages
    ).strip()

    # 문제에서 【문 N】 패턴으로 분할
    prob_cases = _split_by_pattern(prob_text, case_pattern)
    ans_cases = _split_by_pattern_answer(ans_text)

    cases = []
    for case_num, prob_content in prob_cases.items():
        # 배점 추출
        points_match = re.search(r"\((\d+)점\)", prob_content)
        points = int(points_match.group(1)) if points_match else None

        case_data = {
            "id": f"mun{int(case_num):02d}",
            "label": f"문 {int(case_num)}",
            "subtitle": "",
            "pages": prob_pages,
            "problem": prob_content.strip(),
            "answer": {"conclusion": "", "sections": []},
            "blanks": {},
        }
        if points:
            case_data["metadata"] = {"points": points}

        # 답안 매칭 (Case 번호로)
        if case_num in ans_cases:
            ans_content = ans_cases[case_num]
            _, answer_sections = _parse_problem_answer_simple(ans_content)
            case_data["answer"] = answer_sections

        cases.append(case_data)

    # 문제가 하나뿐인 경우 (형법은 보통 1문제/PDF)
    if not prob_cases:
        case_data = {
            "id": f"mun{int(num):02d}",
            "label": f"문 {int(num)}",
            "subtitle": "",
            "pages": prob_pages,
            "problem": prob_text,
            "answer": {"conclusion": "", "sections": _parse_sections(ans_text)},
            "blanks": {},
        }
        points_match = re.search(r"\((\d+)점\)", prob_text)
        if points_match:
            case_data["metadata"] = {"points": int(points_match.group(1))}
        cases.append(case_data)

    return cases


def _split_by_pattern(text: str, pattern: str) -> dict[str, str]:
    """패턴으로 텍스트를 분할하여 {번호: 텍스트} 딕셔너리를 반환."""
    result = {}
    matches = list(re.finditer(pattern, text))
    for i, m in enumerate(matches):
        num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result[num] = text[start:end].strip()
    return result


def _split_by_pattern_answer(text: str) -> dict[str, str]:
    """답안 텍스트를 문 번호 기준으로 분할. 형법 답안은 번호 기반 구분."""
    # "1. 문제점" 등으로 시작하는 것은 섹션. 전체를 하나의 답안으로.
    return {"1": text}


def _parse_problem_answer_simple(text: str) -> tuple[str, dict]:
    """단순 답안 파싱 (형법용)."""
    answer = {"conclusion": "", "sections": _parse_sections(text)}
    return "", answer


# ---------------------------------------------------------------------------
# Case 분리 (형소 — [제N문] 패턴)
# ---------------------------------------------------------------------------

def split_cases_hyeongso(pages: list[dict], case_pattern: str) -> list[dict]:
    """형소 모고 PDF에서 문제를 분리한다."""
    full_text = "\n".join(p["text"] for p in pages)
    cleaned = clean_page_header(full_text)

    # 문제 부분과 답안 부분을 분리
    # 형소 모고는 앞부분이 문제, 뒷부분이 답안
    # 답안은 [N] 번호로 시작하는 해설

    cases = []
    # [제N문] 패턴으로 문제 분할
    prob_parts = _split_by_pattern(cleaned, case_pattern)

    # 답안 부분 분할: [N] 패턴
    answer_pattern = r"\[(\d+)\]\s"
    ans_parts = _split_by_pattern(cleaned, answer_pattern)

    for q_num, prob_content in prob_parts.items():
        # 배점 추출
        points_match = re.search(r"\((\d+)점\)", prob_content)
        points = int(points_match.group(1)) if points_match else None

        case_data = {
            "id": f"mun{int(q_num):02d}",
            "label": f"제{q_num}문",
            "subtitle": "",
            "pages": [p["page_num"] for p in pages],
            "problem": prob_content.strip(),
            "answer": {"conclusion": "", "sections": []},
            "blanks": {},
        }
        if points:
            case_data["metadata"] = {"points": points}

        # 답안 매칭
        if q_num in ans_parts:
            ans_content = ans_parts[q_num]
            _, answer_sections = _parse_problem_answer_simple(ans_content)
            case_data["answer"] = answer_sections

        cases.append(case_data)

    return cases


# ---------------------------------------------------------------------------
# Case 분리 (부등법 — 【문 ○】 패턴)
# ---------------------------------------------------------------------------

def split_cases_budeung(
    problem_pages: list[dict], answer_pages: list[dict]
) -> list[dict]:
    """부등법 예상문제/예상답안을 병합하여 Case를 만든다."""
    prob_text = "\n".join(
        clean_page_header(p["text"]) for p in problem_pages
    ).strip()
    ans_text = "\n".join(
        clean_page_header(p["text"]) for p in answer_pages
    ).strip()

    # 【문 ○】 패턴으로 분할
    prob_pattern = r"【문\s*[○○]】"
    prob_splits = re.split(f"({prob_pattern})", prob_text)
    ans_splits = re.split(f"({prob_pattern})", ans_text)

    # 문제 추출
    prob_questions = []
    for i in range(len(prob_splits)):
        if re.match(prob_pattern, prob_splits[i]):
            content = prob_splits[i + 1] if i + 1 < len(prob_splits) else ""
            prob_questions.append(content.strip())

    # 답안 추출
    ans_questions = []
    for i in range(len(ans_splits)):
        if re.match(prob_pattern, ans_splits[i]):
            content = ans_splits[i + 1] if i + 1 < len(ans_splits) else ""
            ans_questions.append(content.strip())

    cases = []
    for idx, prob_content in enumerate(prob_questions):
        q_num = idx + 1
        points_match = re.search(r"\((\d+)점\)", prob_content)
        points = int(points_match.group(1)) if points_match else None

        # 제목 추출 (첫 줄에서)
        first_line = prob_content.split("\n")[0].strip()

        case_data = {
            "id": f"mun{q_num:02d}",
            "label": f"문 {q_num}",
            "subtitle": first_line[:60] if first_line else "",
            "pages": [p["page_num"] for p in problem_pages],
            "problem": prob_content,
            "answer": {"conclusion": "", "sections": []},
            "blanks": {},
        }
        if points:
            case_data["metadata"] = {"points": points}

        # 답안 매칭 (순서 기반)
        if idx < len(ans_questions):
            _, answer_sections = _parse_problem_answer_simple(ans_questions[idx])
            case_data["answer"] = answer_sections

        cases.append(case_data)

    return cases


# ---------------------------------------------------------------------------
# 파일 분류 및 추출
# ---------------------------------------------------------------------------

def should_exclude(filename: str) -> bool:
    """TTS 대상에서 제외할 파일인지 확인."""
    for kw in EXCLUDE_KEYWORDS:
        if kw in filename:
            return True
    return False


def find_target_files(subject_key: str | None = None) -> list[dict]:
    """추출 대상 파일 목록을 구성한다."""
    targets = []

    subjects = {subject_key: SUBJECT_MAP[subject_key]} if subject_key else SUBJECT_MAP

    for subj_key, subj_config in subjects.items():
        subj_id = subj_config["id"]
        is_split = subj_config.get("split_files", False)

        for dir_info in subj_config["dirs"]:
            dir_name = dir_info["path"]
            dir_prefix = dir_info["prefix"]  # yebi / immun
            dir_path = os.path.join(PDF_BASE, dir_name)
            if not os.path.isdir(dir_path):
                log.warning("디렉토리 없음: %s", dir_path)
                continue

            # macOS는 NFD 유니코드를 사용하므로 NFC로 정규화하여 매칭
            # 실제 파일 경로를 구성할 때는 원본 파일명 사용
            pdf_files_raw = sorted(
                f for f in os.listdir(dir_path) if f.endswith(".pdf")
            )
            # NFC 이름 -> 원본 이름 매핑
            nfc_to_raw = {}
            for raw in pdf_files_raw:
                nfc = unicodedata.normalize("NFC", raw)
                nfc_to_raw[nfc] = raw
            pdf_files = sorted(nfc_to_raw.keys())

            if is_split:
                # 문제/답안 분리 파일 (형법, 부등법)
                for ft_key, ft_config in subj_config["file_types"].items():
                    if "problem_pattern" not in ft_config:
                        continue
                    prob_pattern = ft_config["problem_pattern"]
                    ans_pattern = ft_config["answer_pattern"]

                    # 문제 파일 찾기
                    prob_files = {}
                    ans_files = {}
                    for f in pdf_files:
                        if should_exclude(f):
                            continue
                        pm = re.search(prob_pattern, f)
                        am = re.search(ans_pattern, f)
                        if pm:
                            num = pm.group(1) if pm.lastindex else "1"
                            prob_files[num] = f
                        elif am:
                            num = am.group(1) if am.lastindex else "1"
                            ans_files[num] = f

                    for num in sorted(prob_files.keys()):
                        prob_file = prob_files[num]
                        ans_file = ans_files.get(num)

                        file_id = f"{ft_config['type']}{int(num):02d}"
                        targets.append({
                            "subject_key": subj_key,
                            "subject_id": subj_id,
                            "file_id": file_id,
                            "file_label": f"{ft_key}{num}",
                            "dir_prefix": dir_prefix,
                            "problem_pdf": os.path.join(
                                dir_path, nfc_to_raw.get(prob_file, prob_file)
                            ),
                            "answer_pdf": (
                                os.path.join(
                                    dir_path, nfc_to_raw.get(ans_file, ans_file)
                                )
                                if ans_file
                                else None
                            ),
                            "split": True,
                            "num": num,
                        })
            else:
                # 단일 PDF 파일 (민소, 민법, 형소)
                for ft_key, ft_config in subj_config["file_types"].items():
                    ft_pattern = ft_config["pattern"]
                    for f in pdf_files:
                        if should_exclude(f):
                            continue
                        m = re.search(ft_pattern, f)
                        if m:
                            num = m.group(1)
                            # 접두사로 file_id 충돌 방지
                            type_prefix = ft_config["type"]
                            file_id = f"{dir_prefix}_{type_prefix}{int(num):02d}"
                            target_data = {
                                "subject_key": subj_key,
                                "subject_id": subj_id,
                                "file_id": file_id,
                                "file_label": f"{ft_key}{num}",
                                "dir_prefix": dir_prefix,
                                "pdf_path": os.path.join(
                                    dir_path, nfc_to_raw.get(f, f)
                                ),
                                "split": False,
                            }
                            # file_type별 case_pattern 오버라이드
                            if "case_pattern" in ft_config:
                                target_data["case_pattern"] = ft_config["case_pattern"]
                            targets.append(target_data)

    return targets


def extract_file(target: dict) -> dict | None:
    """단일 파일을 추출하여 JSON 구조로 반환한다."""
    subj_key = target["subject_key"]
    subj_config = SUBJECT_MAP[subj_key]
    # target에 개별 case_pattern이 있으면 그것을 우선 사용
    case_pattern = target.get("case_pattern", subj_config["case_pattern"])

    try:
        if target["split"]:
            # 문제/답안 분리 파일
            prob_pages = extract_pdf_pages(target["problem_pdf"])
            ans_pages = (
                extract_pdf_pages(target["answer_pdf"])
                if target.get("answer_pdf")
                else []
            )

            if subj_key == "형법":
                cases = split_cases_hyeongbeop(
                    prob_pages, ans_pages, case_pattern, target["num"]
                )
            elif subj_key == "부등":
                cases = split_cases_budeung(prob_pages, ans_pages)
            else:
                log.warning("미지원 분리 파일 과목: %s", subj_key)
                return None

            pdf_path_rel = os.path.relpath(target["problem_pdf"], PDF_BASE)
        else:
            # 단일 PDF
            pages = extract_pdf_pages(target["pdf_path"])
            pdf_path_rel = os.path.relpath(target["pdf_path"], PDF_BASE)

            if subj_key == "형소":
                cases = split_cases_hyeongso(pages, case_pattern)
            else:
                # 민소, 민법 — Case XX 또는 제 X 문 패턴
                # 모고 파일은 "제 X 문" 패턴 → label/id 변경
                is_mogo = "case_pattern" in target  # 모고 등 별도 패턴
                id_prefix = "mun" if is_mogo else "case"
                label_prefix = "제" if is_mogo else "Case"
                cases = split_cases_by_case_pattern(
                    pages, case_pattern, id_prefix=id_prefix, label_prefix=label_prefix
                )

        if not cases:
            log.warning(
                "Case를 찾지 못함: %s/%s", subj_key, target["file_label"]
            )

        result = {
            "subject": subj_key,
            "subjectId": target["subject_id"],
            "file": target["file_label"],
            "fileId": target["file_id"],
            "pdfPath": pdf_path_rel,
            "extractedAt": datetime.now(timezone.utc).isoformat(),
            "caseCount": len(cases),
            "cases": cases,
        }
        return result

    except Exception as e:
        log.error("추출 실패: %s/%s — %s", subj_key, target["file_label"], e)
        return None


# ---------------------------------------------------------------------------
# 진행 추적
# ---------------------------------------------------------------------------

def load_progress() -> dict:
    """progress.json을 로드한다."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "lastUpdated": "",
        "subjects": {},
        "stats": {
            "totalFiles": 0,
            "extractedFiles": 0,
            "ttsDoneFiles": 0,
            "totalCases": 0,
            "extractedCases": 0,
        },
    }


def save_progress(progress: dict):
    """progress.json을 저장한다."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
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


def update_progress(progress: dict, target: dict, case_count: int):
    """진행 상태를 업데이트한다."""
    subj_id = target["subject_id"]
    file_id = target["file_id"]

    if subj_id not in progress["subjects"]:
        progress["subjects"][subj_id] = {"files": {}}

    progress["subjects"][subj_id]["files"][file_id] = {
        "status": "extracted",
        "cases": case_count,
        "label": target["file_label"],
    }


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PDF 텍스트 추출 (Phase 1)")
    parser.add_argument(
        "--subject", type=str, help="과목 (민소, 민법, 형법, 형소, 부등)"
    )
    parser.add_argument("--file", type=str, help="파일 (예: 미케02)")
    parser.add_argument(
        "--list", action="store_true", help="대상 파일 목록만 출력"
    )
    args = parser.parse_args()

    # 과목 검증
    if args.subject and args.subject not in SUBJECT_MAP:
        log.error(
            "알 수 없는 과목: %s (가능: %s)",
            args.subject,
            ", ".join(SUBJECT_MAP.keys()),
        )
        sys.exit(1)

    # 대상 파일 찾기
    targets = find_target_files(args.subject)

    # --file 필터
    if args.file:
        targets = [
            t
            for t in targets
            if args.file in t["file_label"] or args.file == t["file_id"]
        ]
        if not targets:
            log.error("파일을 찾지 못함: %s", args.file)
            sys.exit(1)

    if args.list:
        print(f"\n추출 대상 파일: {len(targets)}개\n")
        for t in targets:
            if t["split"]:
                ans_str = (
                    f" + {os.path.basename(t['answer_pdf'])}"
                    if t.get("answer_pdf")
                    else " (답안 없음)"
                )
                print(
                    f"  [{t['subject_key']}] {t['file_label']}: "
                    f"{os.path.basename(t['problem_pdf'])}{ans_str}"
                )
            else:
                print(
                    f"  [{t['subject_key']}] {t['file_label']}: "
                    f"{os.path.basename(t['pdf_path'])}"
                )
        return

    log.info("추출 시작 — 대상 파일: %d개", len(targets))

    # 진행 상태 로드
    progress = load_progress()

    # 이미 pending으로 모든 대상 파일 등록
    for t in targets:
        subj_id = t["subject_id"]
        file_id = t["file_id"]
        if subj_id not in progress["subjects"]:
            progress["subjects"][subj_id] = {"files": {}}
        if file_id not in progress["subjects"][subj_id]["files"]:
            progress["subjects"][subj_id]["files"][file_id] = {
                "status": "pending",
                "cases": 0,
                "label": t["file_label"],
            }

    success_count = 0
    fail_count = 0
    total_cases = 0

    for i, target in enumerate(targets):
        subj_key = target["subject_key"]
        file_label = target["file_label"]
        log.info(
            "[%d/%d] 추출 중: %s/%s",
            i + 1,
            len(targets),
            subj_key,
            file_label,
        )

        result = extract_file(target)
        if result is None:
            fail_count += 1
            continue

        # JSON 저장
        out_dir = OUTPUT_DIR / target["subject_id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{target['file_id']}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        case_count = result["caseCount"]
        total_cases += case_count
        success_count += 1

        # 진행 상태 업데이트
        update_progress(progress, target, case_count)

        log.info(
            "  → %s (%d cases)",
            os.path.relpath(out_path, PROJECT_ROOT),
            case_count,
        )

    # 진행 상태 저장
    save_progress(progress)

    # 요약
    log.info("")
    log.info("=" * 50)
    log.info("추출 완료")
    log.info("  성공: %d 파일, 실패: %d 파일", success_count, fail_count)
    log.info("  총 Cases: %d개", total_cases)
    log.info("  출력: %s", OUTPUT_DIR)
    log.info("  진행: %s", PROGRESS_FILE)
    log.info("=" * 50)


if __name__ == "__main__":
    main()
