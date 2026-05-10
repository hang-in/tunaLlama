"""테스트 환경 fixture.

- Ollama 통합 테스트 → **Ollama Cloud** (qwen3.6:27b-coding-mxfp8). 키 미설정/장애 시 skip.
- LM Studio 통합 테스트 → 로컬 ``nvidia/nemotron-3-nano-4b`` 고정. 미로드 시 skip.

자동 발견 / 워밍업 / 폴백은 의도적으로 제거했다 — 사용자 환경에 명시된 모델만 사용.
"""

from __future__ import annotations

import os

import httpx
import pytest

from tunallama_core.config.models import OllamaCloudProviderConfig

OLLAMA_CLOUD_HOST = "https://ollama.com"
OLLAMA_CLOUD_MODEL = "devstral-small-2:24b"
OLLAMA_CLOUD_API_KEY_ENV = "OLLAMA_CLOUD_API_KEY"

LMSTUDIO_HOST = "http://localhost:1234/v1"
LMSTUDIO_MODEL = "nvidia/nemotron-3-nano-4b"


@pytest.fixture(scope="session")
def ollama_cloud_cfg() -> OllamaCloudProviderConfig:
    if not os.environ.get(OLLAMA_CLOUD_API_KEY_ENV):
        pytest.skip(f"{OLLAMA_CLOUD_API_KEY_ENV} 미설정")
    return OllamaCloudProviderConfig(
        host=OLLAMA_CLOUD_HOST,
        api_key_env=OLLAMA_CLOUD_API_KEY_ENV,
        model=OLLAMA_CLOUD_MODEL,
    )


@pytest.fixture(scope="session")
def lmstudio_chat_model() -> str:
    try:
        r = httpx.get(LMSTUDIO_HOST + "/models", timeout=3)
        r.raise_for_status()
        ids = {x["id"] for x in r.json().get("data", []) if x.get("id")}
    except Exception as e:
        pytest.skip(f"LM Studio 미가용 ({LMSTUDIO_HOST}): {e}")
    if LMSTUDIO_MODEL not in ids:
        pytest.skip(f"LM Studio 에 {LMSTUDIO_MODEL} 모델 미로드")
    return LMSTUDIO_MODEL
