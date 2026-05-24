---
name: dev-le-17895-past-exam-import
description: lawear 17895 기출문제 카테고리 — 법무사 2차 시험 hwp → 7과목 .md 자동 변환 + _file_index entry 등재 + QA 보고서. 표/별첨 제거 4종 룰. 옛 회차(제8~11회) hwp 2.x/3.x는 한컴오피스 거쳐야.
---

# dev-le-17895-past-exam-import — 기출문제 hwp import 스킬

## 트리거

- 사용자: "제{N}회 기출 변환해줘" / "법무사 2차 기출 hwp 받았어"
- 명시 호출: `/dev-le-17895-past-exam-import <hwp_path>`
- 또는 `/dev-le-17895-past-exam-import` (인자 없이 → 다운로드 폴더 일괄 스캔)

## 입력

| 항목 | 값 |
|------|----|
| hwp | 단일 파일 또는 `~/Downloads/2차시험문제/*.hwp` |
| 회차 | 자동 추정 (본문 첫 500자 또는 파일명 `제N회`) — 실패 시 `--round 제30회` 강제 |
| 분할 hwp | 제23회 같은 4분할 (1과목/2과목/3과목/4과목) → 4파일 합본 처리 |

## 출력

- `.md` 7개: `docs/tts-new/기출문제/제{N}회/{과목}.md`
  - 과목 7개: 민법 / 민사소송법 / 부동산등기법 / 등기신청서류의_작성 / 민사사건관련서류의_작성 / 형법 / 형사소송법
  - 옛 회차 (제14~22)는 5과목 (민소법/형소법 없음 → 정상)
- `_file_index.json` entries (`type:"library"` + `round:"제N회"`)
- 17895 사이드패널: `기출문제 > 제N회 > {과목}` 3단 트리

---

## 변환 룰 (사용자 명시 — 절대 준수)

### 1. 회차 only (년도 X)
- 폴더명: `제{N}회` (예: `제31회`)
- entry id: `past_{N}_{과목영문}` (예: `past_31_minbeop`)
- 사용자 결정 2026-05-24: "연도 역추적 버그 무서움. 회차만 정확하게."

### 2. 7과목 split — 단독 헤더 + 【문 1】 기준
```python
PATTERNS = {
    '민법':                 r'(?:법무사\s*제?\s*2\s*차\s*시험\s*민\s*법|《\s*민\s*법\s*》)\s*【문',
    '민사소송법':            r'(?:법무사\s*제?\s*2\s*차\s*시험\s*민사소송법|《\s*민사소송법\s*》)\s*【문',
    '민사사건관련서류의 작성': r'(?:법무사\s*제?\s*2\s*차\s*시험\s*민사사건관련서류의\s*작성|《\s*민사사건관련서류의\s*작성\s*》)\s*【문',
    '형법':                 r'(?:법무사\s*제?\s*2\s*차\s*시험\s*형\s*법|《\s*형\s*법\s*》)\s*【문',
    '형사소송법':            r'(?:법무사\s*제?\s*2\s*차\s*시험\s*형사소송법|《\s*형사소송법\s*》)\s*【문',
    '부동산등기법':           r'(?:법무사\s*제?\s*2\s*차\s*시험\s*부\s*동\s*산\s*등\s*기\s*법|《\s*부\s*동\s*산\s*등\s*기\s*법\s*》)\s*【문',
    '등기신청서류의 작성':     r'(?:법무사\s*제?\s*2\s*차\s*시험\s*등기신청서류의\s*작성|《\s*등기신청서류의\s*작성\s*》)\s*【문',
}
```

옛 회차 변형 흡수:
- `법무사 제2차 시험` / `법무사 2차 시험` (제 옵션)
- `《민 법》` 꺽쇠 (제14회 등)
- 정렬 순서 (사용자 명시): 민법 → 민사소송법 → 부동산등기법 → 등기신청서류의 작성 → 민사사건관련서류의 작성 → 형법 → 형사소송법

### 3. 등기기록부 표 제거 (부등법/부등서류)

표가 lxml 변환 시 한 줄로 합쳐져 가독성 0. 풀이 참고용이라 본문 분석에 불필요.

**시작 마커 4종** (회차마다 다름):
- `\[[가-힣A-Z][^\]]*?(?:기록례|등기사항증명서)\]` (옛 회차 — `[Y 토지 기록례]`)
- `<[가-힣 ]+(?:등기사항증명서|기록례)>` (`<상가건물의 등기사항증명서>` — 제30회)
- `【\s*(?:표\s*제\s*부|갑\s*구|을\s*구|병\s*구)\s*】` (한자 표 마커 — 제28/29회)
- `(?:\d+\.\s*)?부동산\s*\([^)]{1,20}\)\s*의?\s*등기기록` (`2. 부동산(집합건물)의 등기기록`)

**종료 마커** (점수 변환 *후* 적용):
- 다음 마커 (단 한자 마커는 표 안 연속 → 종료점 제외)
- `\*\*\(` (점수 강조 다음 소문제) / `별첨` / `\d+\.\s*(답안작성|사실관계|소장|위임)` / `답안작성\s*유의사항` / EOF

**placeholder**: `> *📋 등기기록부 표 영역 — 문제 풀이 참고용, 별책 시험지 참조 (가독성 위해 본문 제외)*`

**금지**:
- `【문` 종료 마커 X — 다음 문제 본문 통째 삭제됨
- `\n\s*\d+\.` 종료 X — lxml 출력에 `\n` 거의 없어 매칭 실패

### 4. 별첨 제거 (부등서류/민사서류 = NO_APPENDIX)

수험생이 첨부서면 보고 답안 작성하는 과목. 별첨 본문은 분석 대상 X.

**패턴** (`\n` 의존 X — lxml은 `</sub>별첨▣`처럼 줄바꿈 없이 붙음):
- `\[별첨` / `별첨\s*▣` / `별첨\s*7\s*\-\s*\d` / `별첨\s*\d`

**예외**: 형소 [별첨1~3] 같은 **관련 법령 별첨은 포함** (풀이 필수 조문).

### 5. 처리 순서 (중요!)
1. 헤더 라인 제거 (`법무사\s*제?\s*2\s*차\s*시험\s*[가-힣 ,]+?\s*(?=【문)`)
2. **별첨 제거** (먼저 — 표 제거 종료 마커 확보)
3. **점수 변환** `(N점)` → `**(N점)**` (표 제거 종료 마커 `\*\*\(` 활용)
4. **표 제거**
5. 【문 N】 → `## 【문 N】`
6. 페이지 푸터 `(XX-N)` → `<sub>(XX-N)</sub>`
7. 본문 끝 leftover 제거 (`\s*\d{4}년\s*제?\s*\d*\s*회?\s*$`)

### 6. QA 게이트 (필수!)

**각 과목 점수 합산 → 총점 보고서 → 사용자 검수**

```
## 민법 (100점, 본문 3516자)
  【문 1】 (50점 = 5+15+10+15+5) ...
  【문 2】 (50점 = 15+20+5+5+5) ...
...
🎯 제N회 총점: 400점
```

법무사 2차 표준 총점 = **400점** (민법 100 + 민소 70 + 민서류 30 + 형법 50 + 형소 50 + 부등법 70 + 부등서류 30).

옛 5과목 회차 = 240~400점 (다양). 매칭 5/7 = 정상 (민소법/형소법 없음).

총점 큰 차이 → 점수 추출 오류 의심 → 본문 분석.

---

## 실행

### 단일 hwp
```bash
/tmp/hwp_venv/bin/python3 /Users/nhn/zman-lab/lawear/docs/tts-new/_tools/past_hwp_to_md.py <hwp_path>
# 옵션: --round 제N회 (회차 강제) / --dry-run (보고서만) / --report-only
```

### 일괄 (다운로드 폴더)
```bash
cd /Users/nhn/Downloads/2차시험문제
for hwp in *.hwp; do
    /tmp/hwp_venv/bin/python3 /Users/nhn/zman-lab/lawear/docs/tts-new/_tools/past_hwp_to_md.py "$hwp"
done
```

### 분할 hwp (제23회 같은 4파일)
```python
import sys; sys.path.insert(0, '/Users/nhn/zman-lab/lawear/docs/tts-new/_tools')
import past_hwp_to_md as P
parts = [P.extract_text(f'.../제23회 ... ({n}과목).hwp') for n in [1,2,3,4]]
P.write_md_and_entries('제23회', P.split_subjects('\n\n'.join(parts)))
```

### 기존 폴더 검증 (보고서만)
```bash
/tmp/hwp_venv/bin/python3 /Users/nhn/zman-lab/lawear/docs/tts-new/_tools/past_hwp_to_md.py --verify 제30회
```

---

## 변환 실패 케이스 처리

| 에러 | 원인 | 대응 |
|------|------|------|
| `Not an OLE2 Compound Binary File` | hwp 2.x/3.x 옛 포맷 (제8~11회 등) | 한컴오피스로 열어 hwp 5.x로 다시 저장 → 재시도. 또는 skip |
| `Model Stack` (hwp5html 버그) | hwp 5.x인데 도구 내부 에러 (제18회) | 한컴오피스 거치거나 LibreOffice 한컴필터 시도. 또는 skip |
| 점수 합 비표준 (제27회 0점 등) | 본문 형식 변종 — 점수 표기 다름 | `--verify` 보고서 + 본문 직접 확인 → 점수 패턴 보강 |
| 과목 매칭 0/7 | 옛 회차 헤더 형식 다름 (제12/13회) | 본문 헤더 패턴 확인 → `_hp()` helper에 새 변형 추가 |

---

## 의존성

- venv: `/tmp/hwp_venv` (재부팅 시 사라짐 → 재생성 필요)
  - 재생성: `python3 -m venv /tmp/hwp_venv && /tmp/hwp_venv/bin/pip install pyhwp six lxml`
- 스크립트: `/Users/nhn/zman-lab/lawear/docs/tts-new/_tools/past_hwp_to_md.py`

## 머지 후 17895 반영

```bash
launchctl kickstart -k gui/$(id -u)/com.lawear.ttsmerger
curl -s http://127.0.0.1:17895/_file_index.json | grep -c 기출문제
```

---

## 메모리 참조

- 변환 룰 상세: [[feedback_past_exam_conversion_rules]]
- 트리 구조: [[feedback_year_prefix_system]] (회차 only — 년도 X)
- 동시 세션 노터치: [[feedback_no_touch_concurrent_wip]] (머지 시 다른 세션 .md 보존)

## 출처

- lawear-f081 자율주행 2026-05-24
- 머지 커밋 `0206893` (--no-ff) — 17 회차 106 entries
- 핵심 파일: `docs/tts-new/_tools/past_hwp_to_md.py`, `docs/tts-new/merge.html` (library round 그룹핑)
