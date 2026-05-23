# Phase 3 Team 5 — Playwright UI 12 시나리오

> **세션**: lawear-7ad6 / **모델**: Opus + ultrathink
> **포트**: 17899 (워크트리, 메인 17895 별도)
> **도구**: Playwright 1.58.0 Chromium headless (Python)

---

## 결과 요약

| 결과 | 개수 |
|------|------|
| PASS | 9 |
| PARTIAL | 2 |
| FAIL | 1 |
| **TOTAL** | **12** |

| ID | 결과 | 핵심 |
|----|------|------|
| P1 | PASS | input.html 진입 OK, title/breadcrumb 정상 |
| P2 | PARTIAL | merge.html 사이드바 `+ 새 입력` 버튼 **미구현** — 직접 URL 진입만 가능 |
| P3 | PASS | 탭 3개(문제/답안/메모) 전환 + state 보존 OK |
| P4 | PASS | em-btn 22종 (≥20) + `[red]...[/red]` 마커 삽입 OK |
| P5 | PASS | textarea oninput → editor-preview 실시간 동기 OK |
| P6 | PARTIAL | Cmd+S 누른 후 리다이렉트 안 됨 — save-status 비어있음, **저장 자체 미동작** 의심 |
| P7 | PASS | `compare-table.cols-2` 좌우 split 렌더 OK (test_c1.md 정상 인덱스) |
| P8 | **FAIL** | **편집 버튼 onclick HTML 속성 파싱 깨짐** — 큰따옴표 충돌 버그 (아래 §버그) |
| P9 | PASS | 민법 미케01_01 정상 3컬럼 compare-table 렌더 (회귀 OK) |
| P10 | PASS | 두문자/민법.md collapsibles=75개 (라이브러리 분기 OK) |
| P11 | PASS | data-path 노드 634개 + localStorage 키 정상 동작 |
| P12 | PASS | em-btn 341개 노출 + 위장 모드 toggle OK |

---

## 발견 버그 1: P8 편집 버튼 onclick HTML 속성 깨짐

**파일**: `tts-new/merge.html` L1578

**현재**:
```html
<button class="user-input-edit-btn"
  onclick="window.location.href='/input.html?path=' + encodeURIComponent(${JSON.stringify(currentPath)})">
```

**문제**: 템플릿 리터럴이 평가되어 `${JSON.stringify(currentPath)}` → `"2026_사용자_..."`로 큰따옴표 포함. `onclick="..."`의 외부 큰따옴표를 조기 종료시킴.

**렌더 결과 (브라우저 DOM)**:
```
onclick="window.location.href='/input.html?path=' + encodeURIComponent("
```
→ 두 번째 `"`에서 속성값 종료, 클릭해도 동작 안 함.

**수정안** (HTML attribute escaping):
```javascript
const escapedPath = currentPath.replace(/"/g, '&quot;').replace(/&/g, '&amp;');
// 또는 더 안전하게 addEventListener로 바인딩
```

또는:
```html
onclick="window.location.href='/input.html?path=' + encodeURIComponent(${JSON.stringify(currentPath).replace(/"/g, '&quot;')})"
```

**영향**: user_input 분기에서 편집 버튼이 **모든 케이스 동작 불가**.

---

## 발견 버그 2: P6 저장 → 리다이렉트 안 됨 (의심)

**증상**: input.html에서 Cmd+S 키 누른 후 6초 대기해도 URL 변화 없음. `#save-status` 비어 있음.

**가능 원인** (Playwright headless에서 일관 재현):
- `saveFile()` 함수 키보드 단축키 바인딩 누락
- POST 응답 후 `window.location.href` 갱신 누락
- 메타 검증 실패 시 silent fail (콘솔 에러 X)

**권장 후속**: 메인 세션에서 `saveFile()` 함수 + 키보드 핸들러 점검.

---

## 발견 사항 3: P2 사이드바 `+ 새 입력` 버튼 미구현

**스펙 (impl_plan §4 P2)**: "사이드바 하단 `[+ 새 입력]` → input.html 진입"

**실제**: `merge.html` 사이드바에 신규 입력 진입 버튼 없음. `grep "새 입력"` 0건.

**현재 진입 경로**: 직접 URL `/input.html?subject=...&problem=...` 만 가능.

**판단**: 디자인 단순화로 의도적 생략일 수 있음 (메인 세션 확인 필요). 기능 자체는 input.html 단독 동작 정상.

---

## 회귀 시나리오 (P9~P12) 판정

모두 PASS. 기존 17895 동작 (3컬럼 compare-table, 라이브러리 collapsibles, 5단 트리, 편집/위장 모드) **무손상**.

---

## 스크린샷

`playwright_screenshots/p1.png` ~ `p12.png` (13장, p2_before_navigate.png 포함)

---

## 핵심 발견 (한 줄)

**P8 user_input 편집 버튼 onclick HTML 속성 파싱 깨짐 — JSON.stringify 큰따옴표 escaping 누락. 메인 세션에서 즉시 패치 필요.**
