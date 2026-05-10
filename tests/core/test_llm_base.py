import pytest

from tunallama_core.llm.base import ChatResponse, LLMClient


def test_chat_response_dataclass():
    r = ChatResponse(text="hi", model="m", duration_ms=12)
    assert r.text == "hi"
    assert r.tokens_estimated is None


def test_chat_response_frozen():
    r = ChatResponse(text="hi", model="m", duration_ms=12)
    with pytest.raises(Exception):
        r.text = "bye"  # type: ignore[misc]


def test_llm_client_is_abstract():
    with pytest.raises(TypeError):
        LLMClient()  # type: ignore[abstract]


def test_subclass_must_implement_chat():
    class Half(LLMClient):
        pass

    with pytest.raises(TypeError):
        Half()  # type: ignore[abstract]


def test_concrete_subclass_works():
    class Echo(LLMClient):
        def chat(self, *, system: str, prompt: str) -> ChatResponse:
            return ChatResponse(text=prompt, model="echo", duration_ms=0)

    r = Echo().chat(system="s", prompt="hello")
    assert r.text == "hello"
