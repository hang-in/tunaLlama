"""``tunallama init`` 대화식 흐름 테스트.

input() 은 ``builtins.input`` 으로 모듈 레벨 monkeypatch.
"""

from __future__ import annotations

from pathlib import Path


from tunallama_core.cli.init_cmd import run_init


def _stub_input(answers):
    it = iter(answers)
    return lambda *_args, **_kwargs: next(it)


def _patch_no_discovery(monkeypatch):
    monkeypatch.setattr(
        "tunallama_core.cli.init_cmd._discover_ollama_models", lambda host: []
    )
    monkeypatch.setattr(
        "tunallama_core.cli.init_cmd._discover_lmstudio_models", lambda host: []
    )


def test_init_creates_ollama_config_typing_model_directly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_no_discovery(monkeypatch)
    answers = [
        "1",                          # provider = ollama
        "http://localhost:11434",     # host
        "qwen3.5:9b",                 # model (typed)
        "y",                          # enable_logging
        "y",                          # enable_recall
        "on_request",                 # auto_recall
    ]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    rc = run_init(global_=False, force=False)
    assert rc == 0
    body = (tmp_path / ".tunallama" / "config.toml").read_text()
    assert 'provider = "ollama"' in body
    assert 'model = "qwen3.5:9b"' in body
    assert "enable_logging = true" in body
    assert 'auto_recall = "on_request"' in body


def test_init_picks_discovered_ollama_model_by_index(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "tunallama_core.cli.init_cmd._discover_ollama_models",
        lambda host: ["foo:7b", "bar:13b", "baz:32b"],
    )
    answers = [
        "1", "http://localhost:11434", "2",  # index 2 → bar:13b
        "y", "y", "always",
    ]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    rc = run_init()
    assert rc == 0
    body = (tmp_path / ".tunallama" / "config.toml").read_text()
    assert 'model = "bar:13b"' in body
    assert 'auto_recall = "always"' in body


def test_init_refuses_existing_without_force(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / ".tunallama" / "config.toml"
    target.parent.mkdir()
    target.write_text("# pre-existing")
    monkeypatch.setattr(
        "builtins.input", lambda *_a, **_k: ""
    )
    rc = run_init(global_=False, force=False)
    assert rc == 1
    # 보존됨
    assert target.read_text() == "# pre-existing"


def test_init_force_overwrites_and_disables_logging(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / ".tunallama" / "config.toml"
    target.parent.mkdir()
    target.write_text("# old")
    _patch_no_discovery(monkeypatch)
    # logging=n → recall 질문 skip → auto_recall=never
    answers = ["1", "http://localhost:11434", "m", "n"]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    rc = run_init(global_=False, force=True)
    assert rc == 0
    body = target.read_text()
    assert "# old" not in body
    assert "enable_logging = false" in body
    assert "enable_recall = false" in body
    assert 'auto_recall = "never"' in body


def test_init_ollama_cloud_with_env_check(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MY_KEY", "secret")
    answers = [
        "2",                       # ollama_cloud
        "https://ollama.com",
        "MY_KEY",                  # api_key_env
        "devstral-small-2:24b",    # model
        "y", "y", "on_request",
    ]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    rc = run_init()
    assert rc == 0
    body = (tmp_path / ".tunallama" / "config.toml").read_text()
    assert 'provider = "ollama_cloud"' in body
    assert 'api_key_env = "MY_KEY"' in body
    assert 'model = "devstral-small-2:24b"' in body


def test_init_lmstudio_with_discovered_model(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "tunallama_core.cli.init_cmd._discover_lmstudio_models",
        lambda host: ["nano-4b", "gemma-7b"],
    )
    answers = [
        "3",                          # lmstudio
        "http://localhost:1234/v1",
        "1",                          # 첫 번째 모델
        "y", "y", "always",
    ]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    rc = run_init()
    assert rc == 0
    body = (tmp_path / ".tunallama" / "config.toml").read_text()
    assert 'provider = "lmstudio"' in body
    assert 'model = "nano-4b"' in body


def test_init_retries_on_invalid_provider_choice(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_no_discovery(monkeypatch)
    answers = [
        "wrong",                  # invalid
        "9",                      # invalid
        "1",                      # finally valid (ollama)
        "http://localhost:11434",
        "m",
        "n",                      # logging=n
    ]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    rc = run_init()
    assert rc == 0


def test_init_global_writes_to_home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _patch_no_discovery(monkeypatch)
    answers = ["1", "http://x", "m", "n"]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    rc = run_init(global_=True)
    assert rc == 0
    assert (tmp_path / ".tunallama" / "config.toml").exists()


def test_init_ollama_cloud_warns_when_env_missing(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UNSET_KEY", raising=False)
    answers = [
        "2", "https://ollama.com", "UNSET_KEY", "model-x",
        "y", "y", "on_request",
    ]
    monkeypatch.setattr(
        "builtins.input", _stub_input(answers)
    )
    run_init()
    captured = capsys.readouterr().out
    assert "UNSET_KEY" in captured
    assert "[!]" in captured
