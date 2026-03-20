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

# 과목 단축명 -> 과목 키 매핑 (JSON meta.subject 필드 파싱용)
SUBJECT_MAP = {
    "민소": "minso",
    "민사소송법": "minso",
    "민법": "minbeop",
    "형법": "hyung",
    "형소": "hyungso",
    "형사소송법": "hyungso",
    "부등": "budeung",
    "부동산등기법": "budeung",
    "민사서류": "minseo",
    "부등서류": "budseo",
}

# 파일명 prefix -> 표시명 매핑
FILE_NAME_MAP = {
    "immun_mike": "예비순환 미케",
    "yebi_mike": "예비순환 미케",
    "yebi_mogo": "예비순환 모고",
    "immun": "예비순환",
    "yebi": "예비순환",
}


def short_file_from_raw(raw_file_id: str) -> str:
    """
    파일명에서 약자(short_file) 추출.

    immun_mike01 -> mike01
    yebi_mike01  -> ymike01
    yebi_mogo01  -> ymogo01
    immun01      -> immun01
    immun02      -> immun02
    """
    if raw_file_id.startswith("immun_"):
        # immun_mike01 -> mike01
        return raw_file_id[len("immun_"):]
    if raw_file_id.startswith("yebi_"):
        # yebi_mike01 -> ymike01, yebi_mogo01 -> ymogo01
        suffix = raw_file_id[len("yebi_"):]
        return f"y{suffix}"
    # immun01, immun02, ... -> 그대로
    return raw_file_id


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


def file_display_name(raw_file_id: str) -> str:
    """
    파일 ID(raw)에서 표시명 생성.
    FILE_NAME_MAP을 길이 내림차순으로 매칭해서 첫 번째 prefix가 이긴다.

    immun_mike01 -> 예비순환 미케01
    yebi_mike01  -> 예비순환 미케01
    yebi_mogo01  -> 예비순환 모고01
    immun01      -> 예비순환01
    """
    # 길이가 긴 prefix 우선 매칭
    for prefix in sorted(FILE_NAME_MAP.keys(), key=len, reverse=True):
        if raw_file_id.startswith(prefix):
            num = raw_file_id[len(prefix):]
            return f"{FILE_NAME_MAP[prefix]}{num}"
    return raw_file_id


def build_subjects(tts_texts_dir: str) -> list[dict]:
    """pipeline/tts_texts/ 디렉토리를 읽어서 Subject[] 구조 생성."""
    subjects = {}

    for dir_name in sorted(os.listdir(tts_texts_dir)):
        dir_path = os.path.join(tts_texts_dir, dir_name)
        if not os.path.isdir(dir_path) or dir_name not in DIR_TO_SUBJECT:
            continue

        subject_key = DIR_TO_SUBJECT[dir_name]
        meta = SUBJECT_META[subject_key]

        json_files = sorted(
            f for f in os.listdir(dir_path) if f.endswith(".json")
        )

        for json_file in json_files:
            file_path = os.path.join(dir_path, json_file)
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # ── 메타데이터 (JSON에 있으면 사용, 없으면 기본값) ──────────────
            json_meta = data.get("meta", {})
            round_val = json_meta.get("round", "2nd")   # 기본 2차
            year_val = json_meta.get("year", "2026")    # 기본 2026

            # ── Subject ID ────────────────────────────────────────────────────
            subject_id = f"{round_val}_{subject_key}_{year_val}"
            # 예: 2nd_minso_2026

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

            # ── File ID ───────────────────────────────────────────────────────
            raw_file_id = data.get("fileId", json_file.replace(".json", ""))
            file_id = f"{round_val}_{subject_key}_{year_val}_{raw_file_id}"
            # 예: 2nd_minso_2026_immun_mike01

            file_group = {
                "id": file_id,
                "name": file_display_name(raw_file_id),
                "questions": [],
            }

            # ── Questions ─────────────────────────────────────────────────────
            short_file = short_file_from_raw(raw_file_id)

            for case_data in data.get("cases", []):
                problem = text_to_sentences(case_data.get("problem_tts", ""))
                answer = text_to_sentences(case_data.get("answer_tts", ""))
                toc = case_data.get("toc", [])

                raw_case_id = case_data["id"]
                question_id = f"{round_val}_{subject_key}_{short_file}_{raw_case_id}"
                # 예: 2nd_minso_mike01_case01

                question = {
                    "id": question_id,
                    "label": case_data.get("label", raw_case_id),
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
    # subject_id가 round_key_year 형식이므로 subject_key 기준으로 정렬
    order = ["minso", "minbeop", "hyung", "hyungso", "budeung"]
    result = []
    seen_keys = set()
    for sid, sdata in subjects.items():
        seen_keys.add(sid)

    # order 기준으로 subject_key 포함된 항목 순서 정렬
    def subject_order_key(sid: str) -> int:
        for i, key in enumerate(order):
            if f"_{key}_" in sid or sid.endswith(f"_{key}"):
                return i
        return len(order)

    result = sorted(subjects.values(), key=lambda s: subject_order_key(s["id"]))

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
