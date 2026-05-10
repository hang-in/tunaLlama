"""Plugin 의 lazy 싱글톤 — config / client / store.

MCP 도구가 매번 ``_ensure()`` 를 부르고, 모듈 변수에 캐시된 객체를 재사용한다.
테스트는 모듈 변수에 직접 monkeypatch 해서 fake 를 주입할 수 있다.

첫 호출 시 프로젝트 루트의 ``.env`` 를 자동 로드 — settings.json 에 평문 키를
적지 않아도 ``OLLAMA_CLOUD_API_KEY`` 같은 환경변수가 채워진다.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

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
_dotenv_loaded: bool = False


def _load_env_once() -> None:
    """``.env`` 를 cwd → 프로젝트 루트 순으로 한 번만 시도. 실패해도 조용히 통과."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    candidates = (
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    )
    for p in candidates:
        if p.is_file():
            load_dotenv(p, override=False)
            break
    _dotenv_loaded = True


def _ensure() -> tuple[Config, LLMClient, MemoryStore | None]:
    global _config, _client, _store
    if _config is None:
        _load_env_once()
        _config = load_config()
        _client = make_client(_config.llm)
        if _config.memory.enable_logging:
            # device 환경변수 — config 의 embedding_device 가 "auto" 가 아니면 우선 적용.
            if _config.memory.embedding_device != "auto":
                import os
                os.environ.setdefault(
                    "TUNA_EMBEDDING_DEVICE", _config.memory.embedding_device
                )
            _store = MemoryStore(
                _config.memory.db_path,
                korean_tokenizer=_config.memory.korean_tokenizer,
                enable_embeddings=_config.memory.enable_embeddings,
            ).open()
    assert _config is not None
    assert _client is not None
    return _config, _client, _store


def reset() -> None:
    """주로 테스트용 — 캐시된 싱글톤 비우기."""
    global _config, _client, _store, _dotenv_loaded
    if _store is not None:
        _store.close()
    _config = None
    _client = None
    _store = None
    _dotenv_loaded = False
