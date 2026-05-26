---
name: dev-le-17895-case-stat
description: "[case] 조문 인용 전수조사 + 분류 (통문장 과대wrap / 맨텍스트 링크누락 / 정상 wrap / no_token) + sample 추출. 과목/회차/연도/디렉토리 인자. 사고 재발 방지용 스킬화 (lawear-7ea2 2026-05-26)."
---

# dev-le-17895-case-stat 스킬

`[case]` 조문 인용 전수조사 + 4분류 + sample 추출. 사용자 검증 + 패치 영향 분석 자료 생성.

## 배경 (스킬화 사유)

lawear-7ea2 2026-05-26 작업: 민법/민소 [case] 4817개 추정 → 314파 3008개 실측, 통문장 397 / 맨텍스트 3507 / 정상 150 / no_token 2461 분류. **docs 폴더가 다른 세션에 정리되어 알고리즘 손실** → 스킬화 (반복작업 = 스킬, memory `skillify-repeat-work`).

## 입력값

`$ARGUMENTS`

자연어 파싱:
- `/dev-le-17895-case-stat 민법` — 민법 전체 (2025+2026 모든 순환/회차)
- `/dev-le-17895-case-stat 민법 2026 입문` — 민법 2026 입문순환
- `/dev-le-17895-case-stat 민법 2025 3순환 13_02` — 특정 회차/문제
- `/dev-le-17895-case-stat --subject=민법 --year=2026 --round=입문 --out=/tmp/case_stat.md` — 명시형

대상 디렉토리 자동 매핑:
- 민법 → `2025_*_민법/`, `2026_*_민법/`
- 민소 → `2025_*_민소/`, `2026_*_민소/`
- 형법 → `2025_*_형법/`, `2026_*_형법/`
- 형소 → `2025_*_형소/`, `2026_*_형소/`
- 부등법 → `2025_부등법/`, `2026_사용자_부동산등기법/` 등
- 부등서류 → `2026_사용자_부동산등기서류/` 등

## STEP 1: 대상 파일 식별

```bash
BASE=/Users/nhn/zman-lab/lawear/docs/tts-new
PATTERN=$(case "$SUBJECT" in
    민법) echo "*민법*/*.md" ;;
    민소) echo "*민소*/*.md" ;;
    형법) echo "*형법*/*.md" ;;
    형소) echo "*형소*/*.md" ;;
    부등법) echo "*부동산등기법*/*.md" ;;
    부등서류) echo "*부동산등기서류*/*.md" ;;
esac)

FILES=$(cd "$BASE" && ls $PATTERN 2>/dev/null)
FILE_COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
echo "대상 파일: $FILE_COUNT개"
```

## STEP 2: 4분류 카운트

각 [case] 인스턴스를 4분류:

```bash
# 1. 정상 wrap (짧은 토큰, ≤20자, "제N조" 단독 포함)
NORMAL=$(grep -rEo "\[case\][^[]{1,20}\[/case\]" $FILES 2>/dev/null | grep -E "제[0-9]+조" | wc -l)

# 2. 통문장 wrap (50자+, 과대wrap)
TONGMUN=$(grep -rEo "\[case\][^[]{50,}\[/case\]" $FILES 2>/dev/null | wc -l)

# 3. 전체 [case] 인스턴스
TOTAL=$(grep -rEo "\[case\][^[]*\[/case\]" $FILES 2>/dev/null | wc -l)

# 4. no_token ([case] 안에 "제N조" 없음, 키워드/판례명 등)
NO_TOKEN=$(grep -rEo "\[case\][^[]*\[/case\]" $FILES 2>/dev/null | grep -vE "제[0-9]+조" | wc -l)

# 5. 맨텍스트 (case wrap 없는 "제N조" 본문 노출)
MAN_TEXT=$(grep -rEo "(^|[^[])제[0-9]+조" $FILES 2>/dev/null | wc -l)
# 위는 부정확 — 정확 측정 필요 시 본문 [case] 마스킹 후 잔여 "제N조" 카운트

echo "정상: $NORMAL / 통문장: $TONGMUN / no_token: $NO_TOKEN / total: $TOTAL / 맨텍스트: $MAN_TEXT"
```

## STEP 3: multi-article 검출 (통문장 중)

[case] 안에 "제N조" 토큰이 2개 이상:

```bash
grep -rEo "\[case\][^[]*\[/case\]" $FILES 2>/dev/null | awk '{
    count = gsub(/제[0-9]+조/, "&")
    if (count >= 2) print count, $0
}' | sort -rn | head -20
```

## STEP 4: Sample 추출 (분류별 5건)

각 분류 sample 5건 (파일:line + 문맥 ±2줄):

```bash
echo "=== 통문장 sample 5건 ==="
grep -rnE "\[case\][^[]{50,}\[/case\]" $FILES 2>/dev/null | head -5

echo "=== 정상 wrap sample 5건 ==="
grep -rnE "\[case\][^[]{1,20}\[/case\]" $FILES 2>/dev/null | grep -E "제[0-9]+조" | head -5

echo "=== no_token sample 5건 ==="
grep -rnE "\[case\][^[]*\[/case\]" $FILES 2>/dev/null | grep -vE "제[0-9]+조" | head -5

echo "=== multi-article sample 5건 ==="
grep -rnE "\[case\][^[]{50,}\[/case\]" $FILES 2>/dev/null | head -5
```

## STEP 5: 중첩 마커 검출 ([case] 안 [em]/[red]/[blue] 등)

renderer patch v3 C1 가드 발동 대상 분석:

```bash
NESTED=$(grep -rE "\[case\][^\[]{0,200}\[(em[1-4]?|con|fact|bridge|key|free[12]?|red|blue|purple|violet|magenta|indigo|bold|u|blank2?|blank)\]" $FILES 2>/dev/null | wc -l)
echo "중첩 마커 ([case] 안 다른 마커): $NESTED"
```

## STEP 6: 보고서 작성

`--out={경로}` 인자로 받은 위치에 보고서 (.md) 저장. 미지정 시 stdout.

보고서 구조:
```markdown
# [case] 전수조사 — {SUBJECT} {YEAR} {ROUND}

## 통계
| 분류 | 카운트 | 비율 |
| 정상 wrap | N | N% |
| 통문장 (50+) | N | N% |
| no_token | N | N% |
| 맨텍스트 (본문 노출) | N | - |
| 중첩 마커 | N | N% |
| multi-article (2+) | N | N% |
| total | N | 100% |

## Sample (분류별 5건)
...

## renderer patch 영향 예측
- 통문장 wrap → 토큰만 wrap 변경 (positive 변화)
- 중첩 마커 → C1 placeholder guard 발동 fallback
- multi-article → 모든 토큰 호버 가능 (현재 첫 것만)
- 맨텍스트 → patch v3 renderArticleTokensInTextNodes로 wrap (전역 후처리)

## 다른 과목 비교
... (옵션)
```

## 안전장치

1. **read-only** — .md 수정 X (R-09 + feedback_qa_grading_no_md_write)
2. **메인 trees 노터치** — 미커밋 .md 영역 영향 X
3. **결과 .md 저장은 docs/lawear-{세션ID}_case_stat/** 권장 (commit X 위험 — 즉시 commit + push 또는 별도 보존)
4. **사고 사례** — 본 스킬은 lawear-7ea2 2026-05-26 docs 손실 사고 후 스킬화. 결과 .md는 즉시 commit + /dev-push 권장

## 관련 스킬

- `/dev-le-17895-toc-validate` — ##목차 정합성 검증
- `/dev-le-17895-red-stat` — [red] 통계 + 강등 후보
- `/dev-le-17895-nunppong-sweep` — [u] strip + [red] polish
- `/dev-push` — 결과 .md push (가드 적용)
