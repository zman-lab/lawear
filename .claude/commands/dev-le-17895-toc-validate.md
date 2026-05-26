---
name: dev-le-17895-toc-validate
description: "##목차 정합성 검증 (오탐/약신호/진짜 부재 분류). 통합/분할/종합 파일 자동 구분 + 10가지 체크 + weirdness score 가중치 누적 + 임계 보고. 형법/형소/민법/민소/부등 전 과목. 사고 재발 방지용 스킬화 (lawear-7ea2 2026-05-26 toc-validate 후보 명시 → 손실 → 스킬화)."
---

# dev-le-17895-toc-validate 스킬

`##목차` 정합성 검증. 자동검출 오탐 차단 + 진짜 이상한 회차 식별.

## 배경 (스킬화 사유)

lawear-7ea2 2026-05-26: 형법/형소 ##목차 24개 자동검출 → **전수 오탐**. v4 알고리즘 (10가지 체크 + 통합/분할/종합 분류 + weirdness score) 설계 → docs 손실로 휘발 → 스킬화 (memory `skillify-repeat-work` 룰).

## 입력값

`$ARGUMENTS`

자연어:
- `/dev-le-17895-toc-validate 형법` — 형법 전체
- `/dev-le-17895-toc-validate 형소 2026 예비순환` — 형소 2026 예비
- `/dev-le-17895-toc-validate --subject=민법 --threshold=0.4 --out=/tmp/toc_validate.md`

## STEP 1: 대상 파일 + 분류 (통합/분할/종합)

```bash
# 파일명 패턴으로 분류
# 통합: {회차}_{문}.md (예: 미케_01.md, _01.md)
# 분할: {회차}_{문}_{서브}.md (예: 미케_01_1.md ~ _8.md)
# 종합: {회차}_0_*.md 또는 {회차}_종합.md
for f in $FILES; do
    basename=$(basename "$f" .md)
    if [[ "$basename" =~ _([0-9]+)_([0-9]+)$ ]]; then
        echo "분할: $f"
    elif [[ "$basename" =~ _0$ ]] || [[ "$basename" == *종합* ]]; then
        echo "종합: $f"
    else
        echo "통합: $f"
    fi
done
```

## STEP 2: 각 파일 weirdness score 계산 (10 체크)

각 파일별:

```python
# v4 알고리즘 의사코드
score = 0.0
for check in [
    check_h3_count,           # ① 답안 ### H3 카운트 (본문 1./2./3. 무시)
    check_split_lvl1_strict,   # ② 분할 파일 lvl1=1 강제 (다중 시 +0.5)
    check_indent_rule,         # ③ 들여쓰기 룰 (1단 N. / 2단 3칸+N) — 부등법 '- '/4칸/2칸 위반
    check_toc_vs_h3_diff,      # ④ 문N TOC vs 답안 H3 set diff (missing/extra +0.4*N)
    check_short_items,         # ⑤ 너무 짧은 항목
    check_markup_usage,        # ⑥ markup 사용 (예: [em] 안에 헤더성 텍스트)
    check_indent_mix,          # ⑦ 들여쓰기 혼용
    check_number_skip,         # ⑧ 번호 skip (1, 2, 4 — 3 누락)
    check_h3_lvl1_ratio,       # ⑨ H3/lvl1 비율 > 4 (과도)
    check_meta_h3_filter,      # ⑩ 메타 H3 (제목성) 필터
]:
    weight = check(file)
    score += weight

# 쪽지 분기 (분할 파일 특화)
if file_type == "split":
    if h3_count >= 8: score = max(score, 0.7)
    elif h3_count >= 3: score = max(score, 0.4)
    elif h3_count >= 1: score = max(score, 0.1)
    else: score = max(score, 0.05)

# 임계 0.4↑ 보고
if score >= threshold:
    report_candidate(file, score, reasons)
```

## STEP 3: 후보 분류

| score | 분류 | 액션 |
|-------|------|------|
| ≥0.7 | 진짜 이상 | dev-le-17895-toc-extract 적용 권장 |
| 0.4~0.7 | 약신호 | 사용자 검토 |
| 0.1~0.4 | 미세 | 일반적으로 정상 (참고만) |
| <0.1 | 정상 | 무시 |

## STEP 4: 오탐 차단 (자동검출 24 같은 케이스)

기존 자동검출 알고리즘이 오탐한 케이스:
- 형법 1순환 분할 파일 24개 (미케_01_1~8 + 02_1~8 + 03_1~8) — **정상** (1문 1답이라 lvl1=1줄 정상)
- 답안 본문 [bridge]1./2./3. 라인을 헤딩으로 잘못 잡음 → check ⑥ markup 사용으로 차단

본 v4 알고리즘은 위 케이스 자동 정상 분류.

## STEP 5: 보고서

```markdown
# ##목차 정합성 검증 — {SUBJECT} {YEAR} {ROUND}

## 통계
- 대상 파일: N개 (통합 N / 분할 N / 종합 N)
- 정상: N개
- 약신호 (0.1~0.4): N개
- 후보 (0.4~0.7): N개
- 진짜 이상 (≥0.7): N개

## Top N 후보 (score 내림차순)
| 파일 | type | score | reasons |
| ... |

## 권고 액션
- 진짜 이상 (≥0.7): dev-le-17895-toc-extract 적용
- 약신호: 사용자 검토
- 오탐 (분할 1답): 자동 정상 분류 (v4 알고리즘이 차단)
```

## 안전장치

1. **read-only** — .md 수정 X
2. **메인 trees 노터치** — 동시 세션 WIP 영향 X
3. **결과 .md 즉시 commit + /dev-push** — 사고 재발 방지

## 관련 스킬

- `/dev-le-17895-toc-extract` — 목차 계층 추출 (실제 적용)
- `/dev-le-17895-case-stat` — [case] 전수조사
- `/dev-push` — 결과 push (가드)
