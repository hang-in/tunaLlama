"""HyDE 단위 테스트."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from tunallama_core.errors import RecallError
from tunallama_core.llm.base import ChatResponse, LLMClient
from tunallama_core.memory.hyde import generate_hyde
from tunallama_core.memory.search import recall_hyde
from tunallama_core.memory.store import MemoryStore


@dataclass
class _FakeClient(LLMClient):
    response_text: str
    raise_exc: Exception | None = None

    def chat(self, *, system: str, prompt: str, response_schema: Any = None) -> ChatResponse:
        if self.raise_exc is not None:
            raise self.raise_exc
        return ChatResponse(text=self.response_text, model="fake", duration_ms=1)


def test_generate_hyde_basic():
    c = _FakeClient(response_text="A description of memory leak debugging.")
    out = generate_hyde("GC 안 돌아감", client=c)
    assert out == "A description of memory leak debugging."


def test_generate_hyde_strips_code_fence():
    c = _FakeClient(response_text="```\nplain text\n```")
    out = generate_hyde("any", client=c)
    assert out == "plain text"


def test_generate_hyde_empty_falls_back():
    c = _FakeClient(response_text="")
    assert generate_hyde("original", client=c) == "original"


def test_generate_hyde_exception_falls_back():
    c = _FakeClient(response_text="", raise_exc=RuntimeError("api error"))
    assert generate_hyde("original", client=c) == "original"


def test_generate_hyde_empty_query_returns_as_is():
    c = _FakeClient(response_text="not used")
    assert generate_hyde("", client=c) == ""
    assert generate_hyde("  ", client=c) == "  "


@pytest.fixture
def small_store(tmp_path):
    db = tmp_path / "hyde.db"
    store = MemoryStore(
        db, korean_tokenizer="kiwi", enable_embeddings=False
    ).open()
    for phrase in [
        "memory leak detection in python",
        "garbage collection debugging",
        "validate email regex",
    ]:
        store.record_call(
            tool_name="seed", inputs={"q": phrase}, output=f"out for {phrase}",
            model="seed", duration_ms=1,
        )
    yield store
    store.close()


def test_recall_hyde_invalid_base(small_store):
    c = _FakeClient(response_text="any")
    with pytest.raises(RecallError):
        recall_hyde(small_store, "q", client=c, base="invalid")


def test_recall_hyde_uses_hypothetical_doc(small_store):
    """가상 답변 텍스트 ('memory leak') 로 BM25 검색 → 첫 record 매칭."""
    c = _FakeClient(
        response_text="A bug in Python where garbage collection fails to "
        "free memory due to circular references."
    )
    r = recall_hyde(
        small_store, "메모리 문제", client=c, base="bm25", limit=5
    )
    assert len(r.snippets) >= 1
    top = r.snippets[0]
    assert "memory" in top.inputs_summary.lower() or "garbage" in top.inputs_summary.lower()


def test_recall_hyde_falls_back_on_llm_fail(small_store):
    """LLM 실패 시 원 query 로 fallback."""
    c = _FakeClient(response_text="", raise_exc=RuntimeError("api down"))
    r = recall_hyde(
        small_store, "memory leak", client=c, base="bm25", limit=5
    )
    assert len(r.snippets) >= 1
