import json

from tunallama_core.delegation._runner import DelegationResult, run_delegation
from tunallama_core.memory.store import MemoryStore


def test_run_delegation_returns_result_fields(static_client):
    static_client.text = "generated"
    static_client.model = "fake-32b"
    static_client.duration_ms = 42
    static_client.tokens_estimated = 17

    r = run_delegation(
        client=static_client,
        tool_name="generate_code",
        system_prompt="sys",
        user_prompt="user",
        inputs_for_log={"x": 1},
    )
    assert isinstance(r, DelegationResult)
    assert r.text == "generated"
    assert r.model == "fake-32b"
    assert r.duration_ms == 42
    assert r.tokens_estimated == 17
    assert r.tool_name == "generate_code"
    assert r.call_id is None  # store 미제공


def test_run_delegation_passes_prompts_to_client(static_client):
    run_delegation(
        client=static_client,
        tool_name="t",
        system_prompt="sys-x",
        user_prompt="user-y",
        inputs_for_log={},
    )
    assert static_client.calls == [{"system": "sys-x", "prompt": "user-y"}]


def test_run_delegation_records_call_when_store_given(static_client, tmp_path):
    static_client.text = "out"
    with MemoryStore(tmp_path / "m.db") as store:
        r = run_delegation(
            client=static_client,
            tool_name="generate_code",
            system_prompt="sys",
            user_prompt="user",
            inputs_for_log={"requirements": "validate email", "language": "python"},
            store=store,
            project_root="/proj",
            session_id="s1",
        )
        assert r.call_id == 1
        rec = store.get(1)
        assert rec is not None
        assert rec.tool_name == "generate_code"
        assert rec.output == "out"
        assert rec.project_root == "/proj"
        assert rec.session_id == "s1"
        assert json.loads(rec.inputs_json) == {
            "requirements": "validate email",
            "language": "python",
        }


def test_recall_prefix_prepended_to_user_prompt(static_client):
    run_delegation(
        client=static_client,
        tool_name="t",
        system_prompt="sys",
        user_prompt="do thing",
        inputs_for_log={},
        recall_prefix="# 과거 작업\n- did similar thing yesterday",
    )
    sent = static_client.calls[-1]
    assert "do thing" in sent["prompt"]
    assert "과거 작업" in sent["prompt"]
    assert "# Task" in sent["prompt"]
    # 순서: prefix 먼저, Task 다음
    assert sent["prompt"].index("과거 작업") < sent["prompt"].index("# Task")


def test_no_recall_prefix_means_raw_user_prompt(static_client):
    run_delegation(
        client=static_client,
        tool_name="t",
        system_prompt="sys",
        user_prompt="raw",
        inputs_for_log={},
    )
    sent = static_client.calls[-1]
    assert sent["prompt"] == "raw"


def test_dataclass_is_frozen(static_client):
    r = run_delegation(
        client=static_client,
        tool_name="t",
        system_prompt="s",
        user_prompt="u",
        inputs_for_log={},
    )
    import pytest

    with pytest.raises(Exception):
        r.text = "x"  # type: ignore[misc]
