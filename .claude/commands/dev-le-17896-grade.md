---
name: dev-le-17896-grade
description: Lawear 17896 채점 자동화 — status='pending_grade' 기반 신규 채점, 9기준 v7 가중치 + 합격선 A-(73점) + 7묶음 표시 + 한자/영어 등장인물 치환 + answer_text 교정본 저장 + 부장판사+강사 QA 매 채점 + cases path mismatch 알림 + 1줄 보고. 사용자 발화 트리거 (자동 polling 금지).
metadata:
  type: skill
  team: lawear
  domain: 17896-grading
  rule_priority: critical
  originSessionId: lawear-2e42
---

# dev-le-17896-grade — Lawear 17896 채점 자동화

## 개요

사용자가 17896 시험 콘솔에서 답안 서브밋한 attempt를 메인 세션(Opus)이 직접 채점. **신규만** (소급 차단은 하드코딩 X — `status='pending_grade'` 자연 기준). **사용자 발화 트리거** (자동 polling 금지).

## 호출 인자

| 인자 | 의미 |
|------|------|
| `/dev-le-17896-grade` (단독) | 모든 pending 자동 채점 (status='pending_grade') |
| `/dev-le-17896-grade ls` | pending 목록 표시만 (채점 X) |
| `/dev-le-17896-grade "케이스 / 2026 / 민법 / 입문 / 미케01 / 01"` | 5단 (연도 포함, lawear-2e42 2026-05-20) |
| `/dev-le-17896-grade "케이스 / 민법 / 입문 / 미케01 / 01"` | 4단 fallback — 연도 누락 시 최신(2026) 매핑 |

**케이스 경로 파싱 v2 (5단, lawear-2e42 2026-05-20)** — 17896 뷰어 복사 버튼 + 17895 일관성:
- 5단 형식: `"케이스 / {연도} / {과목} / {카테고리} / {파일} / {번호}"` → `case_id`
  - 예: `"케이스 / 2026 / 민법 / 입문 / 미케01 / 01"` → `2026_minbeop_immun_mike01_01`
- 4단 fallback (연도 누락 시 최신 2026 자동):
  - 예: `"케이스 / 민법 / 입문 / 미케01 / 01"` → `2026_minbeop_immun_mike01_01`
- 매핑:
  - 연도: `2025` / `2026` / ... (id 첫 4자리)
  - 과목: 민법=minbeop / 민소=minso / 형법=hyungbeop / 형소=hyungso / 부등=budeung
  - 카테고리: 입문=immun / 예비=yebi
  - 파일: 미케01=mike01 / 모고01=mogo01 / ...

**파싱 알고리즘**:
1. 입력 문자열 ` / ` 또는 `/` 로 split → segment 배열, trim
2. 첫 segment `케이스` / `Cases` 제거
3. segment 수 5 (연도 포함) 또는 4 (fallback) 검증
4. 연도 segment 4자리 숫자 (`/^\d{4}$/`) — 있으면 5단, 없으면 4단 fallback (최신 '2026')
5. 각 segment 매핑 → case_id 조립
6. cases 테이블에서 case_id 존재 검증 (`GET /api/cases/{case_id}`)
7. pending 검색 (`GET /api/attempts?case_id={case_id}&status=pending_grade`)

## 절대 규칙 (위반 시 작업 무효)

1. **Opus + ultrathink** — 메인 + 부장판사+강사 QA 서브에이전트 전부
2. **Sonnet/Haiku 금지** ([[feedback_no_subagent_for_board]])
3. **두레이 X / PR X** ([[feedback_no_dooray_registration]], [[feedback_no_pr_workflow]])
4. **R-09 자의적 해석 금지** — 사용자 답안에 없는 어휘로 채점 X
5. **사용자 27건 침범 X** — 채점은 DB만 변경 (코드/.md 변경 0건). 매 채점 후 `git status -s docs/tts-new/` 0줄 확인 강제
6. **자동 polling 금지** — 사용자 발화 트리거 (a91b #1976)
7. **cases path mismatch 시 자동 SQL UPDATE 금지** — 사용자에게 17895 리스캔 안내만

## 워크플로우

### 1. pending GET

```bash
curl -s "http://127.0.0.1:17896/api/attempts?status=pending_grade"
```

- 인자 `ls` → 목록 표시 + 종료
- 인자 케이스 경로 → 해당 case_id 필터링
- 인자 없음 → 전체 pending 처리

### 2. 각 attempt 처리 (반복)

#### 2.1 case 신선도 GET

```bash
curl -s "http://127.0.0.1:17896/api/cases/{case_id}"
```

- 정상 응답 → 진행
- `md_file_missing` / 500 에러 → **1줄 알림**:
  > ⚠️ case path mismatch — 17896 콘솔 설정에서 "**17895에서 다시 가져오기**" 클릭 후 재시도해주세요. (자동 SQL UPDATE 금지)
- 사용자 액션 후 resume 또는 다음 case로 skip

#### 2.2 답안 본문 분석 + 교정 (메인 직접)

사용자 답안(`answer_subq.단일` 또는 `answer_text`)을 read 후 다음 4단 교정:

**(a) STT 오타 식별** (typo_dict.json 외 추가):
- 법률 컨텍스트 + 발음 유사도 기반
- 예: "제 419주" → "제 419조" (STT 오인식)
- R-09: 조문번호 추정 X (사용자가 명시 안 한 조문 추가 X)
- 사용자 정책: 발음 오타 + 숫자 일치 OK (감점 X, 식별만)

**(b) 한자 등장인물 치환** (사용자 명시 룰, 2026-05-20):

```python
HANJA_MAP = {
    "갑": "甲", "을": "乙", "병": "丙", "정": "丁", "무": "戊",
    "기": "己", "경": "庚", "신": "辛", "임": "壬", "계": "癸"
}
```

**컨텍스트 분석 필수** (단순 치환 X):
- ✅ 변환: "갑은 을에게" → "甲은 乙에게" (1자 인명 + 조사)
- ✅ 변환: "정이 무와 함께" → "丁이 戊와 함께"
- ❌ 변환 X: "병원" / "신청서" / "을지로" (다른 단어)
- ❌ 변환 X: "기준" / "정확" / "정도" (일반 명사)

판단 룰: 1자 + 조사(은/는/이/가/과/에게/도/만/의/를/을/이라/이라는/에서/로/로부터) 또는 단독 (앞뒤 공백/문장부호) — 단 사전적 의미 우선 확인

**(c) 영어 등장인물 치환** (음성 STT가 영문 못 인식한 경우):

```python
ENG_MAP = {
    "에이": "A", "비": "B", "씨": "C", "디": "D",
    "이": "E", "에프": "F", "지": "G", "에이치": "H"
}
```

**문장 정확히 읽고 흐름 파악 필수** — 단순 치환 시 오히려 망침:
- ✅ 변환: "에이는 비에게" → "A는 B에게" (음성 STT 후 한글 표기)
- ❌ 변환 X: "에이전트" / "비(雨)" / "비행기" / "이는 = 是, 此" / "디지털"
- 사용자 답안 전체 흐름 분석 후 결정

**(d) 교정본 생성 + answer_text 갱신** (사용자 정책 — DB 교정본 저장):

```json
PUT /api/attempts/{id}/answer  // 또는 직접 SQL UPDATE
{
  "answer_text": "교정본 본문",
  "answer_subq": {"단일": "교정본 본문"}
}
```

`typo_corrections`에 from/to 보존 (UI 밑줄 표시용):
```json
{"from": "갑은", "to": "甲은", "reason": "한자 등장인물 치환", "source": "main_session"}
{"from": "에이가", "to": "A가", "reason": "영어 등장인물 치환", "source": "main_session"}
{"from": "제 419주", "to": "제 419조", "reason": "STT 발음 오타", "source": "main_session"}
```

→ 사용자 명시: "사용자 제출 답지 자체를 수정해서 저장 + 오타 수정된 곳 밑줄 처리"

#### 2.3 모범답안 + 답안 비교 채점

**9기준 v7 가중치** (사용자 결정 2026-05-20):

| key | weight | 한글 (자연어) | 영어 (스텔스) |
|-----|--------|------|---------------|
| mnem | **10** | 두문자 풀이형 매칭 | Mnemonic match |
| color | **17** | 강조 키워드 매칭 | Highlight match |
| under | **6** | 밑줄 키워드 매칭 | Underline match |
| outline | **7** | 답안 목차 일치 | Outline |
| sem | **15** | 의미 일치 | Semantic |
| articles | **5** | 조문 명시 | Articles |
| rich | **15** | 답안 풍부함 | Richness |
| miss | **13** | 핵심 누락 | Missing |
| case_apply | **12** | 사안의 경우 적용 | Case application |
| **합계** | **100** | | |

**7묶음 표시** (뷰어/보고 — 가중치 계산은 9개 그대로):

| # | 묶음 (한글) | 묶음 (영어) | 포함 key | weight 합 |
|---|------------|-------------|---------|-----------|
| 1 | 두문자 풀이형 매칭 | Mnemonic match | mnem | 10 |
| 2 | 핵심 어휘 매칭 (강조+밑줄) | Highlight & Underline | color + under | 23 |
| 3 | 답안 목차 일치 | Outline | outline | 7 |
| 4 | 의미·조문 일치 | Semantic & Articles | sem + articles | 20 |
| 5 | 답안 풍부함 | Richness | rich | 15 |
| 6 | 핵심 누락 | Missing | miss | 13 |
| 7 | 사안의 경우 적용 | Case application | case_apply | 12 |

**grader v3 5룰** (강제 cap):
1. **N요건 누락 -5** — 요건 갯수 명시 없으면 sem -5
2. **조문 0개 → articles ≤ max × 0.20 (cap 1점)** — 가중치 5점이라 cap 1점
3. **변경판례 4요건 누락 ≤ 60%** — rich/sem
4. **흐름 누락 -5/-3** — outline/sem
5. **사안 적용 결론만 ≤ 50%** — case_apply

**기준 의미**:
- **mnem (두문자 풀이형 매칭)**: Lv.4 [blank2] 두문자(예: 변/대/공/상)를 답안에 정확히 풀어 적었는지 매칭 비율
- **color (강조 키워드 매칭)**: Lv.4 [red]/[blue]/[bold] 강조 키워드를 답안이 의미 기반으로 포함하는지
- **under (밑줄 키워드 매칭)**: Lv.4 [u] 밑줄 키워드 답안 매칭 (보통 사안 적용 구간)
- **outline (답안 목차 일치)**: 원본 모범답안 1./2./3. 구조를 답안이 의미상 따라가는지
- **sem (의미 일치)**: 표현/오타/조사 차이 무시하고 의미 일치
- **articles (조문 명시)**: 원본 조문(예 제565조) 답안 명시 비율
- **rich (답안 풍부함)**: 모범답안 대비 자세히/충실히 적었는지 (의미 유지하면서 깊이)
- **miss (핵심 누락)**: 원본 핵심 논점 누락 정도 (1개 90% / 2개 75% / 3개 60% / 4개+ 50%↓)
- **case_apply (사안 적용)**: 사실관계(일자/사실/당사자명)와 결론 도출 과정을 사안에 어떻게 녹였는지 (정확 매칭 X, 흐름 평가)

#### 2.3.5 4 케이스 감점 가이드 (옵션 C, v2)

사용자 명시 2026-05-21 (옵션 C 도입, 게시판 #2111). inline_comments / 채점 코멘트 category 표기 시 적용.

| 케이스 (category) | 감점 위치 (criterion) | 정도 | 1건 영향 (type/severity) |
|------------------|----------------------|------|--------------------------|
| `off_topic` (논점 무관) | sem | -2 | warning |
| `wrong_basis` (근거 틀림, 논점 OK) | sem | -3 | warning |
| `wrong_conclusion` (결론 틀림) | case_apply | -5 | error (high) |
| `wrong_article` (조문/판례 잘못) | articles | -2 | warning |
| `wrong_concept` (개념 자체 오류) | case_apply or sem | -3~-5 | error |
| `good` (잘한 부분) | - | 0 (인정) | ok |

**적용 룰**:
- 채점 코멘트에 "wrong_xxx" 사유 명시
- inline_comments[].category 4 카테고리 + good 중 하나 부여
- delta는 위 표 정도 그대로 (음수, good은 생략 또는 0)
- 누적 감점은 9기준 점수에 이미 반영 (inline_comments는 시각화 보조)
- R-09: 사용자 답안에 없는 어휘로 comment 작성 X — 답안 원문 인용 + QA 결과 변형만

#### 2.3.6 inline_comments 생성 로직 (옵션 C, v2)

메인 채점 시 답안을 문장 단위로 분석 → 최대 15개 inline_comments 생성.

**알고리즘**:
1. 답안 본문(`answer_text` 교정본)을 문장/구 단위 분할 (마침표/줄바꿈 기준)
2. 각 문장 → 원본 모범답안과 비교 → 분류:
   - `ok` (정확 일치 or 의미 부합) → category `good`
   - `warning` (부분 일치 or 약한 결함) → category `off_topic` / `wrong_basis` / `wrong_article`
   - `error` (결정적 오류 or 핵심 누락) → category `wrong_conclusion` / `wrong_concept`
3. category 부여 + delta (위 2.3.5 표 정도 그대로) + criterion (9기준 key) 매핑
4. comment 작성 (R-09 준수 — 답안 원문에 없는 어휘 추가 X, 강사/판사 QA 표현 변형 가능)
5. cap 15개 — 초과 시 severity high 우선, mid → low 순으로 선별

**JSON 스키마** (게시판 #2111 §2-1):
```json
{
  "span": {"text": "답안 원문 부분 (UI가 본문에서 찾아 wrap)", "line": 12},
  "type": "ok|warning|error",
  "category": "good|off_topic|wrong_basis|wrong_conclusion|wrong_article|wrong_concept",
  "severity": "high|mid|low",
  "comment": "시험관 코멘트 (R-09 준수)",
  "delta": -5,
  "criterion": "case_apply"
}
```

**span.text 룰**:
- 답안 본문(교정본 기준) substring 정확히 인용 — UI applyTypoCorrections 같은 패턴으로 wrap
- 너무 길면 핵심 30~60자만 발췌 (의미 유지)
- 변형/요약 금지 (R-09)

**cap 15개 우선순위** (초과 시 선별):
1. severity high error 전부
2. severity mid warning
3. severity high good (잘한 부분 강조)
4. 나머지 low

#### 2.3.7 gap_roadmap 계산 로직 (옵션 C, v2)

합격선 73점까지 액션 Top 5 — 9기준 점수 vs weight 격차 큰 항목 추출.

**알고리즘**:
1. `current_score` = 9기준 점수 합 (PUT payload `total_score`)
2. `target_score` = 73 (합격선)
3. `gap` = max(0, target_score - current_score)
4. gap이 0이면 actions 빈 배열 (이미 합격)
5. gap이 양수면:
   - 9기준 각 항목 → (weight - score) 격차 큰 순으로 정렬
   - 상위 5개 → action 카드 변환
6. 각 action:
   - `priority`: 1~5 (격차 큰 순)
   - `criterion`: 9기준 key (mnem/color/under/outline/sem/articles/rich/miss/case_apply)
   - `action`: 합리적 1줄 액션 (예: "해제사유의 경합 첫 항목 추가", "제544조 조문 + 4요건 두문자 풀이")
     - 원본 모범답안 + 누락 항목 기반 — R-09 준수 (자의 X)
   - `delta`: 해당 액션 수행 시 점수 회복 추정 (예: miss 4점 → 핵심 누락 1건 추가 시 +3~+5)
     - 합리적 추정: weight × 0.3~0.5 사이
     - 미달분(weight - score)을 초과 X
   - `cumulative`: 직전 누적 + delta (시뮬레이션)

**JSON 스키마** (게시판 #2111 §2-2):
```json
{
  "current_score": 53,
  "target_score": 73,
  "gap": 20,
  "actions": [
    {"priority": 1, "criterion": "miss", "action": "해제사유의 경합 첫 항목 추가", "delta": 5, "cumulative": 58},
    {"priority": 2, "criterion": "articles", "action": "제544조 조문 + 4요건 두문자 풀이", "delta": 6, "cumulative": 64}
  ]
}
```

**R-09 준수**: action 문구는 원본 모범답안에서 누락된 핵심 표현 인용/요약만, 새로운 학습 권고 창작 X.

**delta 합리성**: 누적 cumulative가 target_score를 초과해도 OK (5개 모두 적용 시 합격선 도달 가능). 단, gap 0인 경우 actions 자체 생략.

#### 2.3.8 judge_quote / lecturer_quote 정제 로직 (옵션 C, v2)

부장판사/강사 QA 결과 → 사용자 친화 자연어 1~2문장 정제. R-09 절대 준수.

**입력**: 2.5에서 받은 부장판사 QA 결과 + 강사 QA 결과 (둘 다 `user_quote` 필드 포함 — 2.5 프롬프트 갱신 참조)

**정제 룰**:
- 두 QA가 출력한 `user_quote`를 그대로 `judge_quote` / `lecturer_quote`에 매핑
- 메인은 추가 변형 X (R-09 — QA가 만든 자연어를 메인이 다시 가공 시 어휘 창작 위험)
- 톤 예시 (게시판 #2111 §2-3):
  - judge: "가장 큰 흠은 '을을 제3자로 분류'한 부분. 시험장이라면 -5점. 이건 법리 자체를 잘못 적용한 것이라 단순 누락보다 무거움."
  - lecturer: "결론 정리는 깔끔. 다만 '병/정 구분'이 이 사안의 핵심인데 둘을 묶어 다뤘어요. 시험에서 이런 구분 문제는 100% 출제됩니다."

**판단 룰**:
- 시험장 톤 ("시험장이라면 -N점", "다음엔 의식적으로 적자") 자연 유지
- 사용자 답안 발췌는 작은따옴표 인용만 (R-09)
- QA가 user_quote 누락 시 → 메인이 fallback 생성: 강사/판사 QA 권고 1순위만 발췌 + 자연어 1문장 (창작 X, 발췌만)

#### 2.4 V2 등급 + is_pass

**V2 10등급 + 합격선 A-(73점)** (사용자 결정 2026-05-20):

| 점수 | V2 | V1 | is_pass |
|------|-----|-----|---------|
| 80+ | A+ | A | True |
| 75-79 | A | A | True |
| **73-74** | **A-** | A | **True (합격선)** |
| 65-72 | B+ | A | False |
| 60-64 | B | B | False |
| 55-59 | B- | B | False |
| 50-54 | C+ | C | False |
| 45-49 | C | C | False |
| 40-44 | C- | C | False |
| <40 | F | F | False |

→ **73점 이상 = 합격 / 72점 이하 = 불합격**

#### 2.5 부장판사+강사 QA (매 채점 강제 적용)

사용자 명시 2026-05-19 ([[feedback_qa_judge_lecturer]]).

채점 결과 → 사용자 보고/PUT 전 Opus+ultrathink 2명 병렬 QA:

```python
# 부장판사 SE
Task(model="opus", subagent_type="general-purpose",
     prompt="ultrathink. 법무사 시험 부장판사 역할. R-09 위반 점검 (사용자 답안에 없는 어휘로 채점 X) + 조문/판례 정확성 + 9기준 점수 합리성 + 한자/영어 치환 정확성. PASS/FAIL + line 번호 + 근거. 출력 마지막에 `**user_quote**: 사용자 공개용 1~2문장 자연어 요약` — 시험장 톤 (예: '시험장이라면 -N점, 이건 법리 자체를 잘못 적용한 것이라 단순 누락보다 무거움'). R-09 준수: 답안 원문 인용은 작은따옴표만, 새 어휘 창작 X.",
     run_in_background=True)
# 강사 SE
Task(model="opus", subagent_type="general-purpose",
     prompt="ultrathink. 법무사 시험 강사 역할. 시험 답안 어휘 부합 + 합격 모델 답안 패턴 + next_study_oneliner 합리성 + 학습 효과. PASS/FAIL + 시험 관점 우려 + 권고. 출력 마지막에 `**user_quote**: 사용자 공개용 1~2문장 자연어 요약` — 강의 톤 (예: '결론 정리는 깔끔. 다만 OO 구분이 핵심인데 둘을 묶어 다뤘어요. 시험에서 이런 구분 문제는 100% 출제됩니다'). R-09 준수: 답안 원문 인용은 작은따옴표만, 새 어휘 창작 X.",
     run_in_background=True)
# → 두 결과 후 메인 비판적 검토
# → 두 user_quote → judge_quote / lecturer_quote 매핑 (2.3.8)
```

**메인 비판적 검토**:
- 두 QA 결과 충돌 시 → 실제 답안/원본 기반 판단
- 일반론 필터링
- 큰 이슈 없으면 → 자동 PUT (사용자 컨펌 X)
- 큰 이슈 있으면 → 사용자 컨펌 요청 ([[feedback_user_confirmation_context]] 룰 적용)

**큰 이슈 기준**:
- R-09 위반 발견
- 점수 합리성 의심 (5점 이상 변동)
- 가짜 두문자 의심 ([[feedback_fake_mnemonic_detection]])
- 한자/영어 치환 오류

#### 2.6 PUT /grade

```bash
curl -X PUT "http://127.0.0.1:17896/api/attempts/{id}/grade" \
  -H "Content-Type: application/json" \
  -d @grade.json
```

payload:
```json
{
  "criteria": [
    {"key": "mnem", "score": N, "weight_applied": 10, "comment": "..."},
    {"key": "color", "score": N, "weight_applied": 17, "comment": "..."},
    {"key": "under", "score": N, "weight_applied": 6, "comment": "..."},
    {"key": "outline", "score": N, "weight_applied": 7, "comment": "..."},
    {"key": "sem", "score": N, "weight_applied": 15, "comment": "..."},
    {"key": "articles", "score": N, "weight_applied": 5, "comment": "..."},
    {"key": "rich", "score": N, "weight_applied": 15, "comment": "..."},
    {"key": "miss", "score": N, "weight_applied": 13, "comment": "..."},
    {"key": "case_apply", "score": N, "weight_applied": 12, "comment": "..."}
  ],
  "total_score": N,
  "max_score": 100,
  "score_pct": N,
  "grade": "A|B|C|F",
  "eval_notes": {
    "strength": "...",
    "caution": "...",
    "missing": "...",
    "score_summary": "...",
    "next_study_oneliner": "💡 ...",
    "next_study_actionable": ["..."],
    "pattern_warning": "✅/⚠️ ...",
    "typo_corrections": [
      {"from": "...", "to": "...", "reason": "STT|한자|영어", "source": "main_session"}
    ],

    // ─── 옵션 C 신규 필드 (v2, 게시판 #2111) ───
    "inline_comments": [
      {
        "span": {"text": "답안 원문 부분", "line": 12},
        "type": "ok|warning|error",
        "category": "good|off_topic|wrong_basis|wrong_conclusion|wrong_article|wrong_concept",
        "severity": "high|mid|low",
        "comment": "시험관 코멘트 (R-09 준수)",
        "delta": -5,
        "criterion": "case_apply"
      }
      // ... 최대 15개
    ],
    "gap_roadmap": {
      "current_score": 53,
      "target_score": 73,
      "gap": 20,
      "actions": [
        {"priority": 1, "criterion": "miss", "action": "...", "delta": 5, "cumulative": 58}
        // ... 최대 5개
      ]
    },
    "judge_quote": "부장판사 user_quote 자연어 1~2문장 (2.3.8 매핑)",
    "lecturer_quote": "강사 user_quote 자연어 1~2문장 (2.3.8 매핑)"
  },
  "diff_segments": [
    {"type": "match|partial|miss", "text": "원본/답안 substring"}
  ]
}
```

**v2 명세 참조**: 게시판 #2111 (http://10.77.11.110:8585/post/2111) — 옵션 C 도입 JSON 명세서.

**백워드 호환**:
- 신규 3 필드 (inline_comments / gap_roadmap / judge_quote / lecturer_quote)는 NULL 허용
- 기존 attempts(id 1~32) — 신규 필드 없음 → UI에서 정상 표시 (탭 빈 상태)
- DB 스키마 변경 X (eval_notes는 이미 JSON TEXT, JSON pass-through)

#### 2.7 answer_text 갱신 (DB 교정본 저장)

PUT /grade 직후 또는 동시:
- 17896 server.py에 answer_text PATCH endpoint 있는지 확인
- 없으면 SQL UPDATE 직접 (DB만 변경, 코드 X — lawear 정책):
  ```sql
  UPDATE attempts SET answer_text = '{교정본}', answer_subq = '{교정본 JSON}'
  WHERE id = {attempt_id};
  ```
- typo_corrections에 from/to 보존 → UI applyTypoCorrections가 밑줄 표시

#### 2.8 사용자 27건 침범 검증

```bash
git -C /Users/nhn/zman-lab/lawear status -s docs/tts-new/
```

→ 0줄 확인 (출력 비어있어야 함). 1줄이라도 있으면 즉시 사용자 보고 + 채점 중단.

#### 2.9 1줄 보고 ([[feedback_grading_report_format]])

```
[att N] 카드 XX | 교정✓ 대체✓ 밑줄✓ 요청✓ 완료✓ | 82(A) | M'SS" | NK토큰/$N.NN | http://127.0.0.1:17896/attempts/N
```

5체크 (3~7번 필드):
- 교정 = 오타/한자/영어 식별 진행 OK
- 대체 = answer_text 교정본 갱신 OK
- 밑줄 = typo_corrections 밑줄 wrap OK (UI applyTypoCorrections)
- 요청 = grader v3 채점 진행 OK
- 완료 = PUT /grade 200 OK

부분 실패 시 ⚠️ 마커 + 누락 항목 명시.

### 3. 전체 종료 보고

- pending N개 채점 완료 / X개 실패 (실패 사유: cases path mismatch 등)
- 합격 N개 / 불합격 N개
- 총 소요 시간 / 토큰 / 비용

## 사용자 정책 (절대 준수)

1. STT 오타 감점 X (식별만)
2. **원본 보존 X (answer_text 교정본 저장)** — 한자/영어 치환 포함
3. 평문 키워드 인정 (정확한 법률 용어 아니어도 의미 맞으면 OK)
4. 조문번호 발음 오타 + 숫자 일치 OK / 숫자 다름 감점
5. R-09 자의적 해석 금지
6. Phase 3 AI 자동 교정 포함 (메인 = ai_corrector 역할)
7. V2 10등급 + **합격선 A-(73점)**
8. 7묶음 표시 (한+영 — 영문은 스텔스/영문 모드)

## 메모리 룰 (필수 인지)

- [[reference_grading_workflow]] v7+ — 워크플로우 상세
- [[feedback_grading_report_format]] — 1줄 요약 11필드
- [[feedback_qa_judge_lecturer]] — 부장판사+강사 QA 매 채점
- [[feedback_main_context_priority]] — 메인 맥락 보존 (1줄 보고로 컨텍스트 절약)
- [[feedback_no_subagent_for_board]] — Opus만 (Sonnet/Haiku 금지)
- [[feedback_subagent_self_eval_unreliable]] — 메인 직접 검증
- [[feedback_no_dooray_registration]] / [[feedback_no_pr_workflow]] — lawear 정책
- [[feedback_three_stage_byte_compare]] — 라이브러리 검증 시 (채점에는 적용 X, 두문자 라이브러리 작업용)

## 차단 사항

- pending 자동 polling 금지 (사용자 발화 트리거)
- att 25 V2 표기 정합 정정 X (이미 #1965에서 처리됨, lawear-a8c4 작업)
- .md 변경 X (DB만)
- 매 자동화 후 `git status -s docs/tts-new/` 0줄 강제

## cases path mismatch 처리

오늘(2026-05-20) 발생한 패턴:
- 17895에서 디렉토리 prefix 변경 (예: `입문_민법/` → `2026_입문_민법/`)
- 17896 cases DB는 옛 path 캐시 → GET /api/cases/{id} 시 `md_file_missing` 500 에러
- attempt POST 시 case_id 검증 실패 → attempt 생성 안 됨

**처리**:
1. case GET 시 500 + `md_file_missing` 감지
2. 1줄 알림:
   > ⚠️ {case_id} path mismatch — 17896 콘솔 설정에서 **"17895에서 다시 가져오기"** 클릭 후 재시도해주세요. (메인 자동 SQL UPDATE 금지)
3. 사용자 액션 대기 또는 skip 후 다음 attempt 진행
4. 전체 종료 시 미처리 attempt 리스트 보고

**자동 SQL UPDATE 금지 이유**: 사용자 명시 정책 — "사용자가 명시적으로 뷰어에서 리스캔 버튼 눌렀을 때만 갱신"

## 시나리오 예시

### (a) 전체 채점

```
사용자: /dev-le-17896-grade
메인:
  → pending GET → 3건 ([att 31, 32, 33])
  → att 31 처리:
    - case GET (mike01_03) → OK
    - 답안 read + 교정 (STT 5건 + 한자 3건 + 영어 1건)
    - 부장판사 QA: PASS
    - 강사 QA: PASS
    - 점수: 78 (A) / pass=True
    - PUT /grade + answer_text 갱신
    - 1줄: [att 31] 미케01-03 | 교정✓ 대체✓ 밑줄✓ 요청✓ 완료✓ | 78(A) | 3'22" | 55K/$0.83 | /attempts/31
  → att 32 처리 ... (반복)
  → 전체 종료:
    - 3건 채점 완료 (합격 2 / 불합격 1)
    - 총 소요 9'48" / 168K 토큰 / $2.52
```

### (b) 목록만

```
사용자: /dev-le-17896-grade ls
메인:
  pending 3건:
  - att 31 | 미케01-03 | 2026-05-20T18:30:15
  - att 32 | 미케02-15 | 2026-05-20T19:05:22
  - att 33 | 미케03-25 | 2026-05-20T19:25:48
```

### (c) 특정 케이스

```
사용자: /dev-le-17896-grade "케이스 / 민법 / 입문 / 미케01 / 03"
메인:
  → case_id 매핑: 2026_minbeop_immun_mike01_03
  → pending GET filtered by case_id
  → att 31 발견 → 채점 진행
  → 1줄 보고
```

### (d) cases path mismatch

```
사용자: /dev-le-17896-grade
메인:
  → pending: att 33 (미케03-25)
  → case GET → 500 md_file_missing
  → ⚠️ att 33 미케03-25 path mismatch — 17896 콘솔 설정에서 "17895에서 다시 가져오기" 클릭 후 재시도 부탁드립니다
  → att 33 skip (다음 attempt 없음)
  → 종료 (미처리 1건)
```

### (e) 부장판사+강사 QA 큰 이슈

```
사용자: /dev-le-17896-grade
메인:
  → att 31 채점 → 78점 (A)
  → 부장판사 QA: ⚠️ R-09 의심 — 사용자 답안에 없는 "민사소송법 제60조" 추가됨 (메인 채점 코멘트에)
  → 강사 QA: PASS
  → 메인 비판적 검토: R-09 위반 가능성 확인
  → 사용자 컨펌 요청:
    💡 att 31 채점 시 R-09 의심 — 부장판사 QA가 채점 코멘트에 사용자 답안에 없는 조문 인용 발견.
    - 위치: criteria.articles.comment line 2
    - 원문: "민사소송법 제60조 명시"
    - 사용자 답안 발췌: (해당 조문 명시 0건)
    - 결정 옵션:
      (a) 코멘트 정정 후 PUT 진행
      (b) 점수 그대로 PUT (R-09 우려 수용)
      (c) 채점 재시도
```

## 관련 메모리

[[reference_grading_workflow]] · [[feedback_grading_report_format]] · [[feedback_qa_judge_lecturer]] · [[feedback_main_context_priority]] · [[feedback_no_subagent_for_board]] · [[feedback_subagent_self_eval_unreliable]] · [[feedback_user_confirmation_context]] · [[feedback_no_dooray_registration]] · [[feedback_no_pr_workflow]]

## 출처

- 사용자 결정 2026-05-20 (lawear-2e42 자율주행 작업)
- a91b #1976 채점 인계 (소급 차단은 단순화 — status='pending_grade' 자연 기준)
- [[reference_grading_workflow]] v5 → v7 (가중치 v7 + 합격선 73 + 7묶음 + 한자/영어 치환)
- #2027 한자 표시 작업지시는 다른 영역 (case 본문 표시 — 본 스킬은 답안 측 변환)
- **v2 옵션 C 도입 (2026-05-21, lawear-c63e)**: 게시판 #2111 — inline_comments + gap_roadmap + judge_quote/lecturer_quote 3 필드 추가, 4 케이스 감점 가이드 (off_topic/wrong_basis/wrong_conclusion/wrong_article/wrong_concept), 부장판사/강사 QA 프롬프트 user_quote 요구. 신규 답안부터 적용, att 1~32 백워드 호환 (NULL 허용).
