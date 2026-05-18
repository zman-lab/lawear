# 17897 카드 시스템 (Anki 스타일 SRS) P1 시작 — 새 세션 킥오프

> 선행 세션(lawear-abf3)이 기획 완료. 본 세션은 P1부터 구현 진행.
> 새 세션에서 이 문서 링크만 복붙하면 즉시 P1 작업 시작 가능.

## 참고 자료

- **기획 문서**: `/Users/nhn/zman-lab/lawear/docs/wiki/17897_anki_planning.md`
- **게시판 인덱스**: http://10.77.11.110:8585/post/127
- **라이브러리 소스**: `docs/tts-new/두문자/{민법,민소}.md` (민법 76 + 민소 62 = 138 항목)
- **본보기 코드**:
  - 17895 뷰어: `docs/tts-new/server.py` + `merge.html` (PUT staging, marked.parse, type:library 분기)
  - 17896 시험: `docs/tts-exam/server.py` + `index.html` (SQLite WAL + migrations, settings/bookmarks, 단축키, Reports 3-tab)

## 17897 디자인 핵심

- 포트 **17897** (Python http.server, launchd `com.lawear.cards`, 127.0.0.1)
- 위치: `docs/tts-cards/`
- DB 5테이블: `cards` / `card_stats` (SRS 상태 분리) / `reviews` (히스토리) / `bookmarks` / `settings`
- SQLite WAL + `migrations/{NNN}.sql` 멱등 마이그 (17896 패턴)

## SRS (Anki 기본값)

- Again: interval=1, ease-=0.2
- Hard: interval*=1.2, ease-=0.15
- Good: interval*=ease, ease 유지
- Easy: interval*=ease*1.3, ease+=0.15
- `settings.srs_params` 핫 튜닝 가능

## 카드 추출 (build_cards.py)

- 타입 a: 요건 이름 → 풀이형 (forward **138개**)
- 타입 b: 두문자 글자별 빈칸 (blank **96개**)
- 타입 c: reverse (옵션, 기본 OFF)
- strict + dry-run + TC 5건 필수 (라이브러리 1항목 추가/삭제/수정 + 두문자 변경 + 빈 DB)

## 모드

- `srs` (next_due) / `weak` (fails_30d DESC) / `old` (last_review ASC) / `random`
- 과목/카테고리/즐겨찾기 필터 결합

## UI 패턴 (17896 미러)

- 좌측: 모드 선택 + 통계 위젯
- 중앙: 카드 한 장 (Front → Space=Show → Back + 4버튼)
- 단축키: 1=Again, 2=Hard, 3=Good, 4=Easy, Space=Show, Z=stealth, B=sidebar, S=Skip, ?=help
- 다크 + 영문 위장 모드 (Z 토글)
- Reports 3-tab (일별 review / 약점 top10 / 과목별 진척률)

## lawear 절대 규칙 (메모리)

- Opus + ultrathink만 (Sonnet/Haiku 금지)
- 두레이 등록 금지 (lawear 절대 규칙)
- 뷰어: `127.0.0.1:17895` / 게시판: `10.77.11.110:8585`
- PR 생략, 메인 브랜치 직접 머지
- 워크트리 사용 (워크트리 remove 전 DB 백업 필수)

## 백업 (학습 데이터 손실 방지)

- 일배치 launchd → `~/.lawear_backups/cards_{date}.db` 30일 보관

## P1 작업 (지금)

1. 워크트리 생성: `/dev-worktree cards-srs`
2. `docs/tts-cards/` 디렉토리 신설
3. DB 스키마 (`migrations/001_initial.sql`)
4. `build_cards.py` 작성 + dry-run + TC 5건
5. dry-run 결과 사용자 검수 (게시판 또는 콘솔)

## P2~P6 (P1 검수 OK 후 순차)

- P2: `server.py` REST API (`GET /api/cards/next`, `POST /api/cards/{id}/review`, `GET /api/stats`)
- P3: `index.html` UI (카드 + 단축키 + 위장 모드)
- P4: Stats 3-tab
- P5: launchd 등록 + 일배치 백업 스크립트
- P6: `dev-lawear-shortcut-lib-update` 스킬에 sync 채널 통합

## 첫 명령 (새 세션 첫 발화)

> P1 시작. 워크트리 생성 + DB 스키마 + build_cards.py 작성 + dry-run 결과 보여줘.
> 검수 권장: 라이브러리 .md 138 항목이 카드로 정확히 추출되는지.

— from lawear-abf3 (선행 세션, 2026-05-19)
