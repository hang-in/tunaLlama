"""Ollama provider 구현. 로컬 / 클라우드 모두 같은 SDK 위에서 동작.

차이는 host + Authorization 헤더뿐 — 한 클래스 + 두 팩토리 함수로 처리.
"""

from __future__ import annotations

import time

import httpx
from ollama import Client, ResponseError

from ..config.models import OllamaCloudProviderConfig, OllamaProviderConfig
from ..errors import LLMError
from .base import ChatResponse, LLMClient


class OllamaClient(LLMClient):
    def __init__(
        self,
        *,
        host: str,
        model: str,
        num_ctx: int,
        temperature: float,
        timeout: int,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._client = Client(host=host, headers=headers, timeout=timeout)
        self._model = model
        self._options = {"temperature": temperature, "num_ctx": num_ctx}

    def chat(
        self,
        *,
        system: str,
        prompt: str,
        response_schema: dict | None = None,
    ) -> ChatResponse:
        # Ollama 의 ``format`` 파라미터는 dict (JSON schema) 또는 "json" 문자열을 받음.
        # schema 가 주어지면 sampling 단에서 형식 강제 — 자연어 명령 무시 회피.
        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": self._options,
        }
        if response_schema is not None:
            kwargs["format"] = response_schema
        start = time.monotonic()
        try:
            resp = self._client.chat(**kwargs)
        except (ResponseError, httpx.HTTPError) as e:
            raise LLMError(f"Ollama 호출 실패: {e}") from e
        return ChatResponse(
            text=resp.message.content,
            model=self._model,
            duration_ms=int((time.monotonic() - start) * 1000),
        )


def from_local(
    cfg: OllamaProviderConfig, *, temperature: float, timeout: int
) -> OllamaClient:
    return OllamaClient(
        host=cfg.host,
        model=cfg.model,
        num_ctx=cfg.num_ctx,
        temperature=temperature,
        timeout=timeout,
    )


def from_cloud(
    cfg: OllamaCloudProviderConfig, *, temperature: float, timeout: int
) -> OllamaClient:
    api_key = cfg.resolve_api_key()
    return OllamaClient(
        host=cfg.host,
        model=cfg.model,
        num_ctx=8192,
        temperature=temperature,
        timeout=timeout,
        headers={"Authorization": f"Bearer {api_key}"},
    )
