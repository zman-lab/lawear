# le-tts-find — 과목별 TTS 세부 규칙 로드

> 과목명을 입력하면 해당 과목의 TTS 세부 규칙을 컨텍스트에 로드.
> tts_rules.md(공통)는 /le-tts-load에서 이미 로드된 상태에서 사용.

## 사용법

```
/le-tts-find 형소
/le-tts-find 민법
/le-tts-find 부등예규
```

## 과목명 매핑

| 입력 (어느 걸로든 OK) | 파일 |
|---------------------|------|
| 형소, 형사소송법 | docs/tts_subjects/형소.md |
| 형법 | docs/tts_subjects/형법.md |
| 민소, 민사소송법 | docs/tts_subjects/민소.md |
| 민법 | docs/tts_subjects/민법.md |
| 부등, 부동산등기법, 부등법 | docs/tts_subjects/부등.md |
| 부등예규, 등기예규 | docs/tts_subjects/부등예규.md |

## 실행 시 동작

1. 입력된 과목명을 위 매핑 표에서 찾기
2. 해당 파일 Read
3. 사용자에게 1줄 요약: "{과목명} 세부 규칙 로드 완료 — {규칙 요약}"
4. 파일이 TODO 상태(내용 없음)이면: "아직 세부 규칙 미작성. 공통 규칙(tts_rules.md)만으로 진행합니다."

## 주의

- 이 스킬은 /le-tts-load 이후에 호출 (공통 규칙 먼저 로드)
- 과목 변경 시 다시 호출하면 새 과목 규칙으로 전환

## 입력값

$ARGUMENTS
