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
    mcp_server.tuna_review(code="def x(): pass", focus="security")
    sent = fake_state["client"].calls[-1]
    assert "Focus: security" in sent["prompt"]


def test_tuna_explain_code(fake_state):
    mcp_server.tuna_explain(code="print(1)", audience="beginner")
    assert "Audience: beginner" in fake_state["client"].calls[-1]["prompt"]


def test_tuna_review_requires_input(fake_state):
    out = mcp_server.tuna_review()
    assert "error" in out.lower()


def test_tuna_review_rejects_both_inputs(fake_state):
    out = mcp_server.tuna_review(code="x", file_path="/tmp/y.py")
    assert "error" in out.lower()


def test_tuna_explain_requires_input(fake_state):
    out = mcp_server.tuna_explain()
    assert "error" in out.lower()


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


def test_tuna_review_file_reads_file(fake_state, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # _project_root() = cwd 이므로 confinement 가 tmp_path
    f = tmp_path / "x.py"
    f.write_text("def login(): pass")
    out = mcp_server.tuna_review(file_path=str(f), focus="security")
    assert out == fake_state["client"].text
    assert "def login" in fake_state["client"].calls[-1]["prompt"]
    rec = fake_state["store"].get(1)
    assert rec is not None
    assert "def login" not in rec.inputs_json  # content 누출 X


def test_tuna_explain_file(fake_state, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "y.py"
    f.write_text("Y = 1")
    mcp_server.tuna_explain(file_path=str(f), audience="expert")
    assert "Y = 1" in fake_state["client"].calls[-1]["prompt"]


def test_tuna_analyze_files(fake_state, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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


def test_tuna_dev_review_runs_loop(fake_state):
    fake_state["client"].text = "ok 이상 없음"
    out = mcp_server.tuna_dev_review("write x", "python", 1)
    assert "dev_review" in out
    assert "수렴" in out
    # generate + review + classifier(stage-2) = 3 호출
    assert len(fake_state["client"].calls) == 3
    classifier_calls = [
        c for c in fake_state["client"].calls if "PASS or FAIL" in c["system"]
    ]
    assert len(classifier_calls) == 1


def test_tuna_dev_review_from_spec_reads_file(fake_state, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text(
        "# Task: parse json\n## Requirements\n- handle nesting\n",
        encoding="utf-8",
    )
    fake_state["client"].text = "ok 이상 없음"
    out = mcp_server.tuna_dev_review_from_spec(str(spec), 1)
    assert "수렴" in out
    # 첫 호출 prompt 에 spec 내용 포함
    first_prompt = fake_state["client"].calls[0]["prompt"]
    assert "parse json" in first_prompt
    assert "handle nesting" in first_prompt


def test_auto_recall_prepended_when_routing_always(fake_state, monkeypatch):
    """routing.auto_recall='always' 면 도구 호출 prompt 에 recall context 자동 첨부."""
    from tunallama_core import (
        Config,
        LLMConfig,
        LoggingConfig,
        MemoryConfig,
        OllamaProviderConfig,
        RoutingConfig,
    )
    from plugin import _state

    cfg = Config(
        llm=LLMConfig(
            provider="ollama",
            temperature=0.3,
            timeout_seconds=10,
            ollama=OllamaProviderConfig(host="x", model="m"),
        ),
        memory=MemoryConfig(db_path=fake_state["cfg"].memory.db_path),
        routing=RoutingConfig(auto_recall="always"),
        logging=LoggingConfig(),
    )
    monkeypatch.setattr(_state, "_config", cfg)

    # 첫 호출 — 매칭 record 없으니 prefix 없어야
    fake_state["client"].text = "first output"
    mcp_server.tuna_generate_code("validate email addresses", "python")
    assert "과거 관련 작업" not in fake_state["client"].calls[-1]["prompt"]

    # 두 번째 호출 — 첫 호출이 store 에 있어 매칭 → prefix 첨부
    fake_state["client"].text = "second output"
    mcp_server.tuna_generate_code("validate email format", "python")
    second_prompt = fake_state["client"].calls[-1]["prompt"]
    assert "과거 관련 작업" in second_prompt
    assert "first output" in second_prompt


def test_auto_recall_silent_under_on_request(fake_state):
    """on_request 모드 (fixture 기본값) 에서는 자동 prefix 안 함 — 명시 ``tuna_recall`` 만."""
    fake_state["store"].record_call(
        tool_name="generate_code",
        inputs={"requirements": "validate email"},
        output="prior",
        model="m",
        duration_ms=1,
    )
    mcp_server.tuna_generate_code("validate email format")
    assert "과거 관련 작업" not in fake_state["client"].calls[-1]["prompt"]


def test_auto_recall_skipped_when_routing_never(fake_state, monkeypatch):
    """routing.auto_recall='never' 이면 prefix 없음."""
    from tunallama_core import (
        Config,
        LLMConfig,
        LoggingConfig,
        MemoryConfig,
        OllamaProviderConfig,
        RoutingConfig,
    )
    from plugin import _state

    cfg = Config(
        llm=LLMConfig(
            provider="ollama",
            temperature=0.3,
            timeout_seconds=10,
            ollama=OllamaProviderConfig(host="x", model="m"),
        ),
        memory=MemoryConfig(db_path=fake_state["cfg"].memory.db_path),
        routing=RoutingConfig(auto_recall="never"),
        logging=LoggingConfig(),
    )
    monkeypatch.setattr(_state, "_config", cfg)

    fake_state["store"].record_call(
        tool_name="generate_code",
        inputs={"requirements": "alpha"},
        output="prior",
        model="m",
        duration_ms=1,
    )
    mcp_server.tuna_generate_code("alpha next")
    assert "과거 관련 작업" not in fake_state["client"].calls[-1]["prompt"]


def test_tuna_dev_review_runs_loop_with_routing(fake_state, monkeypatch):
    """dev_review wrapper 가 routing 을 자동 전달해 always 모드에서 recall 첨부."""
    from tunallama_core import (
        Config,
        LLMConfig,
        LoggingConfig,
        MemoryConfig,
        OllamaProviderConfig,
        RoutingConfig,
    )
    from plugin import _state

    cfg = Config(
        llm=LLMConfig(
            provider="ollama",
            temperature=0.3,
            timeout_seconds=10,
            ollama=OllamaProviderConfig(host="x", model="m"),
        ),
        memory=MemoryConfig(db_path=fake_state["cfg"].memory.db_path),
        routing=RoutingConfig(auto_recall="always"),
        logging=LoggingConfig(),
    )
    monkeypatch.setattr(_state, "_config", cfg)

    from pathlib import Path

    fake_state["store"].record_call(
        tool_name="generate_code",
        inputs={"requirements": "validate email"},
        output="prior code",
        model="m",
        duration_ms=1,
        project_root=str(Path.cwd()),  # _adapters.project_root() 와 일치시켜야 매칭
    )
    fake_state["client"].text = "ok 이상 없음"
    mcp_server.tuna_dev_review("validate email format", "python", 1)
    first = fake_state["client"].calls[0]["prompt"]
    assert "과거 관련 작업" in first


def test_tuna_log_limitation_creates_file(fake_state, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tunallama_core.workflow.limitations.DEFAULT_LIMITATIONS_PATH",
        tmp_path / "lim.md",
    )
    out = mcp_server.tuna_log_limitation("한국어 들여쓰기 잘못함")
    assert "[OK]" in out
    body = (tmp_path / "lim.md").read_text(encoding="utf-8")
    assert "한국어 들여쓰기 잘못함" in body
