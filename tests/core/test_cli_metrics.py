"""``tunallama metrics`` CLI 명령 단위 테스트."""

from __future__ import annotations

import pytest

from tunallama_core.cli.metrics_cmd import run_metrics
from tunallama_core.measurement.organic import record_metric


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TUNA_METRICS_DB", str(tmp_path / "metrics.db"))
    yield


def test_show_empty(capsys):
    rc = run_metrics(action="show")
    assert rc == 0
    out = capsys.readouterr().out
    # db 없음 또는 metric 없음 안내.
    assert "없음" in out


def test_show_summarized(capsys):
    record_metric("standalone_toy_rate", 0.0)
    record_metric("standalone_toy_rate", 1.0)
    rc = run_metrics(action="show")
    assert rc == 0
    out = capsys.readouterr().out
    assert "standalone_toy_rate" in out
    assert "tunaLlama organic metrics" in out


def test_list_action(capsys):
    record_metric("ast_excess_score", 3.0, tool_name="generate_code")
    rc = run_metrics(action="list")
    assert rc == 0
    out = capsys.readouterr().out
    assert "ast_excess_score" in out
    assert "generate_code" in out


def test_path_action(capsys):
    rc = run_metrics(action="path")
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("metrics.db")


def test_clear_action(capsys):
    record_metric("x", 1.0, source="organic")
    record_metric("y", 2.0, source="synthetic")
    rc = run_metrics(action="clear", source="organic")
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 metric 삭제" in out


def test_invalid_action(capsys):
    rc = run_metrics(action="bogus")
    assert rc == 1


def test_source_filter(capsys):
    record_metric("x", 1.0, source="organic")
    record_metric("x", 2.0, source="synthetic")
    rc = run_metrics(action="show", source="organic")
    assert rc == 0
    out = capsys.readouterr().out
    # organic 만 - avg 1.0 (count 1).
    assert "1.00" in out
