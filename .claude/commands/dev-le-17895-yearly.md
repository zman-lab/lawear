# dev-le-17895-yearly — 매년 박문각 강사 새 PDF 도착 시 통합 워크플로우

> **17895 TTS 뷰어 기준 매년 반복 작업 통합 스킬.** 강사가 새 연도(2026/2025/2027 등) PDF 올리면 메인이 본 스킬로 일괄 처리.
>
> **사용자 의도**: grep/sed 일괄 변환은 컨텍스트 오탐 위험. Opus 서브에이전트 ultrathink + 문장 컨텍스트 분석 강제. 토큰 비용 안 아낌.

---

## 사용 시점

- 강사가 새 박문각 PDF 패키지 도착 (예: `~/myftp/2026_USB/2026_박문각_피뎁/`)
- 라이브러리·케이스 본문·강조 시스템 갱신 필요
- 사용자 호출: `/dev-le-17895-yearly --year=2026` 또는 `--year=2025`

---

## 절대 규칙

1. **sed/grep 일괄 변환 금지** (컨텍스트 오탐 위험 — lawear-103a 경험)
   - 사례: 부사 "정도(degree)" ↔ 인물명 "丁도(정+도 조사)" 양방향 오탐 17건
   - 사례: 두문자 "·기"가 "·己" 잘못 한자 변환 7건
   - 사례: 회사명 "정은행"이 인물 "丁" prefix로 잘못 매칭 가능
2. **Opus 서브에이전트 ultrathink 강제**
   - Sonnet/Haiku 금지 (lawear `feedback_no_subagent_for_board` 룰)
   - 문장 정독 + 의미 분석 + 정확 판정
3. **R-09 절대 강제** — `## 원본` 섹션은 17896 채점 기준, 변경 X
4. **사용자 약어 정상 인정** (방배제/고필공/유필공/통공/독당참/신의칙/민소)
5. **자동화 + 검증 분리**: 자동 sed 1차 적용 시 즉시 Opus 컨텍스트 검증 2차 필수

---

## 입력값

- `--year=YYYY` (필수): 2026/2025/2027 등 연도
- `--dry-run` (선택): 시뮬레이션만, 적용 안 함
- `--phase=A|B|C|D|E|all` (선택, 기본 all): 부분 실행

---

## 환경 사전 확인 (Phase 0)

```bash
# PDF 위치
ls /Users/nhn/myftp/{YEAR}_USB/{YEAR}_박문각_피뎁/ 2>/dev/null

# 두문자 정본 위치
ls /Users/nhn/myftp/{YEAR}_USB/두문자정리및책/ 2>/dev/null

# 17895 헬스
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:17895/

# 기존 lawear 구조
ls docs/tts-new/{YEAR}_*/  docs/tts-new/두문자/ docs/tts-new/_file_index.json

# 게시판 ON 여부
curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://10.77.11.110:8585/
```

---

## Phase A — 자동화 일괄 변환

**범위**: 한자 인물명 / 금액 숫자화 / 회사명 / 사용자 약어 / 디렉토리 prefix / 인덱스 재생성

### A.1 사용자 약어 사전 등재 (메모리)

기존 메모리 `feedback_user_abbreviations.md` 확인:
- 방배제 (방해배제)
- 고필공 (고유필수적공동소송)
- 유필공 (유사필수적공동소송)
- 통공 (통상공동소송)
- 독당참 (독립당사자참가)
- 신의칙 (신의성실원칙)
- 민소 (민사소송법)

신규 약어 발견 시 메모리 append.

### A.2 한자 인물명 치환 (자동 + 즉시 검증)

**1차 자동 (sed)**:
- 매핑: 갑→甲 / 을→乙 / 병→丙 / 정→丁 / 무→戊 / 기→己
- 스크립트: `/tmp/lawear_hanja_convert.py` (또는 `scripts/lawear_hanja_convert.py`로 정착)
- 안전 정책: 단일 글자 + 조사 패턴 (회사명/일반 단어 회피)
- **주의**: "도" 조사 제거 ("정도" 부사 오탐 방지)

**2차 Opus 검증 (필수)**:
- `dev-le-17895-hanja-verify` 서브 스킬 호출
- 디렉토리별 Opus 4명 병렬 (예비_민법/예비_민소/입문_민법/입문_민소)
- 각자 ultrathink + 문장 정독 + 양방향 오탐 정확 판정

### A.3 금액 숫자화

**자동 (sed)**:
- 매핑: 일~구 → 1~9, 단위(십/백/천/만/억) 한글 유지
- 예: 일억원→1억원, 사천만원→4천만원
- 스크립트: `/tmp/lawear_money_convert.py`
- 안전 정책: 단어 안 회피 ("일반", "이상" 등 단위 동반 패턴만)

**검증**: 한자 검증 Opus가 동시 처리 (금액 패턴도 확인)

### A.4 회사명 한자 치환

**사용자 명시 케이스만 일괄 처리**:
- 정은행→丁은행 (사용자 확정)
- 을회사→乙회사
- 갑회사→甲회사
- 추가 회사명 (병회사/정회사 등)은 사용자 컨펌 후

### A.5 디렉토리 연도 prefix

```bash
git mv docs/tts-new/예비_민법 docs/tts-new/{YEAR}_예비_민법
git mv docs/tts-new/예비_민소 docs/tts-new/{YEAR}_예비_민소
git mv docs/tts-new/입문_민법 docs/tts-new/{YEAR}_입문_민법
git mv docs/tts-new/입문_민소 docs/tts-new/{YEAR}_입문_민소
git mv docs/tts/예비_민법 docs/tts/{YEAR}_예비_민법
git mv docs/tts/예비_민소 docs/tts/{YEAR}_예비_민소
```

### A.6 _file_index.json 재생성

- 스크립트: `/tmp/lawear_index_regen.py` (또는 `scripts/`로 정착)
- 모든 .md 스캔 후 entry 재생성
- userCase 보존 (기존 인덱스에서)

### A.7 archive 마이그레이션

- `docs/tts/{YEAR}_*` 에만 있는 파일 → `docs/tts-new/{YEAR}_*`로 cp
- 인덱스 재생성

---

## Phase B — Lv.4 본문 R-09 sweep

**범위**: 315 파일 × `## 원본` ↔ `Lv.1~4` 1:1 비교

### B.1 디렉토리 분담 (Opus 6명 병렬, ultrathink)

서브 스킬 `dev-le-17895-r09-sweep` 호출. 분담:
- B-1 입문_민법 (60 파일)
- B-2 입문_민소 (34 파일)
- B-3 예비_민법 (55 파일)
- B-4 예비_민소 (95 파일)
- B-5 archive 예비_민법 (58 파일)
- B-6 archive 예비_민소 (56 파일)

### B.2 R-09 4축 검증

각 케이스 .md:
1. **누락**: ## 원본의 결론/근거/판례/조문/사실관계가 Lv.1~4에서 빠짐
2. **자의 추가**: ## 원본에 없는 조문/판례/이론 추가
3. **어휘 변경**: ## 원본 어휘 임의 변경 (사용자 약어 제외)
4. **결론 변경**: 사안별 결론 누락 또는 일반화

### B.3 정정 방식

- **위반만 Edit** (새로 작성 X)
- 사용자 약어 + 한자/금액 변환 정상 인정
- `## 원본` 섹션은 절대 변경 X

### B.4 보고서

- `docs/_lv4_qa_phaseB_*.md` 디렉토리별 6개
- 메인이 통합 + 사용자 검수 권장 사항 추출

---

## Phase C — 강조 sweep (em1~em4 + 의미 5종 + 여분 2종)

**범위**: 315 파일 본문 의미별 강조 적용. 서브 스킬 `dev-le-17895-emphasis-sweep` 호출.

### C.1 강조 시스템 (메모리 `feedback_em_color_system` 참조)

| 종류 | 태그 | 적용 위치 |
|------|------|----------|
| em1 (배경 빨/흰) | `[em1]X[/em1]` | 메인 두문자 글자 (라이브러리 카테고리) |
| em2 (배경 노/흰) | `[em2]X[/em2]` | 메인 풀이 첫 글자 |
| em3 (배경 파/흰) | `[em3]X[/em3]` | 풀이형 보조 두문자 |
| em4 (배경 보/흰) | `[em4]X[/em4]` | 풀이형 풀이 키워드 |
| con (빨강 폰트) | `[con]X[/con]` | 결론 문장 |
| fact (주황 폰트) | `[fact]X[/fact]` | 요건 사실 |
| case (초록 폰트) | `[case]X[/case]` | 중요 판례 |
| bridge (파랑 폰트) | `[bridge]X[/bridge]` | 논리 전개 ("따라서", "사안의 경우" 등) |
| key (보라 폰트) | `[key]X[/key]` | 주요 쟁점·핵심 |
| free1 (베이지) | `[free1]X[/free1]` | 사용자 자유 |
| free2 (라벤더) | `[free2]X[/free2]` | 사용자 자유 |

### C.2 Opus 분담 + 의미 분석

- 디렉토리별 Opus 5~10명 병렬 (R-09 sweep과 동일 분담)
- ultrathink + 문장 정독 + 의미별 강조 위치 결정
- **자동 substring 매칭 X** (의미 매칭만)

### C.3 stealth 모드 호환

- merge.html `body.stealth` 셀렉터에 신규 태그 등록 (이미 lawear-103a 완료)
- 학습 빈칸 모드 일관 작동

---

## Phase D — 가이드 + 스크립트 갱신

### D.1 `_lv4_user_style_guide.md` 갱신

- 0장 절대 룰: 약어 사전 + 표기 표준 (한자/금액/년월일/따옴표/17896 채점 기준)
- 8장 강조 시스템 (em + 폰트 + 여분 + 효과 + stealth + 17895 뷰어)
- 9장 R-09 절대 강제 (4축 + 정정 방식)

### D.2 `scripts/apply_emphasis_lv4.py` 갱신

- 기존 [red]/[blue]/[bold] 자동 매칭 + 신규 13종 추가
- 또는 신규 스크립트 `scripts/apply_emphasis_em_lv4.py`

### D.3 메모리 갱신

- `feedback_em_color_system.md` (시안2 색상)
- `feedback_em_sweep_rules.md` (sweep 변환 룰)
- `feedback_user_abbreviations.md` (사용자 약어)
- 신규 발견 사항 (예: 회사명 한자, 금액 표기 룰) append

---

## Phase E — 라이브러리 두문자 갱신

### E.1 PDF 원문 정리본 (사용자 정본 .md)

- `~/myftp/{YEAR}_USB/두문자정리및책/{과목}/사용자정본_두문자.md` 정독
- lawear 라이브러리 (`docs/tts-new/두문자/{과목}.md`) 신규 카테고리 추가

### E.2 em1~em4 적용

- 메인 두문자 (em1) + 풀이 (em2) + 풀이형 보조 (em3) + 풀이 키워드 (em4)
- 9-2 시범본 (`docs/tts-new/두문자/민소.md` 831~838) 패턴 mirror
- 본문 템플릿 `[blank2]X[/blank2]` → `[em1]X[/em1]` 일괄 변환

### E.3 출처 메타 (검증 가능)

- 사용자.md (USB 절대경로 + line)
- 강사 두문자 정본 PDF (절대경로 + line)
- 강사책 핵심암기장 PDF (Set + page + 위치)

---

## 워크플로우 순서

```
Phase 0 환경 확인
  ↓
Phase A.1 약어 사전 (메모리)
  ↓
Phase A.2 한자 자동 + Opus 검증 ⭐
  ↓
Phase A.3 금액 자동 + Opus 검증
  ↓
Phase A.4 회사명 (사용자 명시)
  ↓
Phase A.5 디렉토리 prefix
  ↓
Phase A.6 인덱스 재생성
  ↓
Phase A.7 archive 마이그레이션
  ↓
Phase B R-09 sweep (Opus 6명 병렬) ⭐
  ↓ (B 통과 후)
Phase C 강조 sweep (Opus 5~10명 병렬) ⭐
  ↓
Phase D 가이드 + 스크립트 + 메모리 갱신
  ↓
Phase E 라이브러리 두문자 (em + 출처 메타)
  ↓
Push + gc + 사용자 보고
```

---

## 서브 스킬 (분담)

- `dev-le-17895-hanja-verify` — 한자 정확성 컨텍스트 검증 (Phase A.2 2차)
- `dev-le-17895-r09-sweep` — Lv.4 R-09 4축 검증 + 정정 (Phase B)
- `dev-le-17895-emphasis-sweep` — em1~em4 + 의미 5종 강조 sweep (Phase C)

---

## 자가 검증 체크리스트

- [ ] Phase 0 환경 확인 완료 (PDF 위치, 17895 헬스, 게시판 ON)
- [ ] Phase A.1 약어 사전 메모리 등재
- [ ] Phase A.2 한자: 자동 sed + Opus 검증 (2단계, sed만으로 끝 X)
- [ ] Phase A.3 금액 자동 + 검증
- [ ] Phase A.4 회사명 사용자 명시 케이스만
- [ ] Phase A.5 디렉토리 prefix git mv
- [ ] Phase A.6 인덱스 재생성 후 17895 fetch 200
- [ ] Phase A.7 archive 마이그레이션 + 인덱스 재갱신
- [ ] Phase B R-09 sweep 6 디렉토리 Opus 보고서 (`docs/_lv4_qa_phaseB_*.md`)
- [ ] Phase C 강조 sweep Opus 보고서 + 사용자 시각 검증
- [ ] Phase D 가이드 + 스크립트 + 메모리 갱신
- [ ] Phase E 라이브러리 em + 출처 메타
- [ ] 17895 새로고침 검증 (라이브러리 + 케이스 색상)
- [ ] 17896 채점 정상 작동 검증
- [ ] git push + gc

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 한자 sed 오탐 (정도→丁도 등) | 조사 매칭 후 컨텍스트 미검증 | Phase A.2 2차 Opus 검증 (sed만으로 끝 X) |
| 두문자 패턴 잘못 한자 변환 (·기→·己) | 가운뎃점 패턴 매칭 | 한자 스크립트 패턴 2 제거 또는 라이브러리 영역 제외 |
| 회사명 잘못 인물명 매칭 | 단일 글자 + 다음 단어 한글 | 사용자 명시 회사명만 변환 (자동 X) |
| Lv.4 본문 자의 변경 | Opus 자체 평가 신뢰 X | 메인 직접 git diff 검증 (`feedback_subagent_self_eval_unreliable`) |
| _file_index.json incomplete | 수동 인덱스 (eef5 이전) | `dev-le-17895-yearly` 의 인덱스 재생성 단계 자동 처리 |
| 17895 fetch 404 | 디렉토리 prefix 변경 후 캐시 | 강제 새로고침 (Cmd+Shift+R) |

---

## 메모리 연동

- `feedback_em_color_system.md` — em1~em4 색상 (시안2)
- `feedback_em_sweep_rules.md` — 라이브러리 sweep 룰 4단계
- `feedback_user_abbreviations.md` — 사용자 약어 사전
- `feedback_subagent_self_eval_unreliable.md` — 메인 직접 검증 강제
- `feedback_no_subagent_for_board.md` — Sonnet/Haiku 금지, Opus만
- `feedback_qa_judge_lecturer.md` — 부장판사+강사 Opus QA
- `feedback_pdf_first_for_typo_doubt.md` — PDF 1차 비교 (오타 의심)
- `feedback_three_stage_byte_compare.md` — 사용자.md + 정본 PDF + 핵심암기장 PDF 3단 byte 대조

---

## 입력값

$ARGUMENTS
