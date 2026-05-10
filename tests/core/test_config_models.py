import pytest

from tunallama_core.config.models import (
    LLMConfig,
    LMStudioProviderConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
)
from tunallama_core.errors import ConfigError


def _llm(provider, **kw):
    return LLMConfig(
        provider=provider,
        temperature=0.3,
        timeout_seconds=10,
        ollama=kw.get("ollama"),
        ollama_cloud=kw.get("ollama_cloud"),
        lmstudio=kw.get("lmstudio"),
    )


def test_active_returns_ollama():
    p = OllamaProviderConfig(host="h", model="m")
    assert _llm("ollama", ollama=p).active() is p


def test_active_returns_ollama_cloud():
    p = OllamaCloudProviderConfig(host="h", api_key_env="X", model="m")
    assert _llm("ollama_cloud", ollama_cloud=p).active() is p


def test_active_returns_lmstudio():
    p = LMStudioProviderConfig(host="h", model="m")
    assert _llm("lmstudio", lmstudio=p).active() is p


@pytest.mark.parametrize("provider", ["ollama", "ollama_cloud", "lmstudio"])
def test_active_missing_section_raises(provider):
    cfg = LLMConfig(provider=provider, temperature=0.3, timeout_seconds=10)
    with pytest.raises(ConfigError):
        cfg.active()


def test_resolve_api_key_present(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret")
    p = OllamaCloudProviderConfig(host="h", api_key_env="MY_KEY", model="m")
    assert p.resolve_api_key() == "secret"


def test_resolve_api_key_missing(monkeypatch):
    monkeypatch.delenv("MY_KEY", raising=False)
    p = OllamaCloudProviderConfig(host="h", api_key_env="MY_KEY", model="m")
    with pytest.raises(ConfigError):
        p.resolve_api_key()


def test_resolve_api_key_empty(monkeypatch):
    monkeypatch.setenv("MY_KEY", "")
    p = OllamaCloudProviderConfig(host="h", api_key_env="MY_KEY", model="m")
    with pytest.raises(ConfigError):
        p.resolve_api_key()


def test_dataclasses_are_frozen():
    p = OllamaProviderConfig(host="h", model="m")
    with pytest.raises(Exception):
        p.host = "x"  # type: ignore[misc]


def test_lmstudio_default_api_key():
    p = LMStudioProviderConfig(host="h", model="m")
    assert p.api_key == "lm-studio"


def test_ollama_default_num_ctx():
    p = OllamaProviderConfig(host="h", model="m")
    assert p.num_ctx == 8192
