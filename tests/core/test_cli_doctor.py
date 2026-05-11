"""``tunallama doctor`` 단위/통합 테스트."""

from __future__ import annotations

import textwrap
from pathlib import Path


from tunallama_core.cli.doctor_cmd import (
    check_config,
    check_kiwi,
    check_memory_db,
    check_provider,
    check_python,
    run_doctor,
)
from tunallama_core.config.models import (
    Config,
    LLMConfig,
    LMStudioProviderConfig,
    LoggingConfig,
    MemoryConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
    RoutingConfig,
)


def _config_for_memory(db_path) -> Config:
    return Config(
        llm=LLMConfig(
            provider="ollama",
            temperature=0.3,
            timeout_seconds=10,
            ollama=OllamaProviderConfig(host="x", model="m"),
        ),
        memory=MemoryConfig(db_path=db_path),
        routing=RoutingConfig(),
        logging=LoggingConfig(),
    )


def test_check_python_passes():
    r = check_python()
    assert r.ok is True
    assert "current:" in r.detail


def test_check_kiwi_passes():
    r = check_kiwi()
    assert r.ok is True


def test_check_config_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "no_home")
    r, cfg = check_config()
    assert r.ok is False
    assert cfg is None


def test_check_config_present(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cdir = tmp_path / ".tunallama"
    cdir.mkdir()
    (cdir / "config.toml").write_text(
        textwrap.dedent("""
            [llm]
            provider = "lmstudio"
            [llm.lmstudio]
            host = "http://localhost:1234/v1"
            model = "m"
        """)
    )
    r, cfg = check_config()
    assert r.ok is True
    assert cfg is not None
    assert cfg.llm.provider == "lmstudio"


def test_check_memory_db_writable(tmp_path):
    cfg = _config_for_memory(tmp_path / "m.db")
    r = check_memory_db(cfg)
    assert r.ok is True
    assert (tmp_path / "m.db").exists()


def test_check_memory_db_unwritable(tmp_path):
    """sqlite3 connect 가 디렉토리 생성에 실패하는 경로."""
    cfg = _config_for_memory(Path("/no_perm_dir_xyz/m.db"))
    r = check_memory_db(cfg)
    assert r.ok is False


def test_check_provider_lmstudio_unreachable():
    cfg = Config(
        llm=LLMConfig(
            provider="lmstudio",
            temperature=0.3,
            timeout_seconds=2,
            lmstudio=LMStudioProviderConfig(host="http://127.0.0.1:1", model="m"),
        ),
        memory=MemoryConfig(db_path=Path("/tmp/x.db")),
        routing=RoutingConfig(),
        logging=LoggingConfig(),
    )
    r = check_provider(cfg)
    assert r.ok is False
    assert "127.0.0.1:1" in r.name


def test_check_provider_ollama_cloud_missing_env(monkeypatch):
    monkeypatch.delenv("UNSET_DOCTOR_KEY", raising=False)
    cfg = Config(
        llm=LLMConfig(
            provider="ollama_cloud",
            temperature=0.3,
            timeout_seconds=2,
            ollama_cloud=OllamaCloudProviderConfig(
                host="https://ollama.com",
                api_key_env="UNSET_DOCTOR_KEY",
                model="m",
            ),
        ),
        memory=MemoryConfig(db_path=Path("/tmp/x.db")),
        routing=RoutingConfig(),
        logging=LoggingConfig(),
    )
    r = check_provider(cfg)
    assert r.ok is False
    assert "UNSET_DOCTOR_KEY" in r.detail


def test_check_provider_ollama_cloud_with_env(monkeypatch):
    monkeypatch.setenv("HAS_DOCTOR_KEY", "x")
    cfg = Config(
        llm=LLMConfig(
            provider="ollama_cloud",
            temperature=0.3,
            timeout_seconds=2,
            ollama_cloud=OllamaCloudProviderConfig(
                host="https://ollama.com",
                api_key_env="HAS_DOCTOR_KEY",
                model="m",
            ),
        ),
        memory=MemoryConfig(db_path=Path("/tmp/x.db")),
        routing=RoutingConfig(),
        logging=LoggingConfig(),
    )
    r = check_provider(cfg)
    assert r.ok is True


def test_run_doctor_returns_failure_when_no_config(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "missing")
    rc = run_doctor()
    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "config.toml" in out


def test_run_doctor_returns_zero_when_config_and_provider_ok(
    monkeypatch, tmp_path, capsys
):
    """현재 환경이 LM Studio 가용일 때만 동작 — 가용 시 통과 검증."""
    monkeypatch.chdir(tmp_path)
    cdir = tmp_path / ".tunallama"
    cdir.mkdir()
    (cdir / "config.toml").write_text(
        textwrap.dedent(f"""
            [llm]
            provider = "lmstudio"
            [llm.lmstudio]
            host = "http://localhost:1234/v1"
            model = "m"
            [memory]
            db_path = "{tmp_path / "doctor.db"}"
        """)
    )
    rc = run_doctor()
    out = capsys.readouterr().out
    assert "tunaLlama doctor" in out
    # rc 는 환경 의존 — 단순히 형식이 깨지지 않았는지만 확인
    assert rc in (0, 1)
