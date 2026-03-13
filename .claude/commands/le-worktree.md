# le-worktree — Lawear 워크트리 규칙

> 모든 코드 작업 시 워크트리를 사용하여 세션 간 충돌을 방지한다.
> 여러 세션이 동시 작업 시 `git add`로 다른 세션 변경사항이 딸려가는 문제 방지.

## 왜 워크트리?
- 여러 세션이 같은 워킹디렉토리에서 작업하면 `git add` 시 다른 세션 변경사항이 딸려감
- 같은 브랜치에서 작업하더라도 워크트리 분리 필수

## 워크트리 생성 (코드 작업 시작 즉시, 예외 없음)

```bash
# 기존 워크트리 확인
git -C /Users/nhn/zman-lab/lawear worktree list

# 생성 (겹치지 않는 이름 사용)
git -C /Users/nhn/zman-lab/lawear worktree add -b wt/{작업명} ../lawear-{작업명} main
```

- `wt/` 접두사로 임시 브랜치 식별
- 작업명은 간결하게 (예: `wt/채팅개선`, `wt/검토강화`)
- **사용자에게 묻지 말고** 바로 생성
- 베이스 브랜치: **main** (develop 아님)

## 워크트리에서 작업

- 모든 파일 수정/읽기는 **워크트리 경로**(`/Users/nhn/zman-lab/lawear-{작업명}/`)에서 수행
- 원본 디렉토리(`/Users/nhn/zman-lab/lawear/`)는 건드리지 않음

## BE 특수 설정 (워크트리에서 서버 실행 시)

> **서버 구조 미정 — TODO**: 서버 구축 시 BE 심링크/환경 설정 확정

현재 확정된 심링크:

```bash
WT=/Users/nhn/zman-lab/lawear-{작업명}
ORIG=/Users/nhn/zman-lab/lawear

# .venv 심링크 (Python 가상환경 — 있으면)
ln -sf $ORIG/.venv $WT/.venv
```

**주의**: 워크트리 제거 시 심링크만 삭제되고 원본은 무사함

## FE 프로젝트 주의사항 (절대 금지!)

- `node_modules`, `.next`, `dist` 등을 **symlink로 워크트리에 연결하지 말 것**
- 워크트리 제거 시 symlink 삭제되면서 **원본 폴더 내용이 비워지는 사고 발생** (2026-02-28 실수)
- 올바른 방법: 워크트리에서 `npm install` 실행 또는 `npx tsc --noEmit`만 수행
- **워크트리 생성 전 미리 판단**: FE 포함 작업이면 node_modules 전략 먼저 결정

## 작업 완료 후 정리 (커밋+푸시 완료 후)

```bash
# 1. 메인에서 머지
git -C /Users/nhn/zman-lab/lawear merge wt/{작업명} --ff-only

# 2. 푸시
git -C /Users/nhn/zman-lab/lawear push

# 3. 워크트리 제거
git -C /Users/nhn/zman-lab/lawear worktree remove ../lawear-{작업명}

# 4. 임시 브랜치 삭제
git -C /Users/nhn/zman-lab/lawear branch -d wt/{작업명}

# 5. gc
git -C /Users/nhn/zman-lab/lawear reflog expire --expire=now --all && git -C /Users/nhn/zman-lab/lawear gc --prune=now
```

## 입력값

