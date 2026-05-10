"""MMR (Maximal Marginal Relevance) - 다양성/관련성 균형 reranking.

Carbonell & Goldstein (1998). 검색 후보들 중 query 와 관련성 + 이미 선택된
결과들과의 다양성 (low similarity) 동시 고려.

수식:
    score(d) = λ · sim(q, d) - (1 - λ) · max_s sim(d, s)
    s ∈ already_selected

λ=1.0 -> 순수 관련성 (변화 없음). λ=0.5 -> 균형. λ=0.0 -> 순수 다양성.

R@5 회복 + σ 감소 위해 도입. 짧은 record 환경에서 top-5 가 같은 task 의
거의 동일한 표현으로 채워지면 R@5 가 정체. MMR 로 다른 paraphrase 끌어올려
R@5 ↑.

cloud 호출 0. 코사인 유사도는 BGE-M3 임베딩 직접 사용.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .search import RecallSnippet
from .store import MemoryStore


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """numpy 1d 벡터 cosine. 둘 다 normalize 됐다고 가정 (BGE-M3 default)."""
    return float(np.dot(a, b))


def mmr_select(
    snippets: Sequence[RecallSnippet],
    *,
    store: MemoryStore,
    query_embedding: np.ndarray,
    k: int = 5,
    lambda_: float = 0.5,
) -> list[RecallSnippet]:
    """``snippets`` 중 ``k`` 개를 MMR 로 선택.

    각 snippet 의 임베딩은 store 의 vector index 에서 조회. 임베딩 없는
    snippet 은 0 벡터로 취급 (다양성 페널티 0).
    """
    if not snippets or k <= 0:
        return []
    if not 0.0 <= lambda_ <= 1.0:
        raise ValueError(f"lambda_ 는 [0, 1] 범위: {lambda_}")

    # snippet id 의 임베딩 batch 조회
    ids = [s.full_id for s in snippets]
    emb_map = store.get_embeddings_for_ids(ids)

    candidates: list[tuple[RecallSnippet, np.ndarray, float]] = []
    for s in snippets:
        emb = emb_map.get(s.full_id)
        if emb is None:
            emb = np.zeros_like(query_embedding)
        rel = _cosine(query_embedding, emb)
        candidates.append((s, emb, rel))

    selected: list[tuple[RecallSnippet, np.ndarray]] = []
    remaining = list(candidates)

    while remaining and len(selected) < k:
        best_idx = -1
        best_score = -float("inf")
        for i, (snip, emb, rel) in enumerate(remaining):
            if not selected:
                score = rel
            else:
                max_sim = max(_cosine(emb, sel_emb) for _, sel_emb in selected)
                score = lambda_ * rel - (1.0 - lambda_) * max_sim
            if score > best_score:
                best_score = score
                best_idx = i
        snip, emb, _ = remaining.pop(best_idx)
        selected.append((snip, emb))

    return [s for s, _ in selected]
