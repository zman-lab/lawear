# SPEC ↔ 스킬 동기화 룰 (영구)

> 모든 `dev-le-17895-new-file-bunseol-{index|a|b|c|d|e|f|g}` 스킬에 적용.
> SPEC = `SESSION_*.md` (이 폴더 내). 스킬 = `.claude/commands/dev-le-17895-new-file-bunseol-*.md`.
> **SPEC = 단일 진실 (single source of truth)**. 스킬은 SPEC를 구현.

---

## 1. SPEC ↔ 스킬 1:1 매핑 (절대 경로)

| 스킬 | SPEC .md | 스킬 .md |
|------|----------|----------|
| `dev-le-17895-new-file-bunseol-index` | `/Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/INDEX.md` | `/Users/nhn/zman-lab/lawear/.claude/commands/dev-le-17895-new-file-bunseol-index.md` |
| `-a` | `.../SESSION_A.md` | `.../dev-le-17895-new-file-bunseol-a.md` |
| `-b` | `.../SESSION_B.md` | `.../dev-le-17895-new-file-bunseol-b.md` |
| `-c` | `.../SESSION_C.md` | `.../dev-le-17895-new-file-bunseol-c.md` |
| `-d` | `.../SESSION_D.md` | `.../dev-le-17895-new-file-bunseol-d.md` |
| `-e` | `.../SESSION_E.md` | `.../dev-le-17895-new-file-bunseol-e.md` |
| `-f` | `.../SESSION_F.md` | `.../dev-le-17895-new-file-bunseol-f.md` |
| `-g` | `.../SESSION_G.md` | `.../dev-le-17895-new-file-bunseol-g.md` |

---

## 2. 스킬 헤더 강제 메타 (자기 SPEC 경로 박기)

각 스킬 작성 시 frontmatter에 다음 명시 강제:

```yaml
---
name: dev-le-17895-new-file-bunseol-{x}
description: ...
spec_path: /Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SESSION_{X}.md
master_skill: dev-le-17895-new-file-bunseol-index
---
```

- `spec_path`: 스킬이 자기 SPEC을 알고 있음 (개편 시 자동 참조)
- `master_skill`: 서브 스킬이 마스터를 알고 있음 (호출 흐름)

---

## 3. 스킬 개편 시 절대 강제 룰 (위반 시 작업 무효)

사용자가 다음 발화 시 = 스킬 개편 트리거:
- "스킬 개편하자"
- "스킬 수정해"
- "이 스킬에 X 추가"
- "이 스킬에서 Y 빼"
- "이 룰 바꿔"
- 기타 스킬 동작/룰 변경 요청

**강제 절차**:

1. **본 SPEC 절대 경로 출력** — 사용자가 알 수 있게 (frontmatter `spec_path` 또는 본 룰 표 참조)
2. **SPEC .md 먼저 Read** — 현행 룰 + 사용자 변경 확인
3. **SPEC .md 먼저 수정** — 변경 사항 명시
4. **변경된 SPEC .md 사용자에게 보여주기** — 절대 경로 + diff 또는 변경 영역 발췌
5. **사용자 OK 신호 받기** — 자동 진행 X
6. **사용자 OK 후 스킬 .md 수정** — SPEC 근거로 수정
7. **SPEC ↔ 스킬 일치 강제** — SPEC에 없는 룰 스킬에 박지 X
8. **사용자가 SPEC 무시하고 스킬만 직접 수정 요청** → **거부** → SPEC 먼저 수정 권장

---

## 4. 사용자 변경 보존 룰

사용자가 SPEC .md 직접 수정한 케이스:
- 도비/AI가 Edit 시 사용자 변경 영역 절대 노터치
- Read 후 사용자 변경 영역 식별 (linter/사용자 표시 또는 git diff)
- 사용자 변경 보존하고 새 룰 추가

---

## 5. 마스터 스킬 (`-index`) 특화 룰

마스터 스킬은 모든 서브 스킬 SPEC 경로를 알고 있어야 함.

마스터 스킬 frontmatter:
```yaml
---
name: dev-le-17895-new-file-bunseol-index
description: ...
spec_path: /Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/INDEX.md
sub_skills:
  - dev-le-17895-new-file-bunseol-a → SESSION_A.md
  - dev-le-17895-new-file-bunseol-b → SESSION_B.md
  - dev-le-17895-new-file-bunseol-c → SESSION_C.md (선택)
  - dev-le-17895-new-file-bunseol-d → SESSION_D.md (선택)
  - dev-le-17895-new-file-bunseol-e → SESSION_E.md
  - dev-le-17895-new-file-bunseol-f → SESSION_F.md
  - dev-le-17895-new-file-bunseol-g → SESSION_G.md
spec_sync_rules: /Users/nhn/zman-lab/lawear/docs/lawear-da75_bunseol_rework/SPEC_SYNC_RULES.md
---
```

마스터 호출 시 사용자에게 출력:
- 워크플로우 (4-2-1 라운드)
- 브랜치 전략
- 각 서브 스킬 SPEC 경로
- 본 SPEC_SYNC_RULES.md 참조

---

## 6. 새 스킬 추가 시 (확장)

향후 `dev-le-17895-new-file-bunseol-h`, `-i`, `-j` 등 신규 서브 스킬 추가 시:

1. 새 SPEC `SESSION_H.md` (또는 사용자 명명) 작성 — 본 동기화 룰 절 포함
2. 본 `SPEC_SYNC_RULES.md` §1 매핑 표에 추가
3. 마스터 스킬 frontmatter `sub_skills` list 갱신
4. INDEX.md §6 (7 세션 역할 표) 갱신
5. 새 스킬 작성 시 본 룰 적용

---

## 7. 검증 (스킬 개편 후)

- [ ] SPEC `.md`에 변경 사항 명시 완료
- [ ] 사용자 OK 신호 받음
- [ ] 스킬 `.md`가 SPEC와 일치 (SPEC에 없는 룰 0)
- [ ] 스킬 frontmatter `spec_path` 정합
- [ ] 마스터 스킬 `sub_skills` 갱신 (신규 스킬 추가 시)
- [ ] 사용자 변경 영역 보존
