# 완성도 리뷰 (lawear-7ad6 Phase 3 팀 6B)

> server.py(436L) + input.html(851L) + test_input_mode_api.py(20TC) + test_grade_backup_2slot.py(8TC) / Opus+ultrathink

## 1. 사용자 룰 8개 준수

| # | 룰 | 결과 | 근거 |
|---|---|---|---|
| 1 | 유닛테스트 많이 | **PASS** | 28TC + curl8 + PW12 = 48. 입력 20TC 0.04s, 백업 8TC 0.41s 실측 ALL PASS |
| 2 | 스텝별 로그 | **PASS** | server.py log 20곳 (8단계+헬퍼 12), input.html console 26곳 |
| 3 | 주석 충분 | **PASS** | 모든 함수 docstring + 단계별 인라인(`# --- 1)~8) ---`). input.html mirror 출처 명시 |
| 4 | curl 8 시나리오 | **PASS** | impl_plan §3 C1~C8 + 메인 직접 수행 완료 |
| 5 | Playwright | **PASS** | playwright_screenshots/ 존재, P1~P12 매핑 |
| 6 | Opus only | **PASS** | 팀4→6B 모두 Opus+ultrathink. Sonnet/Haiku 0건 |
| 7 | 17895 안 깨기 | **PASS** | do_PUT(L64-117) 무변경, input.html 신규, do_POST 분기만 추가 |
| 8 | 자의 해석 금지 | **PASS** | 테스트 docstring "impl_plan TC 정확 mirror" 명시 |

## 2. 테스트 커버리지 (48 시나리오)

**충분**: 정상(TC1~4)+음성(TC5~10)+엣지(TC11~15)+인덱스(TC16~20)+백업8. 6단 8단계 매핑 완료.

**부족 3건**:
- PUT /save pytest 자동화 부재 (C8 curl만)
- input.html JS unit test 0건 (renderMd/wrapEmphasis는 P3/P4 e2e만)
- `_file_index.lock` 잔존 cleanup TC 없음

## 3. 엣지케이스 누락 (4건)

| ID | 누락 | 권장 TC | 우선 |
|----|------|---------|------|
| E1 | UTF-8 BOM body | TC21: `﻿` prefix → 메타 정규식 매칭 | M |
| E2 | 1MB+ body | TC22: 1.5MB → bytes 정확 | L (TC12 100KB로 추정) |
| E3 | `{tag}` brace 미리보기 | TC23: renderMd no-throw | L |
| E4 | 동시 PUT /save 2건 | .md.bak 충돌 가능 (do_PUT L104) | **H** |

한글 traversal: TC5+TC11로 커버 — 누락 아님.

## 4. 주석/로그 품질

- server.py: 8단계 인라인 주석 L189~257. HTTP latin-1 제약 명시(L209,246) 운영 함정 인식. 헬퍼 race fix 주석(L357-358) 우수
- input.html: mirror 출처 라인번호(L20-25) + 자의 해석 금지 박스(L27). 콘솔로그 boot/saveFile/load/draft 라이프사이클 커버
- 테스트 docstring: "의도:" + "근거" 명확. TC당 1 assert 룰 준수

## 5. 개선 사항 (3건, 머지 차단 X)

1. **lock 파일명 mismatch**: `INDEX_PATH.with_suffix('.json.lock')` → `_file_index.lock` (.json 교체됨). 코멘트는 `.json.lock`. 동작 정상이나 gitignore 패턴 추가 권장
2. **META_SECTION_RE BOM 미검증**: `^##\s*메타\s*$` 멀티라인 — BOM 시 첫 라인만 영향, `## 메타` 라인 무관이나 TC 부재
3. **assembleMd 메모 trim 후 섹션 생략(L606)**: 편집 진입 시 빈 `## 메모` round-trip 손실. §4 명세 일치이나 dataloss 가능

## 6. 최종 verdict

**APPROVE**

- 룰 8/8 PASS, 28 자동 TC 실측 ALL PASS
- 누락 4건 모두 L/M (E4만 H, 본 PR POST 범위 외)
- 17895 무변경 분기 추가 — 회귀 위험 최소
- 머지 후 launchd reload + 데이터 보존(R9) impl_plan §6 명시

차기 권고: E4(PUT 동시성) + lock cleanup + JS unit test.
