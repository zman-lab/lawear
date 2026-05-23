# Phase 3 팀 2A — merge.html user_input 분기

> lawear-7ad6 / Opus + ultrathink / 2026-05-23
> 베이스: design.md §1+§5+§6, 17895_analysis §10-5/§10-6

## 변경 요약 (1914 → 1999줄, +85)

| 영역 | 라인 | 유형 |
|------|------|------|
| CSS `.compare-table.cols-2` + `.user-memo` + `.user-input-edit-btn` | L320-348 (+28) | 추가 |
| `renderContent()` user_input 분기 | L1549-1604 (+57) | 추가 |

**기존 코드 수정 0줄.** 4탭/library/edit/stealth 무손상.

## CSS (L320-348) — 기존 `.compare-table` mirror

- `.compare-table.cols-2 th/td { width: 50%; }` — 33.33% override만
- `.compare-table.cols-2 td { vertical-align: top; }` — 좌우 높이 차 자연 정렬
- `.user-memo` — 메모 footer (border-left accent + panel-2 배경)
- `.user-input-edit-btn` — 우상단 편집 버튼 (margin-left: auto)
- 신규 CSS 변수 0건 (기존 --accent/--accent-dim/--panel-2/--text-dim 재사용)

## user_input 분기 (L1549-1604)

**위치**: 라이브러리 분기(L1494-1518) 바로 다음 (사용자 명시 "기존 type:library 분기 옆에" 정확).

**구조** (design.md §1+§6 1글자 일치):

1. **헤더** (일반 케이스 헤더 mirror):
   - case-id-large `{file}-{case}`
   - case-subject `{subjectKor} · {category} · {title} · {points}점`
   - **우상단 [✏️ 다시 편집] 버튼** → `window.location.href='/input.html?path='+encodeURIComponent(currentPath)`
   - breadcrumb + 복사 버튼

2. **본문** (탭 없음 — 라이브러리 분기 mirror):
   ```js
   `<table class="compare-table cols-2">
     <thead><tr><th>문제</th><th>답안</th></tr></thead>
     <tbody><tr>
       <td>${renderMd(extractSection(md,'문제') || '(문제 없음)')}</td>
       <td>${renderMd(extractSection(md,'답안') || '(답안 없음)')}</td>
     </tr></tbody>
   </table>`
   ```

3. **메모 footer** (선택):
   - `extractSection(md,'메모')` 있을 때만 `.user-memo` div 추가, 없으면 빈 문자열

4. **위장 모드**: stealthMode 시 displaySubject/displayCategory + 버튼 라벨 "Edit"

5. **editorWrap appendChild**: 편집 모드(✏️) user_input 케이스에서도 동작 (라이브러리 mirror)

## 트리 분기 (renderTree) — 변경 없음

design.md §5 옵션 1 "5단 트리 자동 합류" 채택. type==='user_input'는 L1030 library 조건 통과 못함 → L1035 else if 5단 트리 자동 매칭 (subjectKor/category/fileKor/file 메타 등록만 필요). **코드 수정 0줄.**

## 사용자 룰 준수

| 룰 | 확인 |
|----|------|
| 주석 충분 | 분기 진입 6줄 + 섹션 추출 3줄 |
| 4탭 안 깨기 | L1520+ 일반 헤더 코드 0줄 수정 |
| library 분기 안 깨기 | L1494-1518 0줄 수정 + 직후 분기 추가 |
| 편집 모드 안 깨기 | toggleEditor 0줄 + editorWrap appendChild |
| 위장 모드 안 깨기 | stealthMode 분기 + displaySubject/displayCategory |
| Opus + ultrathink | 본 작업 수행 |

## 자의 해석 회피

- design.md §1: `<table class="compare-table cols-2">` th/td 50% — 명세 일치
- design.md §6: 우상단 버튼 → `input.html?path=` redirect (modal 옵션 X)
- 17895_analysis §10-5 옵션 1: 트리 분기 코드 0줄
- 17895_analysis §10-6: cols-2는 width: 50% override만

## 검증

- **JS 문법**: node로 script 태그 파싱 OK (55833 chars)
- **wc -l**: 1999줄 (1914 + 85 = 1999 ✓)
- **grep**: `user_input`/`cols-2`/`user-memo`/`user-input-edit-btn` 모두 출현

## dev-qa 게이트 (Phase 5)

4탭/라이브러리/edit/stealth 기존 정상 + user_input split 테이블/편집 버튼 redirect/5단 트리 자동 합류/빈 섹션 fallback/메모 미존재 footer 숨김.

## 후속 (의존)

- 팀 2B/2C: input.html (편집 redirect 대상)
- 팀 1: server.py do_POST `/api/create/`
- 팀 3: _file_index.json entry
