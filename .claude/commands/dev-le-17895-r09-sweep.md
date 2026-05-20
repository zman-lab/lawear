# dev-le-17895-r09-sweep — Lv.4 본문 R-09 4축 검증 + 정정 (서브 스킬)

> `dev-le-17895-yearly` Phase B. Lv.4 본문이 `## 원본` (17896 채점 기준) 의미를 R-09 위반 없이 반영했는지 검증 + 정정.
>
> **단독 호출도 가능**: 사용자가 Lv.4 답안 품질 검수 의뢰 시.

## 사용 시점

- 매년 PDF 도착 후 한자/금액/약어 자동화 직후
- 사용자가 Lv.4 본문 정확성 의심
- 강조 sweep (Phase C) 직전 (의미 정확 본문에 강조 적용 위해)

## 절대 규칙

1. **`## 원본` 섹션은 17896 채점 기준 — 절대 변경 X**
2. **R-09 위반만 Edit** (새로 작성 X — 기존 본문 유지)
3. **사용자 약어 정상 인정** (방배제/고필공/유필공/통공/독당참/신의칙/민소)
4. **한자/금액/회사명 변환 정상 인정** (Phase A 결과)
5. **Opus 6명 ultrathink 강제** (Sonnet/Haiku 금지)
6. **메인 직접 git diff 검증** (Opus 자체 평가 신뢰 X — `feedback_subagent_self_eval_unreliable`)

## R-09 4축 검증

| 축 | 의미 | 처리 |
|----|------|------|
| 누락 | ## 원본의 결론/근거/판례/조문/사실관계가 Lv.1~4에서 빠짐 | Edit 보강 |
| 자의 추가 | ## 원본에 없는 조문/판례/이론을 Lv.1~4가 추가 | Edit 제거 |
| 어휘 변경 | ## 원본 어휘를 Lv.1~4가 임의 변경 (약어 제외) | Edit 원어 복원 |
| 결론 변경 | ## 원본 결론과 Lv.1~4 결론이 다름 (사안별 결론 누락) | Edit 사안별 결론 복원 |

## 분담 (Opus 6명 병렬)

| Agent | 디렉토리 | 파일 수 (예시) |
|-------|---------|--------------|
| B-1 | `docs/tts-new/{YEAR}_입문_민법/` | ~60 |
| B-2 | `docs/tts-new/{YEAR}_입문_민소/` | ~34 |
| B-3 | `docs/tts-new/{YEAR}_예비_민법/` | ~55~58 |
| B-4 | `docs/tts-new/{YEAR}_예비_민소/` | ~52~95 |
| B-5 | `docs/tts/{YEAR}_예비_민법/` (archive) | ~58 |
| B-6 | `docs/tts/{YEAR}_예비_민소/` (archive) | ~56 |

## 각 Opus 프롬프트 (필수 룰)

```
[역할] lawear Lv.4 본문 R-09 sweep — {디렉토리} (Phase B-X, ultrathink + Opus 강제)

[배경]
- 17896 채점 기준 = `## 원본` 섹션 (PDF가 아닌 .md 안의 원본)
- R-09 위반 4축: 누락 / 자의 추가 / 어휘 변경 / 결론 변경
- 사용자 약어 정상 (방배제/고필공/유필공/통공/독당참/신의칙/민소)
- 한자/금액 변환 정상 (Phase A 결과)

[수행 — 파일별]
1. Read로 .md 전체 읽기
2. ## 원본 + ## Lv.1~Lv.4 추출
3. 4축 비교 (ultrathink 깊이)
4. 위반 발견 시 Edit (틀린 곳만)
5. ## 원본 섹션은 절대 변경 X

[보고서] docs/_lv4_qa_phaseB_{디렉토리}.md
- 위반 카테고리별 정정 내역
- 자동 보강 X 권장 사항 (사용자 검수)

[제약]
- Opus + ultrathink (Sonnet/Haiku 금지)
- R-09 위반 발견 시에만 Edit
- 메인 컨텍스트 보호 — JSON 4KB + 상세 .md
```

## 출력 JSON 스키마 (각 Opus 반환)

```json
{
  "phase": "B-X",
  "directory": "...",
  "total_files": 0,
  "verdicts": {"OK": 0, "Minor": 0, "Major": 0},
  "violations_by_type": {"누락": 0, "자의_추가": 0, "어휘_변경": 0, "결론_변경": 0},
  "edits_applied": 0,
  "files_with_major_changes": [
    {"file": "...", "type": "...", "edits": 0}
  ],
  "user_review_candidates": [
    {"file": "...", "issue": "...", "rationale": "자동 보강 X 사유"}
  ],
  "library_addition_candidates": [
    {"category": "...", "addition": "...", "source_case": "..."}
  ],
  "report_path": "..."
}
```

## 메인 후속 처리

1. 6 Opus 결과 통합
2. Major fix는 자동 적용 (Opus 정정 완료)
3. Minor / user_review_candidates는 사용자에게 보고
4. library_addition_candidates는 사용자 컨펌 후 라이브러리 갱신
5. git commit + push

## 메모리 연동

- `feedback_user_abbreviations.md` — 약어 정상 인정
- `feedback_subagent_self_eval_unreliable.md` — 메인 직접 검증
- `feedback_qa_judge_lecturer.md` — 부장판사+강사 QA (필요 시 추가)

## 입력값

$ARGUMENTS
