"""LLM client 공통 인터페이스.

provider-별 SDK 차이는 구현 클래스에서 흡수하고, 호출자는 ``chat()`` 만 본다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatResponse:
    text: str
    model: str
    duration_ms: int
    tokens_estimated: int | None = None


class LLMClient(ABC):
    """단일 turn 채팅 인터페이스.

    Streaming 은 일부러 빼둠 — Phase 1 의 delegation 도구는 일괄 결과만 사용.
    """

    @abstractmethod
    def chat(self, *, system: str, prompt: str) -> ChatResponse:
        """system + user 메시지 → 응답."""
