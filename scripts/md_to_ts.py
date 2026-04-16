#!/usr/bin/env python3
"""
docs/tts/{과목}/*.md 파일들을 파싱하여
web/src/data/tts/2026/ 아래 TypeScript 데이터 파일로 변환하는 스크립트.

210개 .md → minbeop.ts, minso.ts (예비/입문 분리)
"""

import os
import re
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_TTS_DIR = PROJECT_ROOT / "docs" / "tts"
WEB_DATA_DIR = PROJECT_ROOT / "web" / "src" / "data" / "tts" / "2026"

# 폴더 → subject 매핑
FOLDER_CONFIG = {
    "예비_민법": {
        "subject_id": "minbeop_yebi_2026",
        "ts_file": "minbeop.ts",   # minbeop.ts에 예비+입문 합침
        "subject_prefix": "minbeop_yebi",
        "name_prefix": "예비",
    },
    "입문_민법": {
        "subject_id": "minbeop_immun_2026",
        "ts_file": "minbeop.ts",
        "subject_prefix": "minbeop_immun",
        "name_prefix": "입문",
    },
    "예비_민소": {
        "subject_id": "minso_yebi_2026",
        "ts_file": "minso.ts",
        "subject_prefix": "minso_yebi",
        "name_prefix": "예비",
    },
    "입문_민소": {
        "subject_id": "minso_immun_2026",
        "ts_file": "minso.ts",
        "subject_prefix": "minso_immun",
        "name_prefix": "입문",
    },
}

# ts_file별 출력 설정
TS_FILE_CONFIG = {
    "minbeop.ts": {
        "var_name": "files",
    },
    "minso.ts": {
        "var_name": "files",
    },
}


def parse_md_file(filepath: Path) -> Optional[dict]:
    """
    .md 파일을 파싱하여 TTS 데이터를 추출한다.

    Returns:
        {
            "id": "2026_minbeop_yebi_모고01_01",
            "problem": [...],
            "toc": [...],
            "answer": [...],
            "answer_lv2": [...],
            "answer_lv3": [...],
            "answer_lv4": [...],
        }
    """
    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 파일명에서 ID 추출 (확장자 제거)
    file_id = filepath.stem

    # 섹션 분리를 위한 상태머신
    current_h2 = ""
    current_h3 = ""
    sections: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for line in lines:
        # ## 헤더 감지
        h2_match = re.match(r'^## (.+)$', line)
        if h2_match:
            current_h2 = h2_match.group(1).strip()
            current_h3 = ""
            continue

        # ### 헤더 감지
        h3_match = re.match(r'^### (.+)$', line)
        if h3_match:
            current_h3 = h3_match.group(1).strip()
            continue

        # diff 이후 섹션은 무시
        if current_h2.startswith("diff") or current_h2.startswith("체크리스트") or current_h2.startswith("R 적용표"):
            continue

        # 메타, 원본 섹션 무시
        if current_h2 in ("메타", "") or current_h2.startswith("원본"):
            continue

        # 내용 수집
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            # 코드 블록 마커 스킵
            if stripped == "```" or stripped.startswith("```"):
                continue
            # 구분선 스킵
            if stripped == "---":
                continue
            key = f"{current_h2}|{current_h3}"
            sections[current_h2][current_h3].append(stripped)

    # 섹션에서 데이터 추출
    result = {
        "id": file_id,
        "problem": [],
        "toc": [],
        "answer": [],
        "answer_lv2": [],
        "answer_lv3": [],
        "answer_lv4": [],
    }

    # Lv.1 빠른복습
    lv1_key = None
    for k in sections:
        if "Lv.1" in k or "빠른복습" in k:
            lv1_key = k
            break

    if lv1_key:
        lv1 = sections[lv1_key]
        for h3_key, lines_list in lv1.items():
            if "문제" in h3_key:
                result["problem"] = lines_list
            elif "목차" in h3_key:
                result["toc"] = lines_list
            elif "답안" in h3_key:
                result["answer"] = lines_list

    # Lv.2 핵심요약
    lv2_key = None
    for k in sections:
        if "Lv.2" in k or "핵심요약" in k:
            lv2_key = k
            break

    if lv2_key:
        lv2 = sections[lv2_key]
        for h3_key, lines_list in lv2.items():
            if "답안" in h3_key:
                result["answer_lv2"] = lines_list
                break

    # Lv.3 슈퍼심플
    lv3_key = None
    for k in sections:
        if "Lv.3" in k or "슈퍼심플" in k:
            lv3_key = k
            break

    if lv3_key:
        lv3 = sections[lv3_key]
        for h3_key, lines_list in lv3.items():
            if "답안" in h3_key:
                result["answer_lv3"] = lines_list
                break

    # Lv.4 암기노트 — h2 바로 아래에 있는 텍스트 (h3 없이)
    lv4_key = None
    for k in sections:
        if "Lv.4" in k or "암기노트" in k:
            lv4_key = k
            break

    if lv4_key:
        lv4 = sections[lv4_key]
        # Lv.4는 h3 없이 바로 본문이 오는 경우가 대부분
        # "" key (빈 h3)에 수집됨
        all_lv4_lines = []
        for h3_key, lines_list in lv4.items():
            all_lv4_lines.extend(lines_list)
        result["answer_lv4"] = all_lv4_lines

    # 최소 검증: answer가 있어야 유효
    if not result["answer"] and not result["answer_lv4"]:
        return None

    return result


def extract_label_and_subtitle(file_id: str, problem_lines: list[str]) -> tuple[str, str]:
    """
    파일 ID와 문제 텍스트에서 label과 subtitle을 추출한다.

    예: 2026_minbeop_yebi_모고01_01 → label="제1문", subtitle="첫 줄 앞 10자"
    """
    # ID에서 문제 번호 추출
    parts = file_id.split("_")
    q_num = parts[-1] if parts else "01"

    # 부수 문번 처리 (13-1 → 제13문-1)
    if "-" in q_num:
        main, sub = q_num.split("-", 1)
        label = f"제{main}문-{sub}"
    else:
        # 숫자만 추출
        num_match = re.match(r'(\d+)', q_num)
        if num_match:
            label = f"제{int(num_match.group(1))}문"
        else:
            label = f"제{q_num}문"

    # subtitle: 문제 첫 줄에서 키워드 추출 (최대 15자)
    subtitle = ""
    if problem_lines:
        first_line = problem_lines[0]
        # 20자까지 자르기
        subtitle = first_line[:20].rstrip(",. ")
        if len(first_line) > 20:
            subtitle += "..."

    return label, subtitle


def estimate_duration(answer_lines: list[str]) -> str:
    """답안 줄 수로 대략적인 소요시간 추정."""
    total_chars = sum(len(line) for line in answer_lines)
    # 약 200자/분 TTS 속도 기준
    minutes = max(1, round(total_chars / 200))
    if minutes < 2:
        return "1:00"
    return f"{minutes}:00"


def parse_toc_lines(toc_lines: list[str]) -> list[dict]:
    """
    목차 줄을 TocItem 배열로 변환한다.

    입력: ["첫째, 주채무 시효소멸 여부.", "둘째, 연대보증채무 시효소멸 여부."]
    또는: ["1. 문제점", "2. 제소 전 사망자임을 간과한 판결의 효력"]
    """
    result = []
    for i, line in enumerate(toc_lines):
        stripped = line.strip()
        if not stripped:
            continue

        # 들여쓰기 감지
        indent = 0
        if line.startswith("  ") or line.startswith("\t"):
            indent = 1
            if line.startswith("    "):
                indent = 2

        # 번호 추출 시도
        num_match = re.match(r'^(\d+[\.\):])\s*(.+)$', stripped)
        ordinal_match = re.match(r'^(첫째|둘째|셋째|넷째|다섯째|여섯째|일곱째|여덟째|아홉째|열째)[,.]?\s*(.+)$', stripped)
        sub_match = re.match(r'^(\d+\))\s*(.+)$', stripped)

        if num_match:
            number = num_match.group(1).rstrip(".):").strip()
            text = num_match.group(2).strip()
        elif ordinal_match:
            ordinal_map = {"첫째": "1", "둘째": "2", "셋째": "3", "넷째": "4",
                           "다섯째": "5", "여섯째": "6", "일곱째": "7", "여덟째": "8",
                           "아홉째": "9", "열째": "10"}
            number = ordinal_map.get(ordinal_match.group(1), str(i + 1))
            text = ordinal_match.group(2).strip()
        elif sub_match:
            number = sub_match.group(1).rstrip(")").strip()
            text = sub_match.group(2).strip()
            indent = 1
        else:
            number = str(i + 1)
            text = stripped

        result.append({
            "number": number,
            "text": text,
            "indent": indent,
        })

    return result


def group_files_by_mike_mogo(parsed_files: list[dict], folder_name: str) -> dict[str, list[dict]]:
    """
    파싱된 파일들을 미케/모고 번호별로 그룹핑한다.

    예: 미케01_01, 미케01_02 → "미케01" 그룹
        모고01_01, 모고01_02 → "모고01" 그룹
    """
    groups = defaultdict(list)

    for pf in parsed_files:
        file_id = pf["id"]
        # ID에서 그룹키 추출: 2026_minbeop_yebi_미케01_01 → 미케01
        # 파일명 패턴: {year}_{subject}_{stage}_{type}{num}_{qnum}.md
        match = re.match(r'^2026_\w+_\w+_((?:미케|모고)\d+)_', file_id)
        if match:
            group_key = match.group(1)
        else:
            group_key = "기타"

        groups[group_key].append(pf)

    # 그룹 내에서 문제 번호순 정렬
    for key in groups:
        groups[key].sort(key=lambda x: extract_sort_key(x["id"]))

    return dict(groups)


def extract_sort_key(file_id: str) -> tuple:
    """정렬 키 추출. 숫자 부분을 int로 변환하여 자연 정렬."""
    parts = file_id.split("_")
    last = parts[-1] if parts else "0"
    # "01", "02", "13-1", "13-2", "03_02" 등 처리
    nums = re.findall(r'\d+', last)
    return tuple(int(n) for n in nums) if nums else (0,)


def group_key_to_name(group_key: str, folder_prefix: str) -> str:
    """
    그룹키를 사람이 읽을 수 있는 이름으로 변환.
    미케01 → "예비 미케 01" / "입문 미케 01"
    모고01 → "예비 모고 01"
    """
    match = re.match(r'(미케|모고)(\d+)', group_key)
    if match:
        type_name = match.group(1)
        num = match.group(2)
        return f"{folder_prefix} {type_name} {num}"
    return f"{folder_prefix} {group_key}"


def generate_file_group_id(folder_name: str, group_key: str) -> str:
    """
    FileGroup의 id 생성.
    예: 예비_민법 + 미케01 → minbeop_yebi_mike01
    """
    config = FOLDER_CONFIG[folder_name]
    prefix = config["subject_prefix"]

    # 미케/모고 → mike/mogo
    type_map = {"미케": "mike", "모고": "mogo"}
    match = re.match(r'(미케|모고)(\d+)', group_key)
    if match:
        type_en = type_map.get(match.group(1), match.group(1))
        num = match.group(2)
        return f"{prefix}_{type_en}{num}"

    return f"{prefix}_{group_key}"


def build_question(pf: dict) -> dict:
    """파싱된 파일 데이터 → Question 객체 생성."""
    label, subtitle = extract_label_and_subtitle(pf["id"], pf["problem"])
    duration = estimate_duration(pf["answer"])
    toc_items = parse_toc_lines(pf["toc"])

    question = {
        "id": pf["id"],
        "label": label,
        "subtitle": subtitle,
        "duration": duration,
        "content": {
            "problem": pf["problem"],
            "toc": toc_items,
            "answer": pf["answer"],
        }
    }

    # Optional fields
    if pf["answer_lv2"]:
        question["content"]["answer_lv2"] = pf["answer_lv2"]
    if pf["answer_lv3"]:
        question["content"]["answer_lv3"] = pf["answer_lv3"]
    if pf["answer_lv4"]:
        question["content"]["answer_lv4"] = pf["answer_lv4"]

    return question


def generate_ts_content(file_groups: list[dict]) -> str:
    """FileGroup 배열 → TypeScript 소스코드 문자열 생성."""
    ts_lines = []
    ts_lines.append("import { FileGroup } from '../../../types';")
    ts_lines.append("")
    ts_lines.append("export const files: FileGroup[] = [")

    for fg in file_groups:
        ts_lines.append("  {")
        ts_lines.append(f'    "id": {json.dumps(fg["id"], ensure_ascii=False)},')
        ts_lines.append(f'    "name": {json.dumps(fg["name"], ensure_ascii=False)},')
        ts_lines.append(f'    "questions": [')

        for q in fg["questions"]:
            ts_lines.append("      {")
            ts_lines.append(f'        "id": {json.dumps(q["id"], ensure_ascii=False)},')
            ts_lines.append(f'        "label": {json.dumps(q["label"], ensure_ascii=False)},')
            ts_lines.append(f'        "subtitle": {json.dumps(q["subtitle"], ensure_ascii=False)},')
            ts_lines.append(f'        "duration": {json.dumps(q["duration"], ensure_ascii=False)},')
            ts_lines.append(f'        "content": {{')

            # problem
            ts_lines.append(f'          "problem": [')
            for line in q["content"]["problem"]:
                ts_lines.append(f'            {json.dumps(line, ensure_ascii=False)},')
            ts_lines.append(f'          ],')

            # toc
            ts_lines.append(f'          "toc": [')
            for toc_item in q["content"]["toc"]:
                ts_lines.append(f'            {{"number": {json.dumps(toc_item["number"], ensure_ascii=False)}, "text": {json.dumps(toc_item["text"], ensure_ascii=False)}, "indent": {toc_item["indent"]}}},')
            ts_lines.append(f'          ],')

            # answer
            ts_lines.append(f'          "answer": [')
            for line in q["content"]["answer"]:
                ts_lines.append(f'            {json.dumps(line, ensure_ascii=False)},')
            ts_lines.append(f'          ],')

            # answer_lv2
            if "answer_lv2" in q["content"]:
                ts_lines.append(f'          "answer_lv2": [')
                for line in q["content"]["answer_lv2"]:
                    ts_lines.append(f'            {json.dumps(line, ensure_ascii=False)},')
                ts_lines.append(f'          ],')

            # answer_lv3
            if "answer_lv3" in q["content"]:
                ts_lines.append(f'          "answer_lv3": [')
                for line in q["content"]["answer_lv3"]:
                    ts_lines.append(f'            {json.dumps(line, ensure_ascii=False)},')
                ts_lines.append(f'          ],')

            # answer_lv4
            if "answer_lv4" in q["content"]:
                ts_lines.append(f'          "answer_lv4": [')
                for line in q["content"]["answer_lv4"]:
                    ts_lines.append(f'            {json.dumps(line, ensure_ascii=False)},')
                ts_lines.append(f'          ],')

            ts_lines.append(f'        }}')
            ts_lines.append("      },")

        ts_lines.append("    ]")
        ts_lines.append("  },")

    ts_lines.append("];")
    ts_lines.append("")

    return "\n".join(ts_lines)


def main():
    total_files = 0
    success_files = 0
    failed_files = []
    stats = {}  # folder → question count

    # ts_file별 file_groups 수집
    ts_file_groups: dict[str, list[dict]] = defaultdict(list)

    for folder_name, config in FOLDER_CONFIG.items():
        folder_path = DOCS_TTS_DIR / folder_name
        if not folder_path.exists():
            print(f"[SKIP] 폴더 없음: {folder_path}")
            continue

        md_files = sorted(folder_path.glob("*.md"))
        print(f"\n[{folder_name}] {len(md_files)}개 .md 파일 발견")

        parsed_files = []
        for md_file in md_files:
            total_files += 1
            try:
                result = parse_md_file(md_file)
                if result:
                    parsed_files.append(result)
                    success_files += 1
                else:
                    failed_files.append((md_file.name, "파싱 결과 없음 (answer 없음)"))
                    print(f"  [FAIL] {md_file.name}: answer 없음")
            except Exception as e:
                failed_files.append((md_file.name, str(e)))
                print(f"  [FAIL] {md_file.name}: {e}")

        print(f"  파싱 성공: {len(parsed_files)}/{len(md_files)}")

        # 미케/모고별 그룹핑
        groups = group_files_by_mike_mogo(parsed_files, folder_name)

        folder_questions = 0
        for group_key in sorted(groups.keys()):
            group_files = groups[group_key]
            fg_id = generate_file_group_id(folder_name, group_key)
            fg_name = group_key_to_name(group_key, config["name_prefix"])

            questions = [build_question(pf) for pf in group_files]
            folder_questions += len(questions)

            file_group = {
                "id": fg_id,
                "name": fg_name,
                "questions": questions,
            }

            ts_file_groups[config["ts_file"]].append(file_group)

            print(f"  {fg_name}: {len(questions)}문제")

        stats[folder_name] = folder_questions

    # TypeScript 파일 생성
    for ts_file, file_groups in ts_file_groups.items():
        ts_content = generate_ts_content(file_groups)
        out_path = WEB_DATA_DIR / ts_file
        out_path.write_text(ts_content, encoding="utf-8")
        print(f"\n[출력] {out_path} ({len(file_groups)} FileGroups, {sum(len(fg['questions']) for fg in file_groups)} Questions)")

    # 요약
    print(f"\n{'='*50}")
    print(f"총 파일: {total_files}")
    print(f"파싱 성공: {success_files}")
    print(f"파싱 실패: {len(failed_files)}")
    if failed_files:
        for name, reason in failed_files:
            print(f"  - {name}: {reason}")

    for folder, count in stats.items():
        print(f"  {folder}: {count}문제")

    return 0 if not failed_files else 1


if __name__ == "__main__":
    sys.exit(main())
