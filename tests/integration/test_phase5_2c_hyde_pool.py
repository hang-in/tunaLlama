"""Phase 5-2C - HyDE + candidate_pool 확대 측정.

외부 권고 (R@5 회복):
- candidate_pool 20 -> 50 으로 늘려 reranker 가 더 많은 후보에서 고름.
- HyDE: query 를 가상 답변 텍스트로 변환 후 검색.

Phase 5-1 의 524 record 시드 + 24 group leader sample 로 normalized 와
HyDE 비교.
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
from tunallama_core.memory.search import (
    recall_hybrid,
    recall_hyde,
    recall_normalized,
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
def big_store(tmp_path_factory) -> MemoryStore:
    db = tmp_path_factory.mktemp("p52c") / "p52c.db"
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


_SAMPLE_INDICES = list(range(0, 12)) + [
    12, 14, 22, 24, 32, 34, 42, 44, 52, 54, 62, 64,
]


def test_hyde_vs_normalized(big_store, cloud_client, capsys):
    """4 path 비교 (24 group leader): hybrid baseline / normalized / HyDE / rerank pool=50.

    cloud 호출 = 24 (normalized) + 24 (hyde) = 48.
    """
    paths_results: dict[str, list[RetrievalMetrics]] = {
        "hybrid_pool20": [],
        "rerank_pool50": [],
        "normalized": [],
        "hyde": [],
    }
    paths_ndcgs: dict[str, list[float]] = {p: [] for p in paths_results}

    for g_idx in _SAMPLE_INDICES:
        phrases = ALL_GROUPS[g_idx]
        query = phrases[0]
        holdout = g_idx * 6 + 1
        relevant = _group_ids(g_idx) - {holdout}

        # 1. baseline hybrid
        hy = _filter_holdout(
            [s.full_id for s in recall_hybrid(big_store, query, limit=20).snippets],
            holdout,
        )
        # 2. rerank with candidate_pool=50
        rr50 = _filter_holdout(
            [
                s.full_id
                for s in recall_reranked(
                    big_store, query, limit=20,
                    candidate_pool=50, base="hybrid",
                ).snippets
            ],
            holdout,
        )
        # 3. normalized hybrid
        norm = _filter_holdout(
            [
                s.full_id
                for s in recall_normalized(
                    big_store, query, client=cloud_client,
                    base="hybrid", limit=20,
                ).snippets
            ],
            holdout,
        )
        # 4. HyDE hybrid
        hyde_ids = _filter_holdout(
            [
                s.full_id
                for s in recall_hyde(
                    big_store, query, client=cloud_client,
                    base="hybrid", limit=20,
                ).snippets
            ],
            holdout,
        )

        paths_results["hybrid_pool20"].append(compute_metrics(hy, relevant))
        paths_results["rerank_pool50"].append(compute_metrics(rr50, relevant))
        paths_results["normalized"].append(compute_metrics(norm, relevant))
        paths_results["hyde"].append(compute_metrics(hyde_ids, relevant))
        paths_ndcgs["hybrid_pool20"].append(ndcg_at_k(hy, relevant))
        paths_ndcgs["rerank_pool50"].append(ndcg_at_k(rr50, relevant))
        paths_ndcgs["normalized"].append(ndcg_at_k(norm, relevant))
        paths_ndcgs["hyde"].append(ndcg_at_k(hyde_ids, relevant))

    with capsys.disabled():
        print(
            f"\n\n=== Phase 5-2C HyDE + candidate_pool comparison "
            f"({len(_SAMPLE_INDICES)} group leader / {TOTAL_RECORDS} record) ==="
        )
        print(
            f"{'path':<18}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'sigmaP@1':>12}{'sigmaR@5':>12}"
        )
        print("-" * 76)
        for p in ("hybrid_pool20", "rerank_pool50", "normalized", "hyde"):
            ms = paths_results[p]
            avg = average_metrics(ms)
            sp1 = statistics.stdev([m.p1 for m in ms]) if len(ms) > 1 else 0.0
            sr5 = (
                statistics.stdev([m.r_at_k for m in ms])
                if len(ms) > 1 else 0.0
            )
            nd = statistics.mean(paths_ndcgs[p])
            print(
                f"{p:<18}{avg.p1:>8.2f}{avg.r_at_k:>8.2f}{avg.mrr:>8.2f}"
                f"{nd:>10.2f}{sp1:>12.2f}{sr5:>12.2f}"
            )
        print()
