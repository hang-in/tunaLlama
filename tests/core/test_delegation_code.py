import json

import pytest

from tunallama_core.delegation.code import (
    explain_code,
    fix_code,
    general_task,
    generate_code,
    refactor_code,
    review_code,
    write_tests,
)
from tunallama_core.memory.store import MemoryStore


def _last(static_client):
    return static_client.calls[-1]


def test_generate_code_with_language(static_client):
    generate_code("validate email addresses", language="python", client=static_client)
    sent = _last(static_client)
    assert "Language: python" in sent["prompt"]
    assert "validate email" in sent["prompt"]


def test_generate_code_without_language(static_client):
    generate_code("hello", client=static_client)
    assert _last(static_client)["prompt"] == "hello"


def test_review_code_focus_passthrough(static_client):
    review_code("def x(): pass", focus="security", client=static_client)
    sent = _last(static_client)
    assert "Focus: security" in sent["prompt"]
    assert "def x()" in sent["prompt"]


def test_explain_code_audience_default(static_client):
    explain_code("print(1)", client=static_client)
    assert "Audience" not in _last(static_client)["prompt"]


def test_refactor_requires_goal(static_client):
    refactor_code("def f(): pass", "rename to g", client=static_client)
    assert "Goal: rename to g" in _last(static_client)["prompt"]


def test_fix_code_includes_error(static_client):
    fix_code("x =", "SyntaxError: invalid syntax", client=static_client)
    assert "SyntaxError" in _last(static_client)["prompt"]


def test_write_tests_framework(static_client):
    write_tests("def add(a,b): return a+b", framework="pytest", client=static_client)
    assert "Framework: pytest" in _last(static_client)["prompt"]


def test_general_task_with_context(static_client):
    general_task("summarize", context="some context here", client=static_client)
    p = _last(static_client)["prompt"]
    assert "Task: summarize" in p
    assert "Context:\nsome context here" in p


def test_general_task_without_context(static_client):
    general_task("just do it", client=static_client)
    assert _last(static_client)["prompt"] == "just do it"


@pytest.mark.parametrize(
    "fn,args,kwargs,name,expected_keys",
    [
        (generate_code, ("requirements x",), {"language": "go"}, "generate_code", {"requirements", "language"}),
        (review_code, ("code x",), {"focus": "perf"}, "review_code", {"code", "focus"}),
        (explain_code, ("code x",), {"audience": "beginner"}, "explain_code", {"code", "audience"}),
        (refactor_code, ("code x", "goal x"), {}, "refactor_code", {"code", "goal"}),
        (fix_code, ("code x", "err x"), {}, "fix_code", {"code", "error"}),
        (write_tests, ("code x",), {"framework": "unittest"}, "write_tests", {"code", "framework"}),
        (general_task, ("task x",), {"context": "ctx"}, "general_task", {"task", "context"}),
    ],
)
def test_inputs_for_log_shape(static_client, tmp_path, fn, args, kwargs, name, expected_keys):
    with MemoryStore(tmp_path / "m.db") as store:
        fn(*args, client=static_client, store=store, **kwargs)
        rec = store.get(1)
    assert rec is not None
    assert rec.tool_name == name
    inputs = json.loads(rec.inputs_json)
    assert set(inputs.keys()) == expected_keys
