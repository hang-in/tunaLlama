import json

import pytest

from tunallama_core.delegation.files import (
    analyze_files,
    explain_file,
    review_file,
)
from tunallama_core.memory.store import MemoryStore


@pytest.fixture
def py_file(tmp_path):
    p = tmp_path / "auth.py"
    p.write_text("def login(user):\n    return user is not None\n")
    return p


def test_review_file_reads_and_includes_in_prompt(static_client, py_file):
    review_file(str(py_file), focus="security", client=static_client)
    sent = static_client.calls[-1]
    assert "Focus: security" in sent["prompt"]
    assert "def login" in sent["prompt"]
    assert str(py_file) in sent["system"]  # 시스템 프롬프트에 경로 들어감


def test_review_file_log_excludes_content(static_client, tmp_path, py_file):
    """핸드오프 §7.4 시나리오 B — 파일 내용은 메모리에 저장되지 않아야."""
    with MemoryStore(tmp_path / "m.db") as store:
        review_file(str(py_file), focus="security", client=static_client, store=store)
        rec = store.get(1)
    assert rec is not None
    inputs = json.loads(rec.inputs_json)
    assert inputs == {"file_path": str(py_file), "focus": "security"}
    assert "def login" not in rec.inputs_json  # content 누출 X


def test_review_file_missing_path(static_client, tmp_path):
    with pytest.raises(FileNotFoundError):
        review_file(str(tmp_path / "nope.py"), client=static_client)


def test_review_file_directory_rejected(static_client, tmp_path):
    with pytest.raises(FileNotFoundError):
        review_file(str(tmp_path), client=static_client)


def test_explain_file_prompts_file_path(static_client, py_file):
    explain_file(str(py_file), audience="beginner", client=static_client)
    sent = static_client.calls[-1]
    assert "Audience: beginner" in sent["prompt"]
    assert "def login" in sent["prompt"]


def test_analyze_files_combines_multiple(static_client, tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("X = 1\n")
    b.write_text("Y = 2\n")
    analyze_files([str(a), str(b)], "explain dependencies", client=static_client)
    p = static_client.calls[-1]["prompt"]
    assert "Question: explain dependencies" in p
    assert f"=== {a} ===" in p
    assert f"=== {b} ===" in p
    assert "X = 1" in p
    assert "Y = 2" in p


def test_analyze_files_log_keeps_paths_only(static_client, tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("secret = 'X'\n")
    b.write_text("password = 'P'\n")
    with MemoryStore(tmp_path / "m.db") as store:
        analyze_files([str(a), str(b)], "review", client=static_client, store=store)
        rec = store.get(1)
    assert rec is not None
    inputs = json.loads(rec.inputs_json)
    assert inputs["file_paths"] == [str(a), str(b)]
    assert inputs["question"] == "review"
    assert "secret" not in rec.inputs_json
    assert "password" not in rec.inputs_json


def test_analyze_files_empty_list_rejected(static_client):
    with pytest.raises(ValueError):
        analyze_files([], "q", client=static_client)
