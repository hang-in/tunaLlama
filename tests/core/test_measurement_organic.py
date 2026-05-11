"""organic dogfooding metric 수집 단위 테스트."""

from __future__ import annotations

import pytest

from tunallama_core.measurement.organic import (
    clear_metrics,
    collect_organic_after_delegation,
    list_metrics,
    record_metric,
    summarize_metrics,
)


@pytest.fixture(autouse=True)
def isolated_metrics_db(tmp_path, monkeypatch):
    """test 마다 fresh metrics.db."""
    db = tmp_path / "metrics.db"
    monkeypatch.setenv("TUNA_METRICS_DB", str(db))
    monkeypatch.setenv("TUNA_STATE_BASE", str(tmp_path / "state"))
    yield db


def test_empty_db_summarize_returns_empty():
    assert summarize_metrics() == {}


def test_record_and_list():
    record_metric("standalone_toy_rate", 0.0, tool_name="generate_code")
    record_metric("standalone_toy_rate", 1.0, tool_name="generate_code")
    rows = list_metrics(metric="standalone_toy_rate")
    assert len(rows) == 2
    values = sorted(r.value for r in rows)
    assert values == [0.0, 1.0]


def test_record_filter_by_source():
    record_metric("ast_excess_score", 5.0, source="organic")
    record_metric("ast_excess_score", 2.0, source="synthetic")
    organic = list_metrics(source="organic")
    synth = list_metrics(source="synthetic")
    assert len(organic) == 1 and organic[0].value == 5.0
    assert len(synth) == 1 and synth[0].value == 2.0


def test_summarize_aggregates():
    for v in [0.0, 1.0, 0.0, 1.0, 0.0]:
        record_metric("standalone_toy_rate", v)
    summary = summarize_metrics()
    assert "standalone_toy_rate" in summary
    s = summary["standalone_toy_rate"]
    assert s["count"] == 5
    assert s["avg"] == pytest.approx(0.4)
    assert s["min"] == 0.0
    assert s["max"] == 1.0


def test_clear_metrics_filtered_by_source():
    record_metric("x", 1.0, source="organic")
    record_metric("x", 1.0, source="synthetic")
    removed = clear_metrics(source="organic")
    assert removed == 1
    remaining = list_metrics()
    assert len(remaining) == 1
    assert remaining[0].source == "synthetic"


def test_clear_metrics_all():
    record_metric("a", 1.0)
    record_metric("b", 2.0)
    removed = clear_metrics()
    assert removed == 2
    assert list_metrics() == []


def test_collect_organic_clean_code(tmp_path):
    code = "def add(a, b):\n    return a + b\n"
    collect_organic_after_delegation(
        code, tool_name="generate_code", project_root=str(tmp_path),
    )
    summary = summarize_metrics(source="organic")
    # standalone_toy_rate 0.0 (clean) + ast_excess_score 0 + syntactically_valid 1.0
    assert summary["standalone_toy_rate"]["avg"] == 0.0
    assert summary["syntactically_valid"]["avg"] == 1.0
    assert summary["ast_excess_score"]["avg"] == 0.0


def test_collect_organic_toy_code(tmp_path):
    code = "from unittest.mock import Mock\nx = Mock()\n"
    collect_organic_after_delegation(
        code, tool_name="generate_code", project_root=str(tmp_path),
    )
    summary = summarize_metrics(source="organic")
    # Mock 사용 → toy 1.0
    assert summary["standalone_toy_rate"]["avg"] == 1.0


def test_collect_organic_syntax_error(tmp_path):
    code = "def broken(:\n    pass\n"
    collect_organic_after_delegation(
        code, tool_name="generate_code", project_root=str(tmp_path),
    )
    summary = summarize_metrics(source="organic")
    assert summary["syntactically_valid"]["avg"] == 0.0
    assert summary["standalone_toy_rate"]["avg"] == 1.0  # syntax error → toy


def test_collect_organic_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TUNA_ORGANIC_METRICS", "0")
    collect_organic_after_delegation(
        "def x(): pass", tool_name="generate_code", project_root=str(tmp_path),
    )
    assert summarize_metrics() == {}


def test_collect_organic_with_state_md_conventions(tmp_path):
    from tunallama_core.memory.state import (
        SECTION_CONVENTIONS,
        StateEntry,
        append_entry,
        load_state,
        save_state,
    )
    state_base = tmp_path / "state"
    # 사용자가 project_root=tmp_path 호출하면 그 hash 의 state.md 가 만들어짐.
    s = load_state(tmp_path, base=state_base)
    append_entry(s, StateEntry(
        section=SECTION_CONVENTIONS,
        text="use `MemoryStore` not `Store`",
        source="manual",
    ))
    save_state(s)

    # 코드에 MemoryStore 등장 → adherence 1.0.
    code_honored = "from x import MemoryStore\nMemoryStore()"
    collect_organic_after_delegation(
        code_honored, tool_name="generate_code", project_root=str(tmp_path),
    )
    summary = summarize_metrics(source="organic")
    assert "convention_adherence_rate" in summary
    assert summary["convention_adherence_rate"]["avg"] == 1.0
