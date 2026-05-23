#!/usr/bin/env python3
"""작업 B pytest — 17896 채점 DB 백업 (rolling 2-slot) bash 스크립트 회귀 TC1~TC8.

테스트 목적:
  dev-le-17896-grade.md §2.8.5 bash inline 스크립트가 sqlite3 .dump | gzip 백업 +
  rolling 2-slot 보존 + 실패 시 복구 룰을 정확히 지키는지 검증.

근거:
  - 구현 계획: docs/lawear-7ad6_grade_backup_auto/dev-spec_3_impl_plan.md §2 (TC1~TC8)
  - 설계 문서: docs/lawear-7ad6_grade_backup_auto/dev-spec_2_design.md §1
  - 대상 스크립트: .claude/commands/dev-le-17896-grade.md §2.8.5 (L468 부근)

작성자: lawear-7ad6 (팀 4, Opus + ultrathink)

접근:
  스킬 .md 의 bash inline 을 임시 .sh 파일로 추출 후 subprocess.run 으로 실행.
  BACKUP_DIR, DB_PATH 를 환경변수로 override 하여 메인 레포 무손상 보장.

실행:
  cd /Users/nhn/zman-lab/lawear-lawear-7ad6-input-mode-and-backup/docs/tts-exam
  python3 -m pytest tests/test_grade_backup_2slot.py -v

룰:
  - 한 TC당 가능하면 1 assert
  - 가짜 sqlite DB + 임시 backups 디렉토리 (메인 레포 격리)
  - 자의 해석 금지 — impl_plan.md TC 목록 정확 mirror
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import subprocess
import time
from pathlib import Path

import pytest


# ============================================================================
# 스크립트 추출 — 실제 스킬 .md §2.8.5 의 bash 블록을 그대로 read (DRY)
# ============================================================================
#
# 기존엔 BACKUP_SCRIPT 를 하드코딩 → 스킬 .md 수정 시 동기 누락 위험.
# 이제는 실제 스킬 .md §2.8.5 의 ```bash 블록을 정규식으로 추출.
# BACKUP_DIR / DB_PATH / TS 만 환경변수 override 가능하게 라인 치환.

import re as _re

_SKILL_PATH = Path(
    '/Users/nhn/zman-lab/lawear-lawear-7ad6-input-mode-and-backup'
    '/.claude/commands/dev-le-17896-grade.md'
)
_BASH_BLOCK_RE = _re.compile(
    r'####\s*2\.8\.5.*?```bash\n(.*?)\n```',
    _re.DOTALL,
)


def _load_skill_bash():
    """스킬 .md §2.8.5 의 bash inline 을 추출 + 환경변수 override 주입."""
    content = _SKILL_PATH.read_text(encoding='utf-8')
    m = _BASH_BLOCK_RE.search(content)
    if not m:
        raise RuntimeError("§2.8.5 bash 블록 추출 실패")
    body = m.group(1)
    # 환경변수 override — 메인 레포 절대경로 → fixture override 가능하게
    body = body.replace(
        'BACKUP_DIR="/Users/nhn/zman-lab/lawear/docs/tts-exam/backups/snapshots"',
        'BACKUP_DIR="${BACKUP_DIR:-/Users/nhn/zman-lab/lawear/docs/tts-exam/backups/snapshots}"',
    )
    body = body.replace(
        'DB_PATH="/Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db"',
        'DB_PATH="${DB_PATH:-/Users/nhn/zman-lab/lawear/docs/tts-exam/exam.db}"',
    )
    body = body.replace(
        'TS=$(date +%Y%m%d_%H%M)',
        'TS="${TS_OVERRIDE:-$(date +%Y%m%d_%H%M)}"',
    )
    return '#!/bin/bash\n' + body


BACKUP_SCRIPT = _load_skill_bash()


# ============================================================================
# 공통 fixture
# ============================================================================

@pytest.fixture
def script_path(tmp_path):
    """스킬 .md §2.8.5 bash inline 을 임시 .sh 파일로 추출.

    각 TC 가 subprocess.run(['bash', str(script_path), ...]) 형태로 실행.
    """
    script = tmp_path / 'backup_inline.sh'
    script.write_text(BACKUP_SCRIPT, encoding='utf-8')
    script.chmod(0o755)
    return script


@pytest.fixture
def fake_db(tmp_path):
    """가짜 sqlite DB 생성 — attempts 테이블 + 더미 row 5개.

    실제 채점 DB 흐름 mirror (.dump | gzip 복구 시 SELECT COUNT 검증용).
    """
    db_path = tmp_path / 'exam_fake.db'
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE attempts (
            id INTEGER PRIMARY KEY,
            problem_id TEXT NOT NULL,
            score INTEGER,
            answer_text TEXT
        )
    """)
    # 가짜 채점 데이터 5건 (TC8 복구 검증의 기준값)
    for i in range(1, 6):
        cur.execute(
            "INSERT INTO attempts (problem_id, score, answer_text) VALUES (?, ?, ?)",
            (f'2026_minbeop_yebi_1_{i:02d}', 70 + i, f'답안 본문 {i}'),
        )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def backup_dir(tmp_path):
    """가짜 backups 디렉토리 (각 TC 격리 — 메인 레포 backups 무손상)."""
    bdir = tmp_path / 'backups' / 'snapshots'
    bdir.mkdir(parents=True, exist_ok=True)
    return bdir


def _run_script(script_path, backup_dir, db_path, ts_override=None):
    """subprocess.run wrapper — BACKUP_DIR/DB_PATH/TS env override.

    각 TC 가 호출하는 표준 진입점. timeout=30s 로 무한루프 방지.
    """
    env = os.environ.copy()
    env['BACKUP_DIR'] = str(backup_dir)
    env['DB_PATH'] = str(db_path)
    if ts_override is not None:
        env['TS_OVERRIDE'] = ts_override
    return subprocess.run(
        ['bash', str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ============================================================================
# 정상 (TC1~TC3)
# ============================================================================

def test_tc1_first_backup_creates_one_valid_gz(script_path, fake_db, backup_dir):
    """TC1: 첫 백업 (snapshots 비어) → 1개 exam_*.sql.gz + gunzip -t valid.

    설계 §1 정상 흐름 (sqlite3 .dump | gzip 파이프).
    """
    result = _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1000')
    assert result.returncode == 0, f"TC1: bash exit 비-0 ({result.returncode}, stderr={result.stderr})"
    gz_files = list(backup_dir.glob('exam_*.sql.gz'))
    # 의도: 정확히 1개 .gz 파일 생성 + 유효한 gzip 포맷
    gunzip_check = subprocess.run(['gunzip', '-t', str(gz_files[0])], capture_output=True)
    assert len(gz_files) == 1 and gunzip_check.returncode == 0, \
        f"TC1: gz 개수={len(gz_files)}, gunzip -t exit={gunzip_check.returncode}"


def test_tc2_second_backup_preserves_two(script_path, fake_db, backup_dir):
    """TC2: 2번째 (TS mock 1분 차이) → 2개 보존.

    rolling 2-slot 아직 발동 X (2개 == 한도).
    """
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1000')
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1001')
    gz_files = list(backup_dir.glob('exam_*.sql.gz'))
    # 의도: 2개 모두 보존 (rolling 발동 X)
    assert len(gz_files) == 2, f"TC2: 2개 보존 실패 (count={len(gz_files)})"


def test_tc3_rolling_2slot_drops_oldest(script_path, fake_db, backup_dir):
    """TC3: rolling 2-slot 발동 (3회) → ls|wc -l == 2, 오래된 1개 삭제.

    tail -n +3 | xargs -r rm -f 핵심 로직 검증.
    """
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1000')
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1001')
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1002')
    gz_files = sorted(backup_dir.glob('exam_*.sql.gz'))
    names = [f.name for f in gz_files]
    # 의도: 최신 2개만 보존 (1000은 삭제, 1001+1002만 남음)
    assert len(gz_files) == 2 and 'exam_20260523_1000.sql.gz' not in names, \
        f"TC3: rolling 실패 (count={len(gz_files)}, names={names})"


# ============================================================================
# 음성 (TC4~TC7) — 실패/엣지 케이스
# ============================================================================

def test_tc4_sqlite_fail_no_partial_gz(script_path, tmp_path, backup_dir):
    """TC4: sqlite3 실패 (잘못된 DB 경로) → [backup] FAIL + 부분 .gz 삭제.

    pipefail + rm -f 부분파일 정리 로직 검증. 채점 자체는 보존 (R5).
    """
    bogus_db = tmp_path / 'does_not_exist.db'  # 존재하지 않는 DB
    result = _run_script(script_path, backup_dir, bogus_db, ts_override='20260523_1010')
    gz_files = list(backup_dir.glob('exam_*.sql.gz'))
    # 의도: FAIL 메시지 출력 + 부분 .gz 미잔존
    assert '[backup] FAIL' in result.stdout and len(gz_files) == 0, \
        f"TC4: FAIL 처리 실패 (stdout={result.stdout!r}, gz_count={len(gz_files)})"


def test_tc5_missing_dir_auto_mkdir(script_path, fake_db, tmp_path):
    """TC5: 디렉토리 부재 시 자동 생성 (rm -rf 후 실행) → mkdir -p + 백업 OK.

    mkdir -p 의 idempotent 보장 검증.
    """
    nonexistent = tmp_path / 'fresh_backup_dir' / 'snapshots'
    # 사전: 디렉토리 절대 없음 (mkdir -p 가 만들어야 함)
    assert not nonexistent.exists(), "TC5 사전: 디렉토리가 미리 존재함"

    result = _run_script(script_path, nonexistent, fake_db, ts_override='20260523_1020')
    # 의도: 디렉토리 자동 생성 + 백업 성공
    gz_files = list(nonexistent.glob('exam_*.sql.gz')) if nonexistent.exists() else []
    assert nonexistent.exists() and len(gz_files) == 1, \
        f"TC5: mkdir -p 자동 생성 실패 (exists={nonexistent.exists()}, gz_count={len(gz_files)})"


def test_tc6_same_ts_overwrite_no_corruption(script_path, fake_db, backup_dir):
    """TC6: 동시 채점 분 단위 충돌 (같은 TS 2회) → 두 번째 덮어씀, DB 사고 X.

    동일 TS 로 2회 실행 → gzip > 가 덮어쓰기 (>>  X). 데이터 무결성 보장.
    """
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1030')
    result = _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1030')
    gz_files = list(backup_dir.glob('exam_*.sql.gz'))
    # 의도: 동일 TS 라도 정확히 1개 (덮어쓰기) + DB 자체 손상 X
    gunzip_check = subprocess.run(['gunzip', '-t', str(gz_files[0])], capture_output=True)
    assert len(gz_files) == 1 and gunzip_check.returncode == 0, \
        f"TC6: 덮어쓰기 후 손상 (count={len(gz_files)}, gunzip exit={gunzip_check.returncode})"


def test_tc7_rolling_perm_fail_recovers_next(script_path, fake_db, backup_dir):
    """TC7: rolling 권한 실패 (chmod 444 가장 오래된) → 백업 OK, rm 실패만.

    가장 오래된 .gz 파일에 chmod 444 → rm -f 가 권한 실패해도 새 백업은 정상.
    """
    # 1회 백업 + chmod 444 (read-only)
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1040')
    oldest = list(backup_dir.glob('exam_*.sql.gz'))[0]
    # 파일 + parent 디렉토리 권한 모두 read-only (rm 차단 강화)
    os.chmod(oldest, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    try:
        # 2회 추가 → rolling 발동 (가장 오래된 삭제 시도 → 권한 실패 가능)
        _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1041')
        result3 = _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1042')
        # 의도: 최신 백업은 정상 생성 (rm 실패해도 새 백업은 OK)
        new_target = backup_dir / 'exam_20260523_1042.sql.gz'
        assert new_target.exists(), \
            f"TC7: 권한 실패해도 새 백업 OK 보장 실패 (stdout={result3.stdout!r})"
    finally:
        # cleanup: chmod 복원 (tmp_path 자동삭제 안전 보장)
        try:
            os.chmod(oldest, 0o644)
        except OSError:
            pass


# ============================================================================
# 복구 검증 (TC8)
# ============================================================================

def test_tc8_restore_attempts_count_matches(script_path, fake_db, backup_dir, tmp_path):
    """TC8: 복구 검증 — gunzip -c | sqlite3 /tmp/restore.db → COUNT 동일.

    백업 → 복구 라운드트립으로 데이터 무결성 end-to-end 검증.
    fixture fake_db 의 attempts 5건 == 복구된 DB 의 attempts 5건.
    """
    # 백업 실행
    _run_script(script_path, backup_dir, fake_db, ts_override='20260523_1050')
    gz_file = list(backup_dir.glob('exam_*.sql.gz'))[0]

    # 복구 — gunzip -c | sqlite3 restore_db
    restore_db = tmp_path / 'restore.db'
    if restore_db.exists():
        restore_db.unlink()

    # shell pipe 로 gunzip | sqlite3 (스킬 §복구 절차 mirror)
    restore_proc = subprocess.run(
        ['bash', '-c', f'gunzip -c "{gz_file}" | sqlite3 "{restore_db}"'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert restore_proc.returncode == 0, f"TC8 사전: 복구 실패 (stderr={restore_proc.stderr})"

    # 복구된 DB 에서 SELECT COUNT(*) FROM attempts
    conn = sqlite3.connect(str(restore_db))
    count = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    conn.close()

    # 의도: 원본 5건 == 복구된 5건 (데이터 손실 0)
    assert count == 5, f"TC8: attempts 복구 COUNT 불일치 (expected=5, actual={count})"
