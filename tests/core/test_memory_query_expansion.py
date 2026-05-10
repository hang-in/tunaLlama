"""query_expansion + recall_expanded 단위 테스트."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pytest

from tunallama_core.errors import RecallError
from tunallama_core.llm.base import ChatResponse, LLMClient
from tunallama_core.memory.query_expansion import expand_query
from tunallama_core.memory.search import recall_expanded
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


@dataclass
class StaticClient(LLMClient):
    text: str = ""
    calls: list[dict] = field(default_factory=list)

    def chat(self, *, system, prompt, response_schema=None) -> ChatResponse:
        self.calls.append({"system": system, "prompt": prompt})
        return ChatResponse(text=self.text, model="fake", duration_ms=1)


# --- expand_query ---


def test_expand_returns_only_query_when_response_empty():
    c = StaticClient(text="")
    out = expand_query(c, "이메일 검증")
    assert out == ["이메일 검증"]


def test_expand_strips_numbering_and_bullets():
    c = StaticClient(text="1. email validation\n- 메일 검증\n* RFC 5322\n> 정규식 매칭")
    out = expand_query(c, "이메일 검증")
    assert out == [
        "이메일 검증",
        "email validation",
        "메일 검증",
        "RFC 5322",
        "정규식 매칭",
    ]


def test_expand_dedup_against_original():
    c = StaticClient(text="이메일 검증\nemail validation\n이메일 검증")
    out = expand_query(c, "이메일 검증")
    assert out.count("이메일 검증") == 1
    assert "email validation" in out


def test_expand_max_expansions_limit():
    c = StaticClient(text="a\nb\nc\nd\ne\nf")
    out = expand_query(c, "x", max_expansions=3)
    assert len(out) == 4  # 원본 + 3
    assert out[0] == "x"


def test_expand_swallows_chat_exception():
    class Boom(LLMClient):
        def chat(self, *, system, prompt, response_schema=None):
            raise RuntimeError("network")

    out = expand_query(Boom(), "x")
    assert out == ["x"]


def test_expand_zero_or_empty_query():
    assert expand_query(StaticClient(), "") == [""]
    assert expand_query(StaticClient(text="a\nb"), "x", max_expansions=0) == ["x"]


# --- recall_expanded ---


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "qe.db", korean_tokenizer="kiwi") as s:
        yield s


def test_recall_expanded_invalid_mode_raises(store):
    c = StaticClient(text="")
    with pytest.raises(RecallError, match="mode"):
        recall_expanded(store, "x", client=c, mode="bogus")


def test_recall_expanded_zero_limit_raises(store):
    c = StaticClient(text="")
    with pytest.raises(RecallError, match="limit"):
        recall_expanded(store, "x", client=c, limit=0)


def test_recall_expanded_bm25_uses_expansions_for_recall(store):
    """expansion 이 BM25 가 못 잡는 paraphrase 를 잡아준다."""
    rid_kor = store.record_call(
        tool_name="t", inputs={"q": "메모리 누수"}, output="x",
        model="m", duration_ms=1,
    )
    rid_eng = store.record_call(
        tool_name="t", inputs={"q": "memory leak detection"}, output="y",
        model="m", duration_ms=1,
    )
    # query 만으로는 한쪽만 잡힘. expansion 으로 양쪽 가져와야.
    c = StaticClient(text="memory leak detection\n메모리 누수\nGC issue")
    r = recall_expanded(store, "메모리 누수", client=c, mode="bm25", limit=10)
    ids = {s.full_id for s in r.snippets}
    assert rid_kor in ids
    assert rid_eng in ids


def test_recall_expanded_calls_llm_once(store):
    c = StaticClient(text="alt1\nalt2")
    store.record_call(
        tool_name="t", inputs={"q": "x"}, output="y",
        model="m", duration_ms=1,
    )
    recall_expanded(store, "x", client=c, mode="bm25")
    assert len(c.calls) == 1  # LLM 은 expansion 1회만


def test_recall_expanded_falls_back_to_single_query_when_llm_fails(store):
    """LLM 실패 시 원 query 만으로 동작."""

    class Boom(LLMClient):
        def chat(self, *, system, prompt, response_schema=None):
            raise RuntimeError("down")

    rid = store.record_call(
        tool_name="t", inputs={"q": "alpha"}, output="y",
        model="m", duration_ms=1,
    )
    r = recall_expanded(store, "alpha", client=Boom(), mode="bm25")
    assert any(s.full_id == rid for s in r.snippets)
