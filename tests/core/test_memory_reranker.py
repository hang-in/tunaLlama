"""reranker + recall_reranked 단위 테스트.

cross-encoder 모델 다운로드 회피 위해 ``rerank`` 를 fake (입력 길이 기반 점수)
로 monkeypatch.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from tunallama_core.errors import RecallError
from tunallama_core.memory.search import RecallSnippet, recall_reranked
from tunallama_core.memory.store import MemoryStore
from tunallama_core.memory.vector import EMBEDDING_DIM


def _fake_embed(text: str) -> np.ndarray:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    vec = rng.standard_normal(EMBEDDING_DIM, dtype=np.float64).astype(np.float32)
    n = float(np.linalg.norm(vec))
    return vec / n if n else vec


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    monkeypatch.setattr("tunallama_core.memory.vector.embed", _fake_embed)


def _fake_rerank(query, snippets, *, top_k=5):
    """결정적 fake - inputs_summary 와 query 의 글자 겹침으로 score."""
    def score(s):
        q_chars = set(query.lower())
        s_chars = set(s.inputs_summary.lower())
        return len(q_chars & s_chars)

    ranked = sorted(snippets, key=score, reverse=True)
    return [
        RecallSnippet(
            full_id=s.full_id,
            timestamp=s.timestamp,
            tool_name=s.tool_name,
            inputs_summary=s.inputs_summary,
            output_excerpt=s.output_excerpt,
            score=float(score(s)),
        )
        for s in ranked[:top_k]
    ]


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "rr.db", korean_tokenizer="kiwi") as s:
        yield s


# --- rerank 직접 ---


def test_rerank_empty_input(monkeypatch):
    """빈 입력은 빈 리스트."""
    from tunallama_core.memory.reranker import rerank

    # 모델 로드 회피 — _get_reranker 가 호출되면 안 됨
    def fail_load():
        raise AssertionError("should not call model on empty input")

    monkeypatch.setattr(
        "tunallama_core.memory.reranker._get_reranker", fail_load
    )
    assert rerank("q", []) == []


def test_rerank_top_k_zero():
    from tunallama_core.memory.reranker import rerank

    s = RecallSnippet(1, "t", "tool", "in", "out", 0.0)
    assert rerank("q", [s], top_k=0) == []


def test_rerank_real_call_via_fake(monkeypatch):
    """fake 모델 — 결정적 점수로 동작 확인."""

    class FakeCrossEncoder:
        def __init__(self, *args, **kwargs):
            pass

        def predict(self, pairs):
            return [float(len(p[0]) + len(p[1])) for p in pairs]

    monkeypatch.setattr(
        "sentence_transformers.CrossEncoder", FakeCrossEncoder
    )
    monkeypatch.setattr("tunallama_core.memory.reranker._model", None)

    from tunallama_core.memory.reranker import rerank

    snippets = [
        RecallSnippet(1, "t", "tool", "short", "short", 0.0),
        RecallSnippet(2, "t", "tool", "much longer summary text", "and a longer output excerpt", 0.0),
    ]
    out = rerank("query", snippets, top_k=2)
    # 더 긴 게 위로
    assert out[0].full_id == 2
    assert out[1].full_id == 1


# --- recall_reranked ---


def test_recall_reranked_invalid_base(store):
    with pytest.raises(RecallError, match="base"):
        recall_reranked(store, "x", base="bogus")


def test_recall_reranked_zero_limit(store):
    with pytest.raises(RecallError, match="limit"):
        recall_reranked(store, "x", limit=0)


def test_recall_reranked_empty_store(store):
    r = recall_reranked(store, "anything")
    assert r.total_matches == 0
    assert r.snippets == ()


def test_recall_reranked_uses_reranker(monkeypatch, store):
    monkeypatch.setattr("tunallama_core.memory.reranker.rerank", _fake_rerank)
    monkeypatch.setattr(
        "tunallama_core.memory.search.recall_reranked.__globals__"
        "['recall_reranked'].__defaults__"[:1],  # noop — just trigger reload
        ()[0:0],
    ) if False else None  # placeholder
    # 위 placeholder 무시 — 실제 monkeypatch 는 import path 통해서

    from tunallama_core.memory import reranker as _r
    monkeypatch.setattr(_r, "rerank", _fake_rerank)

    rid_a = store.record_call(
        tool_name="t", inputs={"q": "alphabet"}, output="x",
        model="m", duration_ms=1,
    )
    rid_b = store.record_call(
        tool_name="t", inputs={"q": "zulu"}, output="x",
        model="m", duration_ms=1,
    )
    r = recall_reranked(store, "alphabet", limit=2, base="bm25")
    # alphabet 글자 겹침이 더 큰 rid_a 가 1위
    assert r.snippets[0].full_id == rid_a


def test_recall_reranked_falls_back_when_reranker_fails(monkeypatch, store):
    """reranker 호출 실패 → 1차 결과의 top limit 그대로."""

    def boom(*args, **kwargs):
        raise RuntimeError("model load failed")

    from tunallama_core.memory import reranker as _r
    monkeypatch.setattr(_r, "rerank", boom)

    rid = store.record_call(
        tool_name="t", inputs={"q": "alpha"}, output="y",
        model="m", duration_ms=1,
    )
    r = recall_reranked(store, "alpha", limit=1, base="bm25")
    # 1차 결과 그대로 — 적어도 record 가 떠야
    assert any(s.full_id == rid for s in r.snippets)


def test_recall_reranked_candidate_pool_larger_than_limit(monkeypatch, store):
    """candidate_pool 이 limit 보다 커야 reranker 가 의미. pool 기본 20."""
    from tunallama_core.memory import reranker as _r
    monkeypatch.setattr(_r, "rerank", _fake_rerank)
    for i in range(10):
        store.record_call(
            tool_name="t", inputs={"q": f"alpha{i}"}, output="y",
            model="m", duration_ms=1,
        )
    r = recall_reranked(store, "alpha", limit=3, candidate_pool=10, base="bm25")
    assert len(r.snippets) <= 3
