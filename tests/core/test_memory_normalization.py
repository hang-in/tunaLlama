"""normalize_query + recall_normalized 단위 테스트."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from tunallama_core.errors import RecallError
from tunallama_core.llm.base import ChatResponse, LLMClient
from tunallama_core.memory.normalization import normalize_query
from tunallama_core.memory.search import recall_normalized
from tunallama_core.memory.store import MemoryStore


@dataclass
class _FakeClient(LLMClient):
    """테스트용 - chat 결과를 인자로 받음."""

    response_text: str
    raise_exc: Exception | None = None

    def chat(self, *, system: str, prompt: str, response_schema: Any = None) -> ChatResponse:
        if self.raise_exc is not None:
            raise self.raise_exc
        return ChatResponse(text=self.response_text, model="fake", duration_ms=1)


def test_normalize_strips_quotes():
    c = _FakeClient(response_text='"memory leak detection"')
    out = normalize_query("메모리 누수 찾기", client=c)
    assert out == "memory leak detection"


def test_normalize_strips_backticks():
    c = _FakeClient(response_text="`garbage collection failure`")
    out = normalize_query("GC 안 돌아감", client=c)
    assert out == "garbage collection failure"


def test_normalize_takes_first_line():
    c = _FakeClient(response_text="standard form\nextra noise line")
    out = normalize_query("any", client=c)
    assert out == "standard form"


def test_normalize_empty_response_falls_back():
    c = _FakeClient(response_text="")
    out = normalize_query("original query", client=c)
    assert out == "original query"


def test_normalize_whitespace_only_response_falls_back():
    c = _FakeClient(response_text="   \n\n   ")
    out = normalize_query("original", client=c)
    assert out == "original"


def test_normalize_exception_falls_back():
    c = _FakeClient(response_text="", raise_exc=RuntimeError("boom"))
    out = normalize_query("original query", client=c)
    assert out == "original query"


def test_normalize_empty_query_returns_as_is():
    c = _FakeClient(response_text="should not be called")
    assert normalize_query("", client=c) == ""
    assert normalize_query("   ", client=c) == "   "


@pytest.fixture
def small_store(tmp_path):
    db = tmp_path / "norm.db"
    store = MemoryStore(
        db, korean_tokenizer="kiwi", enable_embeddings=False
    ).open()
    for phrase in [
        "memory leak detection",
        "garbage collection debug",
        "validate email regex",
        "JSON parse safe",
    ]:
        store.record_call(
            tool_name="seed", inputs={"q": phrase}, output=f"out for {phrase}",
            model="seed", duration_ms=1,
        )
    yield store
    store.close()


def test_recall_normalized_invalid_base(small_store):
    c = _FakeClient(response_text="memory leak")
    with pytest.raises(RecallError):
        recall_normalized(small_store, "메모리", client=c, base="invalid")


def test_recall_normalized_uses_normalized_query(small_store):
    """정규화 결과로 검색 - 한국어 query 가 영문 record 매칭 가능."""
    c = _FakeClient(response_text="memory leak detection")
    r = recall_normalized(small_store, "메모리 누수", client=c, base="bm25", limit=5)
    # 정규화된 "memory leak detection" 으로 BM25 검색 → 첫 record 매칭.
    assert len(r.snippets) >= 1
    top = r.snippets[0]
    assert "memory leak" in top.inputs_summary.lower()


def test_recall_normalized_fallback_to_original_on_llm_fail(small_store):
    """LLM 호출 실패 시 원 query 로 fallback."""
    c = _FakeClient(response_text="", raise_exc=RuntimeError("api down"))
    r = recall_normalized(
        small_store, "memory leak", client=c, base="bm25", limit=5
    )
    # 원 query "memory leak" 로 검색 - record 매칭됨.
    assert len(r.snippets) >= 1
