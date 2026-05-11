"""Phase 5-2D - MMR (Maximal Marginal Relevance) 측정.

외부 조사 결과 (R@5 / σ 직접 타격) 의 STRONG BUY: MMR.
Carbonell & Goldstein (1998). 후보 pool 에서 관련성 + 다양성 균형 reranking.

Phase 5-1 의 524 record 시드 + full LOPO 432 query.
λ sweep: 1.0 (관련성 only = baseline reorder) / 0.7 / 0.5 / 0.3.
cloud 호출 0 (BGE-M3 임베딩 캐시만).
"""

from __future__ import annotations

import math
import statistics

import pytest

from tests.integration.seeds.extended_500 import (
    ALL_GROUPS,
    NOISE_90,
    TOTAL_RECORDS,
)
from tunallama_core.memory.metrics import (
    RetrievalMetrics,
    average_metrics,
    compute_metrics,
)
from tunallama_core.memory.search import recall_hybrid, recall_mmr
from tunallama_core.memory.store import MemoryStore

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
    db = tmp_path_factory.mktemp("p52d") / "p52d.db"
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


def _group_ids(g_idx: int) -> set[int]:
    start = g_idx * 6 + 1
    return set(range(start, start + 6))


def _filter_holdout(retrieved: list[int], holdout: int) -> list[int]:
    return [r for r in retrieved if r != holdout]


def test_mmr_lambda_sweep(big_store, capsys):
    """4 path × 432 query: hybrid baseline + MMR(λ=1.0, 0.7, 0.5, 0.3).

    cloud 호출 0. CPU embedding lookup + numpy cosine.
    """
    paths_results: dict[str, list[RetrievalMetrics]] = {
        "hybrid": [],
        "mmr_l1.0": [],
        "mmr_l0.7": [],
        "mmr_l0.5": [],
        "mmr_l0.3": [],
    }
    paths_ndcgs: dict[str, list[float]] = {p: [] for p in paths_results}

    for g_idx, phrases in enumerate(ALL_GROUPS):
        all_grp = _group_ids(g_idx)
        for p_idx, query in enumerate(phrases):
            holdout = g_idx * 6 + 1 + p_idx
            relevant = all_grp - {holdout}

            hy = _filter_holdout(
                [s.full_id for s in recall_hybrid(big_store, query, limit=20).snippets],
                holdout,
            )
            paths_results["hybrid"].append(compute_metrics(hy, relevant))
            paths_ndcgs["hybrid"].append(ndcg_at_k(hy, relevant))

            for lam in (1.0, 0.7, 0.5, 0.3):
                key = f"mmr_l{lam}"
                ids = _filter_holdout(
                    [
                        s.full_id
                        for s in recall_mmr(
                            big_store, query, limit=20,
                            candidate_pool=20, lambda_=lam,
                        ).snippets
                    ],
                    holdout,
                )
                paths_results[key].append(compute_metrics(ids, relevant))
                paths_ndcgs[key].append(ndcg_at_k(ids, relevant))

    with capsys.disabled():
        print(
            f"\n\n=== Phase 5-2D MMR lambda sweep "
            f"({TOTAL_RECORDS} record, "
            f"{len(paths_results['hybrid'])} query) ==="
        )
        print(
            f"{'path':<14}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'sigmaP@1':>12}{'sigmaR@5':>12}"
        )
        print("-" * 72)
        for p in ("hybrid", "mmr_l1.0", "mmr_l0.7", "mmr_l0.5", "mmr_l0.3"):
            ms = paths_results[p]
            avg = average_metrics(ms)
            sp1 = statistics.stdev([m.p1 for m in ms]) if len(ms) > 1 else 0.0
            sr5 = (
                statistics.stdev([m.r_at_k for m in ms])
                if len(ms) > 1 else 0.0
            )
            nd = statistics.mean(paths_ndcgs[p])
            print(
                f"{p:<14}{avg.p1:>8.2f}{avg.r_at_k:>8.2f}{avg.mrr:>8.2f}"
                f"{nd:>10.2f}{sp1:>12.2f}{sr5:>12.2f}"
            )
        print()
