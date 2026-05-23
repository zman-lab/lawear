# dev-spec Phase 2-3: 구현 계획 (작업 A — 3과목 입력+뷰어)

> **세션**: lawear-7ad6 / **모델**: Opus + ultrathink
> **베이스**: Phase 2-1 impact + Phase 2-2 design (5건 결정)

---

## 1. 구현 순서 (단계별 + 추정, 총 ~7h)

| 단계 | 작업 | 추정 | 산출물 |
|------|------|------|--------|
| S1 | server.py `do_POST` (~80줄) | 1.5h | 메서드 + `ALLOWED_NEW_DIRS` |
| S2 | `ALLOWED_STAGING_SUBJECTS` 확장 (선택) | 0.2h | L20 + 3과목 |
| S3 | `_append_index_entry` 헬퍼 | 0.8h | flock + atomic + `.bak` |
| S4 | merge.html `type:"user_input"` 분기 | 1.0h | L1030-52 + L1483-518 + `.cols-2` CSS |
| S5 | input.html 신규 (~800줄) | 2.0h | 탭+textarea+25태그+미리보기+저장 |
| S6 | 3과목 데이터 폴더 + .gitkeep | 0.1h | mkdir |
| S7 | 샘플 .md 3개 (각 1건) | 0.4h | dev-qa 시드 |
| S8 | pytest+curl+Playwright 회귀 | 1.0h | 통합 |

**의존**: S1 → S3 → S5 (입력→POST→S4 뷰어). S6/S7 병렬 OK. **임시 포트 17899** (R6, 메인 17895 launchd 충돌 회피).

---

## 2. pytest TC (TC1~TC20, `tests/test_server_create.py`)

### 정상 (TC1~TC4)
- **TC1**: 부등법 .md POST 200 + 파일 + bytes
- **TC2**: 부등서류 .md 200
- **TC3**: 민사서류 .md 200
- **TC4**: parent 부재 시 자동 mkdir (폴더 사전 삭제 후 POST)

### 음성 R2 (TC5~TC10)
- **TC5**: `../../etc/passwd` traversal → 403
- **TC6**: 화이트리스트 밖 `random_dir/x.md` → 403
- **TC7**: 비-.md `.txt` → 403
- **TC8**: 충돌 (같은 파일 2회 POST) → 1차 200, 2차 409
- **TC9**: `## 메타` 누락 → 400
- **TC10**: 빈 body → 400

### 엣지 (TC11~TC15)
- **TC11**: 한글 폴더/파일명 URL 인코딩 처리
- **TC12**: 100KB+ body → bytes 정확
- **TC13**: 특수문자(`<>&"'` + 한자 + 이모지) raw 보존
- **TC14**: 동시 POST 2건 (threading) → flock+atomic, 2 entry append + JSON valid
- **TC15**: _file_index.json 손상 주입 → `.bak` 복구 후 신규 append

### 인덱스 (TC16~TC20)
- **TC16**: `_append_index_entry` 정상 append, total +1
- **TC17**: 중복 id 갱신 X (기존 보존)
- **TC18**: `.bak` 생성 + atomic rename 검증
- **TC19**: JSON validate 실패 시 `.bak` 복원 + 500
- **TC20**: 인덱스 fields (id/subject/category/path/type:"user_input") 일치

---

## 3. curl 시나리오 (M=8)

```bash
PORT=17899; BASE="http://127.0.0.1:${PORT}"

# C1: 정상 (200)
curl -i -X POST "$BASE/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_01.md" \
  -H "Content-Type: text/plain; charset=utf-8" --data-binary @/tmp/sample.md
# expect: 200 + {"created","bytes","index_updated":true,"id"}

# C2: traversal (403)
curl -i -X POST "$BASE/api/create/../../etc/passwd" --data-binary "x"

# C3: 화이트리스트 밖 (403)
curl -i -X POST "$BASE/api/create/random_dir/x.md" --data-binary "x"

# C4: 비-.md (403)
curl -i -X POST "$BASE/api/create/2026_사용자_부동산등기법/x.txt" --data-binary "x"

# C5: 충돌 (409)
curl -i -X POST "$BASE/api/create/2026_사용자_부동산등기법/2026_budeunglaw_user_01.md" --data-binary "..."

# C6: 메타 누락 (400)
curl -i -X POST "$BASE/api/create/2026_사용자_부동산등기법/x_99.md" --data-binary "# no meta"

# C7: 정적 서빙 — input.html GET
curl -i "$BASE/input.html?subject=budeunglaw"

# C8: PUT /api/save/ 회귀 — 기존 17895 .md 갱신 정상
curl -i -X PUT "$BASE/api/save/2026_예비_민법/2026_minbeop_yebi_1_01.md" --data-binary @/tmp/exist.md
```

---

## 4. Playwright 시나리오 (K=12, 회귀 포함)

### 신규 (P1~P8)
- **P1**: 사이드패널 3과목 표시 (인덱스 append 후)
- **P2**: 사이드바 하단 `[+ 새 입력]` → input.html 진입
- **P3**: 탭 전환 (문제→답안→메모) state 보존 + 미리보기 동기
- **P4**: 25종 태그 버튼 클릭 → textarea 마커 삽입 + 미리보기 즉시
- **P5**: 실시간 미리보기 (oninput → renderMd 결과 일치)
- **P6**: 저장 POST 성공 → `merge.html?path=...` 자동 리다이렉트
- **P7**: 뷰어 `compare-table.cols-2` 좌우 split + 메모 footer
- **P8**: `[✏️ 다시 편집]` → `input.html?path=...` 편집 진입

### 회귀 (P9~P12, 룰 1 보장)
- **P9**: 기존 4탭 정상 (`전체` 3컬럼 compare-table 포함)
- **P10**: 라이브러리 분기 정상 (makeLibraryCollapsible + 업로드 바)
- **P11**: 5단 트리 + localStorage `lawear_merge_tree_state` 보존
- **P12**: 편집 모드 + 25종 태그 + `.md.bak`, 위장 모드 'User' 라벨, 다운로드 머지 user_input 제외

---

## 5. 사이드 이펙트

| ID | 영역 | 영향 | 차단 |
|----|------|------|------|
| SE1 | merge.html +~50줄 | 4탭/라이브러리 회귀 | 분기 라이브러리 다음 배치 + P9~P12 |
| SE2 | server.py +~80줄 | FS 쓰기 권한 확대 | 화이트리스트 + `relative_to(ROOT)` |
| SE3 | _file_index.json 174KB 동시 쓰기 | init() 차단 위험 | flock + atomic + `.bak` + validate |
| SE4 | launchd 17895 미반영 | 워크트리 변경 안 보임 | 임시 17899 + 메인 머지 후 launchctl reload |
| SE5 | SUBJECT_ORDER 정렬 | 사이드바 깨짐 | 기존 위치 활용 + L700 `'사용자'` append |
| SE6 | downloadMerge stripEmphasis | user_input 강조 노출 | 머지 분기에서 user_input 제외 |

---

## 6. 롤백 (워크트리 remove로 복구)

**원칙**: 메인 레포 무손상. 워크트리에만 변경.

1. 데이터 보존 (R9): `cp -r tts-new/2026_사용자_* /Users/nhn/zman-lab/lawear/tts-new/` (사용자 입력 손실 방지)
2. `git -C /Users/nhn/zman-lab/lawear worktree remove lawear-lawear-7ad6-input-mode-and-backup`
3. 메인 무변경 확인: `git -C /Users/nhn/zman-lab/lawear diff main`
4. launchd 무변경 — 메인 17895 재시작 불필요

**부분 롤백**: `git reset --hard HEAD~N` (S1 이후 커밋 수).

**복구 보장**: input.html / 2026_사용자_* 신규 → 삭제로 무손상. server.py/merge.html은 워크트리 내 → 머지 전이면 remove로 즉시 복구.

---

## 7. dev-team Phase 3 첫 작업 (S1)

`tts-new/server.py` `do_POST` 신규 ~80줄:

1. 워크트리 임시 포트 실행 (R6):
   ```bash
   cd /Users/nhn/zman-lab/lawear-lawear-7ad6-input-mode-and-backup/docs/tts-new
   PORT=17899 python3 server.py &
   ```
2. L20 부근에 `ALLOWED_NEW_DIRS = frozenset({'2026_사용자_부동산등기법', '2026_사용자_부동산등기서류', '2026_사용자_민사서류'})`
3. `do_POST(self)` 추가 — design §3 순서 8단계:
   - `relative_to(ROOT)` traversal 차단
   - `target.parent.name in ALLOWED_NEW_DIRS` 화이트리스트
   - `.md` 확장자 강제
   - `target.parent.mkdir(parents=True, exist_ok=True)`
   - `target.exists()` → 409
   - body UTF-8 + `## 메타` 정규식 최소 검증
   - `target.write_text(body)`
   - `_append_index_entry(...)` 호출 (S3 미완 시 임시 `index_updated:false`)
   - 200 JSON `{"created","bytes","index_updated","id"}`
4. curl C1~C8 즉시 검증
5. pytest TC1~TC10 실행 (S3 완료 후 TC11~TC20)

**선행 체크**: 워크트리 상태 / `lsof -i :17899` 충돌 X / `pip install pytest requests`.

---

| 일자 | 세션 | 내용 |
|------|------|------|
| 2026-05-23 | lawear-7ad6 | Phase 2-3 impl-plan 작업 A (Opus + ultrathink) |
