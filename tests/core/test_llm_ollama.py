"""OllamaClient 테스트. ``ollama`` SDK 는 mock 으로 차단."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from tunallama_core.config.models import (
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
)
from tunallama_core.errors import LLMError


@pytest.fixture
def fake_ollama(monkeypatch):
    """``ollama`` 모듈을 메모리에 주입. Client / ResponseError 둘 다 mock."""
    mod = types.ModuleType("ollama")

    class FakeResponseError(Exception):
        pass

    fake_client_class = MagicMock(name="Client")
    mod.Client = fake_client_class
    mod.ResponseError = FakeResponseError
    monkeypatch.setitem(sys.modules, "ollama", mod)
    return mod


def test_local_chat_returns_text(fake_ollama):
    instance = MagicMock()
    instance.chat.return_value = {"message": {"content": "hello"}}
    fake_ollama.Client.return_value = instance

    from tunallama_core.llm.ollama import from_local

    cfg = OllamaProviderConfig(host="http://localhost:11434", model="m", num_ctx=2048)
    c = from_local(cfg, temperature=0.4, timeout=30)
    r = c.chat(system="sys", prompt="hi")

    assert r.text == "hello"
    assert r.model == "m"
    assert r.duration_ms >= 0
    fake_ollama.Client.assert_called_once_with(
        host="http://localhost:11434", headers=None, timeout=30
    )
    sent = instance.chat.call_args
    assert sent.kwargs["model"] == "m"
    assert sent.kwargs["options"] == {"temperature": 0.4, "num_ctx": 2048}
    assert sent.kwargs["messages"][0]["role"] == "system"
    assert sent.kwargs["messages"][1]["content"] == "hi"


def test_local_chat_handles_object_response(fake_ollama):
    instance = MagicMock()
    msg = types.SimpleNamespace(content="object-style")
    instance.chat.return_value = types.SimpleNamespace(message=msg)
    fake_ollama.Client.return_value = instance

    from tunallama_core.llm.ollama import from_local

    cfg = OllamaProviderConfig(host="h", model="m")
    r = from_local(cfg, temperature=0.3, timeout=10).chat(system="s", prompt="p")
    assert r.text == "object-style"


def test_local_chat_response_error_wrapped(fake_ollama):
    instance = MagicMock()
    instance.chat.side_effect = fake_ollama.ResponseError("model not found")
    fake_ollama.Client.return_value = instance

    from tunallama_core.llm.ollama import from_local

    cfg = OllamaProviderConfig(host="h", model="m")
    c = from_local(cfg, temperature=0.3, timeout=10)
    with pytest.raises(LLMError, match="Ollama 호출 실패"):
        c.chat(system="s", prompt="p")


def test_cloud_passes_authorization_header(fake_ollama, monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "sk-test")
    instance = MagicMock()
    instance.chat.return_value = {"message": {"content": "ok"}}
    fake_ollama.Client.return_value = instance

    from tunallama_core.llm.ollama import from_cloud

    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com", api_key_env="OLLAMA_API_KEY", model="m"
    )
    from_cloud(cfg, temperature=0.3, timeout=15)
    fake_ollama.Client.assert_called_once_with(
        host="https://ollama.com",
        headers={"Authorization": "Bearer sk-test"},
        timeout=15,
    )


def test_extract_text_unknown_shape(fake_ollama):
    instance = MagicMock()
    instance.chat.return_value = "not-a-dict-not-an-object"
    fake_ollama.Client.return_value = instance

    from tunallama_core.llm.ollama import from_local

    cfg = OllamaProviderConfig(host="h", model="m")
    r = from_local(cfg, temperature=0.3, timeout=10).chat(system="s", prompt="p")
    assert r.text == ""
