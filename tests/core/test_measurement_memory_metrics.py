"""Phase 6-4 memory_metrics 단위 테스트."""

from __future__ import annotations

import pytest

from tunallama_core.measurement.memory_metrics import (
    ConventionResult,
    InterventionRecord,
    MetricSample,
    StateRecallProbe,
    convention_adherence_rate,
    standalone_toy_rate,
    state_recall_rate,
    user_intervention_rate,
)
from tunallama_core.memory.state import (
    SECTION_CONVENTIONS,
    StateEntry,
    StateFile,
)


# ---------- standalone_toy_rate ----------

def test_standalone_toy_empty_returns_zero():
    assert standalone_toy_rate([]) == 0.0


def test_standalone_toy_clean_code():
    rate = standalone_toy_rate([
        "def gcd(a, b):\n    while b: a, b = b, a % b\n    return a\n",
    ])
    assert rate == 0.0


def test_standalone_toy_syntax_error_flagged():
    rate = standalone_toy_rate(["def broken(:\n    pass\n"])
    assert rate == 1.0


def test_standalone_toy_mock_flagged():
    code = "from unittest.mock import Mock\nx = Mock()\n"
    rate = standalone_toy_rate([code])
    assert rate == 1.0


def test_standalone_toy_np_random_flagged():
    code = "import numpy as np\nv = np.random.uniform(0, 1)\n"
    rate = standalone_toy_rate([code])
    assert rate == 1.0


def test_standalone_toy_mixed():
    outputs = [
        "def f(): return 1\n",  # clean
        "from unittest.mock import MagicMock\n",  # toy
        "v = np.random.choice([1])\n",  # toy
        "def g(): return 2\n",  # clean
    ]
    rate = standalone_toy_rate(outputs)
    assert rate == 0.5


def test_standalone_toy_unrelated_keyword():
    """spec 무관 keyword 출현하면 toy."""
    rate = standalone_toy_rate(
        ["import hashlib\ndef gcd(a, b): return hashlib.sha256(b).hexdigest()\n"],
        unrelated_keywords=["hashlib", "sha256"],
    )
    assert rate == 1.0


# ---------- convention_adherence_rate ----------

def test_convention_adherence_empty_state():
    s = StateFile(project_hash="x", project_root="/", last_updated="t")
    assert convention_adherence_rate(s, ["any output"]) == []


def test_convention_adherence_uses_backtick_token():
    s = StateFile(project_hash="x", project_root="/", last_updated="t")
    s.entries.append(StateEntry(
        section=SECTION_CONVENTIONS,
        text="use `MemoryStore` not `Store`", source="manual",
    ))
    outputs = [
        "from x import MemoryStore\nMemoryStore()\n",   # honored
        "from x import Store\nStore()\n",               # not honored
        "irrelevant\n",                                  # not honored
    ]
    results = convention_adherence_rate(s, outputs)
    assert len(results) == 1
    res = results[0]
    assert res.n_total == 3
    assert res.n_honored == 1
    assert res.rate == pytest.approx(1 / 3)


def test_convention_adherence_skips_when_no_anchor():
    """convention 에 식별자 토큰 없으면 skip."""
    s = StateFile(project_hash="x", project_root="/", last_updated="t")
    s.entries.append(StateEntry(
        section=SECTION_CONVENTIONS,
        text="always must use never import from",  # stopwords 만
        source="manual",
    ))
    results = convention_adherence_rate(s, ["any"])
    assert results == []


def test_convention_result_rate_zero_total():
    r = ConventionResult(convention_text="x", n_total=0, n_honored=0)
    assert r.rate == 0.0


# ---------- user_intervention_rate ----------

def test_user_intervention_empty():
    assert user_intervention_rate([]) == 0.0


def test_user_intervention_average():
    records = [
        InterventionRecord(call_id=1, target_file_path="/a.py", intervention_severity=0.0),
        InterventionRecord(call_id=2, target_file_path="/b.py", intervention_severity=0.5),
        InterventionRecord(call_id=3, target_file_path="/c.py", intervention_severity=1.0),
    ]
    rate = user_intervention_rate(records)
    assert rate == pytest.approx(0.5)


# ---------- state_recall_rate ----------

def test_state_recall_empty():
    assert state_recall_rate([]) == 0.0


def test_state_recall_partial():
    probes = [
        StateRecallProbe(target_text="MemoryStore", response_text="...", matched=True),
        StateRecallProbe(target_text="HyDE", response_text="...", matched=True),
        StateRecallProbe(target_text="Kiwi", response_text="...", matched=False),
    ]
    rate = state_recall_rate(probes)
    assert rate == pytest.approx(2 / 3)


# ---------- MetricSample ----------

def test_metric_sample_source_tag():
    m = MetricSample(
        metric="standalone_toy_rate", value=0.6,
        source="synthetic", timestamp="2026-05-11T00:00:00Z",
    )
    assert m.source == "synthetic"
    with pytest.raises(Exception):
        m.value = 0.3  # frozen
