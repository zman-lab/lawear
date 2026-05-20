# dev-le-17895-hanja-verify — 한자 치환 정확성 컨텍스트 검증 (서브 스킬)

> `dev-le-17895-yearly` Phase A.2 의 2차 검증 단계. 자동 sed/grep 후 Opus 서브에이전트 ultrathink + 문장 정독으로 양방향 오탐 정확 판정.
>
> **단독 호출도 가능**: 사용자가 한자 치환 결과 의심 시 `/dev-le-17895-hanja-verify` 호출.

## 사용 시점

- Phase A.2 자동 sed (`/tmp/lawear_hanja_convert.py --apply`) 직후
- 사용자가 한자 치환 결과 검수 의뢰
- "정도/丁도", "기/己" 같은 오탐 의심 케이스 발견

## 절대 규칙

1. **메인 직접 sed/grep 일괄 X** (lawear-103a 경험 — 양방향 오탐)
2. **Opus 4명 병렬 ultrathink 강제** (Sonnet/Haiku 금지)
3. **시각 .md 한자 유지가 사용자 의도** (R-05 TTS 발화 룰은 음성 생성 단계 별도)
   - 사용자가 한자키 없어 한글로 갑/을/병/정 적었음
   - 메인이 한자 변환 = 사용자 노력 도움
   - R-05 적용으로 한자→한글 복원 추천은 무시

## 양방향 오탐 패턴

| 오탐 방향 | 예 | 정답 |
|----------|-----|------|
| 한글 → 한자 (잘못) | "정도(degree)" → "丁도" (조사 매칭) | 한글 "정도" 유지 |
| 한글 → 한자 (잘못) | "패·기/승·각" 두문자 → "패·己/승·각" | 한글 "기" 유지 |
| 한글 → 한자 (잘못) | "정함에" → "丁함에" (보통은 매칭 X, 가능 케이스) | 한글 "정함" 유지 |
| 한자 → 한자 X | "갑도 그랬다, 을도 그랬다, 정도 그랬다" → 한자 인물명 "甲도/乙도/丁도" | **한자 유지가 정답** |
| 일관성 누락 | "정[red]은행" (다른 위치 모두 "丁은행") | "丁[red]은행" 또는 "[red]丁은행" 통일 |

## 분담 (Opus 4명 병렬)

| Agent | 디렉토리 | 파일 수 (예시) |
|-------|---------|--------------|
| C-1 | `docs/tts-new/{YEAR}_예비_민법/` + `docs/tts/{YEAR}_예비_민법/` | ~116 |
| C-2 | `docs/tts-new/{YEAR}_예비_민소/` + `docs/tts/{YEAR}_예비_민소/` | ~151 |
| C-3 | `docs/tts-new/{YEAR}_입문_민법/` | ~60 |
| C-4 | `docs/tts-new/{YEAR}_입문_민소/` | ~34 |

## 각 Opus 프롬프트 (필수 룰)

```
[역할] 한자 치환 정확성 컨텍스트 검증 — {디렉토리} (Opus + ultrathink 강제)

[배경]
- 사용자 의도: 시각 .md = 한자 유지 (사용자가 한자키 없어 한글 입력했고 메인이 한자 변환)
- R-05 (TTS 발화 한자→한글 음독)은 음성 생성 단계 별도, 시각 .md 적용 X
- 양방향 오탐 가능:
  ❌ 부사 "정도(degree)" → "丁도" (조사 매칭 오류)
  ❌ "丁도(인물명+도 조사)" → "정도" (메인 sed 잘못 복원)
  ❌ 두문자 "·기" → "·己" (가운뎃점 매칭 오류)

[검증 4축]
A. 명백 인물명 (한자 유지 정확) — "甲은/이/을/의" "甲과 乙의 매매계약" "甲도 그랬다"
B. 명백 일반 단어 (한자 X, 한글 정답) — "정도(부사)", 두문자 "·기" "·각", "갑작스러운"
C. 모호 (사용자 검수 필요)
D. 일관성 누락 (같은 인물명이 한 파일 안에서 한자/한글 혼재) — 한자로 통일

[수행]
1. Read로 디렉토리 모든 .md 정독
2. 한자 (甲/乙/丙/丁/戊/己) 등장 위치 전수 식별
3. 한글 (갑/을/병/정/무/기) 등장 위치도 검증 (잘못 복원되었나)
4. 각 위치 문장 컨텍스트 분석 — A/B/C/D 판정
5. 정정 필요 시 Edit (틀린 곳만)
6. ## 원본 섹션도 검증 (사용자 의도 정확성 우선)

[보고서] docs/_lv4_qa_hanja_{디렉토리}.md
- 결과 카운트 + 정정 사례 + 모호 케이스 명시

[제약]
- Opus + ultrathink (Sonnet/Haiku 금지)
- 문장 정독 + 의미 분석 (grep/sed 일괄 X)
- R-05 적용 추천 X (시각 .md 한자 유지가 사용자 의도)
- 비용 안 아낌 (사용자 명시)
```

## 출력 JSON 스키마 (각 Opus 반환)

```json
{
  "phase": "hanja-verify",
  "directory": "...",
  "total_files": 0,
  "hanja_positions_scanned": 0,
  "edits_applied": 0,
  "results": {
    "correct_hanja_kept": 0,
    "wrong_hanja_to_hangul": 0,
    "wrong_hangul_to_hanja": 0,
    "consistency_breaks_fixed": 0,
    "ambiguous_user_review": 0
  },
  "ambiguous_cases": [
    {"file": "...", "line": 0, "context": "...", "issue": "..."}
  ],
  "report_path": "..."
}
```

## 메인 후속 처리

1. 4 Opus 결과 통합
2. 충돌 추천 (R-05 적용 한자→한글 등) 무시
3. Edit 미적용 모호 케이스 메인이 Read + 컨텍스트 분석 + Edit
4. git commit + push

## 메모리 연동

- `feedback_user_abbreviations.md` — 사용자 약어 (검증 제외 대상)
- `feedback_subagent_self_eval_unreliable.md` — Opus 자체 평가 신뢰 X, 메인 직접 git diff 검증

## 입력값

$ARGUMENTS
