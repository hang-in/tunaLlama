"""make_client 분기 테스트. 외부 SDK 는 mock."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from tunallama_core.config.models import (
    LLMConfig,
    LMStudioProviderConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
)
from tunallama_core.llm.factory import make_client
from tunallama_core.llm.lmstudio import LMStudioClient
from tunallama_core.llm.ollama import OllamaClient


@pytest.fixture
def stub_ollama(monkeypatch):
    mod = types.ModuleType("ollama")
    mod.Client = MagicMock(name="Client")
    mod.ResponseError = type("ResponseError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "ollama", mod)
    return mod


def test_factory_returns_ollama_for_local(stub_ollama):
    cfg = LLMConfig(
        provider="ollama",
        temperature=0.3,
        timeout_seconds=10,
        ollama=OllamaProviderConfig(host="h", model="m"),
    )
    c = make_client(cfg)
    assert isinstance(c, OllamaClient)


def test_factory_returns_ollama_for_cloud(stub_ollama, monkeypatch):
    monkeypatch.setenv("KEY", "v")
    cfg = LLMConfig(
        provider="ollama_cloud",
        temperature=0.3,
        timeout_seconds=10,
        ollama_cloud=OllamaCloudProviderConfig(
            host="https://ollama.com", api_key_env="KEY", model="m"
        ),
    )
    c = make_client(cfg)
    assert isinstance(c, OllamaClient)


def test_factory_returns_lmstudio():
    cfg = LLMConfig(
        provider="lmstudio",
        temperature=0.3,
        timeout_seconds=10,
        lmstudio=LMStudioProviderConfig(host="h", model="m"),
    )
    c = make_client(cfg)
    assert isinstance(c, LMStudioClient)


def test_factory_raises_when_active_section_missing():
    from tunallama_core.errors import ConfigError

    cfg = LLMConfig(provider="ollama", temperature=0.3, timeout_seconds=10)
    with pytest.raises(ConfigError):
        make_client(cfg)
