#!/usr/bin/env python3
"""간단한 .env KEY=VALUE 파서 (외부 dotenv 의존 X).

dev-impl-plan #51 Step 6 6-2 — env 로더.

사용:
    from env_loader import load_env
    load_env()   # docs/tts-exam/.env 자동 탐색 + os.environ 주입
    load_env("/abs/path/to/.env")   # 명시 경로

규칙:
- KEY=VALUE 한 줄당 한 항목
- `#` 시작 줄 + 빈 줄 무시
- VALUE 양끝 ' " 자동 strip (둘 다 지원)
- 이미 os.environ 에 동일 KEY 가 있으면 덮어쓰지 않음 (system env > .env)
- 파일 없으면 silent skip (예외 X — 부팅 정상 진행)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# .env 기본 위치 (이 모듈과 같은 디렉토리)
DEFAULT_ENV_PATH: Path = Path(__file__).parent.resolve() / ".env"


def _strip_quotes(value: str) -> str:
    """value 양끝 single/double quote 한 쌍 제거."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_env(path: str | Path | None = None, *, override: bool = False) -> dict[str, str]:
    """`.env` 파일 → `os.environ` 주입.

    Args:
        path: env 파일 경로. None 이면 DEFAULT_ENV_PATH (`docs/tts-exam/.env`).
        override: True 면 기존 os.environ 값을 덮어씀. 기본 False.

    Returns:
        실제 주입된 KEY → VALUE dict. 파일 없거나 빈 줄만 있으면 {}.
    """
    env_path = Path(path) if path is not None else DEFAULT_ENV_PATH
    if not env_path.is_file():
        # 파일 없으면 silent skip — 시스템 env 만 사용
        return {}

    injected: dict[str, str] = {}
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[env_loader] .env read failed: {e}", file=sys.stderr)
        return {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # KEY=VALUE 분리 — 첫 '=' 만 split
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = _strip_quotes(value.strip())

        # 시스템 env 가 우선 (override=False 기본)
        if not override and key in os.environ:
            continue
        os.environ[key] = value
        injected[key] = value

    if injected:
        # 로그는 KEY 만 (VALUE 는 비밀)
        keys_str = ", ".join(sorted(injected.keys()))
        print(f"[env_loader] loaded from {env_path}: {keys_str}", file=sys.stderr)
    return injected


def main() -> int:
    """CLI: python3 env_loader.py [path]

    주입된 KEY 목록 출력 (VALUE 은 mask).
    """
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    injected = load_env(arg)
    if not injected:
        print("[env_loader] no .env or empty", file=sys.stderr)
        return 0
    for k in sorted(injected.keys()):
        v = injected[k]
        masked = (v[:4] + "…") if len(v) > 4 else "…"
        print(f"  {k} = {masked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
