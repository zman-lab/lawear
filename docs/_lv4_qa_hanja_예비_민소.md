# Lv.4 한자 치환 정확성 컨텍스트 검증 — 예비_민소

- **세션**: lawear (Opus + ultrathink)
- **대상**: 151개 파일 (tts-new 95 + tts archive 56)
- **방법**: 문장 컨텍스트 분석 (grep/sed 일괄 X)
- **기준 규칙**: R-05 (인명 한자 → 한글), R-09 (PDF 원본 보존, 자의 변경 금지)

## 요약

| 항목 | 값 |
|------|------|
| 총 파일 | 151 (tts-new 95 + tts 56) |
| TTS 영역 한자 잔존 | 149 (98.7%) |
| ORIGIN 영역만 한자 | 0 |
| META 영역만 한자 | 1 (tts/미케01_05 — diff 표 참고용) |
| 완전 클린 | 1 |

### 등장 한자 글자(빈도)

| 한자 | 전체 | TTS body | ORIGIN | META |
|------|------|----------|--------|------|
| 甲 | 2219 | 1045 | 1058 | 116 |
| 乙 | 1814 | 809 | 897 | 108 |
| 丙 | 678 | 296 | 330 | 52 |
| 丁 | 165 | 73 | 81 | 11 |
| 知 | 40 | 12 | 14 | 14 |
| 戊 | 22 | 10 | 11 | 1 |
| 不 | 22 | 6 | 7 | 9 |
| 二 | 5 | 0 | 3 | 2 |
| 段 | 5 | 0 | 3 | 2 |

**관찰**:
- 甲乙丙丁戊 — 모두 R-05 인명. 변환 누락 패턴 일관.
- 知, 不 — 法 용어 "지·부지" (R-05 한자 병기 제거 대상).
- 二, 段 — META 영역의 diff/체크리스트 셀에만 등장 (TTS body 0건). 이단(2단) 변환 완료.

## 심각도 분류 (TTS body 기준)

| 심각도 | TTS 한자 줄 수 | 파일 수 |
|--------|---------------|---------|
| CRITICAL | 10줄 이상 | 8 |
| HIGH | 5~9줄 | 69 |
| MEDIUM | 2~4줄 | 60 |
| LOW | 1줄 | 12 |
| CLEAN | 0줄 (META-only or 완전 클린) | 2 (TTS 클린 + META-only 1) |

## CRITICAL 파일 상세

### tts/2026_minso_yebi_미케01_02.md
- TTS body 한자: 16 줄 / 45 글자
- ORIGIN 한자 (PDF 보존, OK): 5 줄 / 17 글자
- 등장 한자: 丙 乙 甲

### tts/2026_minso_yebi_모고01_01.md
- TTS body 한자: 14 줄 / 42 글자
- ORIGIN 한자 (PDF 보존, OK): 7 줄 / 32 글자
- 등장 한자: 丙 乙 甲

### tts-new/2026_minso_yebi_미케04_34.md
- TTS body 한자: 15 줄 / 40 글자
- ORIGIN 한자 (PDF 보존, OK): 6 줄 / 21 글자
- 등장 한자: 乙 甲

### tts/2026_minso_yebi_미케04_34.md
- TTS body 한자: 15 줄 / 40 글자
- ORIGIN 한자 (PDF 보존, OK): 6 줄 / 21 글자
- 등장 한자: 乙 甲

### tts-new/2026_minso_yebi_미케04_09.md
- TTS body 한자: 13 줄 / 37 글자
- ORIGIN 한자 (PDF 보존, OK): 9 줄 / 30 글자
- 등장 한자: 乙 甲

### tts-new/2026_minso_yebi_모고01_01.md
- TTS body 한자: 11 줄 / 34 글자
- ORIGIN 한자 (PDF 보존, OK): 9 줄 / 36 글자
- 등장 한자: 丙 乙 甲

### tts/2026_minso_yebi_미케01_03.md
- TTS body 한자: 11 줄 / 26 글자
- ORIGIN 한자 (PDF 보존, OK): 6 줄 / 18 글자
- 등장 한자: 丙 乙 甲

### tts/2026_minso_yebi_미케01_04.md
- TTS body 한자: 10 줄 / 14 글자
- ORIGIN 한자 (PDF 보존, OK): 7 줄 / 19 글자
- 등장 한자: 乙 甲

## 특수 패턴 발견

### 1. 知·不知 (法 용어 한자) — 3 파일 한정

R-05 한자 병기 제거 규칙상 "지·부지"로 한글 변환 필요. 다음 파일의 Lv.1/Lv.4 본문에 잔존:

| 파일 | 라인 | 섹션 | 발췌 |
|------|------|------|------|
| tts-new/미케05_07.md | L72 | Lv.1 답안 | 승계인의 [u]知·不知는 문제되지 않[/u]는다 |
| tts-new/미케05_07.md | L90 | Lv.4 암기노트 | 승계인의 知·不知는 문제되지 않는다 |
| tts-new/미케05_13.md | L82 | Lv.1 답안 | 知·不知, 고의·과실을 묻지 않고 일률적으로 차단 |
| tts-new/미케05_13.md | L100 | Lv.4 암기노트 | 知·不知, 고의·과실을 묻지 않고 |
| tts-new/미케05_14.md | L59 | Lv.1 답안 | [u]知·不知, 고의·과실을 묻지 않고[/u] |
| tts-new/미케05_14.md | L76 | Lv.4 암기노트 | 知·不知, 고의·과실을 묻지 않고 |

→ 권장: `知·不知` → `지·부지` 일괄 치환. R-09 위반 없음 (한자→한글 음역, 의미 보존).

### 2. 二段 (이단) — TTS body 0건, META 정상 표기

미케04_07 L39 ORIGIN 섹션: `이단(二段)의 추정` (PDF 표현 보존, R-05 OK).
미케04_32 L114, L140 META(diff/체크리스트): `二段` → `이단/2단` 변환 기록.
→ TTS body 잔존 없음. 적정.

### 3. 인명 한자 (甲乙丙丁戊) — 대거 미변환

**중대 발견**: tts-new와 tts(archive) 양쪽 모두 인명 한자가 TTS reading body에 그대로 남아있음.

- 일관된 패턴: 동일 파일 내 일부는 `갑/을/병`(한글) + 일부는 `甲/乙/丙`(한자) 혼재 — 변환 부분 적용.
- 영향 영역: `## Lv.1 빠른복습`, `## Lv.4 암기노트`, `### 답안`, `### 문제`, `### 사안의 경우` 등.
- TTS 변환 시 한자가 음역되지 않아 SSR/낭독 품질 저하.

### 4. 두문자 "패·기/승·각" — 정확 (R-05 위반 없음)

미케05_40, 미케05_47에 등장하는 두문자 `패·기/승·각`(전소 패소→후소 청구기각, 전소 승소→후소 소각하)에서 "기"는 **한글**로 유지됨 (己 한자 사용 없음). R-05 인명 한자와 구분되어 정확.

### 5. 9-2 반소 영역 (격·추·이익) — 본 디렉토리 내 미존재

`반소` 키워드 자체가 예비_민소 디렉토리 151 파일 전체에 등장 없음. "격·추·이익"(당사자 적격·제3자 추가·반소의 이익) 두문자 패턴도 등장 없음. 해당 영역은 다른 과목(미케/모고) 디렉토리에 있을 가능성. 본 검증 범위 외.

### 6. 모고01_02 변경판례 5가지 이유

tts-new/2026_minso_yebi_모고01_02.md L100, L131-134 확인: 변경판례 5가지 이유 모두 정확 반영.
- 1. 법률적 근거 없음
- 2. 시효중단·제소기간 준수 이익 + 미리 집행권원 확보 이익
- 3. 공동소송참가 + 승계집행문
- 4. 집행장애사유
- 5. 분쟁의 일회적 해결·소송경제
→ 단, 본문 내 甲乙丙丁 한자 인명은 변환 누락 (위 인명 한자 항목과 동일 패턴).

## 전체 파일 표 (심각도순)

| 파일 | 심각도 | TTS줄 | TTS자 | ORIGIN자 | 등장 한자 |
|------|--------|------|------|--------|----------|
| tts/2026_minso_yebi_미케01_02.md | CRITICAL | 16 | 45 | 17 | 丙乙甲 |
| tts-new/2026_minso_yebi_모고02_02.md | HIGH | 8 | 42 | 46 | 乙甲 |
| tts/2026_minso_yebi_모고01_01.md | CRITICAL | 14 | 42 | 32 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케04_34.md | CRITICAL | 15 | 40 | 21 | 乙甲 |
| tts/2026_minso_yebi_미케04_34.md | CRITICAL | 15 | 40 | 21 | 乙甲 |
| tts-new/2026_minso_yebi_미케04_09.md | CRITICAL | 13 | 37 | 30 | 乙甲 |
| tts/2026_minso_yebi_미케02_08.md | HIGH | 7 | 37 | 50 | 丁丙乙甲 |
| tts-new/2026_minso_yebi_모고01_01.md | CRITICAL | 11 | 34 | 36 | 丙乙甲 |
| tts-new/2026_minso_yebi_모고01_02.md | HIGH | 8 | 31 | 35 | 丁乙甲 |
| tts-new/2026_minso_yebi_모고02_01.md | HIGH | 9 | 27 | 42 | 丁乙戊甲 |
| tts-new/2026_minso_yebi_모고02_04.md | HIGH | 7 | 27 | 19 | 乙甲 |
| tts-new/2026_minso_yebi_미케04_01.md | HIGH | 8 | 27 | 25 | 乙甲 |
| tts/2026_minso_yebi_모고02_04.md | HIGH | 7 | 27 | 19 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_08.md | HIGH | 5 | 26 | 19 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케05_42.md | HIGH | 7 | 26 | 17 | 丙乙甲 |
| tts/2026_minso_yebi_미케01_03.md | CRITICAL | 11 | 26 | 18 | 丙乙甲 |
| tts/2026_minso_yebi_미케05_42.md | HIGH | 7 | 26 | 17 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케02_03.md | MEDIUM | 3 | 25 | 38 | 丁丙乙甲 |
| tts-new/2026_minso_yebi_미케04_33.md | HIGH | 6 | 25 | 18 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_01.md | HIGH | 8 | 25 | 17 | 丙乙甲 |
| tts/2026_minso_yebi_미케04_33.md | HIGH | 6 | 25 | 18 | 乙甲 |
| tts-new/2026_minso_yebi_미케04_06.md | HIGH | 9 | 24 | 41 | 丁丙乙甲 |
| tts-new/2026_minso_yebi_미케04_31.md | HIGH | 6 | 24 | 36 | 丙甲 |
| tts/2026_minso_yebi_미케02_07.md | HIGH | 8 | 24 | 26 | 丙乙甲 |
| tts/2026_minso_yebi_미케04_31.md | HIGH | 6 | 24 | 36 | 丙甲 |
| tts-new/2026_minso_yebi_미케04_26.md | HIGH | 9 | 23 | 25 | 乙甲 |
| tts/2026_minso_yebi_미케04_26.md | HIGH | 9 | 23 | 25 | 乙甲 |
| tts-new/2026_minso_yebi_모고02_03.md | HIGH | 6 | 22 | 18 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_13.md | HIGH | 6 | 22 | 23 | 不丙乙甲知 |
| tts-new/2026_minso_yebi_미케05_45.md | MEDIUM | 4 | 22 | 19 | 乙甲 |
| tts/2026_minso_yebi_모고02_03.md | HIGH | 6 | 22 | 18 | 乙甲 |
| tts/2026_minso_yebi_미케05_45.md | MEDIUM | 4 | 22 | 19 | 乙甲 |
| tts-new/2026_minso_yebi_미케04_08.md | HIGH | 7 | 21 | 25 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_35.md | HIGH | 7 | 21 | 14 | 丙乙甲 |
| tts/2026_minso_yebi_미케05_35.md | HIGH | 7 | 21 | 14 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케02_08.md | MEDIUM | 4 | 20 | 17 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케05_11.md | MEDIUM | 4 | 20 | 18 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_14.md | HIGH | 6 | 20 | 12 | 不乙甲知 |
| tts-new/2026_minso_yebi_미케01_02.md | HIGH | 6 | 19 | 18 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케05_07.md | HIGH | 7 | 19 | 15 | 丁不乙甲知 |
| tts-new/2026_minso_yebi_미케05_41.md | HIGH | 5 | 19 | 18 | 丁乙甲 |
| tts-new/2026_minso_yebi_미케05_47.md | HIGH | 6 | 19 | 26 | 丙乙甲 |
| tts/2026_minso_yebi_미케05_41.md | HIGH | 5 | 19 | 18 | 丁乙甲 |
| tts/2026_minso_yebi_미케05_47.md | HIGH | 6 | 19 | 26 | 丙乙甲 |
| tts-new/2026_minso_yebi_모고01_03.md | MEDIUM | 3 | 18 | 20 | 丁乙甲 |
| tts-new/2026_minso_yebi_미케05_36.md | HIGH | 6 | 18 | 18 | 丙甲 |
| tts/2026_minso_yebi_모고01_03.md | MEDIUM | 3 | 18 | 20 | 丁乙甲 |
| tts/2026_minso_yebi_미케02_09.md | HIGH | 7 | 18 | 21 | 丁乙甲 |
| tts/2026_minso_yebi_미케05_36.md | HIGH | 6 | 18 | 18 | 丙甲 |
| tts-new/2026_minso_yebi_미케02_02.md | HIGH | 6 | 17 | 22 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케04_05.md | HIGH | 5 | 17 | 16 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_02.md | HIGH | 7 | 17 | 16 | 丙乙甲 |
| tts-new/2026_minso_yebi_모고01_04.md | HIGH | 5 | 16 | 19 | 丙甲 |
| tts-new/2026_minso_yebi_미케03_01.md | MEDIUM | 4 | 16 | 13 | 丙乙甲 |
| tts/2026_minso_yebi_모고01_04.md | HIGH | 5 | 16 | 19 | 丙甲 |
| tts-new/2026_minso_yebi_미케02_13.md | HIGH | 5 | 15 | 18 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케04_03.md | MEDIUM | 4 | 15 | 16 | 乙甲 |
| tts-new/2026_minso_yebi_미케04_07.md | HIGH | 7 | 15 | 23 | 乙甲 |
| tts-new/2026_minso_yebi_미케04_30.md | HIGH | 5 | 15 | 14 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_10.md | HIGH | 7 | 15 | 17 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_43.md | HIGH | 5 | 15 | 12 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케05_44.md | HIGH | 6 | 15 | 10 | 乙甲 |
| tts/2026_minso_yebi_미케02_13.md | HIGH | 5 | 15 | 18 | 丙乙甲 |
| tts/2026_minso_yebi_미케04_30.md | HIGH | 5 | 15 | 14 | 乙甲 |
| tts/2026_minso_yebi_미케05_43.md | HIGH | 5 | 15 | 12 | 丙乙甲 |
| tts/2026_minso_yebi_미케05_44.md | HIGH | 6 | 15 | 10 | 乙甲 |
| tts-new/2026_minso_yebi_미케05_48.md | MEDIUM | 4 | 14 | 12 | 乙甲 |
| tts/2026_minso_yebi_미케01_04.md | CRITICAL | 10 | 14 | 19 | 乙甲 |
| tts/2026_minso_yebi_미케05_48.md | MEDIUM | 4 | 14 | 12 | 乙甲 |
| tts-new/2026_minso_yebi_미케01_03.md | HIGH | 5 | 13 | 15 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케02_04.md | MEDIUM | 4 | 13 | 13 | 丁乙甲 |
| tts-new/2026_minso_yebi_미케02_11.md | HIGH | 5 | 13 | 17 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케03_15.md | MEDIUM | 4 | 13 | 23 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케05_09.md | HIGH | 5 | 13 | 11 | 丙乙甲 |
| tts/2026_minso_yebi_미케02_11.md | HIGH | 5 | 13 | 17 | 丙乙甲 |
| tts/2026_minso_yebi_미케03_15.md | MEDIUM | 4 | 13 | 23 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케01_04.md | HIGH | 7 | 12 | 18 | 乙甲 |
| tts-new/2026_minso_yebi_미케02_01.md | MEDIUM | 3 | 12 | 8 | 丙乙甲 |
| tts-new/2026_minso_yebi_미케02_14.md | MEDIUM | 4 | 12 | 15 | 乙甲 |
| tts-new/2026_minso_yebi_미케03_06.md | MEDIUM | 3 | 12 | 21 | 丙乙甲 |

...(이하 71개 행 생략 — 같은 패턴 인명 한자 잔존)

## 권장 조치

1. **인명 한자 일괄 치환** (R-05): `甲→갑, 乙→을, 丙→병, 丁→정, 戊→무` — ORIGIN 섹션 제외, TTS body(Lv.1/Lv.4/답안/문제) 한정.
2. **法 용어 한자 치환**: `知·不知 → 지·부지` (3 파일, 6 라인).
3. **자동 sed 일괄 치환 금지** — ORIGIN 섹션의 PDF 보존본을 훼손할 위험. 섹션 인식 후 TTS body만 적용 필요.
4. **양쪽 디렉토리 모두 적용**: tts-new(현행 작업) + tts(archive). 단 archive는 history 보존 정책 확인 후 결정.

## 검증 절차

- 한자 정규식: `[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]` (CJK Unified Ideographs + Ext A + Compatibility)
- 섹션 분류: H2 헤딩 키워드 기반
  - ORIGIN: `## 원본` (PDF 보존, R-05 OK)
  - TTS: `## 답안 / Lv.1~4 / 목차 / 결론 / 문제 / 요지`
  - META: `## 메타 / diff / 체크 / 로그 / QA / 변환 / 적용 / 판사 / 수험생 / R-`
- 컨텍스트 분석: 각 라인의 H2 섹션 + 인접 인용 구조 확인 (grep 일괄 X)
