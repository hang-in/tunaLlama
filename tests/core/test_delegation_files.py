import json

import pytest

from tunallama_core.delegation.files import (
    analyze_files,
    explain_file,
    review_file,
)
from tunallama_core.errors import FileScopeError
from tunallama_core.memory.store import MemoryStore


@pytest.fixture
def py_file(tmp_path):
    p = tmp_path / "auth.py"
    p.write_text("def login(user):\n    return user is not None\n")
    return p


def test_review_file_reads_and_includes_in_prompt(static_client, py_file, tmp_path):
    review_file(
        str(py_file), focus="security", client=static_client, project_root=str(tmp_path)
    )
    sent = static_client.calls[-1]
    assert "Focus: security" in sent["prompt"]
    assert "def login" in sent["prompt"]
    assert str(py_file) in sent["system"]  # 시스템 프롬프트에 경로 들어감


def test_review_file_log_excludes_content(static_client, tmp_path, py_file):
    """핸드오프 §7.4 시나리오 B — 파일 내용은 메모리에 저장되지 않아야."""
    with MemoryStore(tmp_path / "m.db") as store:
        review_file(
            str(py_file),
            focus="security",
            client=static_client,
            store=store,
            project_root=str(tmp_path),
        )
        rec = store.get(1)
    assert rec is not None
    inputs = json.loads(rec.inputs_json)
    assert inputs == {"file_path": str(py_file), "focus": "security"}
    assert "def login" not in rec.inputs_json  # content 누출 X


def test_review_file_missing_path(static_client, tmp_path):
    with pytest.raises(FileNotFoundError):
        review_file(
            str(tmp_path / "nope.py"),
            client=static_client,
            project_root=str(tmp_path),
        )


def test_review_file_directory_rejected(static_client, tmp_path):
    with pytest.raises(FileNotFoundError):
        review_file(str(tmp_path), client=static_client, project_root=str(tmp_path))


def test_explain_file_prompts_file_path(static_client, py_file, tmp_path):
    explain_file(
        str(py_file),
        audience="beginner",
        client=static_client,
        project_root=str(tmp_path),
    )
    sent = static_client.calls[-1]
    assert "Audience: beginner" in sent["prompt"]
    assert "def login" in sent["prompt"]


def test_analyze_files_combines_multiple(static_client, tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("X = 1\n")
    b.write_text("Y = 2\n")
    analyze_files(
        [str(a), str(b)],
        "explain dependencies",
        client=static_client,
        project_root=str(tmp_path),
    )
    p = static_client.calls[-1]["prompt"]
    assert "Question: explain dependencies" in p
    assert f"=== {a} ===" in p
    assert f"=== {b} ===" in p
    assert "X = 1" in p
    assert "Y = 2" in p


def test_analyze_files_log_keeps_paths_only(static_client, tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("normal_var = 'value'\n")
    b.write_text("another_var = 'data'\n")
    with MemoryStore(tmp_path / "m.db") as store:
        analyze_files(
            [str(a), str(b)],
            "review",
            client=static_client,
            store=store,
            project_root=str(tmp_path),
        )
        rec = store.get(1)
    assert rec is not None
    inputs = json.loads(rec.inputs_json)
    assert inputs["file_paths"] == [str(a), str(b)]
    assert inputs["question"] == "review"
    assert "normal_var" not in rec.inputs_json
    assert "another_var" not in rec.inputs_json


def test_analyze_files_empty_list_rejected(static_client, tmp_path):
    with pytest.raises(ValueError):
        analyze_files([], "q", client=static_client, project_root=str(tmp_path))


# ---------------------- security: path confinement ----------------------


def test_missing_project_root_rejected(static_client, py_file):
    with pytest.raises(FileScopeError, match="project_root"):
        review_file(str(py_file), client=static_client)


def test_path_outside_project_root_rejected(static_client, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "hello.py"
    secret.write_text("ok")
    inside = tmp_path / "inside"
    inside.mkdir()
    with pytest.raises(FileScopeError, match="project_root 밖"):
        review_file(
            str(secret), client=static_client, project_root=str(inside)
        )


def test_relative_path_traversal_rejected(static_client, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("secret")
    with pytest.raises(FileScopeError):
        review_file(
            str(project / ".." / "outside.py"),
            client=static_client,
            project_root=str(project),
        )


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.production",
        "id_rsa",
        "id_ed25519",
        "id_ed25519.pub",
        "server.pem",
        "client.key",
        "credentials.json",
        "my_secret.txt",
        "auth_token.txt",
        ".netrc",
    ],
)
def test_secret_filename_patterns_rejected(static_client, tmp_path, name):
    f = tmp_path / name
    f.write_text("anything")
    with pytest.raises(FileScopeError, match="비밀"):
        review_file(str(f), client=static_client, project_root=str(tmp_path))


@pytest.mark.parametrize("dirname", [".ssh", ".aws", ".gnupg", ".git"])
def test_secret_directories_rejected(static_client, tmp_path, dirname):
    d = tmp_path / dirname
    d.mkdir()
    f = d / "config"
    f.write_text("secret")
    with pytest.raises(FileScopeError, match="비밀"):
        review_file(str(f), client=static_client, project_root=str(tmp_path))


def test_oversized_file_rejected(static_client, tmp_path):
    big = tmp_path / "big.py"
    big.write_text("x = '" + ("A" * 1_100_000) + "'\n")
    with pytest.raises(FileScopeError, match="너무 큼"):
        review_file(str(big), client=static_client, project_root=str(tmp_path))


def test_binary_file_rejected(static_client, tmp_path):
    b = tmp_path / "logo.png"
    b.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\xff\xfe\xfd")
    with pytest.raises(FileScopeError, match="binary"):
        review_file(str(b), client=static_client, project_root=str(tmp_path))


def test_analyze_files_propagates_scope_error_for_one_bad_path(
    static_client, tmp_path
):
    good = tmp_path / "good.py"
    good.write_text("ok\n")
    outside = tmp_path.parent / "outside.py"
    outside.write_text("secret")
    try:
        with pytest.raises(FileScopeError):
            analyze_files(
                [str(good), str(outside)],
                "q",
                client=static_client,
                project_root=str(tmp_path),
            )
    finally:
        outside.unlink(missing_ok=True)
