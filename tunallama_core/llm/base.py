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

    ``response_schema`` 가 주어지면 provider 의 native JSON Schema 강제 모드를
    켜서 sampling 단에서 형식을 강제한다. 자연어 system 명령이 무시되는 케이스
    (round 1-5 dogfooding 으로 측정) 의 본질적 해결책.
    """

    @abstractmethod
    def chat(
        self,
        *,
        system: str,
        prompt: str,
        response_schema: dict | None = None,
    ) -> ChatResponse:
        """system + user 메시지 → 응답."""
