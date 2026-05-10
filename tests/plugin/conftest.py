"""Plugin 테스트 fixture — _state 싱글톤을 결정적으로 채운다."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from tunallama_core import (
    ChatResponse,
    Config,
    LLMClient,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    MemoryStore,
    OllamaProviderConfig,
    RoutingConfig,
)


@dataclass
class StaticClient(LLMClient):
    text: str = "ok"
    model: str = "fake"
    duration_ms: int = 1
    tokens_estimated: int | None = None
    calls: list[dict] = field(default_factory=list)

    def chat(self, *, system: str, prompt: str) -> ChatResponse:
        self.calls.append({"system": system, "prompt": prompt})
        return ChatResponse(
            text=self.text,
            model=self.model,
            duration_ms=self.duration_ms,
            tokens_estimated=self.tokens_estimated,
        )


def _build_config(db_path) -> Config:
    return Config(
        llm=LLMConfig(
            provider="ollama",
            temperature=0.3,
            timeout_seconds=10,
            ollama=OllamaProviderConfig(host="http://localhost:11434", model="m"),
        ),
        memory=MemoryConfig(db_path=db_path, korean_tokenizer="kiwi"),
        routing=RoutingConfig(),
        logging=LoggingConfig(),
    )


@pytest.fixture
def static_client() -> StaticClient:
    return StaticClient()


@pytest.fixture
def fake_state(monkeypatch, static_client, tmp_path):
    """``plugin._state`` 의 싱글톤을 fake 로 채워서 _ensure() 호출 시 init 을 건너뛰게 한다."""
    from plugin import _state

    db = tmp_path / "p.db"
    cfg = _build_config(db)
    store = MemoryStore(db, korean_tokenizer="kiwi").open()
    monkeypatch.setattr(_state, "_config", cfg)
    monkeypatch.setattr(_state, "_client", static_client)
    monkeypatch.setattr(_state, "_store", store)
    yield {"cfg": cfg, "client": static_client, "store": store}
    store.close()


@pytest.fixture
def fake_state_no_store(monkeypatch, static_client, tmp_path):
    """memory 비활성 상태 시뮬레이션 — recall 비활성화 분기 검증용."""
    from plugin import _state

    db = tmp_path / "p.db"
    cfg = _build_config(db)
    cfg = Config(
        llm=cfg.llm,
        memory=MemoryConfig(db_path=db, enable_recall=False),
        routing=cfg.routing,
        logging=cfg.logging,
    )
    monkeypatch.setattr(_state, "_config", cfg)
    monkeypatch.setattr(_state, "_client", static_client)
    monkeypatch.setattr(_state, "_store", None)
    yield {"cfg": cfg, "client": static_client}
