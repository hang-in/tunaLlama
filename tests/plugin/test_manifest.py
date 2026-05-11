"""Plugin manifest / 설정 / 스킬·서브에이전트 정의 파일이 정합한지 확인."""

import json
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent.parent / "plugin"


def test_plugin_json_loads_with_required_fields():
    p = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["name"] == "tunaLlama"
    assert data["version"]
    assert data["description"]
    assert data["license"] == "MIT"
    # author 는 object 형식 — Claude Code plugin schema 요구사항
    assert isinstance(data["author"], dict)
    assert data["author"]["name"]


def test_marketplace_json_valid():
    p = PLUGIN_ROOT.parent / ".claude-plugin" / "marketplace.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["name"] == "tunallama-local"
    assert data["plugins"][0]["name"] == "tunaLlama"
    assert data["plugins"][0]["source"].startswith("./")


def test_marketplace_version_matches_plugin_version():
    """marketplace.json 의 plugin version 과 plugin.json 의 version 이 일치해야.

    불일치 시 Claude Code install UI 에 옛 버전 surface (v0.5.3 발견).
    """
    mp = json.loads(
        (PLUGIN_ROOT.parent / ".claude-plugin" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    pj = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert mp["plugins"][0]["version"] == pj["version"], (
        f"marketplace.json version {mp['plugins'][0]['version']} != "
        f"plugin.json version {pj['version']} - install UI 가 옛 버전 표시할 위험"
    )


def test_mcp_json_registers_server():
    p = PLUGIN_ROOT / ".mcp.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    server = data["mcpServers"]["tunallama"]
    # v0.5.9: wrapper script 로 venv python 자동 fallback (mise/pyenv
    # 활성 없이 child process spawn 되면 system python 잡혀서 deps 부재로
    # fail 하던 회귀 해결). wrapper 가 .venv/bin/python 우선, system
    # python fallback.
    assert server["command"] == "${CLAUDE_PLUGIN_ROOT}/bin/tunallama-mcp"
    assert server["args"] == []
    assert "${CLAUDE_PLUGIN_ROOT}" in server.get("cwd", "")


def test_mcp_wrapper_script_exists_and_executable():
    """wrapper script 가 존재 + 실행권한이어야 .mcp.json spawn 이 작동."""
    wrapper = PLUGIN_ROOT / "bin" / "tunallama-mcp"
    assert wrapper.exists(), f"missing: {wrapper}"
    # POSIX 실행권한 - macOS/Linux. Windows 는 별도 .bat (현재 미지원).
    assert wrapper.stat().st_mode & 0o111, f"not executable: {wrapper}"
    body = wrapper.read_text(encoding="utf-8")
    assert body.startswith("#!"), "shebang missing"
    assert "plugin.mcp_server" in body


def test_skill_file_exists_with_frontmatter():
    p = PLUGIN_ROOT / "skills" / "delegate-to-ollama" / "SKILL.md"
    body = p.read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "name: delegate-to-ollama" in body
    assert "description:" in body


def test_subagent_file_exists_with_frontmatter():
    p = PLUGIN_ROOT / "agents" / "tuna-developer.md"
    body = p.read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "name: tuna-developer" in body


@pytest.mark.parametrize("tool_name", [
    "tuna_generate_code", "tuna_review", "tuna_explain",
    "tuna_refactor_code", "tuna_fix_code", "tuna_write_tests",
    "tuna_general_task",
    "tuna_analyze_files", "tuna_recall", "tuna_load_memory",
    "tuna_dev_review", "tuna_dev_review_from_spec", "tuna_log_limitation",
])
def test_each_mcp_tool_is_registered(tool_name):
    from plugin import mcp_server

    fn = getattr(mcp_server, tool_name, None)
    assert callable(fn), f"{tool_name} missing in plugin.mcp_server"
