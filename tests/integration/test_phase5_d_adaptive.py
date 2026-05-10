"""Phase 5-D - Adaptive routing 측정.

휴리스틱 라우터 (cloud 0 분류 + 카테고리별 path 선택) vs HyDE only.
σR@5 비교가 핵심.

3 path:
- baseline_hybrid (cloud 0)
- hyde_only (모든 query 에 HyDE - cloud 1회/query)
- adaptive (keyword=BM25 / natural=HyDE / mixed=rerank - cloud 평균 < 1회)
"""

from __future__ import annotations

import math
import os
import statistics
from collections import Counter

import pytest

from tests.integration.seeds.extended_500 import (
    ALL_GROUPS,
    NOISE_90,
    TOTAL_RECORDS,
)
from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.memory.adaptive import extract_features, recall_adaptive
from tunallama_core.memory.metrics import (
    RetrievalMetrics,
    average_metrics,
    compute_metrics,
)
from tunallama_core.memory.search import recall_hybrid, recall_hyde
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
    db = tmp_path_factory.mktemp("p5d") / "p5d.db"
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


def test_adaptive_vs_hyde(big_store, cloud_client, capsys):
    """3 path × 24 group leader. cloud 호출:
    - baseline: 0
    - hyde: 24 (모든 query)
    - adaptive: <= 24 (natural 만 HyDE, 나머지는 cloud 0).
    """
    paths_results: dict[str, list[RetrievalMetrics]] = {
        "hybrid": [],
        "hyde_only": [],
        "adaptive": [],
    }
    paths_ndcgs: dict[str, list[float]] = {p: [] for p in paths_results}
    category_counter: Counter = Counter()
    adaptive_cloud_calls = 0

    for g_idx in _SAMPLE_INDICES:
        phrases = ALL_GROUPS[g_idx]
        query = phrases[0]
        holdout = g_idx * 6 + 1
        relevant = _group_ids(g_idx) - {holdout}

        # category counting
        feat = extract_features(query)
        category_counter[feat.category] += 1
        if feat.category == "natural":
            adaptive_cloud_calls += 1

        # 1. baseline hybrid
        hy = _filter_holdout(
            [s.full_id for s in recall_hybrid(big_store, query, limit=20).snippets],
            holdout,
        )
        # 2. HyDE only
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
        # 3. Adaptive
        adapt = _filter_holdout(
            [
                s.full_id
                for s in recall_adaptive(
                    big_store, query, cloud_client=cloud_client, limit=20,
                ).snippets
            ],
            holdout,
        )

        paths_results["hybrid"].append(compute_metrics(hy, relevant))
        paths_results["hyde_only"].append(compute_metrics(hyde_ids, relevant))
        paths_results["adaptive"].append(compute_metrics(adapt, relevant))
        paths_ndcgs["hybrid"].append(ndcg_at_k(hy, relevant))
        paths_ndcgs["hyde_only"].append(ndcg_at_k(hyde_ids, relevant))
        paths_ndcgs["adaptive"].append(ndcg_at_k(adapt, relevant))

    with capsys.disabled():
        print(
            f"\n\n=== Phase 5-D Adaptive routing "
            f"({len(_SAMPLE_INDICES)} group / {TOTAL_RECORDS} record) ==="
        )
        print(f"category distribution: {dict(category_counter)}")
        print(
            f"cloud calls: hybrid=0, hyde_only={len(_SAMPLE_INDICES)}, "
            f"adaptive={adaptive_cloud_calls}"
        )
        print()
        print(
            f"{'path':<14}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'sigmaP@1':>12}{'sigmaR@5':>12}"
        )
        print("-" * 72)
        for p in ("hybrid", "hyde_only", "adaptive"):
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
