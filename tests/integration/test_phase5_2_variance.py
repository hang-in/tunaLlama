"""Phase 5-2 - σ reduction 측정.

Phase 4-3b LOPO σR@5 0.18-0.30 의 dominant 변수가 query 표현 차이라는
외부 검토 진단.

비교:
- baseline: hybrid (σR@5 0.27 가 Phase 5-1 524 record 측정값)
- path A: normalized (LLM 으로 query → standard form 후 hybrid)
- path B: tiered confident only (BM25 exact + vector near 만, hard 제외)

목표: σR@5 ≤ 0.15.
"""

from __future__ import annotations

import math
import os
import statistics

import pytest

from tests.integration.seeds.extended_500 import (
    ALL_GROUPS,
    NOISE_90,
    TOTAL_RECORDS,
)
from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.memory.metrics import (
    RetrievalMetrics,
    average_metrics,
    compute_metrics,
)
from tunallama_core.memory.normalization import normalize_query
from tunallama_core.memory.search import recall_hybrid
from tunallama_core.memory.store import MemoryStore
from tunallama_core.memory.tiered import recall_tiered

pytestmark = pytest.mark.search_quality


def ndcg_at_k(retrieved: list[int], relevant: set[int], *, k: int = 5) -> float:
    if not retrieved or not relevant:
        return 0.0
    dcg = 0.0
    for rank, rid in enumerate(retrieved[:k], start=1):
        if rid in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    return dcg / idcg


@pytest.fixture(scope="module")
def big_store(tmp_path_factory) -> MemoryStore:
    db = tmp_path_factory.mktemp("p52") / "p52.db"
    store = MemoryStore(db, korean_tokenizer="kiwi", enable_embeddings=True).open()
    for group in ALL_GROUPS:
        for phrase in group:
            store.record_call(
                tool_name="seed", inputs={"q": phrase},
                output=f"out for {phrase}", model="seed", duration_ms=1,
            )
    for noise in NOISE_90:
        store.record_call(
            tool_name="seed", inputs={"q": noise},
            output=f"out for {noise}", model="seed", duration_ms=1,
        )
    yield store
    store.close()


@pytest.fixture(scope="module")
def cloud_client():
    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        pytest.skip("OLLAMA_CLOUD_API_KEY 미설정")
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model="glm-4.7",
    )
    return from_cloud(cfg, temperature=0.3, timeout=600)


def _group_ids(g_idx: int) -> set[int]:
    start = g_idx * 6 + 1
    return set(range(start, start + 6))


def _filter_holdout(retrieved: list[int], holdout: int) -> list[int]:
    return [r for r in retrieved if r != holdout]


def _measure_tiered(
    big_store, *, threshold_bm25: float, threshold_cosine: float, label: str
):
    """tiered confident 측정 helper - threshold tuning 용."""
    metrics: list[RetrievalMetrics] = []
    ndcgs: list[float] = []
    n_total_confident = 0

    for g_idx, phrases in enumerate(ALL_GROUPS):
        all_grp = _group_ids(g_idx)
        for p_idx, query in enumerate(phrases):
            holdout = g_idx * 6 + 1 + p_idx
            relevant = all_grp - {holdout}
            tier = recall_tiered(
                big_store, query, limit=20,
                threshold_bm25=threshold_bm25,
                threshold_cosine=threshold_cosine,
            )
            confident_ids = _filter_holdout(
                [s.full_id for s in tier.confident], holdout
            )
            n_total_confident += len(confident_ids)
            metrics.append(compute_metrics(confident_ids, relevant))
            ndcgs.append(ndcg_at_k(confident_ids, relevant))

    avg = average_metrics(metrics)
    sp1 = statistics.stdev([m.p1 for m in metrics]) if len(metrics) > 1 else 0.0
    sr5 = (
        statistics.stdev([m.r_at_k for m in metrics])
        if len(metrics) > 1 else 0.0
    )
    ndcg_mean = statistics.mean(ndcgs)
    ndcg_std = statistics.stdev(ndcgs) if len(ndcgs) > 1 else 0.0
    avg_n = n_total_confident / len(metrics)
    return label, avg, sp1, sr5, ndcg_mean, ndcg_std, avg_n


def test_tiered_threshold_sweep(big_store, capsys):
    """tiered confident 의 threshold sweep - filter strict 정도 따라 σ 변화."""
    rows = []
    for label, t_bm, t_cos in (
        ("relax (default)", -1.0, 0.5),
        ("medium", -2.0, 0.6),
        ("strict", -3.0, 0.7),
    ):
        rows.append(_measure_tiered(
            big_store, threshold_bm25=t_bm, threshold_cosine=t_cos, label=label,
        ))

    with capsys.disabled():
        print(
            f"\n\n=== Phase 5-2 tiered threshold sweep "
            f"({TOTAL_RECORDS} record) ==="
        )
        print(
            f"{'preset':<18}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'σP@1':>8}{'σR@5':>8}{'σNDCG':>8}{'avg_n':>8}"
        )
        print("-" * 80)
        for label, avg, sp1, sr5, nd_m, nd_s, an in rows:
            print(
                f"{label:<18}{avg.p1:>8.2f}{avg.r_at_k:>8.2f}{avg.mrr:>8.2f}"
                f"{nd_m:>10.2f}{sp1:>8.2f}{sr5:>8.2f}{nd_s:>8.2f}{an:>8.1f}"
            )
        print()


def test_tiered_confident_only(big_store, capsys):
    """Path B - tiered 의 confident (exact + near) 만. cloud 호출 0.

    full LOPO 432 query.
    """
    metrics: list[RetrievalMetrics] = []
    ndcgs: list[float] = []
    n_total_confident = 0

    for g_idx, phrases in enumerate(ALL_GROUPS):
        all_grp = _group_ids(g_idx)
        for p_idx, query in enumerate(phrases):
            holdout = g_idx * 6 + 1 + p_idx
            relevant = all_grp - {holdout}
            tier = recall_tiered(big_store, query, limit=20)
            confident_ids = _filter_holdout(
                [s.full_id for s in tier.confident], holdout
            )
            n_total_confident += len(confident_ids)
            metrics.append(compute_metrics(confident_ids, relevant))
            ndcgs.append(ndcg_at_k(confident_ids, relevant))

    avg = average_metrics(metrics)
    sp1 = statistics.stdev([m.p1 for m in metrics]) if len(metrics) > 1 else 0.0
    sr5 = (
        statistics.stdev([m.r_at_k for m in metrics])
        if len(metrics) > 1 else 0.0
    )
    ndcg_mean = statistics.mean(ndcgs)
    ndcg_std = statistics.stdev(ndcgs) if len(ndcgs) > 1 else 0.0
    avg_confident_size = n_total_confident / len(metrics)

    with capsys.disabled():
        print(
            f"\n\n=== Phase 5-2 path B (tiered confident, "
            f"{TOTAL_RECORDS} record, {len(metrics)} query) ==="
        )
        print(
            f"{'path':<18}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'σP@1':>8}{'σR@5':>8}{'σNDCG':>8}{'avg_n':>8}"
        )
        print("-" * 80)
        print(
            f"{'tiered_confident':<18}{avg.p1:>8.2f}{avg.r_at_k:>8.2f}"
            f"{avg.mrr:>8.2f}{ndcg_mean:>10.2f}{sp1:>8.2f}{sr5:>8.2f}"
            f"{ndcg_std:>8.2f}{avg_confident_size:>8.1f}"
        )
        print()


def test_normalized_sample(big_store, cloud_client, capsys):
    """Path A - normalized (LLM 정규화 + hybrid). cloud 호출 24 (sample)."""
    sample_indices = list(range(0, 12)) + [12, 14, 22, 24, 32, 34, 42, 44, 52, 54, 62, 64]

    base_metrics: list[RetrievalMetrics] = []
    norm_metrics: list[RetrievalMetrics] = []
    base_ndcgs: list[float] = []
    norm_ndcgs: list[float] = []

    for g_idx in sample_indices:
        phrases = ALL_GROUPS[g_idx]
        query = phrases[0]  # leader
        holdout = g_idx * 6 + 1
        relevant = _group_ids(g_idx) - {holdout}

        # baseline: hybrid 그대로
        base_ids = _filter_holdout(
            [s.full_id for s in recall_hybrid(big_store, query, limit=20).snippets],
            holdout,
        )
        base_metrics.append(compute_metrics(base_ids, relevant))
        base_ndcgs.append(ndcg_at_k(base_ids, relevant))

        # normalized
        norm_q = normalize_query(query, client=cloud_client)
        norm_ids = _filter_holdout(
            [s.full_id for s in recall_hybrid(big_store, norm_q, limit=20).snippets],
            holdout,
        )
        norm_metrics.append(compute_metrics(norm_ids, relevant))
        norm_ndcgs.append(ndcg_at_k(norm_ids, relevant))

    def _stats(ms, nd):
        avg = average_metrics(ms)
        sp1 = statistics.stdev([m.p1 for m in ms]) if len(ms) > 1 else 0.0
        sr5 = statistics.stdev([m.r_at_k for m in ms]) if len(ms) > 1 else 0.0
        nd_mean = statistics.mean(nd) if nd else 0.0
        nd_std = statistics.stdev(nd) if len(nd) > 1 else 0.0
        return avg, sp1, sr5, nd_mean, nd_std

    base_avg, base_sp1, base_sr5, base_nd_m, base_nd_s = _stats(base_metrics, base_ndcgs)
    norm_avg, norm_sp1, norm_sr5, norm_nd_m, norm_nd_s = _stats(norm_metrics, norm_ndcgs)

    with capsys.disabled():
        print(
            f"\n\n=== Phase 5-2 path A (normalized vs hybrid baseline, "
            f"{len(sample_indices)} group leader) ==="
        )
        print(
            f"{'path':<18}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'σP@1':>8}{'σR@5':>8}{'σNDCG':>8}"
        )
        print("-" * 76)
        print(
            f"{'hybrid_baseline':<18}{base_avg.p1:>8.2f}{base_avg.r_at_k:>8.2f}"
            f"{base_avg.mrr:>8.2f}{base_nd_m:>10.2f}{base_sp1:>8.2f}"
            f"{base_sr5:>8.2f}{base_nd_s:>8.2f}"
        )
        print(
            f"{'normalized':<18}{norm_avg.p1:>8.2f}{norm_avg.r_at_k:>8.2f}"
            f"{norm_avg.mrr:>8.2f}{norm_nd_m:>10.2f}{norm_sp1:>8.2f}"
            f"{norm_sr5:>8.2f}{norm_nd_s:>8.2f}"
        )
        print()
        print(
            f"σR@5 reduction = {base_sr5 - norm_sr5:+.3f} "
            f"({'개선' if norm_sr5 < base_sr5 else '악화'})"
        )
