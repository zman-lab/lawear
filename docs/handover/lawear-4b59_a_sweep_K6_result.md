# a_sweep_K6 민법 작업 결과 — 2025_3순환_민법(2) + 2026_입문_민법(28) = 30건

## 작업 요약

- **팀**: a_sweep_K6_민법_2025_3sun_2026_입문
- **총 처리 파일**: 30건
- **마크업 적용 파일**: 10건
- **마크업 미적용 (plain 유지) 파일**: 20건
- **추가된 [em1] 총합**: 38개
- **추가된 [em2] 총합**: 36개
- **R-09 검증**: 10/10 파일 PASS (byte equivalence after stripping em tags)
- **포기 카테고리 풀이 사용 위반**: 0건
- **권고**: QA (부장판사+강사 Opus+ultrathink 2명 병렬)

## 카테고리별 적용 (라이브러리 기준)

| 라이브러리 | 두문자 | 적용 파일 |
|---|---|---|
| 1-6 채권자대위권 (보·필·불·대) | 4-letter | 미케04_42 (3letter), 미케04_52 (4letter x 2회) |
| 1-6 채권자대위권 부록 — 공분청 (불가) | 3-letter | 미케04_54 |
| 1-7 채권자취소 적법성+본안 (피·해·사) | 적법성/본안 | 미케04_57 (적법성 피 2회 + 본안 해/사/피) |
| 6-5 공유물 관리 (관·지·과) | 3-letter | 미케04_40 |
| 6-8 법정지상권 제366조 (저·건물·동·상) | 3-of-4 letter | 미케04_44, 미케04_46 |
| 6-9 점유취득시효 요건 (자·평·공/2·계) | 3-letter | 미케04_37, 미케04_39 |
| 7-3 유치권 (목·련·변제기·점·포) | 3-of-5 letter | 미케04_47 |

## Markup with Evidence List

### 1. 미케04_42 (line 104) — 1-6 채권자대위권

- **library_evidence**:
  - category_header: `### 1-6. 채권자대위권 요건 (제404조)` (line 82-113 라이브러리)
  - letters: `보·필·불·대`
  - 풀이형: 피보전권리 / 보전의 필요성 / 채무자의 권리 불행사 / 피대위권리
  - 본문템플릿_통문장: `[blue]채권자대위권의 요건[/blue]은, [purple]피[em1]보[/em1]전채권의 존재, 보전의 [em1]필[/em1]요성, 채무자가 권리 [em1]불[/em1]행사, 피[em1]대[/em1]위권리가 있을 것[/purple]이다.`
  - library_path: `docs/tts-new/두문자/민법.md` lines 82-113
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_42.md`
  - case_line: 104
  - applied_paragraph_full: `1. 제 404조 [key]채권자대위권[/key]의 요건은, 피[em1]보[/em1][em2]전채권[/em2]이 존재하고 이행기에 있을 것, 채권[em1]보[/em1][em2]전[/em2]의 [em1]필[/em1][em2]요성[/em2]이 있을 것, 채무자가 스스로 권리를 행사하지 않을 것, 피[em1]대[/em1][em2]위권리[/em2]가 존재할 것이다.`
- **match_justification**: 채권자대위권 요건 4종 (보전채권/필요성/불행사/대위권리) 정의 본문 — 라이브러리 1-6 본문 템플릿과 동일 영역. `불` letter는 "권리를 행사하지 않을 것"로 본문에 `불` 글자 부재로 스킵.

### 2. 미케04_44 (line 67) — 6-8 법정지상권

- **library_evidence**:
  - category_header: `### 6-8. 법정지상권 (제366조)`
  - letters: `저·건물·동·상`
  - library_path: `docs/tts-new/두문자/민법.md` lines 668-680
  - 비고: POKI 풀이/본문 — letter는 PDF 정본 유지
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_44.md`
  - case_line: 67
  - applied_paragraph_full: `1. 제366조 [key]법정지상권[/key]의 성립요건은, [em1]저[/em1][em2]당권[/em2] 설정 당시 [em1]건물[/em1]이 존재 할것, [key]저당권[/key] 설정 당시 토지와 건물의 소유자가 [em1]동[/em1][em2]일[/em2] 할것, 저당권 실행으로 건물과 토지의 소유자가 달라질것이다.`
- **match_justification**: 제366조 법정지상권 성립요건 (저당권/건물/동일/달라짐) — 라이브러리 6-8 영역. `상` letter는 "달라질것"로 본문에 `상` 글자 부재로 스킵 (보수 매칭).

### 3. 미케04_46 (line 67) — 6-8 법정지상권 (44와 동일)

- **case_file**: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_46.md`
- **case_line**: 67
- **applied_paragraph_full**: `1. 제366조 [key]법정지상권[/key]의 성립요건은, [key]저당권[/key] 설정 당시 [em1]건물[/em1]이 존재 할것, [em1]저[/em1][em2]당권[/em2] 설정 당시 토지와 건물의 소유자가 [em1]동[/em1][em2]일[/em2] 할것, 저당권 실행으로 건물과 토지의 소유자가 달라질것이다.`
- **match_justification**: 44와 동일 카테고리, 동일 본문 패턴.

### 4. 미케04_47 (line 80) — 7-3 유치권

- **library_evidence**:
  - category_header: `### 7-3. 유치권 (제320조) 요건`
  - letters: `목·련·변제기·점·포`
  - 풀이형: 목적물 / 견련성 / 변제기 도래 / 점유 / 포기특약 없을 것
  - library_path: `docs/tts-new/두문자/민법.md` lines 765-780
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_47.md`
  - case_line: 80
  - applied_paragraph_full: `1. 제320조 [key]유치권[/key]의 성립 요건은, 타인의 물건 또는 유가증권을 [em1]점[/em1][em2]유[/em2]할것, [em1]목[/em1][em2]적물[/em2]에 관하여 생긴 채권이 있을것, [em1]변제기[/em1][em2]에 있을것[/em2], 유치권 배제특약이 없을것이다.`
- **match_justification**: 유치권 성립요건 — 라이브러리 7-3 본문 템플릿과 동일 영역. `련`(견련성), `포`(배제특약) letters는 본문 직접 글자 부재로 스킵 (보수 매칭).

### 5. 미케04_52 (line 68-69) — 1-6 채권자대위권 (2회 적용)

- **library_evidence**: 위 #1과 동일
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_52.md`
  - case_lines: 68-69 (2 paragraphs)
  - applied_paragraph_full L68: `2. 이에 의하면 피[em1]보[/em1][em2]전채권[/em2], 보전의 [em1]필[/em1][em2]요성[/em2], 채무자의 권리[em1]불[/em1][em2]행사[/em2]는 [key]당사자적격[/key]의 요소가 되고, 피[em1]대[/em1][em2]위권리[/em2]는 소송물로서 본안요건이 된다.`
  - applied_paragraph_full L69: `3. [bridge]따라서[/bridge] 피[em1]보[/em1][em2]전채권[/em2], 보전의 [em1]필[/em1][em2]요성[/em2], 채무자의 권리[em1]불[/em1][em2]행사[/em2]의 흠결 시에는 원고적격 흠결로 부적법하고, 피[em1]대[/em1][em2]위권리[/em2] 흠결 시에는 청구가 이유 없게 된다.`
- **match_justification**: 채권자대위소송의 법정 소송담당설 정의에서 4요건 모두 본문에 명시 — `보·필·불·대` 4 letters 완전 매칭. 라이브러리 1-6 본문 템플릿 영역 그대로.

### 6. 미케04_54 (line 82) — 1-6 채권자대위권 부록 (공분청)

- **library_evidence**:
  - category_header: `### 1-6. 채권자대위권 요건` 부록 — `공분청` (불가, 보전 필요성 X)
  - 사용자.md: line 35 그대로
  - library_path: `docs/tts-new/두문자/민법.md` line 99
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_54.md`
  - case_line: 82
  - applied_paragraph_full: `3. 채권자가 자신의 금전채권을 보전하기 위하여 채무자를 대위하여 부동산에 관한 [em1]공[/em1][em2]유물[/em2][em1]분[/em1][em2]할[/em2][em1]청[/em1][em2]구권[/em2]을 행사하는 것은, 책임재산의 보전과 직접적인 관련이 없어 채권의 현실적 이행을 유효 적절하게 확보하기 위하여 필요하다고 보기 어렵고, 채무자의 자유로운 재산관리행위에 대한 부당한 간섭이 되므로 보전의 필요성을 인정할 수 없다.`
- **match_justification**: 금전채권자의 공유물분할청구권 대위행사 = 사용자.md `공분청` 키워드 + "보전 필요성 X" 본문 직접 일치.

### 7. 미케04_57 (line 132, 136-137) — 1-7 채권자취소 적법성+본안

- **library_evidence**:
  - category_header: `### 1-7. 채권자취소권 요건 (제406조)`
  - 두문자 (적법성·각하): `피·대·기`
  - 두문자 (본안·기각): `피·해(사)·사`
  - 사용자.md: line 51-78 그대로
  - library_path: `docs/tts-new/두문자/민법.md` lines 115-151
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_57.md`
  - case_lines: 131-132 (적법성 `피`), 136-137 (본안 `피·해·사`)
  - applied_paragraph_full L132: `[bridge]따라서[/bridge] 수익자 또는 전득자만이 [em1]피[/em1][em2]고[/em2]가 될 수 있고, 채무자는 [em1]피[/em1][em2]고적격[/em2]이 없다.`
  - applied_paragraph_full L136-137: `5. 채권자취소권의 본안 요건은, 사[em1]해[/em1][em2]행위[/em2], 채무자·수익자의 [em1]사[/em1][em2]해의사[/em2]이다, [bridge]사안에서[/bridge] [em1]피[/em1][em2]보전채권[/em2] 존재와 사해의사는 문제되지 않고, 원상회복의 방법이 쟁점이다.`
- **match_justification**: L132 적법성 letter `피`(피고적격) — 라이브러리 1-7 적법성 letter 매칭. L136-137 본안 letters `피`(피보전채권)/`해`(사해행위)/`사`(사해의사) — 라이브러리 1-7 본안 letter 매칭. `대`/`기` letters는 본문 직접 글자 부재로 스킵.

### 8. 미케04_40 (line 86) — 6-5 공유물 관리

- **library_evidence**:
  - category_header: `### 6-5. 공유 — 제265조 (관리)`
  - letters: `관·지·과 / 보존·각`
  - 풀이형: 관리는 지분 과반수 결정 / 보존행위는 각자 가능
  - library_path: `docs/tts-new/두문자/민법.md` lines 632-644
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_40.md`
  - case_line: 86
  - applied_paragraph_full: `4. 제 265조 본문은 [key]공유물의 관리[/key]에 관한 사항을 공유자 [em1]지[/em1][em2]분[/em2]의 [em1]과[/em1][em2]반수[/em2]로 결정할 수 있다 규정하고, 공유물의 임대행위는 [em1]관[/em1][em2]리행위[/em2]에 해당한다.`
- **match_justification**: 제265조 본문 그대로 인용 — 라이브러리 6-5 본문 템플릿 어휘 1:1 일치.

### 9-10. 미케04_37 (line 99), 미케04_39 (line 67) — 6-9 점유취득시효

- **library_evidence**:
  - category_header: `### 6-9. 점유취득시효 — 논증 Set / 요건 (제245조)`
  - letters (요건): `주·상 / 객 / 2·계 / 자·평·공`
  - 풀이형 (요건): 주체 / 상대방 / 객체 / 20년 계속 / 자주·평온·공연
  - library_path: `docs/tts-new/두문자/민법.md` lines 683-699
- **case_markup_evidence**:
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_37.md` line 99
  - applied_paragraph_full L99: `1. 제 245조 제 1항 [key]점유취득시효[/key]는, [em1]2[/em1][em2]0년간[/em2] 소유의 의사로 [em1]평[/em1][em2]온[/em2] [em1]공[/em1][em2]연[/em2]하게 부동산을 점유한 자는 등기로 그 소유권을 취득한다 규정한다.`
  - case_file: `docs/tts-new/2026_입문_민법/2026_minbeop_immun_미케04_39.md` line 67
  - applied_paragraph_full L67: `1. 제 245조 제1항, 타인의 토지를 [em1]2[/em1][em2]0년간[/em2] 소유의 의사로 [em1]평[/em1][em2]온[/em2] [em1]공[/em1][em2]연[/em2]하게 점유한 자는 등기를 함으로써 비로소 소유권을 취득한다.`
- **match_justification**: 제245조 조문 직접 인용 — `2`(20년), `평`(평온), `공`(공연) 모두 본문에 명시. `자`(자주)는 "소유의 의사" 본문에서 letter `자` 글자 부재로 스킵.

## 미적용 파일 사유 (20건)

### 2025_3순환_민법 (2건)
- `2025_minbeop_3sun_10_01.md`: Lv.4 헤더만 있고 본문은 SKIP 메시지 (R-09 본문 없이 마크업 불가)
- `2025_minbeop_3sun_12_01.md`: 동일

### 2026_입문_민법 (18건)
- `미케01_02`: 이중매매 무효 — 라이브러리 3-1 (내·강·조·대·동) POKI letter 본문 부재
- `미케03_34`: 부당이득 — 라이브러리 10-1 두문자 없음 (요건 4개 풀이형만)
- `미케04_35`: 부당이득 — 동일
- `미케04_36`: 토지거래허가 중간생략등기 — 라이브러리 3-8 letter (계·이·손·해·부·조·신/협력·해) 본문 직접 부재
- `미케04_38`: 시효취득 후 등기 전 처분 (채무불이행/대상청구/불법행위) — 라이브러리 직접 매칭 부재
- `미케04_41`: 소수지분권자 보존행위 — 라이브러리 6-5 letter 본문 직접 부재
- `미케04_43`: 양자간 등기명의신탁 불법원인급여 — 라이브러리 6-10 letter (이·3·계·선) 본문 직접 부재 ("양자간"에 `이` 글자 미포함)
- `미케04_45`: 신축 중 건물 법정지상권 — 요건 listing 없음
- `미케04_48`: 제삼자 명의 저당권 부종성 — 라이브러리 직접 매칭 부재
- `미케04_49`: 저당권 침해와 구제 — 라이브러리 7-4 letter 없음 (풀이형만)
- `미케04_50`: 근저당 확정 — 라이브러리 7-6 (결·속/해지/신청/완납) "속"=존속기간 ≠ 본문 "계속적" (동음이의 가짜 매칭 회피)
- `미케04_51`: 공동저당 물상보증인 — 라이브러리 7-5 letter 본문 직접 부재
- `미케04_53`: 동시이행 항변권 — 라이브러리 2-3 letter (쌍·대·제·단) 본문 직접 부재
- `미케04_55`: 합의해제 처분금지효 — 라이브러리 1-6 letter `합해` matches but already inside [key]합의해제[/key] wrap, 중첩 회피
- `미케04_56`: 대위소송 통지 후 처분 — `포기` 단일 letter, 문맥 의미 (양도·포기) ≠ library `포·도`(포기·도산) — 보수적 스킵
- `미케04_58`: 채권양도통지 사해행위 — `사해행위` 단일 mention, 요건 listing 아님
- `미케04_59`: 사해행위 공동저당 — 동일
- `미케04_60`: 사해행위 무권리자 처분 — 동일

## R-09 검증

```
PASS R-09: 2026_minbeop_immun_미케04_37.md
PASS R-09: 2026_minbeop_immun_미케04_39.md
PASS R-09: 2026_minbeop_immun_미케04_40.md
PASS R-09: 2026_minbeop_immun_미케04_42.md
PASS R-09: 2026_minbeop_immun_미케04_44.md
PASS R-09: 2026_minbeop_immun_미케04_46.md
PASS R-09: 2026_minbeop_immun_미케04_47.md
PASS R-09: 2026_minbeop_immun_미케04_52.md
PASS R-09: 2026_minbeop_immun_미케04_54.md
PASS R-09: 2026_minbeop_immun_미케04_57.md
```

10/10 PASS — em 태그 제거 후 HEAD byte 완전 일치.

## 포기 카테고리 사용 위반: 0건

- 모든 markup은 letter만 사용 (풀이형 어휘 차용 X)
- 사용된 카테고리 중 POKI 풀이 카테고리는 6-8(letter만), 7-3(letter만 — 풀이는 letter+1word 안전 expansion)
- 라이브러리 POKI 풀이 어휘 직접 차용 0건

## 추가 정보

- **사용자 약어 마크업 X**: 방배제/고필공/유필공/통공/독당참/신의칙/민소 — 본문 등장 0회
- **§ 추가 X**: 모든 변경은 wrap만
- **메타/원본/Lv.1 변경 X**: 100% Lv.4 섹션만
- **사용자.md 변경 X**

## Recommendation: QA

부장판사 + 강사 Opus+ultrathink 2명 병렬 검증 권고:
1. letter 일치 검증
2. 본문 통문장 ↔ 라이브러리 본문 템플릿 통문장 의미·맥락 매칭
3. POKI 카테고리 letter 사용 시 — 풀이 어휘 차용 부재 확인
