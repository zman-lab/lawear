---
name: dev-le-17895-red-stat
description: "[red] 통계 + 강등 후보 분류 (보존/경계/강등 길이 임계 + 문장형 어미 + 짝 불일치 검출). 정책 D 대화 자료 자동 생성. 부등법/민법/민소/형법/형소 전 과목. 사고 재발 방지용 스킬화 (lawear-7ea2 2026-05-26)."
---

# dev-le-17895-red-stat 스킬

`[red]` 인스턴스 전수 통계 + 강등 후보 분류 (정책 D 대화 자료).

## 배경 (스킬화 사유)

lawear-7ea2 2026-05-26: 부등법 107파/[red]448 → 보존 206 / 경계 143 / 강등 99 분류 + 짝 불일치 1건 검출. docs 손실로 알고리즘 휘발 → 스킬화.

## 입력값

`$ARGUMENTS`

자연어:
- `/dev-le-17895-red-stat 부등법` — 부등법 전체 (default)
- `/dev-le-17895-red-stat 민법 --short=10 --long=20` — 임계 명시
- `/dev-le-17895-red-stat --subject=부등법 --policy=conservative --out=/tmp/red_stat.md`

## 분류 임계 (정책)

| 정책 | 보존 (≤) | 경계 | 강등 (≥) |
|------|----------|------|----------|
| conservative (default) | 10자 | 11~19 | 20자 |
| moderate | 8자 | 9~14 | 15자 |
| aggressive | 5자 | 6~9 | 10자 |

사용자가 정책 D 대화에서 결정.

## STEP 1: [red] 전수 추출

```bash
# 각 인스턴스 길이 측정
grep -rnE "\[red\][^[]*\[/red\]" $FILES 2>/dev/null | while read line; do
    text=$(echo "$line" | sed -E 's/.*\[red\](.*)\[\/red\].*/\1/')
    len=${#text}
    echo "$len|$line"
done | sort -n
```

## STEP 2: 4분류

```bash
# 보존 (≤short_threshold)
PRESERVE=$(awk -v t=$SHORT_THRESHOLD '$1 <= t' < /tmp/red_list.txt | wc -l)

# 경계 (short < len < long)
BOUNDARY=$(awk -v s=$SHORT_THRESHOLD -v l=$LONG_THRESHOLD '$1 > s && $1 < l' < /tmp/red_list.txt | wc -l)

# 강등 (≥long_threshold)
DEMOTE=$(awk -v t=$LONG_THRESHOLD '$1 >= t' < /tmp/red_list.txt | wc -l)

# 문장형 어미 (강등 후보 중 "이다/한다/된다/없다" 등)
SENT_ENDING=$(awk -v t=$SHORT_THRESHOLD '$1 > t' < /tmp/red_list.txt | grep -cE "(이다|한다|된다|없다|있다|만한다|하는|적이|할 수|이라|이며|이고)\[/red\]")
```

## STEP 3: 짝 불일치 검출

`[red]` opens vs `[/red]` closes 카운트 불일치 파일:

```bash
for f in $FILES; do
    opens=$(grep -o "\[red\]" "$f" | wc -l)
    closes=$(grep -o "\[/red\]" "$f" | wc -l)
    if [ "$opens" != "$closes" ]; then
        echo "$f: opens=$opens / closes=$closes (불일치)"
    fi
done
```

## STEP 4: 디렉토리별 편차

```bash
# 2025 vs 2026 강등률 비교
for dir in $DIRS; do
    files_n=$(ls "$dir/"*.md 2>/dev/null | wc -l)
    total=$(grep -rEo "\[red\][^[]*\[/red\]" "$dir/" 2>/dev/null | wc -l)
    demote=$(grep -rEo "\[red\][^[]{$((LONG_THRESHOLD)),}\[/red\]" "$dir/" 2>/dev/null | wc -l)
    rate=$(echo "scale=1; $demote*100/$total" | bc)
    echo "$dir: 파일 $files_n / 총 $total / 강등 $demote ($rate%)"
done
```

## STEP 5: Top 후보 Sample

```bash
# 강등 후보 sample 10건 (파일:line + 발췌)
awk -v t=$LONG_THRESHOLD '$1 >= t' < /tmp/red_list.txt | head -10

# 경계 영역 sample 10건 (정책 D 자료)
awk -v s=$SHORT_THRESHOLD -v l=$LONG_THRESHOLD '$1 > s && $1 < l' < /tmp/red_list.txt | head -10

# 보존 후보 sample 10건 (짧은 판단어)
awk -v t=$SHORT_THRESHOLD '$1 <= t' < /tmp/red_list.txt | head -10
```

## STEP 6: 정책 D 대화 자료

```markdown
# [red] 정책 D 대화 자료 — {SUBJECT}

## 통계 (현재 정책: conservative)
- 전체 [red]: N개
- 보존 (≤10자): N개 (N%)
- 경계 (11~19자): N개 (N%)
- 강등 (≥20자): N개 (N%)
- 문장형 어미 (강등 중): N개

## 정책 옵션
- A (conservative): 강등 99건 (안전, 시각 변화 최소)
- B (moderate): 강등 ~142건 (시각 변화 중간)
- C (aggressive): 강등 ~242건 (대대적 polish)

## 경계 영역 Sample (사용자 결정 필요)
... 10건

## 짝 불일치 (수동 보정 필수)
... N건
```

## STEP 7: 보고서 + .md 출력

`--out={경로}` 또는 stdout.

## 안전장치

1. **read-only**
2. **메인 trees 노터치**
3. **결과 .md 즉시 commit + /dev-push** (사고 재발 방지)
4. **실제 [red]→[em2] 적용은 별도** — `/dev-le-17895-nunppong-sweep` 또는 사용자 직접

## 관련 스킬

- `/dev-le-17895-nunppong-sweep` — 실제 strip/강등 sweep
- `/dev-le-17895-case-stat` — [case] 전수조사
- `/dev-push` — 결과 push
