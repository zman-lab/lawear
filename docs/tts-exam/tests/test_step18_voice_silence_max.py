#!/usr/bin/env python3
"""Step 18 — 음성 silence_sec max 10 → 60 회귀.

사용자 명시 (2026-05-16):
    "잘 생각 안 나면 고민할 수도 있단 말야"
    → 무음 자동 종료 임계치 1~10초 → 1~60초로 확장.

검증:
- VOICE_SILENCE_MAX 상수 = 60
- validate_voice: 60 입력 시 OK
- validate_voice: 61 입력 시 SettingsValidationError(bad_request)
- 하한 1 OK / 0 fail / -1 fail 회귀 (기존 동작 보존)

실행:
    cd docs/tts-exam
    python3 -m pytest tests/test_step18_voice_silence_max.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 본 모듈 import (tests/ → 부모 docs/tts-exam)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings as settings_mod  # noqa: E402


class VoiceSilenceMaxTest(unittest.TestCase):
    """Step 18 — silence_sec 1~60 검증."""

    def test_constant_max_is_60(self) -> None:
        """상수 VOICE_SILENCE_MAX 가 60 으로 갱신됐는지."""
        self.assertEqual(settings_mod.VOICE_SILENCE_MAX, 60)

    def test_constant_min_unchanged_1(self) -> None:
        """하한은 기존 1 그대로 (회귀)."""
        self.assertEqual(settings_mod.VOICE_SILENCE_MIN, 1)

    def test_validate_voice_accepts_60(self) -> None:
        """silence_sec=60 → OK."""
        out = settings_mod.validate_voice({"lang": "ko-KR", "silence_sec": 60})
        self.assertEqual(out["silence_sec"], 60)
        self.assertEqual(out["lang"], "ko-KR")

    def test_validate_voice_accepts_30(self) -> None:
        """silence_sec=30 (기존 max=10 외, 신규 범위 내) → OK."""
        out = settings_mod.validate_voice({"lang": "ko-KR", "silence_sec": 30})
        self.assertEqual(out["silence_sec"], 30)

    def test_validate_voice_rejects_61(self) -> None:
        """silence_sec=61 → SettingsValidationError(bad_request)."""
        with self.assertRaises(settings_mod.SettingsValidationError) as ctx:
            settings_mod.validate_voice({"lang": "ko-KR", "silence_sec": 61})
        self.assertEqual(ctx.exception.error_code, "bad_request")
        self.assertIn("silence_sec", str(ctx.exception))

    def test_validate_voice_rejects_0(self) -> None:
        """하한 회귀: silence_sec=0 → bad_request."""
        with self.assertRaises(settings_mod.SettingsValidationError) as ctx:
            settings_mod.validate_voice({"lang": "ko-KR", "silence_sec": 0})
        self.assertEqual(ctx.exception.error_code, "bad_request")

    def test_validate_voice_accepts_1_boundary(self) -> None:
        """경계: silence_sec=1 OK."""
        out = settings_mod.validate_voice({"lang": "ko-KR", "silence_sec": 1})
        self.assertEqual(out["silence_sec"], 1)


if __name__ == "__main__":
    unittest.main()
