# Lawear 추가 기능 플랜

> 작성일: 2026-03-18
> 기준: TTS 플레이어 + 플레이리스트 관리(즐겨찾기) 구현 완료 이후 단계

---

## 우선순위 정의

| 기호 | 의미 |
|------|------|
| P0 | 합격에 직결 — 없으면 학습 효율이 눈에 띄게 떨어짐 |
| P1 | 있으면 확실히 도움됨 — 다음 스프린트 대상 |
| P2 | 있으면 좋은데 없어도 됨 — 여유 있을 때 |
| P3 | 탐구/실험성 — 일단 아이디어 보관 |

| 기호 | 난이도 |
|------|--------|
| S | Small — 하루 이내 |
| M | Medium — 2~3일 |
| L | Large — 1주일+ |

---

## 1. 학습 효과 극대화

| # | 기능 | P | 난이도 | 설명 |
|---|------|---|--------|------|
| 1-1 | 학습 진도 추적 | P1 | M | 케이스별 재생 횟수 + 마지막 들은 날짜 저장. `localStorage`에 `lawear-progress` 키. `Question` 타입에 통계 오버레이. |
| 1-2 | 취약 영역 마킹 | P0 | S | 재생 중 "모르겠음" 버튼 탭 → 해당 케이스에 취약 플래그. FavoriteScreen처럼 별도 탭 또는 즐겨찾기 플레이리스트로 진입. |
| 1-3 | 오답노트 메모 | P2 | M | 케이스에 텍스트 메모 추가. PlayerScreen 하단에 메모 입력창. `localStorage`에 `lawear-notes` 키로 `{ [questionId]: string }` 저장. |
| 1-4 | 에빙하우스 복습 주기 추천 | P2 | L | 1회 학습 후 1일/3일/7일/14일/30일 후 자동 복습 큐 생성. 홈 화면에 "오늘 복습 케이스 N개" 뱃지 표시. 실제 알람은 Android 알림 채널 필요 → Capacitor 플러그인 연동. |
| 1-5 | 시험 D-day + 남은 학습량 | P1 | S | SettingsScreen에서 시험일 입력 → HomeScreen 상단에 `D-{N}`, 진도율 `{완료}/{전체}` 표시. `Subject.completedQuestions`는 이미 타입에 있으므로 로직만 연결. |

---

## 2. 학습 편의

| # | 기능 | P | 난이도 | 설명 |
|---|------|---|--------|------|
| 2-1 | 구간 반복 | P1 | M | PlayerScreen에서 "A-B 반복" 버튼. 현재 `sentenceIndex` 기준으로 시작/끝 문장 인덱스 지정. `RepeatMode`에 `'repeat-section'` 타입 추가. |
| 2-2 | 북마크 | P1 | S | 재생 중 북마크 버튼 탭 → `{ questionId, sentenceIndex }` 저장. PlayerScreen 가사 뷰에서 북마크 문장 강조. 북마크 목록에서 점프 가능. |
| 2-3 | 텍스트 검색 | P1 | M | 홈/리스트 화면에 검색바. `ttsData.ts`의 `content.problem + toc + answer` 전체 스캔 → 히트 케이스 목록 표시 → 탭하면 PlayerScreen 진입. |
| 2-4 | 다크/라이트 테마 전환 | P2 | S | `useTheme` 훅(`/web/src/hooks/useTheme.ts`)이 이미 존재. SettingsScreen에 토글만 연결하면 됨. |
| 2-5 | 글자 크기 조절 | P2 | S | PlayerScreen 가사 영역 `fontSize` CSS 변수화. SettingsScreen에 슬라이더 (3단계: 소/중/대). `localStorage`에 저장. |

---

## 3. 레벨 시스템

> 현재 `types/index.ts`에 `Level = 1 | 2 | 3` 타입, `PlayerState.level` 필드가 이미 정의되어 있음.
> 레벨 전환 UI는 PlayerScreen/HomeScreen에 탭으로 구현 예정.

| # | 레벨 | P | 난이도 | 설명 |
|---|------|---|--------|------|
| 3-1 | Lv.1 빠른복습 | — | — | **현재 구현된 데이터**. 문제+목차+답안 전체. 기준 버전. |
| 3-2 | Lv.2 핵심요약 | P1 | L | `le-summary` 스킬로 생성. 문제 섹션 생략, 답안 핵심 2~3줄만. `ttsData.ts`에 레벨별 `content` 필드 추가 필요. |
| 3-3 | Lv.3 슈퍼심플 | P2 | L | `le-supersimple` 스킬로 생성. 의의/취지/요건 키워드만 1~2문장. 시험 전날 최종 점검용. |
| 3-4 | 레벨 전환 시 자동 TTS 전환 | P1 | M | `PlayerContext`에서 `level` 변경 감지 → 같은 `questionId`의 해당 레벨 `content`로 `sentences` 재계산. 현재 `sentenceIndex` 리셋 (또는 0번으로). |

---

## 4. 데이터 / 콘텐츠

| # | 기능 | P | 난이도 | 설명 |
|---|------|---|--------|------|
| 4-1 | 나머지 과목 TTS 변환 | P0 | L | 형법, 형사소송법, 부동산등기법 TTS 텍스트 생성 후 `ttsData.ts`에 과목 엔트리 추가. `le-dev` 스킬 워크플로우 그대로 사용. |
| 4-2 | PDF 원문 뷰어 연동 | P3 | L | 재생 중인 문장과 PDF 원문 하이라이트 동기화. PDF.js + Capacitor 파일 접근 플러그인 필요. 난이도 높고 오프라인 저장 고려 필요. |
| 4-3 | 모의고사 모드 | P2 | M | 문제(problem 배열)만 TTS로 읽고 답안은 가리기. `ViewMode`에 `'exam'` 추가. 타이머와 결합하면 실전 감각 훈련 가능. |

---

## 구현 순서 (추천)

1. **P0 즉시**: 취약 영역 마킹 (1-2), 나머지 과목 TTS 데이터 (4-1)
2. **P1 다음 스프린트**: 학습 진도 추적 (1-1), 시험 D-day (1-5), 구간 반복 (2-1), 북마크 (2-2), 텍스트 검색 (2-3), 레벨 Lv.2 (3-2), 레벨 전환 (3-4)
3. **P2 여유 시**: 에빙하우스 (1-4), 오답노트 (1-3), 다크모드 (2-4), 글자 크기 (2-5), 모의고사 모드 (4-3), Lv.3 슈퍼심플 (3-3)
4. **P3 탐구**: PDF 원문 뷰어 (4-2)

---

## 현재 코드 참고 포인트

| 작업 | 참고 파일 |
|------|-----------|
| localStorage 패턴 | `web/src/services/favoritePlaylist.ts` |
| 레벨 타입 | `web/src/types/index.ts` — `Level`, `PlayerState.level` |
| useTheme 훅 | `web/src/hooks/useTheme.ts` |
| 문장 배열 계산 | `web/src/context/PlayerContext.tsx` — `getSentences()` |
| 과목 데이터 | `web/src/data/ttsData.ts` |
