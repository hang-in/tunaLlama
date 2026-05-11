"""Phase 6-1 state.md 단위 테스트."""

from __future__ import annotations


import pytest

from tunallama_core.memory.state import (
    SECTION_ANTIPATTERNS,
    SECTION_CONSTRAINTS,
    SECTION_CONVENTIONS,
    SECTION_DECISIONS,
    StateEntry,
    StateFile,
    append_entry,
    get_project_hash,
    load_state,
    render,
    save_state,
    state_path_for,
)


def test_get_project_hash_non_git_uses_cwd_path(tmp_path):
    digest, root = get_project_hash(tmp_path)
    assert len(digest) == 12
    assert all(c in "0123456789abcdef" for c in digest)
    # 비-git 디렉토리는 자기 자신을 root 로 (parent .git 있으면 git root - 환경 변동).
    assert root.startswith(str(tmp_path.resolve())) or "tunaLlama" in root


def test_get_project_hash_deterministic(tmp_path):
    d1, _ = get_project_hash(tmp_path)
    d2, _ = get_project_hash(tmp_path)
    assert d1 == d2


def test_state_path_for(tmp_path):
    path = state_path_for("abc123def456", base=tmp_path)
    assert path.parts[-2:] == ("abc123def456", "state.md")


def test_load_state_missing_returns_empty(tmp_path):
    s = load_state(tmp_path, base=tmp_path / "base")
    assert s.entries == []
    assert s.last_updated != ""


def test_state_entry_invalid_section_raises():
    with pytest.raises(ValueError):
        StateEntry(section="Unknown", text="x")


def test_state_entry_default_last_seen():
    e = StateEntry(section=SECTION_CONVENTIONS, text="x")
    assert e.last_seen != ""


def test_append_entry_basic(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    e = StateEntry(section=SECTION_DECISIONS, text="use MemoryStore not Store")
    append_entry(s, e)
    assert len(s.entries) == 1


def test_append_entry_dedup_increments_occurrences(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    append_entry(s, StateEntry(section=SECTION_CONSTRAINTS, text="no mocks"))
    append_entry(s, StateEntry(section=SECTION_CONSTRAINTS, text="No Mocks"))  # case insensitive
    assert len(s.entries) == 1
    assert s.entries[0].occurrences == 2


def test_append_entry_manual_upgrades_auto(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    append_entry(s, StateEntry(section=SECTION_DECISIONS, text="x", source="auto"))
    append_entry(s, StateEntry(section=SECTION_DECISIONS, text="x", source="manual"))
    assert s.entries[0].source == "manual"


def test_append_entry_manual_not_downgraded(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    append_entry(s, StateEntry(section=SECTION_DECISIONS, text="x", source="manual"))
    append_entry(s, StateEntry(section=SECTION_DECISIONS, text="x", source="auto"))
    assert s.entries[0].source == "manual"


def test_render_includes_all_sections():
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="2026-05-11T00:00:00Z",
    )
    txt = render(s)
    assert "# tunaLlama Project Memory" in txt
    assert f"## {SECTION_CONVENTIONS}" in txt
    assert f"## {SECTION_DECISIONS}" in txt
    assert f"## {SECTION_CONSTRAINTS}" in txt
    assert f"## {SECTION_ANTIPATTERNS}" in txt
    assert "Last updated: 2026-05-11T00:00:00Z" in txt


def test_render_occurrences_format():
    s = StateFile(project_hash="abc", project_root="/tmp", last_updated="t")
    s.entries.append(StateEntry(
        section=SECTION_ANTIPATTERNS, text="np.random fake", source="auto", occurrences=3,
    ))
    txt = render(s)
    assert "(auto, 3 occurrences) np.random fake" in txt


def test_render_manual_tag():
    s = StateFile(project_hash="abc", project_root="/tmp", last_updated="t")
    s.entries.append(StateEntry(
        section=SECTION_CONVENTIONS, text="korean comments ok", source="manual",
    ))
    txt = render(s)
    assert "(manual) korean comments ok" in txt


def test_save_then_load_roundtrip(tmp_path):
    base = tmp_path / "projects"
    digest, _ = get_project_hash(tmp_path)
    s = load_state(tmp_path, base=base)
    append_entry(s, StateEntry(
        section=SECTION_CONSTRAINTS, text="backend cannot import plugin",
        source="manual",
    ))
    append_entry(s, StateEntry(
        section=SECTION_ANTIPATTERNS, text="np.random fake scores",
        source="auto", occurrences=3,
    ))
    save_state(s)

    s2 = load_state(tmp_path, base=base)
    sections = s2.by_section
    assert any("backend cannot import plugin" in e.text for e in sections[SECTION_CONSTRAINTS])
    np_entry = next(
        e for e in sections[SECTION_ANTIPATTERNS] if "np.random" in e.text
    )
    assert np_entry.occurrences == 3
    assert np_entry.source == "auto"


def test_save_truncates_when_over_budget(tmp_path):
    base = tmp_path / "projects"
    digest, _ = get_project_hash(tmp_path)
    s = load_state(tmp_path, base=base)
    # 큰 entry 다수 - decisions / antipatterns 만 truncate 됨.
    for i in range(50):
        append_entry(s, StateEntry(
            section=SECTION_DECISIONS,
            text=f"decision {i}: " + ("x" * 60),
            source="auto",
            last_seen=f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
        ))
    # constraint 는 truncate 면제.
    append_entry(s, StateEntry(
        section=SECTION_CONSTRAINTS, text="hard rule that must stay",
        source="manual",
    ))
    removed = save_state(s, max_bytes=512)
    assert removed > 0
    s2 = load_state(tmp_path, base=base)
    constraints = s2.by_section[SECTION_CONSTRAINTS]
    assert any("hard rule that must stay" in e.text for e in constraints)


def test_save_keeps_conventions_under_budget(tmp_path):
    base = tmp_path / "projects"
    s = load_state(tmp_path, base=base)
    for i in range(20):
        append_entry(s, StateEntry(
            section=SECTION_CONVENTIONS,
            text=f"convention {i}: " + ("y" * 40),
            source="manual",
        ))
    save_state(s, max_bytes=512)  # 너무 작아 truncate 가 시도되지만 conventions 면제
    s2 = load_state(tmp_path, base=base)
    # 모든 conventions 보존
    convs = s2.by_section[SECTION_CONVENTIONS]
    assert len(convs) == 20


def test_load_state_parses_existing_file(tmp_path):
    base = tmp_path / "projects"
    digest, _ = get_project_hash(tmp_path)
    target = state_path_for(digest, base=base)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# tunaLlama Project Memory\n"
        "<!-- Last updated: 2026-05-11T10:00:00Z -->\n\n"
        f"## {SECTION_DECISIONS}\n"
        "- (manual) chose HyDE for production winner\n"
        "- (auto, 5 occurrences) BGE-M3 default\n\n"
        f"## {SECTION_ANTIPATTERNS}\n"
        "- (auto) Store vs MemoryStore\n",
        encoding="utf-8",
    )
    s = load_state(tmp_path, base=base)
    decisions = s.by_section[SECTION_DECISIONS]
    assert any(e.source == "manual" and "HyDE" in e.text for e in decisions)
    bge = next(e for e in decisions if "BGE-M3" in e.text)
    assert bge.occurrences == 5
    assert bge.source == "auto"
    assert s.last_updated == "2026-05-11T10:00:00Z"
