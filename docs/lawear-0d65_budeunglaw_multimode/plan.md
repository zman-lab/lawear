# 부등법 5모드 채점 시스템 — 작업 계획 + 진행

**세션**: lawear-0d65
**워크트리**: `wt/lawear-0d65/budeunglaw-multimode`
**디렉토리**: `/Users/nhn/zman-lab/lawear-lawear-0d65-budeunglaw-multimode`
**Base**: main (HEAD aa7552c 시점)
**시작**: 2026-05-24
**상태**: 진행 중 (자율 진행)

---

## 사용자 요청 정리

1. 부등법 채점 스킬 픽스 X → **5모드 각각 채점해서 비교**
   - (1) 판사 (2) 강사 (3) 하이브리드 (4) 메인 Opus (5) 만능목차 엄격
2. 점수 표기: **민법/민소와 동일** — 50점 문제 + 10점 → "10/50 (20/100)"
3. 사용자 자기 전 자율 진행 (모든 의사결정 메인 자율)
4. 브랜치+워크트리 따로 (롤백 쉽게)

## 판사+강사 토론 결과 (Opus+ultrathink 2팀)

- **합의**: 만능목차는 채점기준 X, 골격만 outline 절대 기준. 조문 0개 = max 20% 컷.
- **충돌 4개**: schema(10기준 vs 9키 호환) / 출처 분리(sources 통합 vs 분리) / 첨부정보(miss 통합 vs 별도) / 시각 강조(유지 vs 삭제)

## 메인 자율 결정 (사용자 잠)

**5모드 동시 구현** — 사용자 요청대로 1답안 → 5모드 비교. 키 집합은 11키 superset (DB CHECK 호환).

### 5모드 가중치 매트릭스 (한눈에)

| key | judge | lecturer | hybrid | main_opus | strict_outline |
|-----|-------|----------|--------|-----------|----------------|
| outline | 16 | 17 | 17 | 14 | **40** |
| articles | 0 | 15 | 15 | 15 | 20 |
| precedent | 0 | 8 | 8 | 10 | 3 |
| sources_unified | 15 | 0 | 0 | 0 | 0 |
| attached | 0 | 13 | 13 | 12 | 15 |
| procedure | 10 | 12 | 12 | 11 | 12 |
| effect | 0 | 10 | 10 | 11 | 5 |
| case_apply | 10 | 11 | 11 | 13 | 3 |
| richness | 8 | 9 | 9 | 9 | 2 |
| sem | 13 | 0 | 0 | 0 | 0 |
| missing | 13 | -5 | -5 | -5 | -10 |
| color | 6 | 0 | 0 | 0 | 0 |
| under | 4 | 0 | 0 | 0 | 0 |
| mnem | 5 | 0 | 0 | 5 | 0 |

- judge: sources 통합 + sem/color/under/mnem 모두 유지
- lecturer: 강사 안 그대로 (key 분리)
- hybrid: 메인 종합 (강사 안 base)
- main_opus: case_apply ↑ + precedent ↑ + outline 약간 ↓
- strict_outline: outline 압도적 (40) + missing 강화 (-10)

## 구현 단계 (자율 진행 체크리스트)

### Phase A — 워크트리 + 핵심 파일 생성 (사용자 yes 한 번)
- [x] 워크트리 + 브랜치 (`wt/lawear-0d65/budeunglaw-multimode`)
- [x] `budeunglaw_modes.py` (가중치 + prompt + helper)
- [x] `budeunglaw_grader.py` (5모드 채점 wrapper)
- [x] `migrations/008_v7_budeunglaw_multimode.sql` (DB 마이그)
- [x] `plan.md` (본 문서)

### Phase B — cases.py 부등법 파싱 분기 (자율)
- [ ] `parse_md_file()` 부등법 분기 추가 (`## 문제` / `## 답안` 인식)
- [ ] subject_type 'problem_answer' 시 origin_text=## 문제, answer_template=## 답안 매핑
- [ ] Lv.1/Lv.4 null 처리
- [ ] outline_category 자동 추정 (guess_outline_category)

### Phase C — DB migration 적용
- [ ] `python migrations/008_v7_budeunglaw_multimode.sql` 적용 (sqlite3)
- [ ] cases backfill (subject_kor='부동산등기법' → subject_type='problem_answer')
- [ ] 컬럼 추가 검증

### Phase D — server.py + attempts.py API 분기
- [ ] `/api/grade` 부등법 분기 — multi_mode 옵션 시 5모드 일괄
- [ ] `/api/attempts/{id}/grade-multimode` 신규 endpoint
- [ ] grade dispatcher (lv1234 → grader.py / problem_answer → budeunglaw_grader.py)

### Phase E — index.html UI 분기
- [ ] 시험페이지 — subject_type='problem_answer' 시 Lv.1~Lv.4 탭 숨김 + ## 문제 단일 표시
- [ ] 채점탭 — 5모드 비교 표 (mode/score_display/grade)
- [ ] 점수 표시 변경 (민법/민소도 동일) — "21/30 (73/100)" 형식
- [ ] 만능목차 카테고리 사이드 표기

### Phase F — 시범 채점 1건 + 검증
- [ ] 부등법 .md 1건 (2순환/01_모의고사_01.md 추정력 20점) 시범 attempt 생성
- [ ] 5모드 mock 채점 → 결과 JSON 확인
- [ ] 5모드 real 채점 (Anthropic API) → 점수 spread 확인
- [ ] index.html 시각 확인

### Phase G — 커밋 + 머지
- [ ] 워크트리 내 커밋 (단계별 또는 묶음)
- [ ] main 머지 (lawear no-PR 룰 — 메인 직접 머지)
- [ ] 워크트리 정리 (사용자 깨면 결정)

### Phase H — 결과 보고
- [ ] 시범 채점 결과 docs에 저장 (`results_sample.md`)
- [ ] 메모리 등재 (필요 시) — 부등법 채점 시스템 reference
- [ ] 사용자 깨면 1줄 요약 보고

## 사용자 룰 준수

- ✅ R-09 자의 해석 금지 (모든 채점 모드 prompt에 명시)
- ✅ feedback_no_pr_workflow — main 직접 머지
- ✅ feedback_no_dooray_registration — 두레이 등록 X
- ✅ feedback_qa_judge_lecturer — 판사+강사 2명 토론 완료
- ✅ feedback_subagent_brief_with_user_rules — 3블록 의무
- ✅ feedback_grade_pass_line_73 — 합격선 73 유지
- ✅ feedback_grading_report_format — 결과 1줄 요약
- ✅ feedback_no_user_confirmation_for_grading — 채점 자체 컨펌 X
- ✅ 워크트리 + 새 브랜치 (롤백 안전)

## 위험 + 완화

| 위험 | 완화 |
|------|------|
| DB migration 실수로 기존 attempts 손상 | BEGIN/COMMIT 트랜잭션 + DEFAULT NULL (기존 row 무영향) |
| Anthropic API 호출 비용 (5모드 × 부등법 N건) | 시범 1건만 real, 나머지는 mock으로 시스템 검증 후 사용자 결정 대기 |
| UI 분기로 민법/민소 시험페이지 깨짐 | subject_type='lv1234' (default)는 기존 그대로, 분기는 'problem_answer'만 |
| 워크트리 머지 충돌 | base aa7552c 시점 깨끗 (uncommitted 0), 머지 평이 |

## 진행 로그

- 2026-05-24 새벽: 워크트리 + 핵심 파일 4개 생성
- (다음 진행은 이 섹션에 timestamp 추가)
