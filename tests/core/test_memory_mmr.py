"""MMR 단위 테스트.

Phase 9 이후 vector.embed 는 Ollama 서비스를 호출한다. MMR 다양성 검증은
"near-duplicate 는 의미적으로 가깝다" 는 성질에 의존하므로, 서비스 없이도
결정적이고 의미 있게 돌도록 **키워드 기반 fake embed** 로 대체한다(공유 단어가
많을수록 코사인 유사도가 높은 bag-of-words 벡터). CI 는 Ollama 가 없어도 통과.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from tunallama_core.errors import RecallError
from tunallama_core.memory.mmr import mmr_select
from tunallama_core.memory.search import RecallSnippet, recall_mmr
from tunallama_core.memory.store import MemoryStore
from tunallama_core.memory.vector import EMBEDDING_DIM


def _keyword_embed(text: str) -> np.ndarray:
    """결정적 bag-of-words fake — 단어를 dim 에 hash-매핑 후 L2 정규화.
    공유 단어가 많을수록 코사인 유사도가 높다 (near-duplicate 성질 재현)."""
    v = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    for w in text.lower().split():
        idx = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16) % EMBEDDING_DIM
        v[idx] += 1.0
    n = float(np.linalg.norm(v))
    return v / n if n else v


@pytest.fixture
def small_store_with_embeddings(tmp_path, monkeypatch):
    monkeypatch.setattr("tunallama_core.memory.vector.embed", _keyword_embed)
    db = tmp_path / "mmr.db"
    store = MemoryStore(
        db, korean_tokenizer="kiwi", enable_embeddings=True
    ).open()
    for phrase in [
        "memory leak detection",
        "memory leak detection in python",  # near-duplicate of #1
        "garbage collection debug",
        "validate email regex",
        "JSON parser implementation",
    ]:
        store.record_call(
            tool_name="seed", inputs={"q": phrase}, output=f"out for {phrase}",
            model="seed", duration_ms=1,
        )
    yield store
    store.close()


def _snip(rid: int) -> RecallSnippet:
    return RecallSnippet(
        full_id=rid, timestamp="t", tool_name="seed",
        inputs_summary=f"q{rid}", output_excerpt=f"out{rid}", score=0.5,
    )


def test_mmr_empty_returns_empty(small_store_with_embeddings):
    out = mmr_select(
        [], store=small_store_with_embeddings,
        query_embedding=np.zeros(1024), k=5, lambda_=0.5,
    )
    assert out == []


def test_mmr_zero_k_returns_empty(small_store_with_embeddings):
    out = mmr_select(
        [_snip(1)], store=small_store_with_embeddings,
        query_embedding=np.zeros(1024), k=0, lambda_=0.5,
    )
    assert out == []


def test_mmr_invalid_lambda(small_store_with_embeddings):
    with pytest.raises(ValueError):
        mmr_select(
            [_snip(1)], store=small_store_with_embeddings,
            query_embedding=np.zeros(1024), k=1, lambda_=-0.1,
        )
    with pytest.raises(ValueError):
        mmr_select(
            [_snip(1)], store=small_store_with_embeddings,
            query_embedding=np.zeros(1024), k=1, lambda_=1.5,
        )


def test_recall_mmr_invalid_limit(small_store_with_embeddings):
    with pytest.raises(RecallError):
        recall_mmr(small_store_with_embeddings, "q", limit=0)


def test_recall_mmr_invalid_lambda(small_store_with_embeddings):
    with pytest.raises(RecallError):
        recall_mmr(small_store_with_embeddings, "memory", limit=3, lambda_=2.0)


def test_recall_mmr_lambda_one_equals_relevance_only(
    small_store_with_embeddings,
):
    """lambda=1.0 → 다양성 페널티 0, 순수 관련성 순서.

    같은 query 로 hybrid → MMR(λ=1) 호출하면 hybrid 의 top-N 과 같은 순서
    여야. (단, MMR 은 query embedding 으로 다시 sort 하므로 hybrid 의
    BM25+vector RRF 와 정확 같진 않을 수 있음 - top-1 만 일치 검증.)
    """
    r = recall_mmr(
        small_store_with_embeddings, "memory leak", limit=3, lambda_=1.0,
    )
    assert len(r.snippets) >= 1
    # top-1 은 "memory leak" 키워드 매칭 - id 1 또는 2.
    assert r.snippets[0].full_id in {1, 2}


def test_recall_mmr_diversity_at_low_lambda(small_store_with_embeddings):
    """lambda=0.0 (순수 다양성) → near-duplicate (id 1, 2) 둘 다 top 에
    안 들어와야 (둘이 너무 비슷)."""
    r = recall_mmr(
        small_store_with_embeddings, "memory leak", limit=2, lambda_=0.0,
    )
    ids = {s.full_id for s in r.snippets}
    # 첫 번째는 가장 관련성 높은 게 들어가지만, 두 번째는 다양성 우선이라
    # 1, 2 (near-dup) 가 둘 다 들어가지 않아야.
    assert not (1 in ids and 2 in ids)


def test_recall_mmr_default_returns_limit(small_store_with_embeddings):
    r = recall_mmr(small_store_with_embeddings, "memory", limit=3, lambda_=0.5)
    assert 1 <= len(r.snippets) <= 3


def test_recall_mmr_no_embeddings_falls_back(tmp_path):
    """embedding 비활성 store 면 hybrid 결과 limit 까지 (MMR 적용 X)."""
    db = tmp_path / "no_emb.db"
    store = MemoryStore(
        db, korean_tokenizer="kiwi", enable_embeddings=False
    ).open()
    for phrase in ["memory leak", "garbage collection", "json parse"]:
        store.record_call(
            tool_name="seed", inputs={"q": phrase}, output=f"out {phrase}",
            model="seed", duration_ms=1,
        )
    r = recall_mmr(store, "memory", limit=2, lambda_=0.5)
    assert len(r.snippets) >= 1  # hybrid fallback 작동
    store.close()
