# QA 체크리스트

> 작성일: 2026-03-18
> 기준: TTS 플레이어 + 플레이리스트 관리(즐겨찾기) 구현 완료 시점
> 자동 검증: `/le-debug` 스킬 (CDP) / 수동 검증: 갤럭시 실기기

---

## 자동 검증 (CDP — `/le-debug` 스킬로 실행)

> 실행 전: 앱 무선 디버깅 연결 확인 (`docs/phase3_ux/무선디버깅_가이드.md`)

### 화면 네비게이션

- [ ] 앱 실행 → HomeScreen 정상 표시 (7과목 카드 노출)
- [ ] 민사소송법 탭 → ListScreen 진입 + 케이스 목록 로드
- [ ] 케이스 1개 클릭 → PlayerScreen 진입 + 가사(문제/목차/답안) 표시
- [ ] PlayerScreen 뒤로가기 → ListScreen 복귀
- [ ] ListScreen 뒤로가기 → HomeScreen 복귀

### 재생 핵심 기능

- [ ] 재생 버튼 → TTS 시작 + 현재 문장 강조 업데이트
- [ ] 연속 재생 — 5문장 이상 순차 진행 확인 (`currentSentenceIndex` 증가)
- [ ] 배속 변경 (SpeedSheet) → 현재 문장 끊김 없이 다음 문장부터 새 배속 적용
- [ ] 일시정지 → 재개 시 같은 문장에서 이어서 시작
- [ ] 이전/다음 곡 버튼 → `playlistIndex` 변경 + PlayerScreen 곡 정보 업데이트

### 반복 모드 (RepeatModeSheet)

- [ ] 전곡 반복(`repeat-all`) → 마지막 곡 끝 → 첫 곡으로 루프 + 화면 동기화
- [ ] 1곡 반복(`repeat-one`) → 같은 곡 처음부터 재시작
- [ ] 셔플(`shuffle`) → 다음 곡이 랜덤으로 전환 (같은 곡 연속 최소화)
- [ ] 1곡 후 정지(`stop-after-one`) → 현재 곡 끝 후 재생 멈춤

### 선택 재생 + 플레이리스트

- [ ] ListScreen에서 케이스 3개 선택 → "선택 재생" → PlayerScreen 자동 진입 + `playlist` 3개 확인
- [ ] 순차 재생 — 1번 곡 끝 → 2번 곡 자동 전환 + 가사 업데이트
- [ ] PlayerBar 플레이리스트 아이콘 → PlaylistSheet 열림 + 곡 목록 표시
- [ ] PlaylistSheet에서 2번 곡 탭 → 해당 곡으로 점프

### PlayerBar

- [ ] 재생 중 PlayerBar 노출 (곡 정보 + 진행 표시)
- [ ] PlayerBar 8개 버튼 전부 표시: 이전/재생|일시정지/다음/배속/반복모드/플레이리스트/슬립타이머/음성
- [ ] PlayerBar에서 커버 탭 → PlayerScreen 진입

### 즐겨찾기 (FavoriteScreen)

- [ ] ListScreen에서 케이스 선택 → ★ 아이콘 탭 → FavoriteSheet 열림
- [ ] FavoriteSheet에서 "새 플레이리스트" 생성 → 저장 → 목록에 노출
- [ ] HomeScreen 즐겨찾기 탭 → FavoriteScreen 진입 + 저장된 플레이리스트 목록
- [ ] 기존 플레이리스트 선택 → 케이스 추가 → 곡 수 증가 확인
- [ ] 즐겨찾기 플레이리스트 탭 → `playlist` 로드 + PlayerScreen 진입
- [ ] FavoriteScreen ⋯ 메뉴 → 바텀시트 열림 (이름 변경 / 삭제 옵션 표시)
- [ ] 이름 변경 → 목록 즉시 반영
- [ ] 삭제 → 목록에서 제거

### 플레이리스트 상세 뒤로가기

- [ ] 플레이리스트 상세(곡 목록) → 뒤로가기 → FavoriteScreen 목록으로 복귀 (HomeScreen으로 튀지 않음)

---

## 수동 확인 (갤럭시 실기기 — 사용자 직접)

### 오디오

- [ ] TTS 소리 정상 출력 (스피커/이어폰 양쪽)
- [ ] 배속 변경 후 실제 속도 변화 체감 (1.0x vs 1.5x vs 2.0x)
- [ ] 음성 변경(VoiceSheet) → 다른 목소리로 즉시 전환

### 슬립 타이머

- [ ] SleepTimerSheet에서 타이머 설정 → 남은 시간 카운트다운 표시
- [ ] 타이머 만료 → 재생 자동 정지

### 레벨 탭

- [ ] HomeScreen/PlayerScreen 레벨 탭에서 Lv.2, Lv.3 탭 → "준비 중" 메시지 표시 (에러 없음)
- [ ] Lv.1 탭 → 정상 데이터 표시

### 앱 재시작 후 지속성

- [ ] 앱 종료 후 재시작 → 즐겨찾기 목록 유지 (`localStorage` `lawear-favorites`)
- [ ] 앱 종료 후 재시작 → 선택한 음성(TTS 보이스) 유지 (`lawear-selected-voice-uri`)

### 자동 업데이트

- [ ] 앱 시작 시 GitHub 최신 릴리즈 체크 — 최신 버전이면 팝업 없음
- [ ] (버전 낮춰서 테스트 시) 업데이트 팝업 표시 → "업데이트" 탭 → APK 다운로드 링크 열림

---

## 알려진 미구현 항목 (체크 제외)

| 항목 | 상태 |
|------|------|
| MediaSession 잠금화면 컨트롤 | 부분 구현 (`mediaSession.ts` 있음, 실기기 완성도 확인 필요) |
| TTS 엔진 탐지 (`TTSEngine` 타입) | 타입만 있음, UI 미연결 |
| MP3 캐시 (`audioCache.ts`) | 파일 있음, 실제 캐싱 로직 검증 필요 |

---

## QA 완료 기준

- 자동 검증: 전 항목 PASS
- 수동 확인: 오디오/타이머/지속성 전 항목 OK
- 크래시/ANR 없음
- 콘솔 에러 없음 (CDP `console.error` 0건)
