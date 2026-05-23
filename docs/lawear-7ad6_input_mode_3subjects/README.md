# lawear-7ad6 — 입력 모드 3과목 (부등법/부등서류/민사서류)

자율주행 진행 중 (2026-05-23~). lawear-7ad6 세션.

## 목표
- 3과목 사용자 직접 입력 모드 도입
- 기존 17895 (민법/민소/형법/형소) 깨지지 않게 별도 추가
- 입력 UI: 문제/답안 탭 + 17895 태그 툴바 (25종) + 실시간 미리보기
- 뷰어 UI: 좌우 split 테이블 (사용자 명시)

## 워크트리
- 브랜치: `wt/lawear-7ad6/input-mode-and-backup`
- 디렉토리: `/Users/nhn/zman-lab/lawear-lawear-7ad6-input-mode-and-backup`
- 베이스: main `b20fba0`

## 작업 진행 (예정)
- [ ] Phase 1: 17895 정확 분석 (server.py + merge.html)
- [ ] Phase 2: dev-spec 트릴로지 (impact/design/impl-plan)
- [ ] Phase 3: dev-team Phase 4-6 (구현/리뷰/QA)
- [ ] Phase 4: 결과 정리 + 메모리 채움 + 사용자 보고

## 관련 메모리
- [[project_input_mode_3subjects]]
- [[feedback_input_mode_design]]
- [[feedback_3subjects_split_view_pattern]]
- [[reference_input_mode_files]]
- [[feedback_17895_no_tts_section_correction]]

## 사용자 명시 룰
1. 유닛테스트 많이 (글로벌 룰 최소 3 → 20+ TC)
2. 스텝별 로그 충실 (logging.info 단계마다)
3. 주석 충분 (글로벌 디폴트 오버라이드)
4. curl endpoint header + body 검증
5. Playwright UI 검증 (사용자 눈)
6. Opus + ultrathink only (Sonnet/Haiku 금지)
7. 17895 정확 분석 후 dev-spec 호출, 기존 깨지면 안 됨
8. dev-spec → dev-team 자율 진행 (사용자 부재)
