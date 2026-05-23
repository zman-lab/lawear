# dev-spec Phase 2-1: 영향범위 (lawear-7ad6)

> **세션**: lawear-7ad6 / **모델**: Opus + ultrathink
> **작업 A**: 3과목(부등법/부등서류/민사서류) 입력+뷰어 모드
> **작업 B**: 17896 채점 DB 백업 자동화 (rolling 2-slot)
> **근거**: `docs/lawear-7ad6_input_mode_3subjects/17895_analysis.md` (Phase 1, 1088줄)

---

## 1. 작업 A — 3과목 입력+뷰어 모드

### 1.1 변경 파일 (기존)

| 파일 | 변경 | 라인 | 위험 |
|------|------|------|------|
| `tts-new/merge.html` | `renderTree` 분기에 `type:"user_input"` 추가 | L1030-1052 | R1 |
| `tts-new/merge.html` | `renderContent`에 `type:"user_input"` 분기 (좌우 split) | L1483-1518 | R1 |
| `tts-new/merge.html` | `CATEGORY_ORDER`에 `'사용자'` 추가 | L700 | 낮음 |
| `tts-new/merge.html` | `stealthCategoryMap`에 `'사용자':'User'` | L721-726 | 낮음 |
| `tts-new/merge.html` | `.compare-table.cols-2` CSS (2컬럼 50/50) | L316-319 | 낮음 |
| `tts-new/server.py` | `do_POST` 신규 메서드 (~80줄, /api/create/) | L24 위 | R2 |
| `tts-new/server.py` | `ALLOWED_STAGING_SUBJECTS` 3과목 추가 (선택) | L20 | 낮음 |
| `tts-new/_file_index.json` | 3과목 entry 추가 (초기 0건, 자동 append) | append | R3 |

**기존 무손상 영역 (룰 1)**: 4탭(`원본/전체/Lv.1/Lv.4`), `type:"library"` 분기, 5단 트리, 편집/위장 모드, 다운로드 머지, localStorage 3종, launchd 플리스트.

### 1.2 추가 파일 (신규)

| 파일 | 용도 |
|------|------|
| `tts-new/input.html` | 3과목 입력 UI (탭 형식 문제/답안 + 25종 태그 + 미리보기), ~800줄 |
| `tts-new/2026_사용자_부동산등기법/` | 데이터 폴더 (사전 mkdir) |
| `tts-new/2026_사용자_부동산등기서류/` | 데이터 폴더 |
| `tts-new/2026_사용자_민사서류/` | 데이터 폴더 |
| `2026_*_user_NN.md` | 입력 시 자동 생성 |

**.md 포맷** (17895_analysis §10-4):
```markdown
# 2026_budeunglaw_user_01
## 메타
- 과목: 부동산등기법
- Case: 01 / 등록일: 2026-05-23 / 출처: 사용자 직접 입력
## 문제
{...}
## 답안
{...}
## 메모 (선택)
{...}
```

`## 문제`/`## 답안`은 기존 `## 원본/Lv.1/Lv.4`와 수평 분리. `extractSection`(L1595)이 `## ` 시작만 매칭하므로 충돌 없음. **type 분기로 강제 격리**.

### 1.3 추가 API

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/create/{rel_path}` | raw .md (UTF-8) | `{"created":"<path>","bytes":N,"index_updated":true}` |
| PUT | `/api/index/append` (선택) | `{"entry":{id,subject,...}}` | `{"appended":true,"total":N}` |

**기존 API 무변경**: `GET /*`(정적), `PUT /api/save/`(L24-77), `PUT /api/staging/upload/`(L79-117), `OPTIONS /*`(L126).

**`do_POST` 가드**:
- `target.relative_to(ROOT)` (do_PUT L42-46 mirror)
- `ALLOWED_NEW_DIRS = {'2026_사용자_부동산등기법','2026_사용자_부동산등기서류','2026_사용자_민사서류'}` 화이트리스트
- `.md` 확장자 강제
- parent 디렉토리 자동 mkdir (화이트리스트 내만)

### 1.4 기존 깨질 위험 + 회피

| ID | 위험 | 회피 |
|----|------|------|
| R1 | 분기 추가로 기존 5단 트리/4탭 회귀 | `else if (type==='user_input')`를 **library 분기 다음에 배치**. 17895_analysis §12-5 시나리오 8개 Playwright 회귀 |
| R2 | `do_POST` traversal / 임의 폴더 생성 | (1) `relative_to(ROOT)` (2) `ALLOWED_NEW_DIRS` (3) `.md` 강제 (4) parent 자동 mkdir 화이트리스트 내 (5) curl `../` 음성 케이스 검증 |
| R3 | _file_index.json (174KB) 동시 쓰기 손상 → init() 차단 | (1) `fcntl.flock` (2) 임시파일 → atomic rename (3) `.bak` 백업 (do_PUT L60-62 패턴) (4) JSON validate 후 save |
| R6 | launchd가 메인 server.py 실행 → 워크트리 미반영 | 임시 포트 17899 별도 실행 or 메인 머지 후 `launchctl unload/load com.lawear.ttsmerger.plist` |
| R7 | `loadFileByPath`(L1419) 편집 모드 체크 없음 → 입력 중 다른 파일 클릭 시 손실 | confirm 가드 (`editMode && ta.value!==originalContent`) — 입력 모드 동일 적용 |

---

## 2. 작업 B — 17896 백업 자동화

### 2.1 변경 파일 + 추가 파일

| 파일 | 변경 |
|------|------|
| `.claude/commands/dev-le-17896-grade.md` | 채점 마지막 단계(PUT /grade 성공 후) 백업 후처리 박음 |
| `docs/tts-exam/backups/snapshots/` (신규) | 백업 저장 (`exam_YYYYMMDD_HHMM.sql.gz`) |
| `docs/tts-exam/backups/.gitignore` (선택) | 백업 파일 git 추적 차단 |

**후처리 명령** (메모리 `feedback_grade_backup_2slot_policy`):
```bash
BACKUP_DIR="/Users/nhn/zman-lab/lawear/docs/tts-exam/backups/snapshots"
DB_PATH="/Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db"
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M)
sqlite3 "$DB_PATH" .dump | gzip > "$BACKUP_DIR/exam_$TS.sql.gz"
ls -1t "$BACKUP_DIR"/exam_*.sql.gz | tail -n +3 | xargs -r rm -f
```

### 2.2 백업 디렉토리 구조

```
docs/tts-exam/
├── exam.db                              (원본, 무변경)
└── backups/snapshots/
    ├── exam_20260523_1430.sql.gz        (최신)
    └── exam_20260523_1115.sql.gz        (직전)
    # rolling 2-slot — 새 백업 시 가장 오래된 1개 삭제
```

**복구**: `gunzip -c <path>.sql.gz | sqlite3 docs/tts-exam/exam.db`

### 2.3 위험 + 회피

| ID | 위험 | 회피 |
|----|------|------|
| R4 | `rm` 패턴 사고 — 무관 파일 삭제 | (1) 절대경로 `$BACKUP_DIR` 변수 (2) glob `exam_*.sql.gz` 고정 (3) `xargs -r` 빈 입력 보호 (4) `tail -n +3` 3개 이상일 때만 동작 |
| R5 | 채점 실패 시 백업 누락 → 신뢰 깨짐 | **PUT /grade 성공 분기 후 무조건 실행**. 백업 자체 실패는 보고만 (채점 결과 보존) |
| R8 | 디스크 누적 | rolling 2-slot — 항상 2개 고정. SQLite 압축 시 수 MB |
| R9 | 워크트리 remove 시 백업 손실 (gitignored) | 메모리 `feedback_worktree_db_backup` 정책 — remove 전 메인 복사 강제 |

---

## 3. 통합 위험 매트릭스 (총 9건)

| ID | 영역 | 회피 핵심 / 검증 |
|----|------|------|
| R1 | merge.html 회귀 | 분기 순서(library 다음) / Playwright §12-5 8개 |
| R2 | do_POST traversal | 화이트리스트+relative_to+.md / curl `../` 음성 |
| R3 | _file_index.json 손상 | flock+atomic+.bak / 손상 주입 복구 |
| R4 | rm 패턴 사고 | 절대경로+고정 glob+xargs -r / dry-run ls |
| R5 | 채점 실패 시 백업 누락 | PUT /grade 성공 후 무조건 / 실패 시나리오 |
| R6 | launchd 미반영 | 임시포트 17899 or launchctl reload |
| R7 | 편집 중 파일 전환 손실 | confirm 가드 (`editMode && 변경 있음`) |
| R8 | 백업 디스크 누적 | rolling 2-slot — `ls -1 \| wc -l` ≤ 2 |
| R9 | 워크트리 백업 손실 | remove 전 메인 복사 (gitignored) |

---

## 4. 다음 단계 (Phase 2-2 design 입력)

**design 결정 사항**:
1. **input.html 와이어프레임** — 3탭(문제/답안/메모) + 25종 태그 + 좌측 textarea + 우측 미리보기 (L620-655 mirror) + 저장→POST→뷰어 URL
2. **뷰어 분기** — `compare-table.cols-2` 좌우 split, 메모 footer, 편집/위장 자동 적용
3. **`do_POST` 시그니처** — raw .md body, response 포맷, 에러(403/409/400)
4. **_file_index.json 갱신** — flock + atomic rename, 중복 id 체크, .bak 정책
5. **백업 호출 시점** — dev-le-17896-grade 어느 단계, 실패 보고 형식, 동시 채점 분 단위 충돌
6. **데이터 마이그레이션** — 3과목 폴더 사전 mkdir, _file_index.json 초기 0건
7. **dev-qa 시나리오** — §12-5 8개 + 3과목(입력→저장→뷰어→편집) + 백업(채점→생성→회전)

**input 자료**: 본 문서 + `17895_analysis.md` + `README.md` 룰 8개 + `_grade_backup_auto/README.md`

---

| 일자 | 세션 | 내용 |
|------|------|------|
| 2026-05-23 | lawear-7ad6 | Phase 2-1 impact (Opus + ultrathink) |
