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


def test_mcp_json_registers_server():
    p = PLUGIN_ROOT / ".mcp.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    server = data["mcpServers"]["tunallama"]
    # 절대경로로 venv python 을 가리켜야 PATH 무관하게 동작.
    assert server["command"].endswith(".venv/bin/python")
    assert server["args"] == ["-m", "plugin.mcp_server"]


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
    "tuna_generate_code", "tuna_review_code", "tuna_explain_code",
    "tuna_refactor_code", "tuna_fix_code", "tuna_write_tests",
    "tuna_general_task", "tuna_review_file", "tuna_explain_file",
    "tuna_analyze_files", "tuna_recall",
    "tuna_dev_review", "tuna_dev_review_from_spec", "tuna_log_limitation",
])
def test_each_mcp_tool_is_registered(tool_name):
    from plugin import mcp_server

    fn = getattr(mcp_server, tool_name, None)
    assert callable(fn), f"{tool_name} missing in plugin.mcp_server"
