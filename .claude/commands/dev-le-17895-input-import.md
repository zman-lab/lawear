---
name: dev-le-17895-input-import
description: lawear 17895 사용자 입력 모드 — PDF 문제+해설 → 자동 .md 변환 + _file_index entry. 5과목(부등법/부등서류/민사서류/형법/형소) × 2025/2026. 학습 노트화 + 강조 + TTS 친화.
---

# dev-le-17895-input-import — 사용자 입력 모드 PDF import 스킬

## 트리거

- 사용자: "{과목} {연도} {카테고리} 모고 {N}회 만들어줘"
- 또는 명시 호출 `/dev-le-17895-input-import`
- 예: "2025 부등법 2순환 모고 1회 만들어줘"

## 입력

| 항목 | 값 |
|------|-----|
| PDF 2개 | 문제 PDF + 해설(답) PDF |
| 과목 | 부동산등기법 / 부동산등기서류 / 민사서류 / 형법 / 형소 (화이트리스트 5개) |
| 연도 | 2025 / 2026 |
| 각순환 | 입문 / 예비 / 1순환 / 2순환 / 3순환 / 기타 |
| 파일명 | 모의고사_NN (사용자 자유) |

## 출력

- `.md`: `docs/tts-new/{year}_사용자_{과목}/{카테고리}/{NN}_{filename}.md` (NN auto)
- `_file_index.json` entry (`type:"user_input"`)
- 17895 사이드패널: `{year} / {과목} / {카테고리} / {file} / {NN_제목}`

---

## 변환 룰 (사용자 명시 — 절대 준수)

### 1. 큰 문제 vs 하위 설문

| 케이스 | 처리 |
|-------|------|
| 큰 문제 단독 | 1 `.md` / title 1개 |
| 큰 문제 + 하위 설문 N개 | N `.md` / **같은 title 텍스트** / 다른 case / 다른 NN |

같은 큰 문제는 같은 `title` 텍스트로 → L4에서 같은 그룹 자동 표시.

### 2. 답안 작성 룰

#### 2-1. 판례번호 제거

- ❌ `[case]대판 95다39526[/case]` / `[case]대판 2017다360, 377[/case]`
- ✅ `[case]제358조 종물[/case]` (조문 + 조문명) / `[case]종물에도 미친다[/case]` (판례 키워드)
- 판례번호 본문 인용 자체 회피, 키워드/취지만 인용

#### 2-1-2. 법 인용 표기 (사용자 명시 룰)

**부등법 (default, 본 스킬 대상)**:
- ❌ `법 제15조 제1항`
- ✅ `제15조 물적편성주의 제1항` (앞 "법" 생략, **조문명 추가**, 항이 있으면 조문명 뒤)
- ✅ `제29조 신청의 각하` (단독 조문)

**다른 법 (법명 명시)**:
- 부동산등기규칙: `규칙 제{NN}조 {조문명} 제{N}항` (예: `규칙 제43조 신청정보 제1항`)
- 민법: `민법 제{NN}조 {조문명} 제{N}항` (예: `민법 제103조 반사회질서의 법률행위`)
- 그 외: `{법명} 제{NN}조 {조문명} 제{N}항`

**조문명 매핑** (R-09 강제 — LLM 추정 금지):
- **정본 캐시**: `/Users/nhn/zman-lab/lawear/web/src/data/lawArticles.json` (statutes.{법명}.articles.{N}.title)
- **추출 캐시**: `/Users/nhn/zman-lab/lawear/docs/lawear-7ad6_input_mode_3subjects/law_titles_cache.json` (13개 법령 매핑, 검색용)
- 캐시 조회 후 정확한 조문명 사용. 캐시에 없으면 `제{NN}조`만 (조문명 생략).
- LLM 일반 지식 추정 금지 (예: 민법 제200조 "권리의 추정" X → 캐시 정본 "권리의 적법의 추정" O)
- 공백/쉼표/긴 명칭도 캐시 그대로 (예: 제15조 "물적 편성주의" — 공백 보존, 민법 제214조 "소유물방해제거, 방해예방청구권" — 쉼표 보존)
- 확신 안 서면 캐시 조회 후 결정. 캐시 미존재 = 조문명 생략 (안전)

#### 2-2. 빈 목차 제거

- 강사 PDF에서 `2. 요건`만 있고 본문 비면 → 그 섹션 자체 제거
- 본문에 "사용자 검증 필요" 같은 placeholder 메모 X

#### 2-3. 특수문자 → TTS 친화 변환

| Before | After |
|--------|-------|
| (1)(2)(3) | 1 2 3 (괄호 제거) |
| / | "또는", "와" |
| → = | "이고", "되면" |
| O X | "진", "거" |
| ㅡ - _ | 적절한 한글/줄바꿈/콜론 |

#### 2-4. 평어체 짧게

| Before | After |
|--------|-------|
| ~합니다 | ~한다 |
| 되어 있다 | 된다 |
| ~하여 | ~하고 / ~해 |
| 긴 문장 | 사용자 예제 mirror (짧고 명료) |

#### 2-5. 강조 태그

| 태그 | 용도 |
|------|------|
| `[red]` | 핵심 키워드 |
| `[blue]` | 법률 용어 |
| `[u]` | 중요 문장 |
| `[em1]` | 두문자/요건 |
| `[em2]` | 핵심 효과 |
| `[case]` | 조문/판례 키워드 (번호 X) |

#### 2-6. 답안 구조 (강사 PDF mirror)

```
### {주제} [red]의의[/red]
1. ...

### {주제} [red]범위[/red]
인정되는 경우
1. ...
인정되지 않는 경우
1. ...

### {주제} [red]효과[/red]
1. [em2]증명책임의 전환[/em2]
   본문...
```

#### 2-7. 점수 표시

- ❌ 본문에 "이십점.", "(20점)" 표기
- ✅ `## 메타 - 점수: 20점` (메타에만)
- ✅ split table 컬럼 헤더 `<th>문제 (20점)</th>` (merge.html 자동)

### 3. 저작권 회피

강사 PDF 통째 paragraph 복사 X. 핵심 키워드 + 짧은 인용 + 학습 노트화. 사용자 본인 학습 도구 + 본인 자료 범위.

---

## .md 포맷

```markdown
# {year}_{subject_en}_user_{filename}

## 메타
- 과목: {과목}
- 각순환: {카테고리}
- 파일명: {file_name}
- 제목: {큰문제 제목}
- 소제목: {소제목, 있으면}
- 점수: {NN}점
- 등록일: {YYYY-MM-DD}
- 출처: 사용자 직접 입력 (PDF 원본: {PDF 파일명})
- _addedBy: lawear-7ad6-input-mode-v4

## 문제
{PDF 문제 본문 — 점수 표기 X, 평어체}

## 답안
{구조화 + 강조 + 학습 노트}
```

---

## _file_index entry append

```python
new = {
    "id": f"{year}_{subject_en}_user_{filename}",
    "subject": subject_en,        # budeunglaw / hyungbeop / hyungso / minsaseoryu / budeungseoryu
    "subjectKor": 과목,
    "category": 카테고리,
    "file": filename,             # 모의고사_01 (NN 없음 — 그룹화 키)
    "fileKor": f"{year}_{과목}_{카테고리}_{filename}",
    "case": 소제목,                # 하위 설문이면 설문 핵심
    "title": f"{nn:02d}_{큰문제_제목}",  # NN 자동 (같은 file+같은 큰문제 그룹 next)
    "path": f"{year}_사용자_{과목}/{카테고리}/{NN}_{filename}.md",
    "pdfPath": PDF_절대경로,
    "points": 점수_int,
    "userCase": None,
    "type": "user_input",
    "_addedBy": "lawear-7ad6-input-mode-v4",
    "_year": year,
}
```

lock + atomic append (server.py POST 또는 python 직접).

---

## 작업 순서

1. PDF 2개 read (문제 + 해설)
2. 문제 N개 분리:
   - 큰 문제 단독 → 1 .md
   - 큰 문제 + 하위 설문 → N .md (같은 title 텍스트)
3. 각 .md 작성:
   - 메타 (file/title/case/points)
   - 문제 본문 (PDF 그대로, 점수 X)
   - 답안 (구조화 + 강조 + 학습 노트화)
4. .md Write + _file_index entry append
5. 17895 사이드패널 자동 (브라우저 새로고침)

## 검증 체크

- [ ] 판례번호 0건 (`grep '대판.*다[0-9]' .md` → 0)
- [ ] 빈 목차 0건
- [ ] 특수문자 (1)(2) 본문 0건
- [ ] 점수 본문 표기 0건 ("이십점" 등)
- [ ] file 메타 NN 없음 (`file: 01_모의고사` X / `file: 모의고사_01` O)
- [ ] title 메타 NN 있음 (`title: 등기의 효력` X / `title: 01_등기의 효력` O)

## 시범 예시

작성된 모범 예: `docs/tts-new/2025_사용자_부동산등기법/2순환/01_모의고사_01.md` (등기의 효력 / 추정력, 20점). 메타/강조/평어체/빈 목차 제거/판례번호 X 패턴 mirror.

## 관련 메모리

- [[feedback_input_mode_design]]
- [[feedback_input_mode_v4_changes]]
- [[reference_input_mode_files]]
