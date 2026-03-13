# le-deploy-lock — Lawear 배포 락 프로토콜

> Git 태그 기반 배포 락. 여러 세션이 동시 작업 시 push/배포 충돌 방지.
> Git remote는 모든 세션이 공유하는 유일한 인프라이며 항상 접근 가능.

## 락이 필요한 작업

| 작업 | operation 값 | 이유 |
|------|-------------|------|
| `git push` | `git-push` | 동시 push → non-fast-forward reject |
| main 머지 | `main-merge` | 동시 머지 → 충돌 가능 |
| 서버 restart | `server-restart` | 포트 점유 충돌 |
| 배포 | `deploy` | 서비스 중단 위험 (TODO: 서버 환경 확정 시 구체화) |

## 락 불필요한 작업

워크트리 내 코드 수정, git commit, pytest, tsc --noEmit, git pull, 게시판 읽기/쓰기

## 프로토콜

### 1. 락 확인 + 획득 (ACQUIRE)

```bash
# 태그 fetch
git -C /Users/nhn/zman-lab/lawear fetch origin --tags

# 락 존재 확인
git -C /Users/nhn/zman-lab/lawear ls-remote --tags origin deploy-lock
# → 결과 있으면 차단 (누군가 배포 중). 태그 메시지로 누군지 확인:
#   git -C /Users/nhn/zman-lab/lawear fetch origin tag deploy-lock -f
#   git -C /Users/nhn/zman-lab/lawear tag -l deploy-lock -n1

# 락 없으면 → 획득
git -C /Users/nhn/zman-lab/lawear tag -a deploy-lock -m '{"user":"근형","session":"SESSION_ID","time":"ISO시간","task":"작업내용"}'
git -C /Users/nhn/zman-lab/lawear push origin deploy-lock
# → push 실패? 다른 세션이 먼저 잡음 (git push는 atomic!)
```

### 2. 작업 수행

push, main 머지, 서버 restart, 배포 등 수행.

### 3. 락 해제 (RELEASE)

```bash
git -C /Users/nhn/zman-lab/lawear tag -d deploy-lock
git -C /Users/nhn/zman-lab/lawear push origin :refs/tags/deploy-lock
```

**반드시 해제할 것!** 해제 안 하면 다른 세션이 영원히 차단됨.

### 4. Stale 타임아웃 (3분)

태그가 3분 이상 된 경우 → 세션 크래시로 판단, 강제 해제 허용:

```bash
# 태그 생성 시간 확인
git -C /Users/nhn/zman-lab/lawear for-each-ref --format='%(creatordate:iso)' refs/tags/deploy-lock

# 3분 초과 확인 후 강제 해제
git -C /Users/nhn/zman-lab/lawear tag -d deploy-lock
git -C /Users/nhn/zman-lab/lawear push origin :refs/tags/deploy-lock
```

강제 해제 시 게시판에 알림 글 작성 (best-effort).

## 서버 배포 (사용자 명시적 지시 시에만)

> **TODO**: 서버 환경 미정. 서버 구축 시 아래를 채울 것:
> - SSH 접속 정보 (ssh-manager 프로필명)
> - 배포 명령 (docker compose / systemd / etc.)
> - 헬스 체크 URL

```bash
# 1. 배포 락 획득 (위 프로토콜)
# 2. TODO: SSH 접속
# 3. TODO: git pull
# 4. TODO: 서버 재시작 명령
# 5. TODO: 헬스 체크
# 6. 배포 락 해제
```

**기본 동작: 로컬 실행. 배포는 사용자가 직접 요청할 때만 진행**

## 게시판 알림 (보조, best-effort)

락 획득/해제 시 게시판에 글 작성 (Haiku 위임). 게시판 접근 실패해도 무시.
- 획득: `[배포중] {세션ID} - {작업내용} (예상 N분)`
- 해제: `[배포완료] 정상 복구`

## 데드락 없음 — 근거

- 락이 단일 (deploy-lock 하나뿐) → 순환 대기 불가
- `git push` atomic → 동시 획득 시 한쪽 실패, 재시도
- Stale 타임아웃 3분 → 크래시/강종 시 자동 해제
- Git remote 다운 → push 자체 불가 → 배포도 불가 (정상 차단)

## 입력값

