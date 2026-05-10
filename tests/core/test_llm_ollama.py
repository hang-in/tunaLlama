"""OllamaClient 통합 테스트 — Ollama Cloud (qwen3.6:27b-coding-mxfp8).

mock 사용 안 함. 키/네트워크 미가용 시 자동 skip.
"""

from __future__ import annotations

import pytest

from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.errors import ConfigError, LLMError
from tunallama_core.llm.ollama import from_cloud


@pytest.mark.integration
def test_cloud_chat_returns_text(ollama_cloud_cfg):
    r = from_cloud(ollama_cloud_cfg, temperature=0.0, timeout=120).chat(
        system="짧게 한 단어로 답하라.", prompt="hi"
    )
    assert r.text.strip()
    assert r.model == ollama_cloud_cfg.model
    assert r.duration_ms > 0


@pytest.mark.integration
def test_cloud_invalid_model_raises_llmerror(ollama_cloud_cfg):
    bad_cfg = OllamaCloudProviderConfig(
        host=ollama_cloud_cfg.host,
        api_key_env=ollama_cloud_cfg.api_key_env,
        model="this-model-definitely-does-not-exist-xx",
    )
    with pytest.raises(LLMError, match="Ollama"):
        from_cloud(bad_cfg, temperature=0.0, timeout=30).chat(system="s", prompt="p")


def test_resolve_api_key_missing_env_raises(monkeypatch):
    """환경변수 부재 시 ConfigError. 외부 서비스 미가용이어도 통과."""
    monkeypatch.delenv("__NEVER_SET_KEY__", raising=False)
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="__NEVER_SET_KEY__",
        model="m",
    )
    with pytest.raises(ConfigError):
        from_cloud(cfg, temperature=0.0, timeout=10)
