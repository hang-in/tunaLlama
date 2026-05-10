"""``plugin/hooks/pre_tool_use.py`` 동작 검증 (단위 + stdin 시뮬레이션)."""

from __future__ import annotations

import io
import json
import sys

import pytest

from plugin.hooks.pre_tool_use import _DEFAULT_THRESHOLD_BYTES, evaluate, main


def test_evaluate_skips_non_read_tool():
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x"}}
    assert evaluate(payload, threshold=100) is None


def test_evaluate_skips_when_path_missing():
    payload = {"tool_name": "Read", "tool_input": {}}
    assert evaluate(payload, threshold=100) is None


def test_evaluate_skips_missing_file(tmp_path):
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(tmp_path / "no.py")}}
    assert evaluate(payload, threshold=100) is None


def test_evaluate_skips_directory(tmp_path):
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(tmp_path)}}
    assert evaluate(payload, threshold=100) is None


def test_evaluate_skips_small_file(tmp_path):
    f = tmp_path / "small.py"
    f.write_text("x = 1\n")
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(f)}}
    assert evaluate(payload, threshold=10_000) is None


def test_evaluate_returns_message_for_large_file(tmp_path):
    f = tmp_path / "big.py"
    f.write_text("x = 1\n" * 1000)  # ~6000 bytes
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(f)}}
    msg = evaluate(payload, threshold=5000)
    assert msg is not None
    assert str(f) in msg
    assert "tuna_review_file" in msg
    assert "tuna_explain_file" in msg
    assert "tuna_analyze_files" in msg


def test_main_with_invalid_json_returns_zero(monkeypatch, capsys):
    rc = main(stdin_text="not-json")
    assert rc == 0
    assert capsys.readouterr().err == ""


def test_main_with_empty_input_returns_zero():
    rc = main(stdin_text="")
    assert rc == 0


def test_main_advisory_message_goes_to_stderr(tmp_path, capsys):
    f = tmp_path / "big.py"
    f.write_text("y = 2\n" * 1000)
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(f)}}
    rc = main(stdin_text=json.dumps(payload))
    assert rc == 0
    captured = capsys.readouterr()
    assert "tuna_review_file" in captured.err
    assert captured.out == ""


def test_main_threshold_env_override(tmp_path, monkeypatch, capsys):
    f = tmp_path / "small.py"
    f.write_text("z = 3\n")  # < default threshold
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(f)}}
    monkeypatch.setenv("TUNALLAMA_HOOK_THRESHOLD", "5")  # 매우 낮게
    rc = main(stdin_text=json.dumps(payload))
    assert rc == 0
    assert "tuna_review_file" in capsys.readouterr().err


def test_main_invalid_threshold_env_uses_default(tmp_path, monkeypatch, capsys):
    """비정상 환경변수 → 기본값으로 fallback."""
    f = tmp_path / "small.py"
    f.write_text("a = 1\n")
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(f)}}
    monkeypatch.setenv("TUNALLAMA_HOOK_THRESHOLD", "abc")
    rc = main(stdin_text=json.dumps(payload))
    assert rc == 0
    # 작은 파일이라 default threshold(5000) 미달 → 메시지 없음
    assert capsys.readouterr().err == ""


def test_default_threshold_constant():
    assert _DEFAULT_THRESHOLD_BYTES == 5000
