"""make_client 분기 검증.

OllamaClient/LMStudioClient 의 ``__init__`` 은 네트워크를 사용하지 않으므로
실 SDK 그대로 사용. mock 없음.
"""

from __future__ import annotations

import pytest

from tunallama_core.config.models import (
    LLMConfig,
    LMStudioProviderConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
)
from tunallama_core.errors import ConfigError
from tunallama_core.llm.factory import make_client
from tunallama_core.llm.lmstudio import LMStudioClient
from tunallama_core.llm.ollama import OllamaClient


def test_factory_returns_ollama_for_local():
    cfg = LLMConfig(
        provider="ollama",
        temperature=0.3,
        timeout_seconds=10,
        ollama=OllamaProviderConfig(host="http://localhost:11434", model="m"),
    )
    assert isinstance(make_client(cfg), OllamaClient)


def test_factory_returns_ollama_for_cloud(monkeypatch):
    monkeypatch.setenv("KEY", "v")
    cfg = LLMConfig(
        provider="ollama_cloud",
        temperature=0.3,
        timeout_seconds=10,
        ollama_cloud=OllamaCloudProviderConfig(
            host="https://ollama.com", api_key_env="KEY", model="m"
        ),
    )
    assert isinstance(make_client(cfg), OllamaClient)


def test_factory_returns_lmstudio():
    cfg = LLMConfig(
        provider="lmstudio",
        temperature=0.3,
        timeout_seconds=10,
        lmstudio=LMStudioProviderConfig(
            host="http://localhost:1234/v1", model="m"
        ),
    )
    assert isinstance(make_client(cfg), LMStudioClient)


def test_factory_raises_when_active_section_missing():
    cfg = LLMConfig(provider="ollama", temperature=0.3, timeout_seconds=10)
    with pytest.raises(ConfigError):
        make_client(cfg)


def test_factory_raises_when_cloud_key_missing(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    cfg = LLMConfig(
        provider="ollama_cloud",
        temperature=0.3,
        timeout_seconds=10,
        ollama_cloud=OllamaCloudProviderConfig(
            host="x", api_key_env="MISSING_KEY", model="m"
        ),
    )
    with pytest.raises(ConfigError):
        make_client(cfg)
