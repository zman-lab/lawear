# le-debug — Lawear 무선 디버깅 스킬

> 갤럭시 무선 adb로 앱 설치/실행/크래시 분석을 자동화한다.
> JS 로그로 안 잡히는 네이티브(Java) 크래시 디버깅용.

## 언제 사용하나

- 앱이 번개처럼 꺼지는 크래시 (JS window.onerror로 안 잡힘)
- 특정 동작에서 반복 크래시 재현 + 원인 분석
- 새 빌드 설치 후 즉시 테스트

## 기기 정보

- 기기: zman20 noteultra (갤럭시)
- IP 대역: 10.77.76.x (사내망)
- 패키지: com.zmanlab.lawear
- 액티비티: com.zmanlab.lawear/.MainActivity

## 워크플로우

### Phase 1: 연결

```
1. adb 연결 상태 확인
   adb devices

2-a. 이미 연결됨 → Phase 2로
2-b. 연결 안 됨 → 사용자에게 안내:
   "갤럭시 설정 → 개발자 옵션 → 무선 디버깅 ON 후
    '페어링 코드로 기기 페어링' 탭해서
    IP:포트 + 페어링 코드 알려주세요"

3. 페어링 (최초 1회 또는 만료 시)
   adb pair <IP>:<페어링포트> <코드>

4. 연결 (페어링 포트 ≠ 연결 포트! 반드시 사용자에게 별도 확인)
   adb connect <IP>:<연결포트>

5. 연결 확인
   adb devices
```

### Phase 2: 빌드 + 설치

```
1. 웹 빌드
   cd /Users/nhn/zman-lab/lawear/web && npx vite build

2. Android 동기화
   npx cap sync android

3. APK 빌드
   cd /Users/nhn/zman-lab/lawear/web/android && ./gradlew assembleDebug

4. 기존 앱 제거 (레거시 클린)
   adb -s <기기> uninstall com.zmanlab.lawear

5. 새 APK 설치
   adb -s <기기> install /Users/nhn/zman-lab/lawear/web/android/app/build/outputs/apk/debug/app-debug.apk

6. 앱 실행
   adb -s <기기> shell am start -n com.zmanlab.lawear/.MainActivity
```

### Phase 3: 크래시 모니터링

```
1. 로그 클리어
   adb -s <기기> logcat -c

2. 사용자에게 크래시 재현 요청
   "앱에서 [동작] 해주세요"

3. 크래시 발생 후 로그 수집
   adb -s <기기> logcat -d | grep -A 25 "FATAL EXCEPTION"

4. 추가 컨텍스트 필요 시
   adb -s <기기> logcat -d | grep -iE "lawear|zmanlab|capacitor" | tail -30
```

### Phase 4: 분석 + 수정

```
1. 크래시 스택트레이스 분석
   - Java 네이티브 크래시 → node_modules 또는 android/ Java 소스 확인
   - Capacitor 플러그인 크래시 → 해당 플러그인 Java 소스 전체 분석
     (⚠️ 크래시 라인만 보지 말고 null 가능한 필드 전부 확인!)

2. JS 또는 Java 코드 수정

3. Phase 2 반복 (빌드 → 설치 → 실행)

4. Phase 3 반복 (크래시 재현 테스트)

5. 수정 확인되면 커밋 + GitHub Release 배포
```

## 주의사항

- **페어링 포트 ≠ 연결 포트**: 매번 다름, 반드시 사용자에게 둘 다 확인
- **무선 디버깅은 폰 재시작 시 꺼짐**: 다시 켜야 함
- **PC와 폰 같은 Wi-Fi 필수** (사내망 10.77.76.x)
- **Java 크래시 분석 시**: 해당 라인만 보지 말고 **클래스 전체**의 null 가능 필드 점검
- **cap sync 필수**: vite build만 하고 sync 안 하면 APK에 반영 안 됨

## 입력값

$ARGUMENTS
