# dev-commit — Lawear 전용 커밋

> /commit의 개인 프로젝트 버전. 테스트 자동수정 루프 + 패스 시만 보고.

## 프로젝트 정보
- **경로**: `/Users/nhn/zman-lab/lawear`
- **브랜치 규칙**: main 직접 커밋 가능. 워크트리 모드일 때는 `wt/*` 브랜치에서 커밋
- **커밋 형식**: `[근형] type: description`
- **types**: feat | fix | refactor | style | docs | chore | test | security
- **Co-Authored-By 절대 금지**

## 실행 순서

### Step 1: 프로젝트 경로 판별
- 워크트리에서 실행 시 `git -C {cwd} rev-parse --show-toplevel`로 실제 프로젝트 루트 확인
- 워크트리 루트를 `{ROOT}`로 사용 (이하 모든 경로의 기준)

### Step 2: 브랜치 확인
```bash
git -C {ROOT} branch --show-current
```
- main이면 그대로 진행 (직접 커밋 허용)
- `wt/*` 또는 `feature/*` 브랜치도 허용
- **develop 또는 master이면 즉시 중단** → "잘못된 브랜치입니다." 경고

### Step 3: 상태 확인
```bash
git -C {ROOT} status
git -C {ROOT} diff --staged --stat
git -C {ROOT} diff --stat
```
- 변경 없으면 "커밋할 내용 없음" 보고 후 종료

### Step 4: 변경 파일 판별
변경된 파일 경로를 분석해 테스트 대상 결정:
- `tests/` 포함 또는 Python 소스 파일 변경 → **테스트 필요**
- 문서만 (`*.md`, `docs/`, `.claude/`) → **테스트 스킵**
- `.commit-test-ignore` 파일에 나열된 패턴은 테스트 판별에서 제외

### Step 5: 테스트 게이트
**테스트 (tests/ 디렉토리가 있을 때만):**
```bash
python -m pytest {ROOT}/tests/ -v --tb=short
```

- 테스트 스킵 조건에 해당하면 이 단계 건너뜀
- tests/ 디렉토리가 없으면 `[테스트 게이트] 테스트 대상 없음 — 스킵` 출력

### Step 6: 테스트 실패 시 자동 수정 루프 (최대 3회)
1. 실패 로그 + 원래 변경 의도를 수집
2. Opus 서브에이전트에 전달: "이 테스트 실패를 수정해줘"
3. 수정 적용 후 재테스트
4. 3회 실패 시 → 사용자에게 보고 후 중단 (강제 커밋 안 함)
- **중간 실패는 사용자에게 보고하지 않음** (조용히 재시도)

### Step 7: git add + commit
```bash
git -C {ROOT} add {변경파일들}
git -C {ROOT} commit -m "[근형] type: description"
```
- `git add .` 지양, 변경 파일 명시적 지정
- **.env, *.db, __pycache__ 는 커밋 대상 아님** — 반드시 제외 확인

### Step 8: push + gc
```bash
git -C {ROOT} push
git -C {ROOT} reflog expire --expire=now --all && git -C {ROOT} gc --prune=now
```

### Step 9: 결과 보고
- 패스 시에만 보고: 커밋 해시, 브랜치, 변경 요약
- 형식:
  ```
  커밋: `해시` - [근형] type: description → 레포: lawear, 브랜치: {브랜치명}
  푸시: lawear → {브랜치명}
  ```
