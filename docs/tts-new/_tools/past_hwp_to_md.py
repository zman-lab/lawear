#!/usr/bin/env python3
"""기출문제 hwp → 7과목 .md 자동 변환 + _file_index entry 등재 + QA 보고서.

Usage:
  past_hwp_to_md.py <hwp_path> [--round 제30회] [--dry-run] [--report-only]
  past_hwp_to_md.py --verify <round_dir>   # 기존 .md 폴더로 보고서만

QA 게이트:
  - 각 과목별 【문 N】 추출 + (N점) 점수 합산
  - 총점 보고서 (사용자 검수용)
  - dry-run/report-only: .md/entry 생성 안 함, 보고서만
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = '/Users/nhn/zman-lab/lawear-lawear-f081-past-exams/docs/tts-new'
HWP5HTML = '/tmp/hwp_venv/bin/hwp5html'
PAST_DIR = os.path.join(ROOT, '기출문제')
INDEX_PATH = os.path.join(ROOT, '_file_index.json')

# 과목 헤더 패턴 (단독 헤더 + 【문 1】 기준)
# 변형 흡수: '제2차' / '2차' / 《과목》 꺽쇠 / '제 2 차시험' 등
def _hp(subj_pat: str) -> str:
    # 현대 패턴 (법무사 [제]2차 시험 + 과목 + 【문) | 옛 꺽쇠 (《과목》 + 【문)
    return (
        rf'(?:법무사\s*제?\s*2\s*차\s*시험\s*{subj_pat}|'
        rf'《\s*{subj_pat}\s*》)\s*【문'
    )

PATTERNS = {
    '민법':                  _hp(r'민\s*법'),
    '민사소송법':             _hp(r'민사소송법'),
    '민사사건관련서류의 작성':   _hp(r'민사사건관련서류의\s*작성'),
    '형법':                  _hp(r'형\s*법'),
    '형사소송법':             _hp(r'형사소송법'),
    '부동산등기법':            _hp(r'부\s*동\s*산\s*등\s*기\s*법'),
    '등기신청서류의 작성':      _hp(r'등기신청서류의\s*작성'),
}
EN = {
    '민법': 'minbeop', '민사소송법': 'minso',
    '민사사건관련서류의 작성': 'minsadocs',
    '형법': 'hyungbeop', '형사소송법': 'hyungso',
    '부동산등기법': 'budeunglaw', '등기신청서류의 작성': 'budeungdocs',
}
# 별첨 제외 과목 (수험생이 첨부서면 보고 답안 작성)
NO_APPENDIX = {'민사사건관련서류의 작성', '등기신청서류의 작성'}


def extract_text(hwp_path: str) -> str:
    """hwp → html → text."""
    out_dir = tempfile.mkdtemp(prefix='past_hwp_')
    subprocess.run([HWP5HTML, '--output', out_dir, hwp_path], check=True, capture_output=True)
    xhtml = os.path.join(out_dir, 'index.xhtml')
    from lxml import html as lhtml
    tree = lhtml.parse(xhtml)
    text = tree.xpath('//body')[0].text_content()
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def detect_round(text: str, fname: str = '') -> str | None:
    """본문 또는 파일명에서 제N회 추출."""
    for src in (text[:500], fname):
        # "30ȸ" 같은 깨진 한자도 추출
        m = re.search(r'제\s*(\d+)\s*[회ȸ]', src)
        if m:
            return f'제{int(m.group(1))}회'
        m = re.search(r'(\d+)\s*회', src)
        if m:
            return f'제{int(m.group(1))}회'
    return None


def split_subjects(text: str) -> dict[str, dict]:
    """본문 → 7과목 split. 결과 {subj: {start, end, body}}."""
    positions = []
    for subj, pat in PATTERNS.items():
        m = re.search(pat, text)
        if m:
            positions.append((m.start(), subj))
    positions.sort()
    result = {}
    for i, (start, subj) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body = text[start:end].strip()
        result[subj] = {'start': start, 'end': end, 'body': body}
    return result


def extract_problems(body: str) -> list[dict]:
    """과목 본문에서 【문 N】 + 소문제 점수 추출.

    Returns: [{'num': '1', 'snippet': '...', 'sub_scores': [5, 15, ...]}, ...]
    """
    # 【문 N】으로 split (탐욕 X)
    pieces = re.split(r'【문\s*(\d+)】', body)
    # pieces[0] = 헤더(첫 【문 전), pieces[1::2] = 문 번호, pieces[2::2] = 본문
    problems = []
    for i in range(1, len(pieces), 2):
        num = pieces[i]
        content = pieces[i + 1] if i + 1 < len(pieces) else ''
        # 소문제 점수: (N점) 패턴
        scores = [int(s) for s in re.findall(r'\((\d+)\s*점\)', content)]
        # snippet 첫 60자 (페이지 푸터 [N-N] 제거)
        snippet = re.sub(r'\([가-힣 ]+\d+-\d+\)', '', content).strip()
        snippet = re.sub(r'\s+', ' ', snippet)[:80]
        problems.append({'num': num, 'snippet': snippet, 'sub_scores': scores})
    return problems


def report(round_str: str, subjects: dict, dest=sys.stdout):
    """QA 보고서: 과목별 문제 요약 + 점수 + 총점."""
    print(f'\n=== 📋 QA 보고서: {round_str} ===\n', file=dest)
    grand_total = 0
    for subj, data in subjects.items():
        problems = extract_problems(data['body'])
        subj_total = sum(sum(p['sub_scores']) for p in problems)
        grand_total += subj_total
        print(f'## {subj} ({subj_total}점, 본문 {len(data["body"])}자)', file=dest)
        for p in problems:
            score_str = '+'.join(str(s) for s in p['sub_scores']) if p['sub_scores'] else '점수 미검출'
            sub_total = sum(p['sub_scores'])
            print(f'  【문 {p["num"]}】 ({sub_total}점 = {score_str}) {p["snippet"]}', file=dest)
        print('', file=dest)
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━', file=dest)
    print(f'🎯 {round_str} 총점: {grand_total}점', file=dest)
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━', file=dest)
    return grand_total


def make_md(round_str: str, subj: str, body: str) -> str:
    """과목 본문 → .md 포맷 (원문 충실 + 헤더만 마크다운화)."""
    # 헤더 라인 제거 (이미 .md 헤더 추가하므로 중복 제거)
    body = re.sub(
        r'^[^\n]*?법무사\s*제?\s*2\s*차\s*시험\s*[가-힣 ,]+?\s*(?=【문)',
        '', body, count=1, flags=re.DOTALL,
    )
    # Step 1: 별첨 제외 과목 — 줄바꿈 의존 X, 단순 패턴 (`별첨▣`, `별첨[N]`, `[별첨`, `별첨 7-N`)
    if subj in NO_APPENDIX:
        body = re.split(r'\[별첨|별첨\s*▣|별첨\s*7\s*\-\s*\d|별첨\s*[\d]', body, maxsplit=1)[0].strip()
        body += f'\n\n---\n\n> ※ 별첨/첨부서면은 **수험생 검수 영역** — 본 분석용 .md에는 미포함 ({subj}).'
    # Step 2: 점수 변환 먼저 — 표 제거 종료 마커로 사용 (`**(`)
    body = re.sub(r'\((\d+)\s*점\)', r'**(\1점)**', body)
    # Step 3: 등기기록부 표 제거
    #   시작 마커: [XX 기록례] | <XX 등기사항증명서> | 【 표제부/갑구/을구/병구 】 |
    #             (옵션 'N. ') 부동산(X)의 등기기록
    #   종료 마커: 다음 마커 | **( | 별첨 | \d+\.\s*(답안작성|사실관계|소장|위임) | 답안작성유의사항 | EOF
    body = re.sub(
        r'(?:\[[가-힣A-Z][^\]]{0,30}?(?:기록례|등기사항증명서)\]|'
        r'<[가-힣 ]{0,30}?(?:등기사항증명서|기록례)>|'
        r'【\s*(?:표\s*제\s*부|갑\s*구|을\s*구|병\s*구)\s*】|'
        r'(?:\d+\.\s*)?부동산\s*\([^)]{1,20}\)\s*의?\s*등기기록)'
        r'.*?'
        r'(?=\[[가-힣A-Z][^\]]{0,30}?(?:기록례|등기사항증명서)\]|'
        r'<[가-힣 ]+?(?:등기사항증명서|기록례)>|'
        r'\*\*\(|별첨|\d+\.\s*(?:답안작성|사실관계|소장|위임)|답안작성\s*유의사항|\Z)',
        '\n\n> *📋 등기기록부 표 영역 — 문제 풀이 참고용, 별책 시험지 참조 (가독성 위해 본문 제외)*\n\n',
        body, flags=re.DOTALL,
    )
    # Step 4: 【문 N】 → ## 【문 N】
    body = re.sub(r'(?<!#)【문\s*(\d+)】', r'\n\n## 【문 \1】\n', body)
    # Step 5: 페이지 푸터 → <sub>
    body = re.sub(r'\(([가-힣 ]+\d+-\d+)\)', r'<sub>(\1)</sub>', body)
    # Step 6: 본문 끝 leftover (예: '2024년 제30회', '2024년') 제거
    body = re.sub(r'\s*\d{4}년\s*제?\s*\d*\s*회?\s*$', '', body).strip()
    header = f'# {round_str} 법무사 제2차 시험 — {subj}\n\n> 법원행정처\n'
    if subj in NO_APPENDIX:
        header += f'>\n> ※ 별첨 제외 (수험생이 첨부서면 보고 답안 작성하는 과목).\n'
    return header + '\n---\n' + body.strip() + '\n'


def write_md_and_entries(round_str: str, subjects: dict, dry_run: bool = False):
    """과목별 .md 작성 + _file_index entry 추가."""
    round_dir = os.path.join(PAST_DIR, round_str)
    if not dry_run:
        os.makedirs(round_dir, exist_ok=True)
    round_num = re.search(r'(\d+)', round_str).group(1)

    with open(INDEX_PATH) as f:
        index = json.load(f)
    existing_ids = {e['id'] for e in index['files']}

    written = []
    for subj, data in subjects.items():
        fname = subj.replace(' ', '_') + '.md'
        md_path = os.path.join(round_dir, fname)
        md_content = make_md(round_str, subj, data['body'])
        if not dry_run:
            with open(md_path, 'w') as f:
                f.write(md_content)
        # entry
        entry_id = f'past_{round_num}_{EN[subj]}'
        rel_path = f'기출문제/{round_str}/{fname}'
        entry = {
            'id': entry_id,
            'subject': 'past',
            'subjectKor': '기출문제',
            'type': 'library',
            'round': round_str,
            'case': subj,
            'title': f'{round_str} 법무사 2차 — {subj}',
            'path': rel_path,
            'pdfPath': None,
            'points': None,
            'userCase': None,
            '_addedBy': 'past_hwp_to_md',
        }
        if not dry_run:
            # 중복 제거 + 추가
            index['files'] = [e for e in index['files'] if e['id'] != entry_id]
            index['files'].append(entry)
        written.append((subj, md_path, len(md_content)))
    if not dry_run:
        with open(INDEX_PATH, 'w') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hwp', nargs='?', help='hwp 파일 경로')
    ap.add_argument('--round', help='회차 강제 지정 (예: 제30회)')
    ap.add_argument('--dry-run', action='store_true', help='파일 생성 없이 보고서만')
    ap.add_argument('--report-only', action='store_true', help='보고서만 출력 (entry/.md X)')
    ap.add_argument('--verify', help='기존 round 폴더 검증 (예: 제31회)')
    args = ap.parse_args()

    if args.verify:
        # 기존 .md 폴더 검증
        round_dir = os.path.join(PAST_DIR, args.verify)
        subjects = {}
        for subj in PATTERNS:
            fname = subj.replace(' ', '_') + '.md'
            md_path = os.path.join(round_dir, fname)
            if os.path.exists(md_path):
                subjects[subj] = {'body': open(md_path).read(), 'start': 0, 'end': 0}
        report(args.verify, subjects)
        return

    if not args.hwp:
        ap.error('hwp 경로 필수 (또는 --verify)')
    text = extract_text(args.hwp)
    round_str = args.round or detect_round(text, os.path.basename(args.hwp))
    if not round_str:
        sys.exit('❌ 회차 자동 추정 실패. --round 지정 필요')
    subjects = split_subjects(text)
    if len(subjects) < 7:
        print(f'⚠️ 과목 매칭 {len(subjects)}/7 — 누락: {set(PATTERNS) - set(subjects)}', file=sys.stderr)
    report(round_str, subjects)
    if args.dry_run or args.report_only:
        print('\n(dry-run/report-only — .md/entry 생성 안 함)')
        return
    written = write_md_and_entries(round_str, subjects)
    print(f'\n✅ .md {len(written)}개 + entry {len(written)}개 생성:')
    for subj, path, size in written:
        print(f'  {subj:30s}  {size:6d}b  {path}')


if __name__ == '__main__':
    main()
