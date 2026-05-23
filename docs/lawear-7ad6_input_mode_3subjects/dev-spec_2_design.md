# dev-spec Phase 2-2: 설계 (작업 A — 3과목 입력+뷰어 모드)

> **세션**: lawear-7ad6 / **모델**: Opus + ultrathink
> **베이스**: Phase 1 (17895_analysis.md) + Phase 2-1 (dev-spec_1_impact.md)
> **결정 5건 확정** (룰 1+5+4 우선, 자의 해석 X)

---

## 1. 뷰어 split 테이블 구현

**결정**: `<table class="compare-table cols-2">` — 기존 4탭 `전체` 모드(merge.html L1573-1581)의 3컬럼 `compare-table`을 mirror하고 2컬럼 변종만 CSS 추가.

**근거**:
- 사용자 룰 5 "기존 17895처럼 테이블로 좌우 나눠서 문제/답안 형식" — table 명시
- 기존 compare-table 컴포넌트 재사용 → 룰 1 (기존 무손상) 보장
- flexbox/grid는 신규 CSS 변종 필요 + 인쇄 시 깨지기 쉬움. table은 17895 다크 테마 변수와 이미 정합

**HTML/CSS**:
```html
<table class="compare-table cols-2">
  <thead><tr><th>문제</th><th>답안</th></tr></thead>
  <tbody><tr>
    <td class="md-cell">${renderMd(extractSection(md, '문제'))}</td>
    <td class="md-cell">${renderMd(extractSection(md, '답안'))}</td>
  </tr></tbody>
</table>
<!-- 메모 있으면 footer -->
<div class="user-memo">${renderMd(extractSection(md, '메모'))}</div>
```

```css
.compare-table.cols-2 th,
.compare-table.cols-2 td { width: 50%; vertical-align: top; }
.user-memo { margin-top: 16px; padding: 12px; border-left: 3px solid var(--accent); opacity: 0.85; }
```

기존 `extractSection`(L1595-1605)은 `## ` 시작 + `includes()` 매칭 → `## 문제/답안/메모` 자동 매칭. 변경 0줄.

---

## 2. 입력 UI 동작

**결정**: `input.html` 단일 파일, 상단 탭(문제/답안/메모) + 좌측 textarea + 우측 미리보기 split + 17895 편집 툴바(L620-655) 25종 그대로 복사 + `wrapEmphasis`(L1851-1868) 재사용.

**핵심 동작**:
1. **탭 전환**: 현재 textarea를 `state.problemMd/answerMd/memoMd`에 저장 → 새 탭 textarea 로드 + 미리보기 갱신
2. **태그 툴바**: `wrapEmphasis(tag)` 함수 그대로 복사 — allTags 25종 동일 (em1~4/con/fact/case/bridge/key/red/blue/purple/violet/magenta/indigo/bold/u/blank/blank2/free1/free2/clear)
3. **실시간 미리보기**: `oninput="updatePreview()"` → `renderMd()` (merge.html L793-822 복사) → 우측 div 갱신
4. **저장**: 4섹션 .md 조립 → `POST /api/create/{rel_path}` → 200 시 `window.location='/merge.html?path=<rel_path>'`
5. **편집 모드 이탈 confirm** (R7): 미저장 변경 있으면 confirm — toggleEditor L1823-1843 mirror

**Case 번호**: 클라이언트 자동 (01부터 순차) + POST 409 시 +1 재시도.

**localStorage**: `lawear_input_draft_{과목}` — 페이지 새로고침 대비 임시본.

---

## 3. API 시그니처

**결정**: **POST `/api/create/{rel_path}` 신규** (PUT /save 재사용 X).

**근거**:
- PUT `/api/save/`(L24-77)는 parent 디렉토리 존재 강제(L47-49) → 신규 폴더 거부
- POST는 신규 (target.exists() 시 409), PUT은 갱신 — 의도 분리로 R3 (id 충돌/덮어쓰기) 차단
- 17895_analysis §10-7~10-8 권고와 정합 — _file_index.json 자동 append까지 한 트랜잭션

**요청/응답**:
```
POST /api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_01.md
Content-Type: text/plain; charset=utf-8
<.md body>

200: {"created":"...","bytes":N,"index_updated":true,"id":"2026_budeunglaw_user_01"}
403: path traversal / 화이트리스트 밖 폴더 / 비-.md
409: 이미 존재 → 클라이언트 +1 재시도
400: .md 최소 섹션(`## 메타`) 누락
```

**서버 do_POST 순서**:
1. `relative_to(ROOT)` traversal 차단
2. `target.parent.name in ALLOWED_NEW_DIRS` 화이트리스트
3. `.md` 확장자 강제
4. `target.parent.mkdir(parents=True, exist_ok=True)` 자동 생성
5. `target.exists()` 시 409
6. body UTF-8 + `## 메타` 정규식 최소 검증
7. `target.write_text(body)`
8. _file_index.json 갱신 (`flock` + 임시파일 atomic rename + `.bak` — R3)
9. JSON 응답

---

## 4. .md 멀티섹션 포맷

**결정**: frontmatter 없음. 17895 기존 포맷(17895_analysis §7-1) mirror.

```markdown
# 2026_budeunglaw_user_01

## 메타
- 과목: 부동산등기법
- Case: 01
- 등록일: 2026-05-23
- 출처: 사용자 직접 입력
- _addedBy: lawear-7ad6-input-mode

## 문제
{사용자 입력 — 강조 태그 자유}

## 답안
{사용자 입력 — 강조 태그 자유}

## 메모 (선택)
{비어있으면 섹션 자체 생략 가능}
```

**근거**:
- 17895 기존 `## 메타/원본/Lv.1/Lv.4`와 수평 분리, extractSection 충돌 없음
- YAML frontmatter는 renderMd/makeLibraryCollapsible 처리 안 됨 → 본문 노출 사고. 기존 패턴 mirror가 안전

**파일명**: `{year}_{subject_en}_user_{NN}.md` (예: `2026_budeunglaw_user_01.md`, `2026_minsaseoryu_user_01.md`).

---

## 5. 사이드패널 통합 vs 별도

**결정**: **사이드패널은 merge.html 통합** + **입력 UI는 별도 input.html 신규** (옵션 C 하이브리드).

**근거**:
- 룰 1 "기존 17895 무손상" — 사이드바는 SUBJECT_ORDER(L707)에 부등법/부등/민사서류/부등서류 이미 등록 → _file_index.json entry만 추가하면 자동 표시. merge.html 분기 추가 최소화
- 룰 4 "입력 UI = 탭 형식" — 자유 설계 필요 → 별도 .html. merge.html 1914줄을 2500줄+로 비대화 시 회귀 위험
- 룰 5 "뷰어 = 좌우 split 테이블 = 기존 17895처럼" — compare-table 재사용 자연스러움 → 뷰어는 merge.html

**merge.html 분기 추가** (L1030-1052 / L1483-1518):
- `meta.type === 'user_input'` 신규 type — **라이브러리 분기 mirror, 다음에 배치** (R1 회피)
- 5단 트리 분기 코드 변경 0줄 (라이브러리처럼 별도 분기)

---

## 6. URL 라우팅

- 입력 진입: `http://127.0.0.1:17895/input.html?subject={budeunglaw|budeungseoryu|minsaseoryu}` (과목 prefill)
- subject 미지정 시 첫 화면 과목 선택 드롭다운
- 입력 → 저장 200 → `http://127.0.0.1:17895/merge.html?path=2026_사용자_부동산등기법/2026_budeunglaw_user_01.md` (뷰어 자동 이동)
- 뷰어 user_input 케이스 우상단 `[✏️ 다시 편집]` → `input.html?path=...` (편집 진입)
- merge.html 사이드바 하단 신규 링크: `[+ 새 입력 (3과목)]`

---

## 7. 17895 무손상 검증 체크리스트 (dev-qa Phase 5)

17895_analysis §12-5 기반 확장:

- [ ] 기존 4탭 정상 (`원본/전체/Lv.1/Lv.4`) — 특히 `전체` 3컬럼 compare-table
- [ ] 라이브러리 분기 정상 (두문자/민법.md, 민소.md — makeLibraryCollapsible + 업로드 바)
- [ ] 5단 트리 정상 + localStorage 보존 (`lawear_merge_tree_state`)
- [ ] 편집 모드 정상 (✏️ → textarea + 미리보기 + 25종 태그 + 저장 → `.md.bak`)
- [ ] 위장 모드 정상 (신규 '사용자' 카테고리 'User' 라벨)
- [ ] 다운로드 머지 정상 (stripEmphasis — user_input 케이스는 머지 제외)
- [ ] 3과목 추가 후 사이드바 정렬 깨지지 않음 (SUBJECT_ORDER 위치)
- [ ] 입력→뷰어→재편집→저장 round-trip 정상
- [ ] 음성: `POST /api/create/../../../etc/passwd` → 403
- [ ] 음성: `POST /api/create/random_dir/x.md` → 403
- [ ] 충돌: 같은 파일명 2회 POST → 두 번째 409, +1 재시도 OK
- [ ] R3 동시성: 동시 POST 2건 → flock + atomic rename, 두 entry 모두 append + JSON validate

---

| 일자 | 세션 | 내용 |
|------|------|------|
| 2026-05-23 | lawear-7ad6 | Phase 2-2 design 작업 A (Opus + ultrathink) |
