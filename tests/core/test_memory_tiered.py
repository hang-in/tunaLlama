"""Tiered recall 단위 테스트."""

from __future__ import annotations

import pytest

from tunallama_core.memory.search import RecallSnippet
from tunallama_core.memory.store import MemoryStore
from tunallama_core.memory.tiered import TieredRecall, recall_tiered


@pytest.fixture
def small_store(tmp_path):
    db = tmp_path / "tiered.db"
    store = MemoryStore(db, korean_tokenizer="kiwi", enable_embeddings=False).open()
    # BM25 만 작동 (embedding 비활성).
    for phrase in [
        "memory leak detection in Python",
        "garbage collection debugging",
        "validate email format with regex",
        "JSON parsing safety",
    ]:
        store.record_call(
            tool_name="seed", inputs={"q": phrase}, output=f"out for {phrase}",
            model="seed", duration_ms=1,
        )
    yield store
    store.close()


def test_empty_returns_empty(small_store):
    r = recall_tiered(small_store, "", limit=5)
    assert isinstance(r, TieredRecall)
    assert r.exact == () and r.near == () and r.hard == ()


def test_zero_limit(small_store):
    r = recall_tiered(small_store, "memory leak", limit=0)
    assert r.exact == () and r.near == () and r.hard == ()


def test_exact_match_lands_in_exact_tier(small_store):
    """BM25 점수 충분히 negative 한 query 는 exact tier 로 (FTS5 bm25 negative)."""
    r = recall_tiered(
        small_store, "memory leak detection",
        limit=5, threshold_bm25=-0.5, threshold_cosine=2.0,  # cosine 임계 매우 높여 차단
    )
    # 키워드 일치하는 record (BM25 score < -0.5) 는 exact 에 들어가야.
    assert len(r.exact) >= 1
    # vector 비활성 (enable_embeddings=False) 이라 near = ().
    assert r.near == ()


def test_confident_property_excludes_hard(small_store):
    r = recall_tiered(small_store, "memory leak", limit=5)
    # confident 는 exact + near 만.
    assert all(s in r.exact or s in r.near for s in r.confident)
    # hard 는 confident 에 없어야.
    for s in r.hard:
        assert s not in r.confident


def test_iter_yields_all_tiers(small_store):
    r = recall_tiered(small_store, "validate email", limit=5, threshold_bm25=-0.5)
    items = list(r)
    # 길이 = exact + near + hard.
    assert len(items) == len(r.exact) + len(r.near) + len(r.hard)


def test_threshold_too_strict_pushes_all_to_hard(small_store):
    """impossibly strict 임계 → 모든 후보가 hard tier."""
    r = recall_tiered(
        small_store, "memory leak",
        limit=5, threshold_bm25=-10000.0, threshold_cosine=10000.0,
    )
    assert r.exact == () and r.near == ()
    # hybrid 가 후보 잡았으면 hard 에 들어감.
    assert isinstance(r.hard, tuple)


def test_returns_recall_snippet_instances(small_store):
    r = recall_tiered(small_store, "JSON parsing", limit=3, threshold_bm25=-0.5)
    for s in r:
        assert isinstance(s, RecallSnippet)
        assert s.full_id > 0
