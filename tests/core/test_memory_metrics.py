"""검색 품질 metrics 단위 테스트."""

from __future__ import annotations

import pytest

from tunallama_core.memory.metrics import (
    RetrievalMetrics,
    average_metrics,
    compute_metrics,
)


def test_empty_retrieval_returns_zero():
    m = compute_metrics([], {1, 2}, k=5)
    assert (m.p1, m.p_at_k, m.r_at_k, m.mrr) == (0.0, 0.0, 0.0, 0.0)


def test_empty_relevant_returns_zero():
    m = compute_metrics([1, 2, 3], set(), k=5)
    assert (m.p1, m.p_at_k, m.r_at_k, m.mrr) == (0.0, 0.0, 0.0, 0.0)


def test_top1_hit_gives_p1_one_and_mrr_one():
    m = compute_metrics([7, 1, 2, 3, 4], {7, 99}, k=5)
    assert m.p1 == 1.0
    assert m.mrr == 1.0
    # |{7} ∩ {7,99}| = 1, k=5, retrieved 5 → P@5 = 1/5
    assert m.p_at_k == pytest.approx(1 / 5)
    assert m.r_at_k == pytest.approx(1 / 2)


def test_first_relevant_at_rank_3():
    m = compute_metrics([10, 11, 7, 12, 13], {7, 99}, k=5)
    assert m.p1 == 0.0
    assert m.mrr == pytest.approx(1 / 3)


def test_no_relevant_in_top_k_but_relevant_overall():
    """top-k 안에 relevant 없지만 더 뒤에 있으면 MRR 은 잡힌다."""
    m = compute_metrics([1, 2, 3, 4, 5, 99], {99}, k=5)
    assert m.p1 == 0.0
    assert m.r_at_k == 0.0  # top-5 에 99 없음
    assert m.mrr == pytest.approx(1 / 6)


def test_p_at_k_uses_actual_top_length_when_short():
    """top 의 길이가 k 보다 작으면 P@K 분모는 실제 top 길이."""
    m = compute_metrics([7, 1], {7}, k=5)
    # top=[7,1], hits=1, len(top)=2 → P=1/2
    assert m.p_at_k == pytest.approx(1 / 2)


def test_average_metrics_empty():
    assert average_metrics([]) == RetrievalMetrics(0.0, 0.0, 0.0, 0.0)


def test_average_metrics_simple():
    a = RetrievalMetrics(1.0, 0.4, 0.5, 1.0)
    b = RetrievalMetrics(0.0, 0.2, 0.5, 0.5)
    avg = average_metrics([a, b])
    assert avg.p1 == 0.5
    assert avg.p_at_k == pytest.approx(0.3)
    assert avg.r_at_k == 0.5
    assert avg.mrr == 0.75


def test_metrics_dataclass_frozen():
    m = RetrievalMetrics(0.0, 0.0, 0.0, 0.0)
    with pytest.raises(Exception):
        m.p1 = 1.0  # type: ignore[misc]
