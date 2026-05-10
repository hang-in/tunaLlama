"""LMStudioClient 통합 테스트 + 네트워크 실패 단위 검증.

mock 사용 안 함. LM Studio 미가용 시 통합 테스트는 skip.
"""

from __future__ import annotations

import pytest

from tunallama_core.errors import LLMError
from tunallama_core.llm.lmstudio import LMStudioClient

LMSTUDIO_HOST = "http://localhost:1234/v1"


@pytest.mark.integration
def test_chat_returns_text(lmstudio_chat_model):
    c = LMStudioClient(
        host=LMSTUDIO_HOST,
        model=lmstudio_chat_model,
        api_key="lm-studio",
        temperature=0.0,
        timeout=120,
    )
    r = c.chat(system="briefly", prompt="say pong")
    assert r.text.strip()
    assert r.model == lmstudio_chat_model
    assert r.duration_ms > 0


def test_unreachable_host_raises_llmerror():
    """닿을 수 없는 포트 → 자연스러운 httpx 실패 → LLMError 로 wrapping."""
    c = LMStudioClient(
        host="http://127.0.0.1:1",
        model="x",
        api_key="x",
        temperature=0.0,
        timeout=2,
    )
    with pytest.raises(LLMError, match="LM Studio"):
        c.chat(system="s", prompt="p")
