"""Adaptive routing 단위 테스트."""

from __future__ import annotations

import pytest

from tunallama_core.memory.adaptive import (
    QueryFeatures,
    extract_features,
    recall_adaptive,
)
from tunallama_core.memory.store import MemoryStore


def test_extract_empty_query():
    f = extract_features("")
    assert f.n_chars == 0
    assert f.n_words == 0
    assert f.has_korean is False


def test_extract_korean_natural():
    f = extract_features("메모리 누수 탐지하는 방법")
    assert f.has_korean is True
    assert f.korean_ratio > 0.3
    assert f.category == "natural"


def test_extract_short_english_keyword():
    f = extract_features("os.path.join")
    assert f.has_code_tokens is True
    assert f.is_short_keyword is True
    assert f.category == "keyword"


def test_extract_mixed_english_natural():
    f = extract_features("how to detect memory leaks in long running python services")
    assert f.has_korean is False
    assert f.is_short_keyword is False  # 단어 많음
    assert f.category == "mixed"


def test_extract_camel_case_token():
    f = extract_features("getUserById")
    assert f.has_code_tokens is True


def test_extract_snake_case_token():
    f = extract_features("rate_limit")
    assert f.has_code_tokens is True
    assert f.is_short_keyword is True


def test_extract_korean_short_phrase_is_natural():
    """짧아도 한국어면 natural (keyword 아님)."""
    f = extract_features("파일 압축")
    assert f.has_korean is True
    assert f.category == "natural"


@pytest.fixture
def small_store(tmp_path):
    db = tmp_path / "adapt.db"
    store = MemoryStore(
        db, korean_tokenizer="kiwi", enable_embeddings=False
    ).open()
    for phrase in [
        "memory leak detection in python",
        "validate email regex",
        "한국어 자연어 검색",
    ]:
        store.record_call(
            tool_name="seed", inputs={"q": phrase},
            output=f"out for {phrase}", model="seed", duration_ms=1,
        )
    yield store
    store.close()


def test_recall_adaptive_keyword_uses_bm25(small_store):
    """식별자성 짧은 영문 → BM25."""
    r = recall_adaptive(small_store, "memory_leak", limit=3)
    assert len(r.snippets) >= 1


def test_recall_adaptive_natural_no_cloud_falls_back(small_store):
    """한국어 query + cloud_client=None → reranked hybrid fallback."""
    r = recall_adaptive(small_store, "한국어 자연어 검색하기", limit=3)
    # embedding 비활성 store 라 reranked 도 hybrid 결과 그대로 - 어쨌든 결과 옴.
    assert len(r.snippets) >= 1


def test_recall_adaptive_mixed_uses_rerank(small_store):
    """영문 자연어 → reranked hybrid path (cloud 0)."""
    r = recall_adaptive(
        small_store, "how to validate user email format with regex",
        limit=3,
    )
    assert len(r.snippets) >= 1


def test_query_features_frozen():
    f = QueryFeatures(0, 0, False, 0.0, False, False)
    with pytest.raises(Exception):
        f.n_chars = 100  # type: ignore[misc]
