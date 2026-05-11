"""``tunallama state`` CLI 명령 단위 테스트."""

from __future__ import annotations


from tunallama_core.cli.state_cmd import run_state
from tunallama_core.memory.state import (
    SECTION_CONSTRAINTS,
    SECTION_DECISIONS,
    StateEntry,
    append_entry,
    load_state,
    save_state,
)


def test_state_show_no_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "tunallama_core.cli.state_cmd.load_state",
        lambda: load_state(tmp_path, base=tmp_path / "projects"),
    )
    rc = run_state(action="show")
    assert rc == 0
    out = capsys.readouterr().out
    assert "아직" in out or "없음" in out


def test_state_path_action(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "tunallama_core.cli.state_cmd.load_state",
        lambda: load_state(tmp_path, base=tmp_path / "projects"),
    )
    rc = run_state(action="path")
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("state.md")


def test_state_clean_removes_auto_preserves_manual(tmp_path, monkeypatch, capsys):
    base = tmp_path / "projects"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "tunallama_core.cli.state_cmd.load_state",
        lambda: load_state(tmp_path, base=base),
    )
    s = load_state(tmp_path, base=base)
    append_entry(s, StateEntry(section=SECTION_DECISIONS, text="auto x", source="auto"))
    append_entry(s, StateEntry(
        section=SECTION_CONSTRAINTS, text="manual rule", source="manual",
    ))
    append_entry(s, StateEntry(
        section=SECTION_DECISIONS, text="verified y", source="verified",
    ))
    save_state(s)

    rc = run_state(action="clean")
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 개 삭제" in out  # auto 1개만 삭제

    s2 = load_state(tmp_path, base=base)
    sections = s2.by_section
    assert any(e.text == "manual rule" for e in sections[SECTION_CONSTRAINTS])
    assert any(e.source == "verified" for e in sections[SECTION_DECISIONS])
    assert all(e.source != "auto" for e in s2.entries)


def test_state_invalid_action_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "tunallama_core.cli.state_cmd.load_state",
        lambda: load_state(tmp_path, base=tmp_path / "projects"),
    )
    rc = run_state(action="bogus")
    assert rc == 1
