"""Phase 5-E (C) - 984 record LOPO. 524 → 984 corpus 확장 효과.

기존 524 record 의 σR@5 0.21-0.26 이 더 큰 corpus 에서 줄어드는지 검증.
외부 가설: σ ∝ 1/√N 경향. 524 → 984 면 σ × √(524/984) ≈ 0.73x.

측정 분할:
- ``test_lopo_1k_local_paths``: BM25 / vec / hybrid / rerank, full 792 query
  (132 task × 6 paraphrase). cloud 0.
- expanded path 는 cloud 호출 부담 큼 - 별 trigger (sample 24).

회전마다 fresh DB X. 시드 1번 색인 + retrieved 에서 holdout 제외.
"""

from __future__ import annotations

import math
import statistics

import pytest

from tests.integration.seeds.extended_1k import (
    ALL_GROUPS_132,
    NOISE_192,
    TOTAL_RECORDS_1K,
)
from tunallama_core.memory.metrics import (
    RetrievalMetrics,
    average_metrics,
    compute_metrics,
)
from tunallama_core.memory.search import (
    recall,
    recall_hybrid,
    recall_reranked,
)
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
def big_store_1k(tmp_path_factory) -> MemoryStore:
    """984 record 시드 1번 색인. id 1-based, group N 의 6 paraphrase 는
    id (N*6+1) ~ (N*6+6)."""
    db = tmp_path_factory.mktemp("p5e") / "p5e.db"
    store = MemoryStore(db, korean_tokenizer="kiwi", enable_embeddings=True).open()
    for group in ALL_GROUPS_132:
        for phrase in group:
            store.record_call(
                tool_name="seed", inputs={"q": phrase},
                output=f"out for {phrase}", model="seed", duration_ms=1,
            )
    for noise in NOISE_192:
        store.record_call(
            tool_name="seed", inputs={"q": noise},
            output=f"out for {noise}", model="seed", duration_ms=1,
        )
    yield store
    store.close()


def _group_ids(g_idx: int) -> set[int]:
    start = g_idx * 6 + 1
    return set(range(start, start + 6))


def _holdout_id(g_idx: int, p_idx: int) -> int:
    return g_idx * 6 + 1 + p_idx


def _filter_holdout(retrieved: list[int], holdout: int) -> list[int]:
    return [r for r in retrieved if r != holdout]


def test_lopo_1k_local_paths(big_store_1k, capsys):
    """4 path × 792 query (132 task × 6 paraphrase). cloud 0."""
    by_path: dict[str, list[RetrievalMetrics]] = {
        "BM25": [], "vec": [], "hybrid": [], "rerank": [],
    }
    ndcg_by_path: dict[str, list[float]] = {p: [] for p in by_path}

    for g_idx, phrases in enumerate(ALL_GROUPS_132):
        all_grp = _group_ids(g_idx)
        for p_idx, query in enumerate(phrases):
            holdout = _holdout_id(g_idx, p_idx)
            relevant = all_grp - {holdout}
            bm = _filter_holdout(
                [s.full_id for s in recall(big_store_1k, query, limit=20).snippets],
                holdout,
            )
            vec = _filter_holdout(
                [h.id for h in big_store_1k.search_vectors(query, limit=20)],
                holdout,
            )
            hy = _filter_holdout(
                [s.full_id for s in recall_hybrid(big_store_1k, query, limit=20).snippets],
                holdout,
            )
            rr = _filter_holdout(
                [s.full_id for s in recall_reranked(
                    big_store_1k, query, limit=20, candidate_pool=50, base="hybrid"
                ).snippets],
                holdout,
            )
            by_path["BM25"].append(compute_metrics(bm, relevant))
            by_path["vec"].append(compute_metrics(vec, relevant))
            by_path["hybrid"].append(compute_metrics(hy, relevant))
            by_path["rerank"].append(compute_metrics(rr, relevant))
            ndcg_by_path["BM25"].append(ndcg_at_k(bm, relevant))
            ndcg_by_path["vec"].append(ndcg_at_k(vec, relevant))
            ndcg_by_path["hybrid"].append(ndcg_at_k(hy, relevant))
            ndcg_by_path["rerank"].append(ndcg_at_k(rr, relevant))

    avg = {p: average_metrics(ms) for p, ms in by_path.items()}

    with capsys.disabled():
        n = sum(len(g) for g in ALL_GROUPS_132)
        print(
            f"\n\n=== Phase 5-E LOPO 1k local paths "
            f"(seed {TOTAL_RECORDS_1K} record, {n} query / path) ==="
        )
        print(
            f"{'path':<10}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'σP@1':>8}{'σR@5':>8}"
        )
        print("-" * 60)
        for p in ("BM25", "vec", "hybrid", "rerank"):
            m = avg[p]
            sp1 = (
                statistics.stdev([x.p1 for x in by_path[p]])
                if len(by_path[p]) > 1 else 0.0
            )
            sr5 = (
                statistics.stdev([x.r_at_k for x in by_path[p]])
                if len(by_path[p]) > 1 else 0.0
            )
            ndcg = statistics.mean(ndcg_by_path[p])
            print(
                f"{p:<10}{m.p1:>8.2f}{m.r_at_k:>8.2f}{m.mrr:>8.2f}"
                f"{ndcg:>10.2f}{sp1:>8.2f}{sr5:>8.2f}"
            )
        print()

    assert avg["vec"].p1 >= avg["BM25"].p1 - 0.10
