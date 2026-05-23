# 17895 뷰어 완전 분석 (lawear-7ad6 Phase 1)

> **목적**: 3과목(부동산등기법/부동산등기서류/민사서류) 전용 입력+뷰어 모드 신규 추가 전, 기존 17895 (민법/민소/형법/형소) 구조를 코드 라인 단위로 완전 분석.
> **베이스 코드**: `/Users/nhn/zman-lab/lawear/docs/tts-new/` (워크트리도 동일)
> **분석 일자**: 2026-05-23 (lawear-7ad6 Phase 1)
> **분석 모델**: Opus + ultrathink

---

## 1. 파일 구조

`/Users/nhn/zman-lab/lawear/docs/tts-new/` 직접 구성:

```
tts-new/
├── server.py                 (142줄, 백엔드)
├── merge.html                (1914줄, 단일 SPA 뷰어)
├── exam_hint_mockup.html     (70 KB, 별도 mockup — 채점탭이 아닌 hint mockup)
├── exam_mockup.html          (77 KB, 별도 mockup)
├── _file_index.json          (174 KB, 메타데이터 인덱스)
├── _staging/                 (라이브러리 staging 임시 폴더 — server.py 자동 생성)
│
├── 2024_예비순환_민법/        (디렉토리 = 메타 카테고리 + 과목 결합)
├── 2024_예비순환_민소/
├── 2025_1순환_민소/
├── 2025_2순환_민법/
├── 2025_2순환_민소/
├── 2025_3순환_민법/
├── 2025_3순환_민소/
├── 2025_예비순환_민법/
├── 2026_예비_민법/
├── 2026_예비_민소/
├── 2026_입문_민법/
├── 2026_입문_민소/
│
└── 두문자/                   (라이브러리 분기 — type:"library")
    ├── 민법.md               (1414줄, 두문자/요건 라이브러리)
    ├── 민소.md
    ├── _pdf_원문_민법.md     (PDF 원문 정리본 — 라이브러리 type)
    └── _pdf_원문_민소.md
```

### 1-1. launchd 등록 (server.py 실행 진입점)

`~/Library/LaunchAgents/com.lawear.ttsmerger.plist`:
- WorkingDirectory: `/Users/nhn/zman-lab/lawear/docs/tts-new`
- ProgramArguments: `/usr/bin/python3 server.py`
- KeepAlive: true
- 로그: `/tmp/lawear_ttsmerger.log`, `/tmp/lawear_ttsmerger.err`

**즉, 워크트리(lawear-lawear-7ad6-*)에서 코드 수정해도 launchd는 메인 레포의 server.py를 실행.** 코드 수정 후 launchd 재시작 or 메인 머지가 반영 조건.

### 1-2. _file_index.json 구조 (실제 데이터 발췌)

```json
{
  "files": [
    {
      "id": "2024_minbeop_yebi_mogo1_01",
      "subject": "minbeop",
      "subjectKor": "민법",
      "category": "예비순환",
      "file": "mogo1",
      "fileKor": "2024_민법_예비순환_mogo1",
      "case": "01",
      "title": "TBD — Opus Lv.1/Lv.4 작성 후 사용자 검수",
      "path": "2024_예비순환_민법/2024_minbeop_yebi_1_01.md",
      "pdfPath": "/Users/nhn/myftp/2026_USB/2025_법무사_합격/1. 민법/이혁준/[2024_예비순환]민법_모고_1_이혁준.pdf",
      "points": 0,
      "userCase": null,
      "_addedBy": "lawear-96c3-autorun-v2",
      "_year": "2024"
    },
    ...
    {
      "type": "library",
      "subject": "index",
      "subjectKor": "두문자",
      "case": "민법",
      "title": "민법 두문자/요건 라이브러리",
      "path": "두문자/민법.md"
    }
  ]
}
```

**필드 종류**:
- 일반 케이스: `id` / `subject` / `subjectKor` / `category` / `file` / `fileKor` / `case` / `title` / `path` / `pdfPath` / `points` / `userCase` / `_addedBy` / `_year`
- 라이브러리: `type: "library"` / `subject: "index"` 또는 `"pdf_raw"` / `subjectKor` / `case` / `title` / `path`

**현재 subject 종류** (`grep -c "type": "library"` = 4건):
- `minbeop` (민법)
- `minso` (민소)
- `index` (두문자 라이브러리)
- `pdf_raw` (PDF 원문 라이브러리)

**현재 subjectKor 종류** (실제 데이터):
- `민법`
- `민소`
- `두문자`

**즉, 현재 _file_index.json에는 형법/형소/부등/민사서류/부등서류 데이터가 0건.** 코드(merge.html line 707, 717-720)에는 SUBJECT_ORDER + stealthSubjectMap에 등록되어 있어 인프라는 준비됨.

**현재 category 종류**: `입문`, `예비`, `예비순환`, `1순환`, `2순환`, `3순환`. 모의고사는 CATEGORY_ORDER에는 있으나 데이터 0건.

---

## 2. 사이드패널 (실제 트리 구조)

### 2-1. 사이드바 컨테이너 (merge.html L586-612)

```html
<div id="sidebar">
  <div class="sidebar-header">
    <h2 id="sidebar-title">Internal Review Console <span class="sub">/ TTS Merge</span></h2>
    <div class="stats" id="stats"></div>
  </div>
  <div class="filters">
    <div class="filter-row">
      <button class="active" data-filter="all" id="filter-all">All Cases</button>
      <button data-filter="err" id="filter-err">High Error</button>
      <button data-filter="stale" id="filter-stale">Long Pending</button>
      <button data-filter="book" id="filter-book">Bookmarked</button>
    </div>
    <input type="text" class="search" id="search" placeholder="Search by ID or keyword…">
  </div>
  <div class="sidebar-actions">
    <button onclick="openDownloadModal()" class="primary" id="btn-download">Download</button>
    <button onclick="expandAll()" id="btn-expand">Expand all</button>
    <button onclick="collapseAll()" id="btn-collapse">Collapse all</button>
  </div>
  <div class="selected-count" id="selected-count">Selected: 0</div>
  <div class="case-list" id="fileTree">
    <div class="case-group-label" style="padding: 12px;">Loading…</div>
  </div>
  <div class="sidebar-actions">
    <a href="http://127.0.0.1:17896/" target="_blank" ...>🎯 Console (17896)</a>
  </div>
</div>
```

### 2-2. 트리 구조 (renderTree, merge.html L998-1263)

**3가지 트리 분기 동시 빌드** (코드 L1008-1010):
1. `tree5` — L0 year → L1 subject → L2 category → L3 file → L4 case (5단)
2. `libraryTree` — L1 subjectKor → L2 case (2단 평탄) — type:"library" 전용
3. `noMeta` — dir → filename (fallback, 풍부 메타 없을 때)

**렌더 순서** (L1066+):
1. 라이브러리 트리 먼저 (L1067-1094)
2. 풍부 메타 트리 (L1096-1204) — year 내림차순, 'unknown'은 맨 아래
3. fallback (L1206-1226)

### 2-3. 분기 판정 로직 (L1030-1052)

```javascript
if (meta && meta.type === 'library' && meta.subjectKor) {
  // 두문자 등 라이브러리: 평탄 트리 (L1 subjectKor → L2 case 항목 직접)
  libraryTree.get(sk).items.push(...);
} else if (meta && meta.subjectKor && meta.category && meta.fileKor) {
  // 5단 트리
  tree5.get(year).get(sk).categories.get(cat).files.get(fileCode).items.push(...);
} else {
  // fallback
  noMeta.get(dir).push(...);
}
```

### 2-4. 정렬 순서 (L699-711)

```javascript
const CATEGORY_ORDER = ['민법', '민소', '입문', '예비', '1순환', '2순환', '3순환', '모의고사', '모고'];
const SUBJECT_ORDER  = ['두문자', '민법', '민소법', '민소', '민사소송법', '형법', '형소법', '형소', '형사소송법', '부등법', '부등', '민사서류', '부등서류'];
```

**3과목 신규 추가는 이미 SUBJECT_ORDER에 등록되어 있음** — `부등법`, `부등`, `민사서류`, `부등서류`. 데이터만 _file_index.json에 추가하면 트리에 자동 표시됨.

### 2-5. 트리 상태 (localStorage)

- 키: `lawear_merge_tree_state` (L683)
- 노드별 펼침/접힘 boolean 저장
- `treeNodeKey(level, ...parts)` 함수로 키 생성:
  - L0: `y:2026`
  - L1: `s:2026|민법`
  - L1 라이브러리: `lib:두문자`
  - L2: `c:2026|민법|입문`
  - L3: `f:2026|민법|입문|미케01`
  - dir fallback: `d:두문자`

### 2-6. 필터 시스템 (L1287-1295)

- `all` (기본)
- `err` (High Error) — 데이터 없음 → 항상 빈 결과
- `stale` (Long Pending) — 데이터 없음 → 항상 빈 결과
- `book` (Bookmarked) — localStorage 기반 (`lawear_merge_bookmarks` 키, L1266)

### 2-7. Selection (체크박스 머지용)

- `selectedFiles` Set (L679)
- toggleSubjectSelection / toggleCategorySelection / toggleFileSelection / toggleDirSelection (L1311-1346)
- 디렉토리 체크박스 상태: indeterminate 지원 (L1348-1391)

---

## 3. 메인 영역 (실제 탭/버튼 — TTS 유무 확정)

### 3-1. 헤더 우측 토글 버튼 (L614-617)

```html
<div class="right-toggles">
  <button id="editor-toggle" onclick="toggleEditor()" title="편집 모드 토글 (E)">✏️</button>
  <button id="stealth-toggle" onclick="toggleStealth()" title="위장 모드 토글 (Z)">👀</button>
</div>
```

**버튼 2개만 존재**:
1. ✏️ **편집 모드 토글** — `toggleEditor()` 호출, 단축키 `E`
2. 👀 **위장 모드 토글** — `toggleStealth()` 호출, 단축키 `Z`

또한 사이드바 접기 토글 (L613): `‹` 버튼, 단축키 `B`.

### 3-2. 탭 구조 (L1546-1554, L756, L1487-1488)

**탭 키**: `['원본', '전체', 'Lv.1', 'Lv.4']` (코드 L1488, `tabKeys`)
**탭 라벨**:
- real 모드: `['원본', '전체', 'Lv.1', 'Lv.4']`
- stealth 모드: `['Source', 'All', 'V1', 'V4']`

**기본 활성 탭**: `'전체'` (인덱스 1, L1548 `i===1?' active':''`)

**탭 동작** (showSection, L1556-1593):
- `전체`: 3컬럼 비교 테이블 (원본 / Lv.1 / Lv.4) — L1573-1581
- `원본`: 원본 섹션만
- `Lv.1`: Lv.1 빠른복습 섹션만
- `Lv.4`: Lv.4 암기노트 섹션만

### 3-3. **TTS 탭 유무 확정: NO**

**메인 가정 정정 — TTS 탭은 존재하지 않음**.

- merge.html 전체에 `TTS 탭`, `tts-tab`, `TTS 다운로드` 등 별도 탭 UI 0건
- 4개 탭만 존재: `원본 / 전체 / Lv.1 / Lv.4` (L1488)
- TTS는 **다운로드 모달의 머지 옵션**으로만 존재 (L658-670)

### 3-4. 다운로드 모달 (L658-670)

```html
<div id="download-modal" class="modal-overlay" onclick="if(event.target===this) closeModal()">
  <div class="modal">
    <h3>머지 다운로드</h3>
    <p class="modal-info" id="modal-info">0개 파일 머지</p>
    <label><input type="radio" name="merge-level" value="원본"> 원본</label>
    <label><input type="radio" name="merge-level" value="Lv.1" checked> Lv.1 빠른복습</label>
    <label><input type="radio" name="merge-level" value="Lv.4"> Lv.4 암기노트</label>
    <div class="modal-buttons">
      <button onclick="closeModal()">취소</button>
      <button class="primary" onclick="doDownload()">확인</button>
    </div>
  </div>
</div>
```

**머지 옵션 3가지만**:
1. 원본
2. Lv.1 빠른복습 (기본값)
3. Lv.4 암기노트

**Lv.2/Lv.3 옵션 없음.** stripEmphasis 함수(L1633-1660)는 모든 [tag] 강조 제거 + (라이브러리 N-N) 출처 표기 제거.

### 3-5. 페이지 헤더 (L1520-1543, L1501-1505 라이브러리용)

일반 케이스 표시:
- `case-id-large`: `{file}-{case}` (예: `미케01-01`)
- `case-subject`: `{subjectKor} · {category} · {title} · {points}점 · User#{userCase}`
- `breadcrumb`: `{year} / {subjectKor} / {category} / {fileCode} / Case {case}` + 복사 버튼

라이브러리 표시 (L1494-1517):
- 별도 업로드 바 (`library-upload-bar`) 노출
- breadcrumb: `{year} / {subjectKor} / {case}`
- 탭 없이 마크다운 전체 렌더 + `makeLibraryCollapsible()` 적용

---

## 4. 편집 모드 (toggleEditor 흐름)

### 4-1. toggleEditor 함수 (L1823-1843)

```javascript
function toggleEditor() {
  if (!editMode && !currentFile) {
    alert('파일을 먼저 선택하세요');
    return;
  }
  if (editMode) {
    const ta = document.getElementById('editor-textarea');
    if (ta && ta.value && ta.value !== originalContent) {
      if (!confirm('저장하지 않은 변경 사항이 있습니다. 버리시겠습니까?')) return;
    }
  }
  editMode = !editMode;
  document.body.classList.toggle('editing', editMode);
  document.getElementById('editor-toggle').classList.toggle('active', editMode);
  if (editMode) {
    originalContent = fullContent || '';
    document.getElementById('editor-textarea').value = originalContent;
    updateEditorPreview();
    setSaveStatus('', '');
  }
}
```

**흐름**:
1. 파일 미선택 → alert + return
2. 편집 모드 진입 시 originalContent 저장 + textarea 초기화
3. 종료 시 변경 사항 있으면 confirm
4. `body.editing` 클래스로 CSS 분기 (L510-515: 편집 중에는 lv-tabs/mdContent/page-header 숨김, editor-wrap 표시)

### 4-2. 편집 UI 구조 (L620-655)

```html
<div id="editor-wrap">
  <div class="editor-toolbar">
    <span class="label">강조:</span>
    <!-- 강조 버튼 13종 (기존) + em 시스템 4 + 의미 5 + 여분 2 + 제거 1 = 25개 -->
    <button class="em-btn em-red" onclick="wrapEmphasis('red')">red</button>
    ... (red, blue, purple, violet, magenta, indigo, bold, u, blank, blank2)
    <button class="em-btn em-em1" onclick="wrapEmphasis('em1')">em1</button>
    ... (em1, em2, em3, em4)
    <button class="em-btn em-con" onclick="wrapEmphasis('con')">결론</button>
    ... (con, fact, case, bridge, key)
    <button class="em-btn em-free1" onclick="wrapEmphasis('free1')">free1</button>
    <button class="em-btn em-free2" onclick="wrapEmphasis('free2')">free2</button>
    <button class="em-btn em-clear" onclick="wrapEmphasis('clear')">제거</button>
    <button class="save-btn" id="save-btn" onclick="saveFile()">💾 저장</button>
    <span class="save-status" id="save-status"></span>
  </div>
  <div class="editor-split">
    <textarea id="editor-textarea" oninput="updateEditorPreview()" spellcheck="false"></textarea>
    <div class="editor-preview" id="editor-preview"></div>
  </div>
</div>
```

**좌측 textarea + 우측 미리보기 split**.

### 4-3. wrapEmphasis (L1851-1868)

```javascript
function wrapEmphasis(tag) {
  const ta = document.getElementById('editor-textarea');
  const start = ta.selectionStart;
  const end = ta.selectionEnd;
  if (start === end) { setSaveStatus('텍스트를 먼저 선택하세요', 'error'); return; }
  const selected = ta.value.substring(start, end);
  const allTags = ['em1', 'em2', 'em3', 'em4', 'con', 'fact', 'case', 'bridge', 'key', 'free1', 'free2', 'red', 'blue', 'purple', 'violet', 'magenta', 'indigo', 'bold', 'u', 'blank2', 'blank'];
  let cleaned = selected;
  for (const t of allTags) {
    const re = new RegExp(`\\[${t}\\]([\\s\\S]+?)\\[\\/${t}\\]`, 'g');
    cleaned = cleaned.replace(re, '$1');
  }
  const wrapped = tag === 'clear' ? cleaned : `[${tag}]${cleaned}[/${tag}]`;
  ta.setRangeText(wrapped, start, end, 'select');
  ta.focus();
  updateEditorPreview();
  setSaveStatus(tag === 'clear' ? '강조 제거' : `[${tag}] 적용`, 'success');
}
```

**기존 강조 제거 후 새 태그 wrap** (중첩 강조 방지). `clear`만 unwrap.

### 4-4. 키보드 단축키 (L1803-1817)

- `Ctrl+S` / `Cmd+S`: 편집 중일 때 saveFile() 호출
- `B`: 사이드바 토글
- `Z`: 위장 모드 토글
- `E`: 편집 모드 토글
- `Esc`: 모달 닫기 + 편집 모드 종료

---

## 5. 저장 메커니즘 (saveFile + API)

### 5-1. saveFile 함수 (L1870-1902)

```javascript
async function saveFile() {
  if (!editMode) return;
  if (!currentPath) { setSaveStatus('파일이 선택되지 않음', 'error'); return; }
  const ta = document.getElementById('editor-textarea');
  const newContent = ta.value;
  if (newContent === originalContent) {
    setSaveStatus('변경 사항 없음', 'success');
    return;
  }
  const saveBtn = document.getElementById('save-btn');
  saveBtn.disabled = true;
  setSaveStatus('저장 중...', '');
  try {
    const res = await fetch(`/api/save/${encodeURI(currentPath)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      body: newContent
    });
    if (res.ok) {
      const data = await res.json();
      setSaveStatus(`✓ 저장 완료 (${data.bytes} bytes)`, 'success');
      originalContent = newContent;
      fullContent = newContent;
    } else {
      const errText = await res.text().catch(() => '');
      setSaveStatus(`✗ 저장 실패 (${res.status}): ${errText.slice(0, 80)}`, 'error');
    }
  } catch (e) {
    setSaveStatus(`✗ 네트워크 오류: ${e.message}`, 'error');
  } finally {
    saveBtn.disabled = false;
  }
}
```

### 5-2. 백엔드 do_PUT (server.py L24-77)

```python
def do_PUT(self):
    # Staging endpoint
    if self.path.startswith('/api/staging/upload/'):
        self._handle_staging_upload()
        return

    if not self.path.startswith('/api/save/'):
        self.send_error(404, "Not Found")
        return

    rel_path = unquote(self.path[len('/api/save/'):])
    target = (ROOT / rel_path).resolve()

    # path traversal 방지
    try:
        target.relative_to(ROOT)
    except ValueError:
        self.send_error(403, "Path traversal blocked")
        return

    if target.suffix != '.md':
        self.send_error(403, "Only .md files allowed")
        return

    if not target.parent.exists():
        self.send_error(404, "Parent directory not found")
        return

    # 백업 .md.bak 생성 (이전 버전 보존)
    if target.exists():
        backup = target.with_suffix('.md.bak')
        backup.write_text(target.read_text(encoding='utf-8'), encoding='utf-8')

    target.write_text(content, encoding='utf-8')
    ...
```

**보안 가드**:
1. path traversal (`../`) 차단
2. .md 확장자만 허용
3. 부모 디렉토리 존재 필수
4. 자동 백업 (`.md.bak`)

**중요**: **존재하지 않는 디렉토리에는 저장 불가** — 신규 과목 폴더는 미리 생성해야 함.

### 5-3. fileMetadata / currentFile / currentPath (L674-678)

```javascript
let fileIndex = {};       // {dir: [filename, ...]} — 구 형식 호환용
let fileMetadata = {};    // path → 풍부 메타
let currentFile = null;
let currentPath = null;   // dir/filename
let fullContent = '';
```

### 5-4. loadFileByPath (L1419-1429)

```javascript
async function loadFileByPath(path) {
  const slash = path.indexOf('/');
  const dir = path.slice(0, slash);
  const filename = path.slice(slash + 1);
  document.querySelectorAll('.case-item').forEach(i => i.classList.toggle('active', i.dataset.path === path));
  const res = await fetch(path, { cache: 'no-store' });
  fullContent = await res.text();
  currentFile = filename;
  currentPath = path;
  renderContent();
}
```

**파일 fetch는 정적 GET** (server.py는 SimpleHTTPRequestHandler 상속이라 자동 처리).

---

## 6. API endpoint 목록 (server.py)

| Method | Path | 함수 | 동작 |
|--------|------|------|------|
| GET | `/*` | `SimpleHTTPRequestHandler` 기본 | 정적 파일 (html/json/md/css) |
| OPTIONS | `/*` | `do_OPTIONS` (L126-128) | CORS preflight (204) |
| PUT | `/api/save/{rel_path}` | `do_PUT` (L24-77) | .md 파일 저장 + 백업 |
| PUT | `/api/staging/upload/{subject}` | `_handle_staging_upload` (L79-117) | 라이브러리 staging 임시 저장 |

### 6-1. /api/save/{rel_path}

- Request: PUT, body = 새 .md 내용 (UTF-8)
- Response: `{"saved": "<rel_path>", "bytes": <N>}`
- 에러: 403 (path traversal / 비-.md), 404 (parent missing), 400 (empty/invalid)
- 부작용: `.md.bak` 백업 생성

### 6-2. /api/staging/upload/{subject}

- 허용 subject: `{'민법', '민소', '형법', '형소', '부등'}` (L20, **`민사서류`/`부등서류` 없음**)
- 저장 위치: `_staging/{subject}_{YYYYMMDD_HHMMSS}.md`
- Response: `{"staged": "_staging/...", "subject": "...", "bytes": N, "next_step": "AI에게 '... 두문자 업로드했어' ..."}`
- 뷰어 즉시 갱신 X (AI가 별도 분석/머지)

### 6-3. CORS 헤더 (L119-124)

```python
def end_headers(self):
    self.send_header('Access-Control-Allow-Origin', '*')
    self.send_header('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS')
    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    super().end_headers()
```

POST/DELETE는 없음. 신규 추가 시 do_POST 핸들러 추가 필요할 수 있음.

---

## 7. .md 저장 포맷 (실제 샘플 발췌)

### 7-1. 일반 케이스 (`2026_입문_민법/2026_minbeop_immun_미케01_01.md`, 118줄)

```markdown
# 2026_minbeop_immun_미케01_01

## 메타
- PDF: /Users/nhn/myftp/2026_USB/2026_박문각_피뎁/입문_민법/민법_입문_미케_01.pdf
- Case: 01
- 점수: 17점
- 주제: 비법인사단 · 대표권 제한
- 사용자 정답지 매핑: Case 21

## 원본 (17점)

### 사실관계
...

### 문제
A조합의 대표자인 甲은 乙회사와 ... 서술하시오?

### 결론
乙회사의 청구는 [blank]청구인용[/blank]된다.

### 답안

1. A조합의 법적 성격
...

## Lv.1 빠른복습

### 문제
...

### 목차
1. A조합의 법적 성격
2. ...

### 답안
...

## Lv.4 암기노트 (사용자 스타일)
[con]결론, 乙회사의 A조합에 대한 설계용역비 청구는 인용 될 수 있다.[/con]
1. [em2]비법인사단[/em2]이란, ...
```

**구조 요약**:
- frontmatter 없음 (메타데이터는 별도 `## 메타` 섹션)
- 섹션: `## 메타` → `## 원본 ({점수}점)` → `## Lv.1 빠른복습` → `## Lv.4 암기노트`
- 원본 내부: `### 사실관계` / `### 문제` / `### 결론` / `### 답안`
- Lv.1 내부: `### 문제` / `### 목차` / `### 답안`
- Lv.4 내부: 자유 (con/em1/em2/case/bridge 등 강조 태그)

### 7-2. 섹션 추출 함수 (L1595-1605)

```javascript
function extractSection(md, sectionName) {
  const lines = md.split('\n');
  let capture = false;
  let result = [];
  for (const line of lines) {
    if (line.startsWith('## ') && line.includes(sectionName)) { capture = true; continue; }
    if (capture && line.startsWith('## ')) break;
    if (capture) result.push(line);
  }
  return result.join('\n').trim();
}
```

**`includes()` 사용** → `## 원본 (17점)`, `## Lv.1 빠른복습` 모두 매칭됨. 새 섹션 추가 시 키워드만 고유하면 안전.

### 7-3. 라이브러리 (`두문자/민법.md`, 1414줄)

```markdown
# 민법 두문자 / 요건 라이브러리

> **용도**: lawear Lv.4 (암기노트) TTS 변환 시 풀이형 본문 + 두문자 인덱스 참조용.
> **본보기**: 미케03_27/28 — 사용자 P1 통과 스타일.
> **출처**: ...
> **인라인 태그 룰**:
> - `[blue]…[/blue]` 요건 헤더
> - `[purple]…[/purple]` 요건 본문 (강조)
> ...

---

## 1. 채권 일반 / 채무불이행

### 1-1. 채무불이행 손해배상 요건 (제390조)
- **두문자**: ...
- **풀이형**: ...
- **본문 템플릿**:
  ```
  [blue]제546조 이행불능 해제 요건[/blue]은, [purple]채[em1]무[/em1]발생 [em1]후[/em1] ...[/purple]일것이다.
  ```
- **참고 — ...**
- **출처 (검증 가능)**:
  - 사용자.md: ...
  - 강사 두문자 정본 PDF: ...
- **정정 이력**: 2026-05-21 lawear-4b59 K1 — ...

...

## 부록
(두문자 룩업 인덱스)
```

**구조 요약**:
- `# 제목` (H1)
- `> 메타` (blockquote 형식 — frontmatter 대안)
- `## N. 카테고리` (H2)
- `### N-M. 요건명` (H3, 각 항목)
- `- **두문자**:` / `- **풀이형**:` / `- **본문 템플릿**:` / `- **출처**:` (정형 bullet)
- `## 부록` 이후는 makeLibraryCollapsible에서 변환 제외 (L841)

### 7-4. makeLibraryCollapsible (L828-927)

**라이브러리 전용 ### → `<details>` 변환**:
- 각 `### N-M. 요건` → `<details class="lib-item">` + `<summary>`
- summary 내용: `{순번}. {두문자 본문 템플릿} [{H3번호} {H3제목}]`
- 본문 템플릿 추출 우선순위:
  1. `- **본문 템플릿**:` 다음 코드블록 (`<pre><code>` 또는 `<code>`)
  2. `- **두문자**:` 다음 inline 내용

---

## 8. localStorage 사용

| 키 | 값 | 위치 |
|----|------|------|
| `lawear_merge_tree_state` | `{nodeKey: bool}` (펼침/접힘) | L683 |
| `lawear_merge_bookmarks` | `string[]` (path 배열) | L1266 |
| `stealth` | `"true"` / `"false"` | L680, L953 |

`window.__bookmarks`로 메모리 캐시 (L1276-1283). 페이지 새로고침 시 다시 로드.

**서버 DB 없음** — 모든 사용자별 상태는 localStorage. 다른 컴퓨터에서 접속하면 트리 상태/북마크 초기화.

---

## 9. 두문자 라이브러리 통합 (type:"library" 분기)

### 9-1. 분기 트리거

`_file_index.json`에 `"type": "library"` 메타 추가 → 자동 분기 (코드 L1030, L1494).

### 9-2. 트리 렌더 (L1067-1094)

- L1 = subjectKor (예: "두문자")
- L2 = case 직접 (메타의 `case` 필드, 예: "민법", "민소", "민법 PDF 원문")
- year 구분 없음 (평탄)
- `style="padding-left: 22px;"` 들여쓰기 별도

### 9-3. 컨텐츠 렌더 (L1494-1518)

```javascript
if (meta && meta.type === 'library') {
  // 탭 없음 + 마크다운 전체 렌더 + makeLibraryCollapsible
  const headerHtml = `<div class="page-header">...</div>`;
  const uploadBarHtml = `<div class="library-upload-bar" ...>
    <input type="file" id="lib-upload-${uploadKey}" accept=".md,text/markdown" />
    <button type="button" class="lib-upload-btn" ...>새 두문자 업로드 (Staging — AI가 분석 후 머지)</button>
    <span class="lib-upload-hint">현재 파일: <code>${currentPath}</code>...</span>
    <span class="lib-upload-status" ...></span>
  </div>`;
  content.innerHTML = headerHtml + uploadBarHtml + '<div id="mdContent"></div>';
  if (editorWrap) content.appendChild(editorWrap);
  const target = document.getElementById('mdContent');
  target.innerHTML = makeLibraryCollapsible(renderMd(fullContent || ''));
  bindLibraryUpload();
  return;
}
```

**라이브러리 모드 특징**:
- 4탭 없이 전체 마크다운 렌더
- 별도 업로드 바 노출
- `makeLibraryCollapsible()` 적용 (각 ### → `<details>`)
- 편집 모드 (✏️) 동일하게 작동 (editorWrap 유지)

### 9-4. bindLibraryUpload (L1431-1481)

업로드 → PUT `/api/staging/upload/{subject}` → `_staging/{subject}_{ts}.md` 임시 저장. 뷰어 즉시 갱신 X. **AI 발화로 최종 머지**.

---

## 10. 3과목 신규 추가 — 추천 패턴 (안전 분석)

### 10-1. 옵션 비교

| 옵션 | 장점 | 단점 |
|------|------|------|
| **A. merge.html 분기 추가** | - 사이드패널 통합 (한 곳에서 모든 과목 탐색)<br>- 기존 모든 기능 (편집/위장/머지/북마크) 자동 적용<br>- _file_index.json만 추가하면 끝<br>- 라이브러리 분기 패턴 재사용 가능 | - 단일 파일 1914줄 → 더 비대해짐<br>- 입력 UI(탭 형식 문제/답안) 추가 시 코드 분기 증가 |
| **B. 별도 .html + route 분리** | - 책임 분리 (3과목 전용 input UI 자유 설계)<br>- merge.html 안정성 보장 (절대 깨지지 않음)<br>- 사용자 요구 "입력 UI = 탭 형식" 자유 구현 | - 사이드패널 중복 구현<br>- 사용자가 2개 URL 오가야 함<br>- 서버 라우팅 추가 (server.py 수정)<br>- localStorage 키 분리 필요 |
| **C. 하이브리드 (merge.html 분기 + 별도 input UI)** | - 뷰어는 merge.html 통합 (기존 깨지지 않음)<br>- 입력은 별도 .html (자유 설계)<br>- _file_index.json 공유 | - 입력→뷰어 전환 흐름 명확화 필요<br>- 중간 복잡도 |

### 10-2. **추천: 옵션 C (하이브리드)**

**근거**:

1. **사용자 룰 1번 (기존 17895 깨지면 안 됨) 최우선** — merge.html 직접 수정 최소화.
2. **사용자 룰 4번 (입력 UI = 탭 형식)** — 새 UI 자유 설계 가능.
3. **사용자 룰 5번 (뷰어 UI = 좌우 split 테이블 = 기존 17895처럼)** — merge.html `compare-table` (L1573-1581) 그대로 재사용 가능.
4. 라이브러리 분기 패턴(`type: "library"`)이 이미 존재 → **3과목용 `type: "subject_3"` 같은 분기 추가**로 안전하게 격리 가능.

**구체적 구조**:

```
tts-new/
├── server.py              (do_POST 추가 or do_PUT 확장 — 신규 폴더 생성 허용)
├── merge.html             (뷰어 — 3과목 데이터 자동 표시, 최소 분기 추가)
├── input.html             (NEW — 3과목 전용 입력 UI, 탭 형식 문제/답안)
├── 2026_사용자_부동산등기법/  (NEW — 데이터 폴더)
├── 2026_사용자_부동산등기서류/ (NEW)
├── 2026_사용자_민사서류/      (NEW)
└── _file_index.json       (3과목 entry 추가)
```

### 10-3. 사이드패널 통합 (merge.html 최소 수정)

**기존 SUBJECT_ORDER에 이미 등록됨** (L707):
```javascript
const SUBJECT_ORDER = ['두문자', '민법', '민소법', '민소', '민사소송법', '형법', '형소법', '형소', '형사소송법', '부등법', '부등', '민사서류', '부등서류'];
```

**stealthSubjectMap도 이미 등록됨** (L717-720):
```javascript
'부등법': 'RealEstate', '부등': 'RealEstate',
'민사서류': 'CivilDocs', '부등서류': 'REDocs',
```

**stealthCategoryMap 신규 추가 필요** (예: '사용자' 카테고리):
```javascript
'사용자': 'User',
```

**CATEGORY_ORDER에 '사용자' 추가 필요**:
```javascript
const CATEGORY_ORDER = ['민법', '민소', '입문', '예비', '1순환', '2순환', '3순환', '모의고사', '모고', '사용자'];
```

**3과목 _file_index.json 추가만으로 사이드패널 자동 표시됨** — 기존 5단 트리(L1035) 재사용.

### 10-4. .md 저장 포맷 (3과목용 제안)

기존 포맷 mirror하되, 사용자 룰 4번 "입력 UI 탭 형식 = 문제/답안"에 맞춰 섹션 단순화:

```markdown
# 2026_budeunglaw_user_01

## 메타
- 과목: 부동산등기법
- Case: 01
- 등록일: 2026-05-23
- 출처: 사용자 직접 입력

## 문제
{문제 텍스트}

## 답안
{답안 텍스트}

## 메모 (선택)
{사용자 추가 메모}
```

**섹션 키 `## 원본`/`## Lv.1`/`## Lv.4`와 충돌 없도록** `## 문제` / `## 답안`으로 분리. 뷰어 4탭 중 어느 것도 매칭되지 않으므로 **라이브러리 분기처럼 별도 분기 추가** 또는 **입력 모드 전용 분기 추가** 필요.

### 10-5. 신규 type 분기 추가 패턴 (라이브러리 mirror)

`_file_index.json`:
```json
{
  "id": "2026_budeunglaw_user_01",
  "type": "user_input",
  "subject": "budeunglaw",
  "subjectKor": "부등법",
  "category": "사용자",
  "file": "user01",
  "fileKor": "2026_부등법_사용자_user01",
  "case": "01",
  "title": "{사용자 입력 제목}",
  "path": "2026_사용자_부동산등기법/2026_budeunglaw_user_01.md",
  "points": 0,
  "_year": "2026",
  "_addedBy": "lawear-7ad6-input-mode"
}
```

**`type: "user_input"` 분기 추가** (merge.html L1030 if 분기에 추가):
```javascript
} else if (meta && meta.type === 'user_input') {
  // 5단 트리에 합류 OR 별도 트리 — 사용자 결정 사항
}
```

**옵션 1: 기존 5단 트리에 통합** (간단, 추천) — 데이터에 category/file/fileKor가 있으면 자동.

**옵션 2: 별도 입력 트리 (input mode 전용)** — 사용자 룰 2번 "3과목 전용 입력+뷰어 모드 신규 추가" 명시 → 별도 트리가 적절할 수도.

### 10-6. 뷰어 분기 (renderContent L1483+)

`type: "user_input"` 케이스 추가:
```javascript
if (meta && meta.type === 'user_input') {
  // 좌우 split: 좌 문제 / 우 답안
  // 또는: 좌우 split + 메모 footer
  // 사용자 룰 5번 (좌우 split 테이블)에 맞춰 compare-table 패턴 재사용
}
```

**compare-table 재사용 예**:
```html
<table class="compare-table">
  <thead><tr><th>문제</th><th>답안</th></tr></thead>
  <tbody><tr>
    <td>${renderMd(extractSection(md, '문제'))}</td>
    <td>${renderMd(extractSection(md, '답안'))}</td>
  </tr></tbody>
</table>
```

기존 3컬럼 compare-table CSS (L316-319) → 2컬럼 변종 추가:
```css
.compare-table.cols-2 th { width: 50%; }
```

### 10-7. server.py 확장 (do_PUT은 신규 폴더 생성 거부 — L47-49)

```python
if not target.parent.exists():
    self.send_error(404, "Parent directory not found")
    return
```

**신규 .md 생성 시 폴더가 없으면 404**. 3과목 폴더는 사전 mkdir 필요 (사용자가 한 번 만들거나, server.py에 폴더 자동 생성 추가).

**옵션 A**: 사전 mkdir (안전, 변경 최소):
```bash
mkdir -p tts-new/2026_사용자_부동산등기법 tts-new/2026_사용자_부동산등기서류 tts-new/2026_사용자_민사서류
```

**옵션 B**: server.py에 do_POST 추가 (신규 .md 생성 전용, 폴더도 자동 생성):
```python
def do_POST(self):
    if self.path.startswith('/api/create/'):
        # 폴더 자동 생성 (ALLOWED_NEW_DIRS 화이트리스트)
        ALLOWED_NEW_DIRS = {'2026_사용자_부동산등기법', '2026_사용자_부동산등기서류', '2026_사용자_민사서류'}
        ...
```

**옵션 A 추천** — 최소 변경, 안전.

### 10-8. _file_index.json 자동 갱신

현재 _file_index.json은 수동 관리 (174 KB). 입력 모드에서 신규 케이스 추가 시 갱신 필요:

**옵션 A**: server.py에 `/api/index/append` 엔드포인트 추가 — 새 entry append + 저장
**옵션 B**: 별도 스크립트 (`scripts/rebuild_index.py`) — 사용자가 수동 실행
**옵션 C**: 클라이언트에서 fetch + 수정 + PUT — 동시성 문제 (락 없음)

**옵션 A 추천** — 입력 UI에서 직접 호출, 사용자 흐름 매끄러움.

---

## 11. 위험 요소 + 회피 방법

### 11-1. 위험: launchd가 메인 레포 server.py 실행

- 위험: 워크트리에서 server.py 수정 → launchd 변경 미반영 → 테스트 시 옛 코드 실행
- 회피: server.py 변경 시 launchd 재시작 (`launchctl unload/load ~/Library/LaunchAgents/com.lawear.ttsmerger.plist`)
- **또는** 워크트리 server.py를 임시로 별도 포트(예: 17899)에서 실행 → 테스트 후 메인 머지

### 11-2. 위험: SUBJECT_ORDER 신규 추가 시 정렬 깨짐

- 위험: 새 subject를 SUBJECT_ORDER에 안 넣으면 999 rank로 맨 아래
- 회피: SUBJECT_ORDER에 이미 부등법/부등/민사서류/부등서류 등록됨 (L707) — 수정 불필요
- **검증**: 신규 데이터 추가 후 사이드바에서 위치 확인

### 11-3. 위험: extractSection includes() 매칭 충돌

- 위험: `## 문제` 키워드가 `## 원본 (17점)` 안의 `### 문제`와 충돌 가능 → **충돌 없음** (extractSection은 `## ` 시작 라인만 매칭)
- 단, `## 문제` 섹션 추가 시 기존 케이스 (`### 문제`)와 헷갈리지 않게 **type 분기로 별도 처리** 필수

### 11-4. 위험: localStorage 키 충돌

- 키 3개 모두 prefix 없음 (`lawear_merge_*`)
- 회피: 신규 키 도입 시 `lawear_input_*` prefix 권장

### 11-5. 위험: stealth 모드 라벨 누락

- 위험: stealthSubjectMap에 신규 subject 없으면 한글 노출 (L759 fallback)
- 회피: 부등법/부등/민사서류/부등서류는 이미 등록됨 (L717-720) — 수정 불필요

### 11-6. 위험: _file_index.json 손상

- 위험: 174 KB JSON 수동 편집 → 깨지면 init() 실패 (L962-985 모든 데이터 로드 차단)
- 회피: 백업 후 편집, JSON validator 필수. server.py에 backup 메커니즘 추가 권장

### 11-7. 위험: 편집 모드 진입 후 다른 파일 클릭

- 현재 코드: `loadFileByPath` (L1419)는 편집 모드 체크 없음 → 변경 사항 손실 가능
- 회피: 편집 모드 중 클릭 시 confirm 추가 권장 (영향 분석 결과 기존 기능)

### 11-8. 위험: 머지 다운로드 stripEmphasis 신규 태그 누락

- stripEmphasis (L1633-1660)는 현재 [em1-4]/[con/fact/case/bridge/key]/[free1-2] 등 모두 포함
- 새 태그 도입 시 stripEmphasis에 추가 필수
- 회피: 신규 태그 도입 시 wrapEmphasis의 allTags(L1857) + stripEmphasis 동시 수정

### 11-9. 위험: 라이브러리 staging ALLOWED_STAGING_SUBJECTS 제한

- 현재 (server.py L20): `{'민법', '민소', '형법', '형소', '부등'}`
- 민사서류/부등서류 staging은 차단됨
- 회피: 3과목용 staging 필요 시 ALLOWED_STAGING_SUBJECTS 확장

### 11-10. 위험: 사용자 룰 3 무시 (TTS 탭 가정)

- 메인 가정 "TTS 탭 있음"은 **오류** — 실제 4탭은 `원본/전체/Lv.1/Lv.4`
- 회피: TTS는 다운로드 모달 옵션이지 탭이 아님. dev-spec에 반드시 정정 명시

---

## 12. dev-spec 입력 자료 (다음 Phase 2에 넘길 핵심 정보)

### 12-1. 영향 범위 (코드 라인 단위)

| 변경 항목 | 파일 | 라인 | 변경 유형 |
|----------|------|------|----------|
| 신규 type 분기 (트리) | merge.html | L1030-1052 (renderTree 조건문) | 추가 |
| 신규 type 분기 (콘텐츠) | merge.html | L1483+ (renderContent) | 추가 |
| CATEGORY_ORDER 갱신 | merge.html | L700 | 추가 ('사용자') |
| stealthCategoryMap 갱신 | merge.html | L721-726 | 추가 |
| compare-table 2컬럼 변종 | merge.html | L316-319 (CSS) | 추가 |
| 신규 입력 .html | tts-new/input.html | 신규 파일 | NEW |
| _file_index.json 갱신 API | server.py | (do_POST 신규 or 별도 스크립트) | 추가 |
| 신규 데이터 폴더 | tts-new/2026_사용자_* | 신규 디렉토리 | NEW |
| ALLOWED_STAGING_SUBJECTS (선택) | server.py | L20 | 확장 (필요 시) |

### 12-2. 기존 변경 금지 (절대 깨지면 안 됨)

- 기존 4탭 구조 (`원본/전체/Lv.1/Lv.4`) — 사용자 룰 1
- 기존 라이브러리 분기 (`type: "library"`)
- 기존 5단 트리 렌더 (year > subject > category > file > case)
- 편집 모드 (toggleEditor, wrapEmphasis, saveFile)
- 위장 모드 (stealthMode + applyStealthUI)
- 다운로드 머지 (formatOriginalMerge/formatLv1Merge/formatLv4Merge)
- localStorage 키 (`lawear_merge_*` 3종)
- launchd 등록 (포트 17895)

### 12-3. 기존 패턴 재사용 권장

- **라이브러리 분기 패턴** (`type: "library"`) → 3과목용 `type: "user_input"` 동일 패턴
- **compare-table** (L316-319) → 2컬럼 변종으로 좌우 split (사용자 룰 5)
- **편집 모드 인프라** (editor-wrap, wrapEmphasis) → 입력 모드에서 답안 강조 시 재사용
- **page-header + breadcrumb** (L321-358) → 입력/뷰어 공통
- **다크 테마 CSS 변수** (L11-29) → 신규 input.html에 그대로 사용

### 12-4. 핵심 결정 사항 (사용자 컨펌 필요)

1. **별도 입력 .html 분리 vs merge.html 분기 추가** → 추천 옵션 C (하이브리드: 뷰어는 merge.html, 입력은 별도 input.html)
2. **3과목 _file_index.json type 분류** → `type: "user_input"` 신규 (라이브러리 패턴 mirror)
3. **데이터 폴더명** → `2026_사용자_{과목}` (기존 `2026_입문_민법` 명명 규칙 mirror, 카테고리 prefix '사용자')
4. **_file_index.json 자동 갱신 방식** → server.py에 do_POST `/api/create/` 엔드포인트 추가 추천
5. **백업 정책** → 현재 .md.bak 1단계만 — 사용자 룰 "DB 백업 필수"와 연계해 추가 백업 메커니즘 고려
6. **편집 모드 진입 시 확인** → 사용자 룰 (사용자 자율) — 현재 confirm 없음

### 12-5. 검증 (사용자 룰 1 보장)

**dev-qa 게이트 필수 시나리오**:
- [ ] 기존 4탭 (원본/전체/Lv.1/Lv.4) 정상 작동
- [ ] 라이브러리 (두문자/민법.md, 민소.md) 정상 렌더 + 업로드 바 표시
- [ ] 편집 모드 진입/종료 + 저장/백업 정상
- [ ] 위장 모드 토글 정상
- [ ] 다운로드 머지 (원본/Lv.1/Lv.4) 정상
- [ ] 5단 트리 (year > subject > category > file > case) 정상
- [ ] localStorage 펼침/접힘/북마크 보존
- [ ] 신규 3과목 사이드패널 추가 후에도 기존 트리 위치 깨지지 않음 (정렬 검증)

### 12-6. 데이터 마이그레이션 영향

- 현재 _file_index.json: 174 KB, ~290 entry (`grep -c "id":` 추정, 확인 필요)
- 3과목 추가 시 entry 늘어남 → init() 로드 시간 영향 미미 (174 KB는 충분히 빠름)
- 동시성: 사용자 1명 작업이라 락 없어도 안전

### 12-7. 단계별 작업 순서 (Phase 2~ 권장)

1. **Phase 2 (dev-design)**: 3과목 폴더명/메타 스키마 확정, server.py do_POST 설계, input.html UI 와이어프레임
2. **Phase 3 (dev-impl-plan)**: 파일별 패치 계획 (merge.html 분기 추가 위치, input.html 골격), 테스트 케이스 목록
3. **Phase 4 (구현)**: 워크트리에서 작업 → 메인 머지 → launchd 재시작
4. **Phase 5 (dev-qa)**: 12-5 시나리오 전수 검증 + 사용자 수동 검증

---

## 부록: 핵심 코드 라인 참조표

| 항목 | merge.html 라인 |
|------|----------------|
| 색상/CSS 변수 | L11-29 |
| 사이드바 컨테이너 | L586-612 |
| 우측 토글 버튼 (편집/위장) | L614-617 |
| 편집 UI (editor-wrap) | L620-655 |
| 다운로드 모달 | L658-670 |
| 상태 변수 (fileIndex, fileMetadata, etc) | L674-697 |
| CATEGORY_ORDER / SUBJECT_ORDER | L700, L707 |
| stealthSubjectMap | L714-720 |
| stealthCategoryMap | L721-726 |
| stealthDirMap | L728-741 |
| stealthUI | L743-757 |
| renderMd (마크다운 + 강조) | L793-822 |
| makeLibraryCollapsible | L828-927 |
| init() (데이터 로드) | L961-985 |
| renderTree (트리 빌드) | L998-1263 |
| 분기 판정 (library/5단/fallback) | L1030-1052 |
| 라이브러리 트리 렌더 | L1067-1094 |
| 5단 트리 렌더 | L1096-1204 |
| fallback 트리 | L1206-1226 |
| 북마크 (localStorage) | L1266-1285 |
| 필터 (all/err/stale/book) | L1287-1295 |
| loadFileByPath | L1419-1429 |
| bindLibraryUpload | L1431-1481 |
| renderContent (메인) | L1483-1554 |
| 라이브러리 콘텐츠 분기 | L1494-1518 |
| 일반 케이스 헤더 + 4탭 | L1520-1554 |
| showSection (탭 동작) | L1556-1593 |
| extractSection | L1595-1605 |
| stripEmphasis (다운로드용) | L1633-1660 |
| formatOriginalMerge / formatLv1Merge / formatLv4Merge | L1675-1714 |
| openDownloadModal / doDownload | L1716-1749 |
| 키보드 단축키 (B/Z/E/Esc/Ctrl+S) | L1803-1817 |
| toggleEditor | L1823-1843 |
| wrapEmphasis | L1851-1868 |
| saveFile | L1870-1902 |

| 항목 | server.py 라인 |
|------|---------------|
| 포트 / BIND / ROOT 상수 | L16-18 |
| ALLOWED_STAGING_SUBJECTS | L20 |
| do_PUT (저장 + traversal 가드 + 백업) | L24-77 |
| _handle_staging_upload | L79-117 |
| CORS end_headers | L119-124 |
| do_OPTIONS | L126-128 |

---

## 변경 이력

| 일자 | 세션 | 내용 |
|------|------|------|
| 2026-05-23 | lawear-7ad6 | Phase 1 — 17895 뷰어 완전 분석 작성 (Opus + ultrathink) |
