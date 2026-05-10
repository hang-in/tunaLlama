import textwrap
from pathlib import Path

import pytest

from tunallama_core.config.loader import find_config_path, load_config
from tunallama_core.errors import ConfigError

_OLLAMA_TOML = textwrap.dedent("""
    [llm]
    provider = "ollama"
    temperature = 0.3
    timeout_seconds = 60
    [llm.ollama]
    host = "http://localhost:11434"
    model = "qwen2.5:32b"
    num_ctx = 4096
""")


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(body)
    return p


def test_load_basic_ollama(tmp_path):
    cfg = load_config(_write(tmp_path, _OLLAMA_TOML))
    assert cfg.llm.provider == "ollama"
    assert cfg.llm.ollama is not None
    assert cfg.llm.ollama.model == "qwen2.5:32b"
    assert cfg.llm.ollama.num_ctx == 4096
    assert cfg.llm.temperature == 0.3
    assert cfg.llm.timeout_seconds == 60
    assert cfg.source_path is not None


def test_load_ollama_cloud(tmp_path):
    body = textwrap.dedent("""
        [llm]
        provider = "ollama_cloud"
        [llm.ollama_cloud]
        host = "https://ollama.com"
        api_key_env = "OLLAMA_API_KEY"
        model = "qwen2.5-coder:32b"
    """)
    cfg = load_config(_write(tmp_path, body))
    active = cfg.llm.active()
    assert active.api_key_env == "OLLAMA_API_KEY"  # type: ignore[union-attr]


def test_load_lmstudio(tmp_path):
    body = textwrap.dedent("""
        [llm]
        provider = "lmstudio"
        [llm.lmstudio]
        host = "http://localhost:1234/v1"
        model = "qwen2.5-coder-32b-instruct"
    """)
    cfg = load_config(_write(tmp_path, body))
    active = cfg.llm.active()
    assert active.api_key == "lm-studio"  # type: ignore[union-attr]


def test_unknown_provider(tmp_path):
    body = (
        '[llm]\nprovider = "openai"\n'
        '[llm.ollama]\nhost="x"\nmodel="y"\n'
    )
    with pytest.raises(ConfigError, match="provider"):
        load_config(_write(tmp_path, body))


def test_active_section_missing(tmp_path):
    body = (
        '[llm]\nprovider = "lmstudio"\n'
        '[llm.ollama]\nhost="x"\nmodel="y"\n'
    )
    with pytest.raises(ConfigError, match="lmstudio"):
        load_config(_write(tmp_path, body))


@pytest.mark.parametrize("temp", [-0.1, 2.1])
def test_temperature_out_of_range(tmp_path, temp):
    body = (
        f'[llm]\nprovider = "ollama"\ntemperature = {temp}\n'
        '[llm.ollama]\nhost="x"\nmodel="y"\n'
    )
    with pytest.raises(ConfigError, match="temperature"):
        load_config(_write(tmp_path, body))


@pytest.mark.parametrize("temp", [0.0, 1.0, 2.0])
def test_temperature_in_range(tmp_path, temp):
    body = (
        f'[llm]\nprovider = "ollama"\ntemperature = {temp}\n'
        '[llm.ollama]\nhost="x"\nmodel="y"\n'
    )
    cfg = load_config(_write(tmp_path, body))
    assert cfg.llm.temperature == temp


@pytest.mark.parametrize("v", [0, -1])
def test_timeout_non_positive(tmp_path, v):
    body = (
        f'[llm]\nprovider = "ollama"\ntimeout_seconds = {v}\n'
        '[llm.ollama]\nhost="x"\nmodel="y"\n'
    )
    with pytest.raises(ConfigError, match="timeout"):
        load_config(_write(tmp_path, body))


def test_missing_llm_section(tmp_path):
    p = _write(tmp_path, '[memory]\ndb_path="/tmp/x.db"\n')
    with pytest.raises(ConfigError, match=r"\[llm\]"):
        load_config(p)


def test_unknown_korean_tokenizer(tmp_path):
    body = _OLLAMA_TOML + '\n[memory]\nkorean_tokenizer = "mecab"\n'
    with pytest.raises(ConfigError, match="korean_tokenizer"):
        load_config(_write(tmp_path, body))


@pytest.mark.parametrize("tok", ["kiwi", "konlpy_okt", "none"])
def test_known_korean_tokenizer(tmp_path, tok):
    body = _OLLAMA_TOML + f'\n[memory]\nkorean_tokenizer = "{tok}"\n'
    cfg = load_config(_write(tmp_path, body))
    assert cfg.memory.korean_tokenizer == tok


def test_auto_recall_invalid(tmp_path):
    body = _OLLAMA_TOML + '\n[routing]\nauto_recall = "maybe"\n'
    with pytest.raises(ConfigError, match="auto_recall"):
        load_config(_write(tmp_path, body))


@pytest.mark.parametrize("v", ["always", "on_request", "never"])
def test_auto_recall_known(tmp_path, v):
    body = _OLLAMA_TOML + f'\n[routing]\nauto_recall = "{v}"\n'
    cfg = load_config(_write(tmp_path, body))
    assert cfg.routing.auto_recall == v


def test_recall_limit_non_positive(tmp_path):
    body = _OLLAMA_TOML + "\n[routing]\nrecall_limit = 0\n"
    with pytest.raises(ConfigError, match="recall_limit"):
        load_config(_write(tmp_path, body))


def test_logging_level_invalid(tmp_path):
    body = _OLLAMA_TOML + '\n[logging]\nlevel = "TRACE"\n'
    with pytest.raises(ConfigError, match="level"):
        load_config(_write(tmp_path, body))


def test_logging_file_expansion(tmp_path):
    body = (
        _OLLAMA_TOML
        + '\n[logging]\nlevel = "INFO"\nfile = "~/.tunallama/test.log"\n'
    )
    cfg = load_config(_write(tmp_path, body))
    assert cfg.logging.file is not None
    assert "~" not in str(cfg.logging.file)


def test_db_path_expansion(tmp_path):
    body = _OLLAMA_TOML + '\n[memory]\ndb_path = "~/.tunallama/memory.db"\n'
    cfg = load_config(_write(tmp_path, body))
    assert "~" not in str(cfg.memory.db_path)


def test_explicit_path_missing(tmp_path):
    p = tmp_path / "missing.toml"
    with pytest.raises(ConfigError, match="명시"):
        find_config_path(p)


def test_find_path_returns_explicit_when_exists(tmp_path):
    p = _write(tmp_path, _OLLAMA_TOML)
    assert find_config_path(p) == p


def test_find_path_searches_cwd(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / ".tunallama").mkdir(parents=True)
    target = proj / ".tunallama" / "config.toml"
    target.write_text(_OLLAMA_TOML)
    monkeypatch.chdir(proj)
    assert find_config_path() == Path(".tunallama") / "config.toml"


def test_find_path_no_candidates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "no_home")
    with pytest.raises(ConfigError, match="찾을 수 없"):
        find_config_path()


def test_load_minimum_uses_defaults(tmp_path):
    body = textwrap.dedent("""
        [llm]
        provider = "ollama"
        [llm.ollama]
        host = "http://localhost:11434"
        model = "qwen2.5:32b"
    """)
    cfg = load_config(_write(tmp_path, body))
    assert cfg.memory.korean_tokenizer == "kiwi"
    assert cfg.memory.enable_logging is True
    assert cfg.memory.enable_recall is True
    assert cfg.routing.auto_recall == "on_request"
    assert cfg.routing.recall_limit == 5
    assert cfg.logging.level == "INFO"
    assert cfg.logging.file is None
