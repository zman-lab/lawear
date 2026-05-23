# lawear-7ad6 v4 최종 결과

**완료 일자**: 2026-05-23 22:00
**워크트리**: `wt/lawear-7ad6/input-mode-and-backup`
**최종 commit**: (이 문서 commit 시점)

## v4 변경 사항 (v3 → v4)

| 변경 | 내용 |
|------|------|
| 진입 흐름 | + 버튼 prompt 팝업 X → 즉시 input.html (모든 입력 input.html 안) |
| 카테고리 | text input → **콤보박스** (입문/예비/1~3순환/기타) + 기타 자유 |
| 데이터 모델 | file = 파일명(그룹화, NN 없음) / title = `NN_주제목` / case = 소제목 |
| L3 사이드패널 | `meta.file` 그대로 (예: 모고1회) — NN 없는 자동 그룹화 |
| L4 사이드패널 | shortId = `meta.title` (NN 포함) / case-title = `meta.case` (소제목) |
| 헤더 네비 | 5단 `year / subject / category / file / title` |
| NN 자동 부여 | 같은 file 그룹 내 next_nn 계산 + 이중 NN 방지 (lock 안) |
| marked.js | `breaks: true` (단일 \n → `<br>` — 엔터 정상 표시) |
| 음성입력 | input.html textarea 옆 🎤 mic 버튼 (Web Speech API) |
| stealthCategoryMap | '사용자' → 'UserInput' 매핑 추가 |

## 코드 통계

| 파일 | v3 | v4 | 차이 |
|------|----|----|------|
| server.py | 615L | ~640L | +25 (NN 자동 + meta key 추가) |
| merge.html | 2050L | ~2055L | +5 (L3 file / L4 swap / pathParts 5단 / marked breaks) |
| input.html | 1193L | 1320L | +127 (콤보박스 + mic + 시각 분리) |
| dev-le-17896-grade.md | (기존) | (그대로) | 0 |

## 검증

- pytest 28/28 PASS (단독 실행 — 작업 A 20 + 작업 B 8, fixture 격리 OK)
- curl 8/8 의도 동작
- Playwright 회귀 P9~P12 PASS (17895 무손상)
- 임팩트 + 완성도 리뷰 APPROVE

## 데이터 마이그레이션

기존 user_input entry 2건 patch:
- file: `01_모고1회 → 모고1회`, `02_모고1회 → 모고1회` (NN 제거, L3 그룹화)
- title: `공유물분할 약술 → 01_공유물분할 약술`, `→ 02_공유물분할 약술` (NN 추가)

## 머지 후 메인 17895 launchd reload 필요

```bash
launchctl unload ~/Library/LaunchAgents/com.lawear.ttsmerger.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.lawear.ttsmerger.plist
```

## 메모리 신규/갱신

- [[project_input_mode_3subjects]] (v3 → v4 반영)
- [[project_grade_backup_2slot]] (변경 없음)
- [[feedback_input_mode_v4_changes]] (신규 — v4 변경 정리)
- [[feedback_input_mode_design]] / [[feedback_3subjects_split_view_pattern]] (v3 그대로)

## 신규 사용자 입력 흐름 (자동)

1. http://17895/merge.html → 사이드패널 "+ 새 사용자 입력 문제" 클릭
2. input.html 진입 → 콤보박스 + 자유 입력 + 음성
3. 저장 → server.py가 자동:
   - 폴더 생성 (`mkdir -p {year}_사용자_{subject}/{category}/`)
   - 파일 저장 (`NN_{file}.md`, NN auto)
   - 메타 파싱 → _file_index entry 추가 (file=파일명 / title=`NN_주제목` / case=소제목)
   - lock + atomic + .bak
4. merge.html 자동 이동 → split table 뷰
