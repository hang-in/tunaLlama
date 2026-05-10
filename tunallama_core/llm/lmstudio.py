"""LM Studio provider — OpenAI 호환 ``/chat/completions`` 엔드포인트.

다른 OpenAI 호환 서버(vLLM 등)가 등장하면 이 클래스를 베이스로 분리할 수 있다.
"""

from __future__ import annotations

import time

import httpx

from ..errors import LLMError
from .base import ChatResponse, LLMClient


class LMStudioClient(LLMClient):
    def __init__(
        self,
        *,
        host: str,
        model: str,
        api_key: str,
        temperature: float,
        timeout: int,
    ) -> None:
        self._url = host.rstrip("/") + "/chat/completions"
        self._model = model
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._temperature = temperature
        self._timeout = timeout

    def chat(
        self,
        *,
        system: str,
        prompt: str,
        response_schema: dict | None = None,
    ) -> ChatResponse:
        body: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": self._temperature,
        }
        # OpenAI 호환 `response_format.json_schema` — strict 모드면 sampling 강제.
        # LM Studio 모델별 지원 차이 있으나, schema 미지원 모델은 strict=False 로 hint 동작.
        if response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "tuna_response",
                    "schema": response_schema,
                    "strict": True,
                },
            }
        start = time.monotonic()
        try:
            r = httpx.post(
                self._url, headers=self._headers, json=body, timeout=self._timeout
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise LLMError(f"LM Studio 호출 실패: {e}") from e

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"LM Studio 응답 형식 이상: {data}") from e

        tokens = None
        usage = data.get("usage") if isinstance(data, dict) else None
        if isinstance(usage, dict):
            tokens = usage.get("total_tokens")

        return ChatResponse(
            text=text,
            model=self._model,
            duration_ms=int((time.monotonic() - start) * 1000),
            tokens_estimated=tokens,
        )
