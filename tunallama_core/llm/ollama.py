"""Ollama provider 구현. 로컬 / 클라우드 모두 같은 SDK 위에서 동작.

차이는 host + Authorization 헤더뿐 — 한 클래스 + 두 팩토리 함수로 처리.
"""

from __future__ import annotations

import time
from typing import Any

from ..config.models import OllamaCloudProviderConfig, OllamaProviderConfig
from ..errors import LLMError
from .base import ChatResponse, LLMClient


def _extract_text(resp: Any) -> str:
    """ollama SDK 응답에서 본문 추출. 신규(객체) / 구버전(dict) 모두 수용."""
    if isinstance(resp, dict):
        return resp.get("message", {}).get("content", "")
    msg = getattr(resp, "message", None)
    return getattr(msg, "content", "") if msg is not None else ""


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
        # 지연 import — `ollama` 미설치 환경에서도 다른 provider 테스트가 돌도록.
        from ollama import Client  # type: ignore[import-not-found]

        self._client = Client(host=host, headers=headers, timeout=timeout)
        self._model = model
        self._options = {"temperature": temperature, "num_ctx": num_ctx}

    def chat(self, *, system: str, prompt: str) -> ChatResponse:
        from ollama import ResponseError  # type: ignore[import-not-found]

        start = time.monotonic()
        try:
            resp = self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                options=self._options,
            )
        except ResponseError as e:
            raise LLMError(f"Ollama 호출 실패: {e}") from e
        return ChatResponse(
            text=_extract_text(resp),
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
