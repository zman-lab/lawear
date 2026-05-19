"""lawear-9bdc/typo-system-v2 — ai_corrector.py 단위 테스트.

ANTHROPIC_API_KEY 없음 / mock urlopen / parse 변형 / 중복 from 처리.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error

import pytest

PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)

import ai_corrector  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """각 TC 마다 ANTHROPIC_API_KEY 환경 제거 — TC 가 명시적으로 set 해야 동작."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _mock_response(corrections_list):
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({"corrections": corrections_list}, ensure_ascii=False),
            }
        ]
    }


def test_is_available_no_key():
    assert ai_corrector.is_available() is False


def test_is_available_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert ai_corrector.is_available() is True


def test_correct_no_key_graceful():
    out, corrs = ai_corrector.correct_with_ai("test text")
    assert out == "test text"
    assert corrs == []


def test_correct_too_long_skip():
    long_text = "a" * 8001
    out, corrs = ai_corrector.correct_with_ai(long_text, api_key="dummy-key")
    assert out == long_text
    assert corrs == []


def test_correct_empty_input():
    out, corrs = ai_corrector.correct_with_ai("")
    assert out == ""
    assert corrs == []


def test_correct_success_simple(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mock_resp = _mock_response([
        {"from": "둑은", "to": "또는", "reason": "STT 오타"}
    ])
    monkeypatch.setattr(ai_corrector, "_call_anthropic_api", lambda *a, **k: mock_resp)

    out, corrs = ai_corrector.correct_with_ai("둑은 공동 채무자")
    assert out == "또는 공동 채무자"
    assert len(corrs) == 1
    assert corrs[0]["from"] == "둑은"
    assert corrs[0]["to"] == "또는"
    assert corrs[0]["source"] == "ai"


def test_correct_skip_duplicate_with_static(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mock_resp = _mock_response([
        {"from": "둑은", "to": "또는", "reason": "AI 중복 보고"}
    ])
    monkeypatch.setattr(ai_corrector, "_call_anthropic_api", lambda *a, **k: mock_resp)

    static_corrs = [{"from": "둑은", "to": "또는", "source": "static_dict"}]
    out, corrs = ai_corrector.correct_with_ai("text", static_corrections=static_corrs)
    # static 에 이미 있으므로 ai 결과 추가 X
    assert corrs == []
    assert out == "text"  # 변경 없음 — 이미 정적이 적용했다고 가정


def test_correct_timeout_graceful(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def _raise(*a, **k):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(ai_corrector, "_call_anthropic_api", _raise)
    out, corrs = ai_corrector.correct_with_ai("test text")
    assert out == "test text"
    assert corrs == []


def test_correct_http_error_graceful(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def _raise(*a, **k):
        raise urllib.error.HTTPError("url", 500, "server error", {}, None)

    monkeypatch.setattr(ai_corrector, "_call_anthropic_api", _raise)
    out, corrs = ai_corrector.correct_with_ai("test text")
    assert out == "test text"
    assert corrs == []


def test_correct_url_error_graceful(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def _raise(*a, **k):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(ai_corrector, "_call_anthropic_api", _raise)
    out, corrs = ai_corrector.correct_with_ai("test text")
    assert out == "test text"
    assert corrs == []


def test_correct_unexpected_error_graceful(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def _raise(*a, **k):
        raise RuntimeError("unexpected weirdness")

    monkeypatch.setattr(ai_corrector, "_call_anthropic_api", _raise)
    out, corrs = ai_corrector.correct_with_ai("test text")
    assert out == "test text"
    assert corrs == []


def test_parse_corrections_with_code_block_json():
    text = (
        "```json\n"
        '{"corrections": [{"from": "abc", "to": "xyz", "reason": "test"}]}\n'
        "```"
    )
    out = ai_corrector._parse_corrections(text)
    assert len(out) == 1
    assert out[0]["from"] == "abc"
    assert out[0]["source"] == "ai"


def test_parse_corrections_with_code_block_plain():
    text = (
        "```\n"
        '{"corrections": [{"from": "abc", "to": "xyz"}]}\n'
        "```"
    )
    out = ai_corrector._parse_corrections(text)
    assert len(out) == 1
    assert out[0]["from"] == "abc"


def test_parse_corrections_invalid_json():
    out = ai_corrector._parse_corrections("not json at all")
    assert out == []


def test_parse_corrections_empty_corrections():
    out = ai_corrector._parse_corrections('{"corrections": []}')
    assert out == []


def test_parse_corrections_dedupe_from():
    text = json.dumps(
        {
            "corrections": [
                {"from": "abc", "to": "xyz", "reason": "first"},
                {"from": "abc", "to": "qqq", "reason": "duplicate from"},
            ]
        }
    )
    out = ai_corrector._parse_corrections(text)
    assert len(out) == 1
    assert out[0]["to"] == "xyz"


def test_parse_corrections_filter_empty_and_identical():
    text = json.dumps(
        {
            "corrections": [
                {"from": "", "to": "x"},
                {"from": "a", "to": ""},
                {"from": "same", "to": "same"},
                {"from": "valid", "to": "ok"},
            ]
        }
    )
    out = ai_corrector._parse_corrections(text)
    assert len(out) == 1
    assert out[0]["from"] == "valid"


def test_parse_corrections_jsonblock_with_extra_text():
    text = (
        "Sure, here is the response:\n"
        '{"corrections": [{"from": "Q", "to": "R", "reason": "wat"}]}\n'
        "End of response."
    )
    out = ai_corrector._parse_corrections(text)
    assert len(out) == 1
    assert out[0]["from"] == "Q"


def test_correct_long_from_first_applied(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # 짧은 'abc' 와 긴 'abc def' 모두 매칭 후보 — 긴 from 부터 적용해야 substring 충돌 방지
    mock_resp = _mock_response([
        {"from": "abc", "to": "AAA", "reason": "short"},
        {"from": "abc def", "to": "BBBBB", "reason": "long"},
    ])
    monkeypatch.setattr(ai_corrector, "_call_anthropic_api", lambda *a, **k: mock_resp)

    out, corrs = ai_corrector.correct_with_ai("abc def 입력")
    # 긴 키부터 — 'abc def' → 'BBBBB' 적용 후 'abc' 는 'BBBBB' 안에 없음
    assert "BBBBB" in out
    # corrs 에 2건 다 들어가지만 짧은 건 적용 안 됨 (in 검사 fail)
    assert any(c["from"] == "abc def" for c in corrs)
