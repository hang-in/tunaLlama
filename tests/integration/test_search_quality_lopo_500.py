"""Phase 5-1 - 524 record LOPO + cross-corpus 비교.

102 record (Phase 4-3b LOPO) → 524 record. 외부 검토 권고: corpus 가
커지면 σ 가 줄어들고 reranker 가치 ↑ 가설 검증.

측정 분할:
- ``test_lopo_local_paths``: BM25 / vec / hybrid / rerank 만 (cloud 0). full
  432 query (72 task × 6 paraphrase).
- ``test_lopo_expanded_sample``: expanded path. cloud 부담 줄여 24 group ×
  leader = 24 cloud call.

회전마다 fresh DB 만들지 않고 시드 1번 색인 + retrieved 에서 holdout 제외
(LOPO 시뮬레이션). BGE-M3 임베딩 524 record 1번만.
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
    recall,
    recall_expanded,
    recall_hybrid,
    recall_reranked,
)
from tunallama_core.memory.store import MemoryStore

pytestmark = pytest.mark.search_quality


# ---------------- NDCG@5 ----------------

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


# ---------------- Big store fixture (시드 1번 색인) ----------------

@pytest.fixture(scope="module")
def big_store(tmp_path_factory) -> MemoryStore:
    """524 record 시드 1번 색인. id 1-based, group N 의 6 paraphrase 는
    id (N*6+1) ~ (N*6+6)."""
    db = tmp_path_factory.mktemp("p51") / "p51.db"
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
    """group N (0-based) 의 6 record id (1-based)."""
    start = g_idx * 6 + 1
    return set(range(start, start + 6))


def _holdout_id(g_idx: int, p_idx: int) -> int:
    return g_idx * 6 + 1 + p_idx


def _filter_holdout(retrieved: list[int], holdout: int) -> list[int]:
    """LOPO 시뮬: query record (holdout) 자기 자신은 retrieved 에서 제외."""
    return [r for r in retrieved if r != holdout]


# ---------------- Test 1: local paths (cloud 0) ----------------

def test_lopo_local_paths(big_store, capsys):
    """4 path × 432 query (72 task × 6 paraphrase). cloud 호출 0."""
    by_path: dict[str, list[RetrievalMetrics]] = {
        "BM25": [], "vec": [], "hybrid": [], "rerank": [],
    }
    ndcg_by_path: dict[str, list[float]] = {p: [] for p in by_path}

    for g_idx, phrases in enumerate(ALL_GROUPS):
        all_grp = _group_ids(g_idx)
        for p_idx, query in enumerate(phrases):
            holdout = _holdout_id(g_idx, p_idx)
            relevant = all_grp - {holdout}
            bm = _filter_holdout(
                [s.full_id for s in recall(big_store, query, limit=20).snippets],
                holdout,
            )
            vec = _filter_holdout(
                [h.id for h in big_store.search_vectors(query, limit=20)],
                holdout,
            )
            hy = _filter_holdout(
                [s.full_id for s in recall_hybrid(big_store, query, limit=20).snippets],
                holdout,
            )
            rr = _filter_holdout(
                [s.full_id for s in recall_reranked(
                    big_store, query, limit=20, candidate_pool=20, base="hybrid"
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
        n = sum(len(g) for g in ALL_GROUPS)
        print(
            f"\n\n=== Phase 5-1 LOPO local paths "
            f"(seed {TOTAL_RECORDS} record, {n} query / path) ==="
        )
        print(
            f"{'path':<10}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'σP@1':>8}{'σR@5':>8}{'σNDCG':>8}"
        )
        print("-" * 70)
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
            ndcg_mean = statistics.mean(ndcg_by_path[p])
            ndcg_std = (
                statistics.stdev(ndcg_by_path[p])
                if len(ndcg_by_path[p]) > 1 else 0.0
            )
            print(
                f"{p:<10}{m.p1:>8.2f}{m.r_at_k:>8.2f}{m.mrr:>8.2f}"
                f"{ndcg_mean:>10.2f}{sp1:>8.2f}{sr5:>8.2f}{ndcg_std:>8.2f}"
            )
        print()

    # 가설 검증 - 약한 assertion
    assert avg["vec"].p1 >= avg["BM25"].p1 - 0.10
    rerank_ndcg = statistics.mean(ndcg_by_path["rerank"])
    hybrid_ndcg = statistics.mean(ndcg_by_path["hybrid"])
    assert rerank_ndcg >= hybrid_ndcg - 0.05


# ---------------- Test 2: expanded path sample ----------------

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


def test_lopo_expanded_sample(big_store, cloud_client, capsys):
    """expanded path 만 24 group × leader = 24 cloud calls (sample).

    full LOPO (432 cloud) 는 비용 ↑ → 24 group leader 로 평균 추정.
    24 = 12 기존 task + 12 신규 (각 카테고리 2 개). cross-section 보장.
    """
    sample_indices = list(range(0, 12)) + [12, 14, 22, 24, 32, 34, 42, 44, 52, 54, 62, 64]
    metrics: list[RetrievalMetrics] = []
    ndcgs: list[float] = []

    for g_idx in sample_indices:
        phrases = ALL_GROUPS[g_idx]
        query = phrases[0]
        holdout = _holdout_id(g_idx, 0)
        relevant = _group_ids(g_idx) - {holdout}
        ex = _filter_holdout(
            [
                s.full_id
                for s in recall_expanded(
                    big_store, query, client=cloud_client,
                    mode="hybrid", limit=20,
                ).snippets
            ],
            holdout,
        )
        metrics.append(compute_metrics(ex, relevant))
        ndcgs.append(ndcg_at_k(ex, relevant))

    avg = average_metrics(metrics)
    sp1 = statistics.stdev([m.p1 for m in metrics]) if len(metrics) > 1 else 0.0
    sr5 = (
        statistics.stdev([m.r_at_k for m in metrics])
        if len(metrics) > 1 else 0.0
    )
    ndcg_mean = statistics.mean(ndcgs)
    ndcg_std = statistics.stdev(ndcgs) if len(ndcgs) > 1 else 0.0

    with capsys.disabled():
        print(
            f"\n\n=== Phase 5-1 expanded sample "
            f"({len(sample_indices)} group leader / 524 record) ==="
        )
        print(
            f"{'path':<10}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'σP@1':>8}{'σR@5':>8}{'σNDCG':>8}"
        )
        print("-" * 70)
        print(
            f"{'exp+H':<10}{avg.p1:>8.2f}{avg.r_at_k:>8.2f}{avg.mrr:>8.2f}"
            f"{ndcg_mean:>10.2f}{sp1:>8.2f}{sr5:>8.2f}{ndcg_std:>8.2f}"
        )
        print()
