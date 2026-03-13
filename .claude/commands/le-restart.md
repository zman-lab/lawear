# le-restart — Lawear 서버 재시작 스킬

> BE 서버 상태 확인, 중지, 재시작, 검증을 한번에 처리.
> 독립 스킬 — 세션 활성 여부와 무관하게 단독 호출 가능.
> **nohup 방식** — 세션 종료 후에도 서버 유지.

> **TODO**: 서버 포트/구성 미정. 서버 구축 시 아래 상수를 채울 것.

---

## 경로 상수 (서버 확정 시 업데이트!)

```
PROJECT=/Users/nhn/zman-lab/lawear
LOG_DIR=$PROJECT/logs                  # 로그 디렉토리 (gitignored)
LOG_RETENTION_DAYS=4                  # 로그 보관 기간

# TODO: 서버 구성 확정 시 채울 것
BE_PORT=????                          # BE 포트 미정
BE_DIR=$PROJECT/????                  # BE 디렉토리 미정
```

---

## 실행 순서 (1→N 순서대로, 스킵 금지)

### 1. 상태 확인

```bash
# TODO: BE_PORT 확정 후 아래를 실제 포트로 변경
# lsof -ti :{BE_PORT} 2>/dev/null

echo "TODO: 서버 포트 미정 — 서버 구축 후 이 스킬을 업데이트하세요."
```

각각 실행 중/미실행 상태 출력.

### 2. 기존 프로세스 종료

실행 중인 프로세스가 있을 때만:

```bash
# TODO: BE_PORT 확정 후 활성화
# lsof -ti :{BE_PORT} | xargs kill -9 2>/dev/null
```

종료 후 1초 대기, 포트 해제 확인.
포트 미해제 시 → 사용자에게 알리고 중단.

### 3. 로그 준비

```bash
# 로그 디렉토리 생성
mkdir -p /Users/nhn/zman-lab/lawear/logs

# 4일 초과 로그 삭제
find /Users/nhn/zman-lab/lawear/logs -name "*.log*" -mtime +4 -delete 2>/dev/null
echo "로그 정리 완료 (4일 초과 삭제)"

# 현재 남은 로그
ls -la /Users/nhn/zman-lab/lawear/logs/ 2>/dev/null || echo "로그 없음 (첫 실행)"
```

### 4. BE 재시작

```bash
# TODO: 서버 구조 확정 후 아래 명령 작성
# 예시 (FastAPI 사용 시):
# DATE=$(date +%Y%m%d)
# cd /Users/nhn/zman-lab/lawear/{BE_DIR} && \
#   nohup .venv/bin/uvicorn app.main:app --reload --port {BE_PORT} \
#   >> /Users/nhn/zman-lab/lawear/logs/be-$DATE.log 2>&1 & disown

echo "TODO: BE 재시작 명령 미정 — 서버 구축 후 이 스킬을 업데이트하세요."
```

- **반드시 BE 디렉토리에서 실행** (상대 임포트 때문)
- **nohup + disown** — 세션 종료 후에도 프로세스 유지
- **`>>`로 append** — 같은 날 재시작 시 기존 파일에 이어서 씀

### 5. 검증

```bash
# TODO: 헬스 체크 URL 확정 후 활성화
# curl -sf http://localhost:{BE_PORT}/docs > /dev/null && echo "BE OK" || echo "BE FAIL"

echo "TODO: 헬스 체크 URL 미정 — 서버 구축 후 이 스킬을 업데이트하세요."
```

- OK → 완료 보고
- FAIL → 해당 서버 로그 확인 후 사용자에게 보고

---

## 보고 형식

```
## Lawear 서버 재시작 완료

| 서버 | 포트 | 상태 | PID |
|------|------|------|-----|
| BE   | TODO | OK   | {pid} |

- BE: http://localhost:{BE_PORT}/
- 로그: /Users/nhn/zman-lab/lawear/logs/ (4일 보관)
```

---

## 워크트리 모드

워크트리에서 서버를 띄워야 할 경우:

```bash
WT=/Users/nhn/zman-lab/lawear-{작업명}
DATE=$(date +%Y%m%d)

# .venv 심링크 (Python 가상환경 — 있으면)
ls -la $WT/.venv 2>/dev/null || ln -sf /Users/nhn/zman-lab/lawear/.venv $WT/.venv 2>/dev/null

# 로그 디렉토리 (워크트리도 원본 logs/ 사용)
mkdir -p /Users/nhn/zman-lab/lawear/logs

# TODO: BE 시작 명령 (서버 구조 확정 후 채울 것)
# cd $WT/{BE_DIR} && nohup .venv/bin/uvicorn app.main:app --reload --port {BE_PORT} \
#   >> /Users/nhn/zman-lab/lawear/logs/be-$DATE.log 2>&1 & disown
```

---

## 트러블슈팅

### BE가 안 뜰 때
- `.venv` 없음 → `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- 포트 충돌 → `lsof -ti :{BE_PORT} | xargs kill -9`

### 로그 확인
```bash
# BE 최신 로그
ls -t /Users/nhn/zman-lab/lawear/logs/be-*.log | head -1 | xargs tail -f

# 전체 로그 용량
ls -lh /Users/nhn/zman-lab/lawear/logs/
```

---

## TODO 체크리스트 (서버 구축 시 이 스킬 업데이트!)

- [ ] BE 포트 확정 → `BE_PORT` 설정
- [ ] BE 디렉토리 구조 확정 → `BE_DIR` 설정
- [ ] 실행 명령 확정 (uvicorn / gunicorn / 기타)
- [ ] 헬스 체크 URL 확정
- [ ] venv 경로 확정 (`.venv` 또는 시스템 python3)
- [ ] FE 서버 여부 결정 (있으면 FE 재시작 단계 추가)
- [ ] ngrok 필요 여부 결정

---

## 입력값

