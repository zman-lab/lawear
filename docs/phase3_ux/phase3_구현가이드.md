# Phase 3 UX — 구현 가이드

- 커밋: `83afba0`
- 브랜치: `feature/ux-phase3`
- 게시판: #655

## 구현 기능

### 1. TTS 엔진 자동탐지

**파일**: `TTSFilePlugin.java`, `ttsFile.ts`, `VoiceSheet.tsx`

- `getEngines()`: Android `TextToSpeech.getEngines()` 래핑 → 설치된 TTS 엔진 목록
- `openTTSSettings()`: Android TTS 설정 화면 열기
- VoiceSheet에 현재 엔진 표시 + 엔진 뱃지 + "변경" 버튼

### 2. MP3 렌더링/캐시

**파일**: `TTSFilePlugin.java`, `renderQueue.ts`, `audioCache.ts`, `SettingsScreen.tsx`

#### 렌더링 플로우
```
SettingsScreen "저장" 버튼
  → getSubjectRenderItems(subjectId) → RenderItem[]
  → renderQueue.enqueue(items) → startQueue()
  → 각 항목:
    1. hasCachedAudio() 확인 → 있으면 스킵
    2. TTSFile.synthesizeToFile() → WAV 파일 생성
    3. markAsCached() → 매니페스트 업데이트
  → 완료 시 캐시 정보 새로고침
```

#### TTSFilePlugin 주요 기능
- `synthesizeToFile()`: 텍스트 → WAV 파일
  - 4000자 초과 시 자동 청크 분할 + WAV 결합
  - 문장 경계에서 분할 (마침표/물음표/느낌표)
  - 백그라운드 스레드 실행 (UI 블로킹 없음)
  - 청크별 120초 타임아웃

#### 캐시 구조
```
{앱내부저장소}/lawear-audio/
  ├── _manifest.json
  └── {subjectId}/
      └── {fileId}/
          └── {questionId}.wav
```

### 3. MediaSession (기존 완성 확인)

- `mediaSession.ts` + PlayerContext 연동 이미 완성
- Android 퍼미션 (FOREGROUND_SERVICE, WAKE_LOCK 등) 이미 설정됨
- 추가 작업 없음

## 수정 파일 목록

| 파일 | 변경 | 줄수 |
|------|------|------|
| `TTSFilePlugin.java` | NEW | 316 |
| `ttsFile.ts` | NEW | 53 |
| `MainActivity.java` | EDIT | 플러그인 등록 |
| `types/index.ts` | EDIT | TTSEngine 타입 |
| `audioCache.ts` | EDIT | markAsCached + .wav |
| `renderQueue.ts` | REWRITE | 실제 렌더링 |
| `VoiceSheet.tsx` | EDIT | 엔진 UI |
| `SettingsScreen.tsx` | EDIT | 렌더링 UI |

## 주의사항

- WAV 형식 (비압축): 과목당 200~500MB 예상
- 네이티브(Android)에서만 렌더링 지원, 웹은 미지원
- Android 14+(API 34) 타겟이므로 Foreground Service 퍼미션 필수 (이미 설정됨)
- TTS 엔진 변경 후 음성 목록이 바뀌므로 VoiceSheet 재진입 시 새로고침됨

## 테스트 방법

1. APK 빌드: `cd web && npm run build && npx cap sync android`
2. Android Studio에서 실행
3. 설정 → 오프라인 저장 → 과목별 "저장" 버튼
4. 프로그레스 바 확인 + 완료 후 캐시 크기 확인
5. 캐시된 문제 재생 → WAV로 재생되는지 확인
