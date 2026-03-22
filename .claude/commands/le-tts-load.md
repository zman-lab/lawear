# le-tts-load — TTS 규칙 + 기준 샘플 컨텍스트 로딩

> TTS 변환 작업 전 반드시 호출. 규칙/기준 샘플을 메인 에이전트 컨텍스트에 로드.
> le-dev에서 TTS 시작 시 자동 호출 (수동 호출도 가능: `/le-tts-load`).

## 실행 시 자동 수행 (순서대로)

### Step 1. 규칙 파일 읽기

```
Read: /Users/nhn/zman-lab/lawear/docs/handover/tts_rules.md (전체)
```

### Step 2. 기준 게시글 읽기 (확정된 형식/샘플)

```
mcp__claude-board__read_post(post_id=756)  — 형소 제1문 확정판 (비교표 형식 기준)
mcp__claude-board__read_post(post_id=760)  — 4과목 Lv.1/2/3 비교
mcp__claude-board__read_post(post_id=761)  — A/B/C/F 구조 확정
```

게시판 서버 OFF 시: Step 2 스킵하고 사용자에게 "기준 게시글 로드 불가" 알림. tts_rules.md + 메모리만으로 진행.

### Step 3. 메모리 피드백 읽기

```
Read: memory/project_level_system.md       — Lv.1/2/3 정의
Read: memory/project_id_system.md          — ID 체계 ({yyyy}_{과목}_{단계}_{문번}_{부수문번})
Read: memory/feedback_tts_brevity.md       — R-12
Read: memory/feedback_tts_toc_generic.md   — R-13
Read: memory/feedback_tts_number_reading.md — R-14
Read: memory/feedback_tts_problem_concise.md — R-12 강화
Read: memory/feedback_tts_opus_only.md     — Opus only
Read: memory/feedback_tts_team_structure.md — 3인 팀 구조
Read: memory/feedback_tts_v3_round.md      — R-15~R-18
Read: memory/feedback_tts_v4_round.md      — R-19~R-22
```

### Step 4. 로드 완료 보고

사용자에게 1줄 요약:
> "TTS 규칙 로드 완료 — tts_rules.md(R-01~R-23) + 기준 게시글 N건 + 메모리 피드백 N건. 변환 준비 OK."

### Step 5. 규칙 충돌 체크

- tts_rules.md vs 기준 게시글 vs 메모리 간 불일치 발견 시 → 사용자에게 보고
- 없으면 생략

## le-dev 연동

- le-dev의 TTS 변환 워크플로우 Step 3에서 자동 호출
- 이미 같은 세션에서 호출한 적 있으면 스킵 (재로드 시 수동 `/le-tts-load` 호출)
- 세션 최초 TTS 작업 시 1회만 실행

## 수동 호출 시나리오

- 규칙이 업데이트됐을 때 강제 리로드: `/le-tts-load`
- "규칙 뭐 있었지?" 확인용
- 새 세션 시작 시 명시적 로드

## 주의

- 이 스킬은 **규칙 로딩만** 한다. 작업 지시(과목/문제번호 등)는 받지 않는다.
