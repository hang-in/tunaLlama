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


def test_mcp_json_registers_server():
    p = PLUGIN_ROOT / ".mcp.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    server = data["mcpServers"]["tunallama"]
    assert server["command"] == "python"
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
])
def test_each_mcp_tool_is_registered(tool_name):
    from plugin import mcp_server

    fn = getattr(mcp_server, tool_name, None)
    assert callable(fn), f"{tool_name} missing in plugin.mcp_server"
