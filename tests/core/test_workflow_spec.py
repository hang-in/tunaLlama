import textwrap

import pytest

from tunallama_core.workflow.spec import parse_spec, parse_spec_file


def test_parse_full_spec():
    text = textwrap.dedent("""
        # Task: Build email validator

        ## Requirements
        - regex check
        - reject empty

        ## Constraints
        - Pure stdlib

        ## Acceptance
        - pytest covers 5 cases
    """)
    s = parse_spec(text)
    assert s.title == "Build email validator"
    assert "regex check" in s.requirements
    assert "Pure stdlib" in s.constraints
    assert "pytest" in s.acceptance


def test_parse_spec_to_prompt_contains_all_sections():
    text = textwrap.dedent("""
        # Task: T
        ## Requirements
        R
        ## Constraints
        C
        ## Acceptance
        A
    """)
    p = parse_spec(text).to_prompt()
    assert "Task: T" in p
    assert "Requirements:\nR" in p
    assert "Constraints (treat as hard rules):\nC" in p
    assert "Acceptance:\nA" in p


def test_parse_spec_without_headers_uses_full_text_as_requirements():
    text = "just write a parser"
    s = parse_spec(text)
    assert s.title is None
    assert s.requirements == "just write a parser"
    assert s.constraints == ""
    assert s.acceptance == ""


def test_parse_spec_only_title():
    text = "# Task: Just a title\n"
    s = parse_spec(text)
    assert s.title == "Just a title"
    assert s.requirements == ""


def test_parse_spec_partial_sections():
    text = textwrap.dedent("""
        # Task: P
        ## Requirements
        only this
    """)
    s = parse_spec(text)
    assert s.title == "P"
    assert "only this" in s.requirements
    assert s.constraints == ""


def test_parse_spec_case_insensitive_headers():
    text = textwrap.dedent("""
        # Task: T
        ## requirements
        r
        ## CONSTRAINTS
        c
    """)
    s = parse_spec(text)
    assert "r" in s.requirements
    assert "c" in s.constraints


def test_parse_spec_file_reads_disk(tmp_path):
    f = tmp_path / "spec.md"
    f.write_text("# Task: From file\n## Requirements\nx\n", encoding="utf-8")
    s = parse_spec_file(f)
    assert s.title == "From file"
    assert "x" in s.requirements


def test_parse_spec_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_spec_file(tmp_path / "nope.md")


def test_to_prompt_falls_back_to_raw_when_empty():
    s = parse_spec("")
    assert s.to_prompt() == ""


def test_phase_parsed_and_normalized_uppercase():
    text = textwrap.dedent("""
        # Task: T
        ## Phase
        implement
        ## Requirements
        r
    """)
    s = parse_spec(text)
    assert s.phase == "IMPLEMENT"


def test_phase_invalid_value_becomes_none():
    text = textwrap.dedent("""
        # Task: T
        ## Phase
        random
    """)
    s = parse_spec(text)
    assert s.phase is None


def test_focus_takes_first_line_only():
    text = textwrap.dedent("""
        # Task: T
        ## Focus
        error handling first
        secondary line ignored
        ## Requirements
        r
    """)
    s = parse_spec(text)
    assert s.focus == "error handling first"


def test_to_prompt_includes_phase_focus_constraints_in_order():
    text = textwrap.dedent("""
        # Task: build
        ## Phase
        IMPLEMENT
        ## Focus
        validation first
        ## Requirements
        - regex
        ## Constraints
        - stdlib only
    """)
    p = parse_spec(text).to_prompt()
    assert "Phase: IMPLEMENT" in p
    assert "Task: build" in p
    assert "Priority focus: validation first" in p
    assert "Constraints (treat as hard rules)" in p
    # 순서: Phase → Task → Focus → Requirements → Constraints
    assert (
        p.index("Phase: IMPLEMENT")
        < p.index("Task: build")
        < p.index("Priority focus")
        < p.index("Requirements")
        < p.index("Constraints")
    )


def test_phase_only_no_other_sections():
    text = "## Phase\nVERIFY\n"
    s = parse_spec(text)
    assert s.phase == "VERIFY"
    assert s.title is None
    assert s.requirements == ""


@pytest.mark.parametrize("phase", ["DESIGN", "IMPLEMENT", "VERIFY"])
def test_all_valid_phases(phase):
    text = f"## Phase\n{phase}\n"
    s = parse_spec(text)
    assert s.phase == phase
