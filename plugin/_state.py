"""Plugin 의 lazy 싱글톤 — config / client / store.

MCP 도구가 매번 ``_ensure()`` 를 부르고, 모듈 변수에 캐시된 객체를 재사용한다.
테스트는 모듈 변수에 직접 monkeypatch 해서 fake 를 주입할 수 있다.
"""

from __future__ import annotations

from tunallama_core import (
    Config,
    LLMClient,
    MemoryStore,
    load_config,
    make_client,
)

_config: Config | None = None
_client: LLMClient | None = None
_store: MemoryStore | None = None


def _ensure() -> tuple[Config, LLMClient, MemoryStore | None]:
    global _config, _client, _store
    if _config is None:
        _config = load_config()
        _client = make_client(_config.llm)
        if _config.memory.enable_logging:
            _store = MemoryStore(
                _config.memory.db_path,
                korean_tokenizer=_config.memory.korean_tokenizer,
            ).open()
    assert _config is not None
    assert _client is not None
    return _config, _client, _store


def reset() -> None:
    """주로 테스트용 — 캐시된 싱글톤 비우기."""
    global _config, _client, _store
    if _store is not None:
        _store.close()
    _config = None
    _client = None
    _store = None
