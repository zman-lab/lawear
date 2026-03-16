#!/usr/bin/env python3
"""
Phase 2 TTS JSON -> web/src/data/ttsData.ts 변환 스크립트.

pipeline/tts_texts/ 하위 JSON 파일을 읽어서
웹앱의 Subject[] 구조에 맞는 TypeScript 파일을 생성한다.
"""

import json
import math
import os
import re
import sys

# ──────────────────────────────────────────────────────────────────────────────
# 과목 매핑
# ──────────────────────────────────────────────────────────────────────────────
SUBJECT_META = {
    "minso": {
        "name": "민사소송법",
        "shortName": "민소",
        "colorClass": "blue",
        "aliases": ["민소", "민사소송법"],
    },
    "minbeop": {
        "name": "민법",
        "shortName": "민법",
        "colorClass": "emerald",
        "aliases": ["민법"],
    },
    "hyung": {
        "name": "형법",
        "shortName": "형법",
        "colorClass": "rose",
        "aliases": ["형법"],
    },
    "hyungso": {
        "name": "형사소송법",
        "shortName": "형소",
        "colorClass": "violet",
        "aliases": ["형소", "형사소송법"],
    },
    "budeung": {
        "name": "부동산등기법",
        "shortName": "부등",
        "colorClass": "amber",
        "aliases": ["부등", "부동산등기법"],
    },
}

# Phase 2 JSON 디렉토리명 -> 과목 ID 매핑
DIR_TO_SUBJECT = {
    "minso": "minso",
    "minbeop": "minbeop",
    "hyung": "hyung",
    "hyungso": "hyungso",
    "hyeongbeop": "hyung",
    "hyeongso": "hyungso",
    "budeung": "budeung",
}

# 파일명 -> 표시명 매핑
FILE_DISPLAY_NAMES = {
    "yebi_mike": "예비 미케",
    "yebi_mogo": "예비 모고",
    "sun2_mogo": "2순환 모고",
}


def text_to_sentences(text: str) -> list[str]:
    """TTS 텍스트(단일 문자열)를 문장 배열로 변환."""
    if not text or not text.strip():
        return []
    # 줄바꿈으로 분리 후 빈 줄 제거
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines


def estimate_duration(problem: list[str], answer: list[str]) -> str:
    """문장 수 기반으로 대략적 재생 시간 추정 (분:초)."""
    total_chars = sum(len(s) for s in problem) + sum(len(s) for s in answer)
    # 한국어 TTS 평균 약 300자/분
    total_minutes = total_chars / 300
    minutes = int(total_minutes)
    seconds = int((total_minutes - minutes) * 60)
    # 10초 단위로 반올림
    seconds = math.ceil(seconds / 10) * 10
    if seconds >= 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


def file_display_name(file_id: str) -> str:
    """파일 ID에서 표시명 생성. yebi_mike01 -> 예비 미케01"""
    for prefix, display in FILE_DISPLAY_NAMES.items():
        if file_id.startswith(prefix):
            num = file_id[len(prefix):]
            return f"{display}{num}"
    return file_id


def build_subjects(tts_texts_dir: str) -> list[dict]:
    """pipeline/tts_texts/ 디렉토리를 읽어서 Subject[] 구조 생성."""
    subjects = {}

    for dir_name in sorted(os.listdir(tts_texts_dir)):
        dir_path = os.path.join(tts_texts_dir, dir_name)
        if not os.path.isdir(dir_path) or dir_name not in DIR_TO_SUBJECT:
            continue

        subject_id = DIR_TO_SUBJECT[dir_name]
        meta = SUBJECT_META[subject_id]

        if subject_id not in subjects:
            subjects[subject_id] = {
                "id": subject_id,
                "name": meta["name"],
                "shortName": meta["shortName"],
                "colorClass": meta["colorClass"],
                "files": [],
                "totalQuestions": 0,
                "completedQuestions": 0,
            }

        json_files = sorted(
            f for f in os.listdir(dir_path) if f.endswith(".json")
        )

        for json_file in json_files:
            file_path = os.path.join(dir_path, json_file)
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            file_id = data.get("fileId", json_file.replace(".json", ""))
            file_group = {
                "id": file_id,
                "name": file_display_name(file_id),
                "questions": [],
            }

            for case_data in data.get("cases", []):
                problem = text_to_sentences(case_data.get("problem_tts", ""))
                answer = text_to_sentences(case_data.get("answer_tts", ""))
                toc = case_data.get("toc", [])

                question = {
                    "id": case_data["id"],
                    "label": case_data.get("label", case_data["id"]),
                    "subtitle": case_data.get("subtitle", ""),
                    "duration": estimate_duration(problem, answer),
                    "content": {
                        "problem": problem,
                        "toc": toc,
                        "answer": answer,
                    },
                }
                file_group["questions"].append(question)

            subjects[subject_id]["files"].append(file_group)
            subjects[subject_id]["totalQuestions"] += len(
                file_group["questions"]
            )
            subjects[subject_id]["completedQuestions"] += len(
                file_group["questions"]
            )

    # 과목 순서 고정 (민소, 민법, 형법, 형소, 부등)
    order = ["minso", "minbeop", "hyung", "hyungso", "budeung"]
    result = []
    for sid in order:
        if sid in subjects:
            result.append(subjects[sid])
        else:
            meta = SUBJECT_META[sid]
            result.append(
                {
                    "id": sid,
                    "name": meta["name"],
                    "shortName": meta["shortName"],
                    "colorClass": meta["colorClass"],
                    "files": [],
                    "totalQuestions": 0,
                    "completedQuestions": 0,
                }
            )
    return result


def generate_typescript(subjects: list[dict]) -> str:
    """Subject[] 데이터를 TypeScript 소스로 변환."""
    lines = []
    lines.append("import { Subject } from '../types';")
    lines.append("")
    lines.append(
        "// Auto-generated by scripts/build_app_data.py — DO NOT EDIT MANUALLY"
    )
    lines.append(
        f"// Generated from pipeline/tts_texts/ ({sum(s['totalQuestions'] for s in subjects)} cases)"
    )
    lines.append("")

    # JSON으로 직렬화 후 TypeScript 변수로 할당
    json_str = json.dumps(subjects, ensure_ascii=False, indent=2)

    lines.append(f"export const subjects: Subject[] = {json_str};")
    lines.append("")

    return "\n".join(lines)


def main():
    # 프로젝트 루트 자동 감지
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    tts_texts_dir = os.path.join(project_root, "pipeline", "tts_texts")
    output_path = os.path.join(project_root, "web", "src", "data", "ttsData.ts")

    if not os.path.isdir(tts_texts_dir):
        print(f"ERROR: {tts_texts_dir} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Reading Phase 2 JSON from: {tts_texts_dir}")
    subjects = build_subjects(tts_texts_dir)

    total = sum(s["totalQuestions"] for s in subjects)
    for s in subjects:
        files_count = len(s["files"])
        q_count = s["totalQuestions"]
        print(f"  {s['name']}: {files_count} files, {q_count} cases")

    ts_code = generate_typescript(subjects)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ts_code)

    print(f"\nGenerated: {output_path}")
    print(f"Total: {total} cases across {sum(len(s['files']) for s in subjects)} files")


if __name__ == "__main__":
    main()
