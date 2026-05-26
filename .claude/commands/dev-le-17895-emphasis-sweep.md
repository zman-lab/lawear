# dev-le-17895-emphasis-sweep — em1~em4 + 폰트 5종 + 여분 강조 sweep (서브 스킬)

> `dev-le-17895-yearly` Phase C. R-09 검증 완료된 Lv.4 본문에 의미별 강조 일관 적용.
>
> **단독 호출도 가능**: 사용자가 특정 케이스 강조 재적용 의뢰 시.

## 사용 시점

- Phase B R-09 sweep 완료 후
- 새 케이스 .md 변환 후 강조 적용
- 사용자가 강조 시스템 갱신 의뢰

## 절대 규칙

1. **R-09 위반 본문에 강조 적용 X** (Phase B 통과 후 진행)
2. **Opus 5~10명 ultrathink 강제** (의미 분석)
3. **자동 substring 매칭 X** — 의미별 정확 분석
4. **사용자 기존 강조 초기화** (`[red]/[blue]/[purple]` 등) 후 신규 시스템 재적용 (사용자 명시)
5. **stealth 모드 호환** (merge.html `body.stealth` 셀렉터에 신규 태그 등록 — lawear-103a 완료)
6. **em 글자 길이 룰 절대 없음** — em1~em4는 **두문자 뎁스**만 기준. "1글자 룰"·"2글자 강등" 등 자의 해석 금지. 라이브러리 실 적용 정답(`[em1]단체[/em1]`/`[em1]가해자 불명[/em1]`/`[em1]공분청[/em1]` 등 다단어 다수) 패턴 mirror.
7. **자의 해석 금지** — 스킬·메모리·라이브러리 명시 룰 외 새 룰 도출 금지. QA가 "X 룰 위반" 운운 시 메인이 근거 검증 후 reject.
8. **QA 권고 근거 의무** — 부장판사·강사가 권고/지적 시 파일경로+라인/PDF+페이지/URL 등 실존 근거 제시 강제. 근거 없으면 자동 reject.

## 강조 시스템 13종

### em 시스템 (배경 + 흰글, 라이브러리 두문자 뎁스)

| 태그 | 색 | 의미 |
|------|----|------|
| `[em1]` | 빨 #c92a2a / 흰 | 메인 두문자 글자 (라이브러리 카테고리) |
| `[em2]` | 노 #f59f00 / 흰 | 메인 풀이 첫 글자 |
| `[em3]` | 파 #1971c2 / 흰 | 풀이형 보조 두문자 |
| `[em4]` | 보 #6741d9 / 흰 | 풀이형 풀이 키워드 |

### 폰트 시스템 (텍스트 색, Lv.4 케이스 의미별)

| 태그 | 색 | 의미 |
|------|----|------|
| `[con]` | 빨 (다크 #ff6b6b) | 결론 문장 ⭐ |
| `[fact]` | 주황 (다크 #ff922b) | 요건 사실 |
| `[case]` | 초록 (다크 #51cf66) | 중요 판례 |
| `[bridge]` | 파랑 (다크 #339af0) | 논리 전개 ("따라서", "사안의 경우" 등) |
| `[key]` | 보라 (다크 #9775fa) | 주요 쟁점·핵심 |

### 여분 시스템 (사용자 자유)

| 태그 | 색 | 의미 |
|------|----|------|
| `[free1]` | 베이지 (다크 #ddc9a3) | 사실관계 배경 / 부가 정보 |
| `[free2]` | 라벤더 (다크 #b197fc) | 부수 키워드 / 약한 핵심 |

### 효과 (어느 태그와도 중첩 OK)

- `[u]` 밑줄
- `[bold]` 굵게 (컬러 태그는 자동 굵게, [bold]는 색 없이 굵게만)

## 적용 룰

### 라이브러리 (두문자/민법.md, 민소.md, _pdf_원문_*.md)

- 메인 두문자 라인: `- **두문자 (XXX)**: 동·공` → 글자 `[em1]` 감싸기
- 메인 풀이: `- **풀이형 (XXX)**: **동**종 소송절차` → `[em2]동[/em2]종 소송절차`
- 풀이형 보조 두문자: `격·추 이익` → `[em3]격[/em3]·[em3]추[/em3] 이익`
- 풀이형 풀이 키워드 (em-dash 뒤 markdown bold): `(당사자) **적격**` → `(당사자) [em4]적격[/em4]`
- 본문 템플릿 `[blank2]X[/blank2]` → `[em1]X[/em1]` 일괄

### Lv.4 케이스 본문

- 결론 문장 ("결론, ~"): `[con]결론, ~[/con]`
- 사실관계 / 요건 사실: `[fact]압류 및 추심명령이 송달[/fact]`
- 인용 판례 ("판례는 ~ 했다"): `[case]변경판례는 당사자적격을 상실하지 않는다[/case]`
- 추론 연결어 ("따라서", "사안의 경우"): `[bridge]따라서[/bridge]`
- 그 외 핵심 키워드: `[key]시효중단·제소기간 준수 이익[/key]`
- 자유 강조: `[free1]` 또는 `[free2]`

## 분담 (Opus 5~10명 병렬)

R-09 sweep과 동일 디렉토리 분담:
- E-1 입문_민법 (60)
- E-2 입문_민소 (34)
- E-3 예비_민법 (55~58)
- E-4 예비_민소 (52~95)
- E-5 archive 예비_민법 (58)
- E-6 archive 예비_민소 (56)
- E-Lib 라이브러리 (두문자/민법.md + 민소.md + _pdf_원문_*.md, 라이브러리만 별도 분담)

## 각 Opus 프롬프트 (필수 룰)

```
[역할] lawear Lv.4 강조 sweep — {디렉토리} (Phase C, ultrathink + Opus 강제)

[배경]
- Phase B R-09 sweep 완료 (위반 0건 보장)
- 사용자 기존 [red]/[blue]/[purple]/[u]/[bold]/[blank] 초기화 후 신규 시스템 재적용
- 강조 시스템 13종 (em1~em4 + con/fact/case/bridge/key + free1/2) 의미별 분석

[수행 — 파일별]
1. Read로 .md 전체 읽기 (## 원본 + Lv.1~4)
2. 기존 강조 태그 제거 (사용자 명시 — 초기화 후 재적용)
3. ## 원본 의미 분석:
   - 결론 위치 → [con]
   - 요건 사실 위치 → [fact]
   - 인용 판례 → [case]
   - 추론 연결어 → [bridge]
   - 핵심 쟁점·키워드 → [key]
4. 라이브러리 두문자 라인 (em1~em4):
   - 메인 두문자 글자 → [em1]
   - 메인 풀이 첫 글자 → [em2]
   - 풀이형 보조 두문자 → [em3]
   - 풀이형 풀이 키워드 → [em4]
5. 자유 강조 위치 (옵션) → [free1] / [free2]
6. Edit으로 강조 태그 인라인 삽입

[제약]
- Opus + ultrathink (Sonnet/Haiku 금지)
- 자동 substring X (의미 매칭만)
- ## 원본 섹션 강조 X (채점 기준 본문, 강조 추가도 R-09 위반)
- 효과 [u]/[bold]는 어느 태그와도 중첩 OK
- 비용 안 아낌 (사용자 명시)
```

## 출력 JSON 스키마 (각 Opus 반환)

```json
{
  "phase": "C-X",
  "directory": "...",
  "total_files": 0,
  "emphasis_applied": {
    "em1": 0, "em2": 0, "em3": 0, "em4": 0,
    "con": 0, "fact": 0, "case": 0, "bridge": 0, "key": 0,
    "free1": 0, "free2": 0
  },
  "previous_emphasis_removed": {
    "red": 0, "blue": 0, "purple": 0, "blank": 0, "blank2": 0, "u": 0, "bold": 0
  },
  "files_processed": 0,
  "files_skipped_no_lv4": 0,
  "report_path": "..."
}
```

## 메인 후속 처리

1. Opus 결과 통합
2. 사용자 시각 검증 권장 (17895 새로고침)
3. 강조 위치 어색한 케이스 spot-check
4. git commit + push

## Dry-run 모드 (`--dry-run`, 2026-05-26 추가)

본 sweep 시작 전 영향 분석. **실제 .md 수정 X**. lawear-7ea2 docs 손실 사고 후 추가 (사전 영향 분석 필수).

### 사용

```
/dev-le-17895-emphasis-sweep --dry-run --subject=민법 --year=2026 --round=입문
/dev-le-17895-emphasis-sweep --dry-run --subject=민법 --out=/tmp/sweep_preview.md
```

### Dry-run 흐름 (실제 sweep과 동일하나 Edit 호출 X)

1. **대상 파일 식별** (E-1~E-6 + E-Lib 분담과 동일)
2. **각 파일 Read** (Opus 의미 분석)
3. **변경 예측 카운트** (Edit 호출 직전 시뮬레이션):
   - 신규 적용: em1/em2/em3/em4/con/fact/case/bridge/key/free1/2 — 카운트만
   - 기존 제거: red/blue/purple/blank/blank2/u/bold — 카운트만
4. **per-file 변경 요약** + **sample Before/After 5건** (`diff` 형식)
5. **보고서 `.md` 저장** (`--out={경로}`, 미지정 시 stdout)

### Dry-run 출력 형식

```markdown
# Phase C sweep dry-run — {SUBJECT} {YEAR} {ROUND}

## 대상 파일: N개 (E-1 N / E-2 N / ... / E-Lib N)

## 변경 영향 예측 (총합)
- 신규 적용: em1=N / em2=N / em3=N / em4=N / con=N / fact=N / case=N / bridge=N / key=N / free1=N / free2=N
- 기존 제거: red=N / blue=N / purple=N / blank=N / blank2=N / u=N / bold=N
- 순 변경: +N -N = 총 N 강조 변경

## per-file 변경 라인 수 Top 10
| 파일 | 신규 | 제거 | 순 변경 |
|------|------|------|---------|
| ... |

## Sample Before/After (5건)
... (diff 형식, 의미 분석 근거 포함)

## 권고
- 변경 영향 큰 파일 (Top 10) spot-check 후 실제 sweep
- R-09 위반 우려 케이스 (있으면) 별도 표시
- 실제 적용: --dry-run 제거 후 재호출 또는 --apply flag
```

### 실제 적용 (dry-run 검토 후)

```
/dev-le-17895-emphasis-sweep --subject=민법 --year=2026 --round=입문
```

`--dry-run` 없이 호출 시 실제 적용. 또는 `--apply` 명시.

### 권장 워크플로우

1. `--dry-run` 호출 → 영향 분석 보고서
2. 사용자/메인 spot-check (Top 10 변경 큰 파일 + R-09 우려 케이스)
3. 문제 없으면 실제 sweep (Phase C 본 흐름)
4. 결과 즉시 commit + `/dev-push` (사고 재발 방지)

## 메모리 연동

- `feedback_em_color_system.md` — 시안2 색상 정의
- `feedback_em_sweep_rules.md` — 라이브러리 sweep 룰 4단계 (9-2 시범본 정답)
- `feedback_library_template_color.md` — [blue]/[purple] 라이브러리 본문 색상

## 입력값

$ARGUMENTS
