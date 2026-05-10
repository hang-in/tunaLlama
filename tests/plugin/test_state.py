"""``plugin._state`` 의 lazy 초기화/리셋 검증.

실제 config 파일을 ./.tunallama/config.toml 에 만들고 _ensure() 가 그것을
읽어 client + store 까지 채워주는지 확인. 외부 네트워크는 건드리지 않는다 —
LMStudioClient.__init__ 은 connect 안 하므로.
"""

from __future__ import annotations

import textwrap

import pytest


_CONFIG = textwrap.dedent("""
    [llm]
    provider = "lmstudio"
    temperature = 0.3
    timeout_seconds = 10
    [llm.lmstudio]
    host = "http://localhost:1234/v1"
    model = "nvidia/nemotron-3-nano-4b"

    [memory]
    db_path = "{db}"
    enable_logging = true
    enable_recall = true
""")


@pytest.fixture
def isolated_state(monkeypatch, tmp_path):
    """plugin._state 모듈 변수를 비우고 cwd 를 격리된 tmp 디렉토리로 옮긴다."""
    cdir = tmp_path / ".tunallama"
    cdir.mkdir()
    db = tmp_path / "mem.db"
    (cdir / "config.toml").write_text(_CONFIG.format(db=db))
    monkeypatch.chdir(tmp_path)

    from plugin import _state

    monkeypatch.setattr(_state, "_config", None)
    monkeypatch.setattr(_state, "_client", None)
    monkeypatch.setattr(_state, "_store", None)
    yield _state
    # 명시 정리
    if _state._store is not None:
        _state._store.close()


def test_ensure_initializes_lazily(isolated_state):
    cfg, client, store = isolated_state._ensure()
    assert cfg.llm.provider == "lmstudio"
    assert client is not None
    assert store is not None  # enable_logging=true


def test_ensure_caches_after_first_call(isolated_state):
    cfg1, client1, store1 = isolated_state._ensure()
    cfg2, client2, store2 = isolated_state._ensure()
    assert cfg1 is cfg2
    assert client1 is client2
    assert store1 is store2


def test_reset_closes_store(isolated_state):
    isolated_state._ensure()
    assert isolated_state._store is not None
    isolated_state.reset()
    assert isolated_state._config is None
    assert isolated_state._client is None
    assert isolated_state._store is None


def test_ensure_skips_store_when_logging_disabled(monkeypatch, tmp_path):
    cdir = tmp_path / ".tunallama"
    cdir.mkdir()
    body = textwrap.dedent("""
        [llm]
        provider = "lmstudio"
        [llm.lmstudio]
        host = "http://localhost:1234/v1"
        model = "m"
        [memory]
        enable_logging = false
    """)
    (cdir / "config.toml").write_text(body)
    monkeypatch.chdir(tmp_path)

    from plugin import _state

    monkeypatch.setattr(_state, "_config", None)
    monkeypatch.setattr(_state, "_client", None)
    monkeypatch.setattr(_state, "_store", None)

    cfg, client, store = _state._ensure()
    assert store is None
