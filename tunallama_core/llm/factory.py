"""LLMConfig → LLMClient 매핑."""

from __future__ import annotations

from ..config.models import (
    LLMConfig,
    LMStudioProviderConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
)
from .base import LLMClient
from .lmstudio import LMStudioClient
from .ollama import from_cloud, from_local


def make_client(cfg: LLMConfig) -> LLMClient:
    p = cfg.active()
    t = cfg.temperature
    timeout = cfg.timeout_seconds

    if isinstance(p, OllamaProviderConfig):
        return from_local(p, temperature=t, timeout=timeout)
    if isinstance(p, OllamaCloudProviderConfig):
        return from_cloud(p, temperature=t, timeout=timeout)
    if isinstance(p, LMStudioProviderConfig):
        return LMStudioClient(
            host=p.host,
            model=p.model,
            api_key=p.api_key,
            temperature=t,
            timeout=timeout,
        )
    raise AssertionError(f"unreachable: {type(p).__name__}")
