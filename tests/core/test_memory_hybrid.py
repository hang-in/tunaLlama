"""Phase 2-2 — recall_hybrid (BM25 + 벡터 RRF)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from tunallama_core.errors import RecallError
from tunallama_core.memory.search import recall_hybrid
from tunallama_core.memory.store import MemoryStore
from tunallama_core.memory.vector import EMBEDDING_DIM


def _fake_embed(text: str) -> np.ndarray:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    vec = rng.standard_normal(EMBEDDING_DIM, dtype=np.float64).astype(np.float32)
    n = float(np.linalg.norm(vec))
    return vec / n if n else vec


@pytest.fixture
def patched_embed(monkeypatch):
    monkeypatch.setattr("tunallama_core.memory.vector.embed", _fake_embed)
    return _fake_embed


@pytest.fixture
def store(tmp_path, patched_embed):
    with MemoryStore(tmp_path / "h.db", korean_tokenizer="kiwi") as s:
        yield s


def test_empty_store_returns_empty_result(store):
    r = recall_hybrid(store, "anything")
    assert r.total_matches == 0
    assert r.snippets == ()


def test_non_positive_limit_raises(store):
    with pytest.raises(RecallError):
        recall_hybrid(store, "x", limit=0)


def test_dedup_when_both_paths_match(store):
    rid = store.record_call(
        tool_name="generate_code",
        inputs={"q": "validate email"},
        output="def is_valid_email(): pass",
        model="m",
        duration_ms=1,
    )
    # 같은 문구로 검색 — BM25 와 벡터 모두 hit
    r = recall_hybrid(store, "validate email")
    ids = [s.full_id for s in r.snippets]
    assert ids.count(rid) == 1  # dedup


def test_vector_only_record_still_appears(monkeypatch, store):
    """BM25 가 못 잡고 벡터만 잡는 record 도 hybrid 결과에 들어간다."""
    rid = store.record_call(
        tool_name="t",
        inputs={"q": "alphabetical"},
        output="related",
        model="m",
        duration_ms=1,
    )
    # BM25 가 빈 결과를 주도록 강제 — recall 을 monkeypatch
    from tunallama_core.memory import search as search_mod
    from tunallama_core.memory.search import RecallResult

    def empty_bm25(*a, **kw):
        return RecallResult(query=kw.get("query", ""), total_matches=0, snippets=())

    monkeypatch.setattr(search_mod, "recall", empty_bm25)
    r = recall_hybrid(store, "alphabetical")
    assert r.total_matches >= 1
    assert any(s.full_id == rid for s in r.snippets)


def test_works_when_no_embeddings_present(tmp_path, monkeypatch):
    """모든 record 가 embedding=NULL 인 store 에서도 BM25 결과만으로 동작."""
    monkeypatch.setattr(
        "tunallama_core.memory.vector.embed",
        lambda text: (_ for _ in ()).throw(RuntimeError("no model")),
    )
    with MemoryStore(tmp_path / "no_vec.db") as s:
        rid = s.record_call(
            tool_name="t",
            inputs={"q": "validate email"},
            output="def is_valid(): pass",
            model="m",
            duration_ms=1,
        )
        # embedding 은 NULL 로 들어갔어야
        row = s.conn.execute(
            "SELECT embedding FROM calls WHERE id=?", (rid,)
        ).fetchone()
        assert row["embedding"] is None
        r = recall_hybrid(s, "validate email")
        assert any(snip.full_id == rid for snip in r.snippets)


def test_limit_truncates_top(store):
    for i in range(6):
        store.record_call(
            tool_name="t",
            inputs={"q": f"alpha{i}"},
            output=f"out{i}",
            model="m",
            duration_ms=1,
        )
    r = recall_hybrid(store, "alpha", limit=3)
    assert len(r.snippets) <= 3


def test_total_matches_counts_unique_ids(store):
    rid_a = store.record_call(
        tool_name="t", inputs={"q": "alpha"}, output="x", model="m", duration_ms=1
    )
    rid_b = store.record_call(
        tool_name="t", inputs={"q": "beta"}, output="y", model="m", duration_ms=1
    )
    r = recall_hybrid(store, "alpha", limit=10)
    # 2 record 모두 등장 가능 (벡터 유사도) — total_matches 는 unique id 합집합
    assert r.total_matches >= 1
    assert r.total_matches <= 2
