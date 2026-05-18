# le-typo-fix — 음성 답안 오타 교정 스킬

> Opus SE 가 음성 답안(STT) 오타를 정적 사전 + 법률 컨텍스트 분석으로 교정하여 채점 직전 메인에게 반환.
> lawear-e571/typo-system (2026-05-19) 도입. 사용자 attempt 6/7/8/9 에서 발견한 오타 패턴 기반.

## 역할

```
사용자가 음성으로 답안 작성 → STT 오타 다수 → 채점 전에 교정해야 정확한 채점 가능
  ↓
이 스킬: typo_dict.json (정적 사전) + 법무사 시험핏 컨텍스트 분석
  ↓
교정된 답안 텍스트 + corrections diff list 반환
  ↓
메인이 PUT /grade 시 eval_notes.typo_corrections 에 누적
```

## 호출 패턴

### 1. attempt_id 로 호출 (서버에서 답안 fetch)

```
/le-typo-fix attempt:N
```

- N = 17896 의 attempt PK (예: `/le-typo-fix attempt:9`)
- 스킬이 GET /api/attempts/N 호출하여 answer_text 가져온 후 교정

### 2. 답안 텍스트 직접 호출

```
/le-typo-fix answer:"파산관제인은 통정표시 행위를 추인할 수 있다"
```

- 즉석 텍스트 교정 (테스트/디버그용)

## 처리 워크플로우

```
1. 입력 수신 (attempt_id 또는 answer text)

2. 답안 텍스트 확보
   - attempt_id 모드: curl GET http://localhost:8585/api/attempts/{id}
   - text 모드: 직접 사용

3. 정적 사전 1차 패스 (typo_corrector.py)
   - typo_dict.json static_replacements 매칭
   - 조문 번호(제103/104/108 등) 인접 영역 보호
   - 긴 키 우선 매칭 (부분 충돌 방지)

4. Opus SE 문맥 분석 (필요시)
   - 정적 사전이 못 잡은 오타 추가 식별
   - 법률 용어 + 시험핏 컨텍스트 기반
   - JSON 응답: {original, corrected, corrections}

5. 결과 반환
```

## 출력 스키마 (JSON 5KB)

```json
{
  "attempt_id": 9,
  "original": "파산관제인은 통정표시 행위를 추인할 수 있다.",
  "corrected": "파산관재인은 통정허위표시 행위를 추인할 수 있다.",
  "corrections": [
    {"from": "파산관제인", "to": "파산관재인", "reason": "음성 STT 오타", "source": "static_dict"},
    {"from": "통정표시", "to": "통정허위표시", "reason": "음성 STT 오타", "source": "static_dict"}
  ],
  "static_dict_hits": 2,
  "ai_additions": 0,
  "ready_for_grade": true
}
```

## 사용 시점

### 메인이 채점 직전 호출 권장

```
1. 사용자가 답안 제출 (음성 STT)
2. attempt 생성 → status='pending_grade'
3. 메인이 /le-typo-fix attempt:N 호출 (이 스킬)
4. 결과의 corrected text + corrections 메모
5. 메인이 채점 SE 호출 (또는 직접 채점)
   - 채점 SE 에게 corrected text 전달 (오타 끌림 방지)
6. PUT /api/attempts/N/grade 시 body 의 eval_notes.typo_corrections
   에 corrections 그대로 주입
```

### 채점 SE 가 자체적으로 호출

채점 SE 가 grader.py 의 `grade()` 함수를 직접 호출할 경우, `typo_corrector.correct()`
가 자동으로 1차 패스 적용 — 이 스킬은 명시적 사전 검토용.

## 사전 누적 (사용자 발견 오타 추가)

새 오타 발견 시:

```
1. docs/tts-exam/typo_dict.json 의 static_replacements 에 추가
2. clear_cache() 또는 서버 재시작 (캐시 무효화)
3. 다음 채점부터 자동 적용
```

예시:
```json
"static_replacements": {
  ...
  "새오타키": "정정된키",  // 사용자 발견 (어느 attempt)
  ...
}
```

## 제약

- 조문 번호(제103/104/108 등) 와 핵심 두문자는 **절대 치환 X** — 그건 진짜 모르는 것
- preserve_terms 인접 영역 (±15자) 자동 보호
- Sonnet/Haiku 금지 (lawear 정책 — Opus 만)
- 정적 사전 0건 매칭이라도 호출 안전 (graceful, corrections=[] 반환)

## 참고

- 모듈: `docs/tts-exam/typo_corrector.py`
- 사전: `docs/tts-exam/typo_dict.json`
- 통합 위치: `grader.py grade()` / `grade_attempt_subq()` 자동 1차 패스
- 스키마: `attempts.py eval_notes.typo_corrections` (8번째 확장 키)
- UI: `index.html buildRichSummaryHtml — 🔤 오타 N건 자동 교정 섹션`
- 게시판 보고: lawear-work (300자 초과 시)
