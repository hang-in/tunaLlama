# Phase 4-3b - LOPO (leave-one-paraphrase-out) 측정

## 배경

기존 `test_search_quality_extended.py` 의 measurement 는 query =
`paraphrases[0]` 가 시드 record 와 정확히 동일 → P@1 / MRR 모든 path
1.00 일괄, **ranking 변별력 0**. 외부 Opus 4.7 + Codex 5.5 검토 결론:
LOPO 패턴으로 corpus 와 query 를 분리해야 P@1 / MRR 이 살아난다.

## Hypothesis

- H1: LOPO 시드에서는 path 별 P@1 / MRR 가 분리된다 (vec/rerank > BM25
  expectation).
- H2: σR@5 가 평균 R@5 보다 사용자 신뢰의 강한 지표. LOPO 측정에서
  σR@5 < 0.20 이면 신뢰 쓸만함, ≥ 0.20 이면 추가 안정화 필요.

## 측정 design

### Seed (기존과 다름)

12 task × 6 paraphrase + 30 noise. **각 회전마다 corpus 와 query 분리**:

- task 마다 paraphrase[i] (i ∈ 0..5) 를 query 로 사용
- 그 task 의 나머지 5 paraphrase + 다른 11 task × 6 paraphrase + 30 noise
  = corpus 95 record
- relevant set = 그 task 의 나머지 5 paraphrase id

12 task × 6 회전 = **72 query** 측정. 각 회전마다 fresh DB 새로 만들지
않고 in-memory id remapping 으로 효율화.

### Metrics

각 query 마다:
- P@1 (top-1 hit)
- R@5
- MRR (1-based first-relevant rank, 못 찾으면 0)
- NDCG@5 (relevance binary 0/1, log2 discount)

per-path 평균 + σ.

### Paths

기존 5 path 유지: BM25, vec, hybrid, reranked-hybrid, expanded-hybrid (cloud
glm-4.7).

## Required Imports

```python
import math
import os
import statistics
from dataclasses import dataclass

import pytest

from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.memory.metrics import RetrievalMetrics, compute_metrics, average_metrics
from tunallama_core.memory.search import recall, recall_expanded, recall_hybrid, recall_reranked
from tunallama_core.memory.store import MemoryStore
```

## Required Call Signatures

```python
# Store - 기존 102 record 시드 작성과 동일
store = MemoryStore(db_path, korean_tokenizer="kiwi", enable_embeddings=True).open()
store.record_call(tool_name="seed", inputs={"q": phrase}, output=f"out for {phrase}", model="seed", duration_ms=1)

# 5 search paths
bm25_results = recall(store, query, limit=20).snippets        # has .full_id
vec_results = store.search_vectors(query, limit=20)            # has .id
hybrid_results = recall_hybrid(store, query, limit=20).snippets
rerank_results = recall_reranked(store, query, limit=20, candidate_pool=20, base="hybrid").snippets
expanded_results = recall_expanded(store, query, client=cloud_client, mode="hybrid", limit=20).snippets

# Metrics
m = compute_metrics(retrieved_ids: list[int], relevant: set[int], k=5)
# returns RetrievalMetrics dataclass(p1: float, p_at_k: float, r_at_k: float, mrr: float)

avg = average_metrics(per_query: list[RetrievalMetrics])
# returns RetrievalMetrics
```

## NDCG@5 helper (새로 작성)

```python
def ndcg_at_k(retrieved: list[int], relevant: set[int], *, k: int = 5) -> float:
    """binary relevance NDCG@k. log2(rank+1) discount."""
    if not retrieved or not relevant:
        return 0.0
    dcg = 0.0
    for rank, rid in enumerate(retrieved[:k], start=1):
        if rid in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg
```

## Output 표

per-path 출력 (capsys.disabled prints):
```
=== Phase 4-3b LOPO (12 × 6 = 72 query) ===
path           P@1     R@5     MRR    NDCG@5    σP@1    σR@5    σNDCG
BM25           0.??    0.??    0.??    0.??     0.??    0.??    0.??
vec            ...
hybrid         ...
rerank         ...
exp+H          ...
```

## Acceptance

- 72 query × 5 path = 360 measurement. expanded path 는 cloud 호출 12 회
  (회전마다 모든 path 가 다르지만 expanded 만 cloud 호출 - paraphrase
  생성 cache 가능하면 12, 안 되면 72).
- 모든 path 의 P@1, R@5, MRR, NDCG@5 평균 + σ 출력.
- assertion 은 약하게: `vec.p1 >= BM25.p1 - 0.10`, `rerank.ndcg >= hybrid.ndcg - 0.05`.
- `pytest.mark.search_quality` 마커 필수.

## Forbidden Patterns

- `from tunallama_core.store import Store` ← 존재하지 않음. 정확 import 위와 같음.
- `compute_metrics` 가 dict 반환 가정 ← 실제는 `RetrievalMetrics` dataclass.
- `store.add(text)` ← 존재하지 않음. `record_call(tool_name, inputs, output, ...)` 사용.
- `MockSearchEngine` / `MockStore` ← real `MemoryStore` 사용 필수.
- `np.random` 으로 결과 시뮬 ← 실 검색 path 호출 필수.
- 기존 `test_search_quality_extended.py` 함수 수정 ← 새 파일 별도 작성.

## File path

새 파일: `tests/integration/test_search_quality_lopo.py`. 기존 파일 수정 X.

## Constraints (hard rules)

- 검색 path / metrics 모듈 코드 변경 X (측정만).
- 기존 시드 (12 task + 30 noise) 재사용 - 새 시드 만들지 않음.
- 알고리즘 (BM25 / vector / RRF / reranker) 수정 X.
- Cloud 호출 timeout 최소 600 초 (Phase 4-4 에서 short timeout 으로 fail 4번).
