---
name: dev-le-17895-tag-pair-validate
description: "모든 강조 태그 짝 ([red]/[blue]/[u]/[em1~4]/[case]/[con]/[fact]/[bridge]/[key]/[free1~2]/[bold]/[purple]/[blank]/[blank2]) 전수 검증. orphan open/close 정확 line + 발췌 + 권고 fix. read-only (자동 fix 옵션 --auto-fix). 사고 재발 방지용 스킬화 (lawear-7ea2 2026-05-26 C팀이 [red] 1건만 검출 → 실측 8건 사고)."
---

# dev-le-17895-tag-pair-validate 스킬

모든 강조 태그 짝 (`[태그]...[/태그]`) 전수 검증. orphan open/close 정확 line + 발췌 + 권고 fix.

## 배경 (스킬화 사유)

lawear-7ea2 2026-05-26: C팀 자율 야간이 `[red]` 1건만 보고 → 실측 8건 (red 1 + blue 1 + u 1 + em1 1 + em2 1 + case 3). 원인: line 20 강조 가이드 라인이 6마커 모두 `[/태그]` 누락 + case 2건 다른 위치. **태그별 specific 스킬은 다른 태그 누락을 못 봄** → generic 전 태그 검증 스킬 필요.

## 입력값

`$ARGUMENTS`

자연어:
- `/dev-le-17895-tag-pair-validate` — 전체 .md (default)
- `/dev-le-17895-tag-pair-validate 부등법` — 부등법만
- `/dev-le-17895-tag-pair-validate --file=docs/tts-new/.../xxx.md` — 특정 파일
- `/dev-le-17895-tag-pair-validate --auto-fix` — orphan open이 같은 line 다음 마커 직전이면 자동 `[/태그]` 추가 (사용자 컨펌 후)

## 검증 대상 태그 (16종)

| 카테고리 | 태그 |
|---------|------|
| em 시스템 | em1, em2, em3, em4 |
| 폰트 시스템 | con, fact, case, bridge, key |
| 여분 | free1, free2 |
| 효과 | u, bold |
| 라이브러리 | red, blue, purple, blank, blank2 |

`TAGS` 변수 추가/제거로 확장 가능.

## STEP 1: 대상 파일 식별

```bash
case "$SUBJECT" in
    민법) PATTERN="*민법*/*.md" ;;
    민소) PATTERN="*민소*/*.md" ;;
    형법) PATTERN="*형법*/*.md" ;;
    형소) PATTERN="*형소*/*.md" ;;
    부등법|부등) PATTERN="*부동산등기*/*.md" ;;
    *) PATTERN="*.md" ;;
esac
FILES=$(find /Users/nhn/zman-lab/lawear/docs/tts-new -name "$PATTERN" -type f)
```

## STEP 2: 태그별 짝 검증 (전수, python)

```python
import re

TAGS = ['red', 'blue', 'u', 'em1', 'em2', 'em3', 'em4',
        'case', 'con', 'fact', 'bridge', 'key',
        'free1', 'free2', 'bold', 'purple', 'blank', 'blank2']

def strip_inline_code(text):
    """백틱 inline code 안 마커 제거 (false positive 회피).

    사고: lawear-7ea2 2026-05-26 — line 18 `[case]` (백틱 안)이
    orphan open으로 매칭됨. 실제 렌더 영향 0인데 알고리즘 false positive.
    백틱 inline code (`...`)와 fenced code block (```...```) 안 내용 무시."""
    # fenced code block 먼저 (```...```)
    text = re.sub(r'```[\s\S]*?```', lambda m: '`' * len(m.group()), text)
    # inline code (`...`)
    text = re.sub(r'`[^`\n]*`', lambda m: '`' * len(m.group()), text)
    return text

def validate_file(F):
    text = open(F, encoding='utf-8').read()
    text = strip_inline_code(text)  # false positive 회피
    results = {}
    for tag in TAGS:
        positions = []
        for m in re.finditer(rf'\[/?{tag}\]', text):
            line_no = text[:m.start()].count('\n') + 1
            positions.append((m.start(), m.group(), line_no))

        stack = []
        orphan_closes = []
        for pos, mtag, line_no in positions:
            if mtag == f'[{tag}]':
                stack.append((pos, line_no))
            elif mtag == f'[/{tag}]':
                if stack:
                    stack.pop()
                else:
                    orphan_closes.append((pos, line_no))

        if stack or orphan_closes:
            results[tag] = {
                'opens': len([p for p in positions if p[1] == f'[{tag}]']),
                'closes': len([p for p in positions if p[1] == f'[/{tag}]']),
                'orphan_opens': stack,
                'orphan_closes': orphan_closes,
            }
    return results
```

## STEP 3: 보고서

```markdown
# 짝 불일치 검증 — {대상}

## 통계 (불일치 파일 N개 / 검증 파일 N개)

| 파일 | 불일치 태그 | orphan open | orphan close |
| ... | ... | ... | ... |

## 태그별 통계
| 태그 | opens | closes | orphan |

## Orphan open (닫는 태그 누락) — 자동 fix 후보
| 파일:line | 발췌 | 권고 fix |
| ... |

## Orphan close (여는 태그 누락) — 수동 보정 필요
| 파일:line | 발췌 |
| ... |
```

## STEP 4: 자동 fix (`--auto-fix` 옵션)

orphan open이 같은 line에서 다음 마커 직전에 위치한 경우 (예: line 20 강조 가이드 라인 패턴) 자동 `[/태그]` 추가:

```python
# orphan_open이 같은 line에서 다음 ` ·` 또는 ` ` 직전에 위치
# 예: [blue]법률용어/서면명 · [u]도출... → [blue]법률용어/서면명[/blue] · [u]도출...
def auto_fix(text, tag, orphan_pos):
    line_start = text.rfind('\n', 0, orphan_pos) + 1
    line_end = text.find('\n', orphan_pos)
    line = text[line_start:line_end if line_end > 0 else len(text)]
    # 다음 마커 ` · [` 또는 ` [` 위치
    rest = text[orphan_pos:]
    next_marker = re.search(r' [·]? ?\[', rest[len(f'[{tag}]'):])
    if next_marker:
        insert_pos = orphan_pos + len(f'[{tag}]') + next_marker.start()
        return text[:insert_pos] + f'[/{tag}]' + text[insert_pos:]
    return text  # 안전 fail
```

단 사용자 컨펌 권장 (R-09 위반 X — 단순 짝 보정).

## STEP 5: commit + /dev-push

검증/fix 완료 후 즉시 commit + `/dev-push` (가드 적용, 사고 재발 방지).

## 안전장치

1. **read-only 기본** — `--auto-fix` 명시 시만 수정
2. **메인 trees 노터치** — 워크트리 권장 (큰 변경 시)
3. **사용자 컨펌 권장** — auto-fix는 단순 보정이나 사용자 학습 흐름 침해 우려
4. **R-09 위반 X** — 정규식 기반 짝 보정 (자의 해석 X)
5. **결과 .md 즉시 commit + /dev-push** (사고 재발 방지)

## 사고 case study

| 항목 | 값 |
|------|-----|
| 일시 | 2026-05-26 |
| 세션 | lawear-7ea2 |
| 파일 | `docs/tts-new/2026_사용자_부동산등기서류/공통/첨부서면해설_공통캐시.md` |
| C팀 자율 야간 보고 | `[red]` 1건만 |
| 실측 | 8건 (red 1 + blue 1 + u 1 + em1 1 + em2 1 + case 3) |
| 원인 | line 20 강조 가이드 라인 6마커 [/태그] 누락 + case 2건 다른 위치 |
| 본 스킬 적용 시 | 자동 전수 검출 가능 |

## 관련 스킬

- `/dev-le-17895-red-stat` — [red] 특화 통계 (강등 후보 분류)
- `/dev-le-17895-case-stat` — [case] 전수조사 4분류
- `/dev-push` — 결과 push (가드 적용)
