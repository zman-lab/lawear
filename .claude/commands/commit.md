# Git 커밋 스킬

프로젝트에 변경사항을 커밋하고 푸시합니다.

## 사용법

```
/commit [프로젝트경로] [커밋메시지]
```

- 프로젝트경로 생략 시: 현재 작업 중인 프로젝트 자동 감지
- 커밋메시지 생략 시: 변경사항 분석 후 자동 생성

## 필수 규칙 (절대 준수)

### 1. 브랜치 확인 (커밋 전 필수)
```bash
git -C {프로젝트경로} branch --show-current
```
- **develop, master 브랜치면 즉시 중단**
- 작업 브랜치가 아니면 사용자에게 경고

### 2. git -C 플래그 사용 (필수)
working directory 문제 방지를 위해 **모든 git 명령어에 `-C` 플래그 사용**:
```bash
# 올바른 방법
git -C /Users/nhn/zman-lab/lawear status
git -C /Users/nhn/zman-lab/lawear add ...
git -C /Users/nhn/zman-lab/lawear commit ...

# 잘못된 방법 (사용 금지)
cd /path/to/project && git status
git status  # working directory가 다르면 실패
```

### 3. 커밋 메시지 형식
```
[근형] 작업내용
```
- **Co-Authored-By 절대 금지**
- 작업자 이름은 항상 "근형"

### 4. push 후 gc 실행 (필수)
```bash
git -C {프로젝트경로} reflog expire --expire=now --all && git -C {프로젝트경로} gc --prune=now
```

## 실행 순서

### Step 1: 브랜치 확인
```bash
git -C {프로젝트경로} branch --show-current
```
- develop/master면 중단하고 경고

### Step 2: 상태 확인
```bash
git -C {프로젝트경로} status
git -C {프로젝트경로} diff --stat
```

### Step 3: 테스트 게이트 (커밋 전 필수!)
프로젝트 타입을 감지하여 해당 테스트를 실행합니다. **테스트 실패 시 커밋을 중단**합니다.

#### 프로젝트 타입 감지
```bash
# python 프로젝트: pyproject.toml 또는 setup.py 존재
# node 프로젝트: package.json 존재
# 둘 다 없으면: 테스트 게이트 스킵 (경고 출력)
```

#### python 프로젝트
```bash
# tests/ 디렉토리가 있을 때만 실행
if [ -d "{프로젝트경로}/tests" ]; then
  # .commit-test-ignore 파일이 있으면 --ignore 옵션으로 제외
  # 파일 형식: 한 줄에 하나씩 제외할 경로 (# 주석 가능)
  # 예: tests/test_fpdf.py
  #     tests/legacy/
  IGNORE_OPTS=""
  if [ -f "{프로젝트경로}/.commit-test-ignore" ]; then
    while IFS= read -r line; do
      line=$(echo "$line" | sed 's/#.*//' | xargs)  # 주석/공백 제거
      [ -n "$line" ] && IGNORE_OPTS="$IGNORE_OPTS --ignore={프로젝트경로}/$line"
    done < "{프로젝트경로}/.commit-test-ignore"
  fi
  python -m pytest {프로젝트경로}/tests/ -v --tb=short $IGNORE_OPTS
fi
```
- **ALL PASS 확인 후 다음 단계로 진행** (`.commit-test-ignore`에 명시된 테스트는 제외)
- 실패 시: 커밋 중단 + 실패 내용 보고 + 수정 제안
- `.commit-test-ignore` 파일이 없으면 기존 동작 (모든 테스트 실행)

#### node 프로젝트
```bash
# tsconfig.json이 있을 때만 실행
if [ -f "{프로젝트경로}/tsconfig.json" ]; then
  {프로젝트경로}/node_modules/.bin/tsc --noEmit --project {프로젝트경로}/tsconfig.json
fi
```
- **에러 없음 확인 후 다음 단계로 진행**
- 실패 시: 커밋 중단 + 타입 에러 목록 보고

#### 테스트 없는 프로젝트
- tests/ 디렉토리도 없고 tsconfig.json도 없으면 게이트 스킵
- 콘솔에 `[테스트 게이트] 테스트 대상 없음 — 스킵` 출력

#### 테스트 통과 시
- 콘솔에 `[테스트 게이트 PASS]` 출력 후 다음 단계 진행

### Step 4: 파일 추가
```bash
# 특정 파일만 추가 (권장)
git -C {프로젝트경로} add "파일1" "파일2"

# 전체 추가 (주의: .env 등 민감파일 확인)
git -C {프로젝트경로} add -A
```

### Step 5: 커밋
```bash
git -C {프로젝트경로} commit -m "[근형] 커밋메시지"
```

### Step 6: 푸시
```bash
git -C {프로젝트경로} push
```

### Step 7: gc 실행
```bash
git -C {프로젝트경로} reflog expire --expire=now --all && git -C {프로젝트경로} gc --prune=now
```

### Step 8: 결과 보고
```
**커밋 완료**
- 브랜치: {브랜치명}
- 커밋: {커밋해시}
- 메시지: [근형] {메시지}
- 테스트: {PASS / 스킵 (사유)}
```

## 프로젝트 경로 목록

| 프로젝트 | 경로 |
|---------|------|
| lawear | `/Users/nhn/zman-lab/lawear` |

## 트러블슈팅

### "not a git repository" 에러
**원인**: working directory가 프로젝트 루트가 아님
**해결**: `git -C {프로젝트경로}` 플래그 사용

### 브랜치가 develop/master인 경우
**해결**:
```bash
git -C {프로젝트경로} checkout -b feature/{작업명}
```

## 예시

### 기본 사용
```
/commit
```
→ 현재 프로젝트 감지, 변경사항 확인 후 커밋

### 프로젝트 지정
```
/commit lawear
```

### 메시지 지정
```
/commit lawear "버그 수정"
```
→ `[근형] 버그 수정` 으로 커밋
