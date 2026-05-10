"""MCP 도구 함수가 backend 도구를 올바르게 호출/기록하는지 검증.

@mcp.tool() 데코레이터는 함수를 그대로 두고 등록만 하므로 직접 호출 가능.
"""

from __future__ import annotations

from plugin import mcp_server


def test_tuna_generate_code_calls_backend(fake_state):
    out = mcp_server.tuna_generate_code("validate email", "python")
    assert out == fake_state["client"].text
    rec = fake_state["store"].get(1)
    assert rec is not None
    assert rec.tool_name == "generate_code"


def test_tuna_review_code_focus(fake_state):
    mcp_server.tuna_review_code("def x(): pass", "security")
    sent = fake_state["client"].calls[-1]
    assert "Focus: security" in sent["prompt"]


def test_tuna_explain_code(fake_state):
    mcp_server.tuna_explain_code("print(1)", "beginner")
    assert "Audience: beginner" in fake_state["client"].calls[-1]["prompt"]


def test_tuna_refactor_code(fake_state):
    mcp_server.tuna_refactor_code("def f(): pass", "rename to g")
    assert "Goal: rename to g" in fake_state["client"].calls[-1]["prompt"]


def test_tuna_fix_code(fake_state):
    mcp_server.tuna_fix_code("x =", "SyntaxError")
    assert "SyntaxError" in fake_state["client"].calls[-1]["prompt"]


def test_tuna_write_tests(fake_state):
    mcp_server.tuna_write_tests("def f(): pass", "pytest")
    assert "Framework: pytest" in fake_state["client"].calls[-1]["prompt"]


def test_tuna_general_task(fake_state):
    mcp_server.tuna_general_task("summarize", "ctx")
    p = fake_state["client"].calls[-1]["prompt"]
    assert "Task: summarize" in p
    assert "ctx" in p


def test_tuna_review_file_reads_file(fake_state, tmp_path):
    f = tmp_path / "x.py"
    f.write_text("def login(): pass")
    out = mcp_server.tuna_review_file(str(f), "security")
    assert out == fake_state["client"].text
    assert "def login" in fake_state["client"].calls[-1]["prompt"]
    rec = fake_state["store"].get(1)
    assert rec is not None
    assert "def login" not in rec.inputs_json  # content 누출 X


def test_tuna_explain_file(fake_state, tmp_path):
    f = tmp_path / "y.py"
    f.write_text("Y = 1")
    mcp_server.tuna_explain_file(str(f), "expert")
    assert "Y = 1" in fake_state["client"].calls[-1]["prompt"]


def test_tuna_analyze_files(fake_state, tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("X=1")
    b.write_text("Y=2")
    mcp_server.tuna_analyze_files([str(a), str(b)], "deps?")
    p = fake_state["client"].calls[-1]["prompt"]
    assert "X=1" in p and "Y=2" in p
    rec = fake_state["store"].get(1)
    assert rec is not None
    assert "X=1" not in rec.inputs_json


def test_tuna_recall_returns_no_match_message(fake_state):
    out = mcp_server.tuna_recall("nothing-stored")
    assert "매칭 없음" in out


def test_tuna_recall_finds_recorded_entry(fake_state):
    mcp_server.tuna_generate_code("validate email", "python")
    out = mcp_server.tuna_recall("email")
    assert "매칭 1건" in out
    assert "generate_code" in out


def test_tuna_recall_disabled_when_store_none(fake_state_no_store):
    out = mcp_server.tuna_recall("anything")
    assert "비활성" in out


def test_default_empty_string_args_become_none(fake_state):
    """`language=""` 같이 빈 문자열을 받으면 backend 에는 None 으로 전달되어야 한다."""
    mcp_server.tuna_generate_code("just code")
    sent = fake_state["client"].calls[-1]
    # Language 라벨이 prompt 에 포함되지 않으면 language=None 으로 전달된 것.
    assert "Language:" not in sent["prompt"]
