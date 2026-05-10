from datetime import datetime, timezone

import pytest

from tunallama_core.workflow.limitations import (
    load_limitations,
    log_limitation,
    with_limitations,
)


def test_load_returns_empty_when_no_file(tmp_path):
    assert load_limitations(tmp_path / "missing.md") == ""


def test_with_limitations_passthrough_when_empty(tmp_path):
    assert (
        with_limitations("do thing", path=tmp_path / "missing.md") == "do thing"
    )


def test_log_creates_file_and_appends(tmp_path):
    p = tmp_path / "lim.md"
    log_limitation("한국어 인덴트 잘못 씀", path=p)
    body = p.read_text(encoding="utf-8")
    assert "# Limitations" in body
    assert "한국어 인덴트 잘못 씀" in body
    today = datetime.now(timezone.utc).date().isoformat()
    assert today in body


def test_log_appends_when_file_exists(tmp_path):
    p = tmp_path / "lim.md"
    log_limitation("first", path=p)
    log_limitation("second", path=p)
    body = p.read_text(encoding="utf-8")
    assert body.count("- [") == 2
    assert "first" in body
    assert "second" in body


def test_with_limitations_prepends_section(tmp_path):
    p = tmp_path / "lim.md"
    log_limitation("avoid lambdas", path=p)
    out = with_limitations("write a sorter", path=p)
    assert "# Known limitations" in out
    assert "avoid lambdas" in out
    assert "# Task" in out
    assert "write a sorter" in out
    # 순서: limitations 섹션이 먼저
    assert out.index("Known limitations") < out.index("write a sorter")


def test_log_handles_file_without_trailing_newline(tmp_path):
    p = tmp_path / "lim.md"
    p.write_text("# Limitations\n\n- old", encoding="utf-8")  # no trailing \n
    log_limitation("new", path=p)
    body = p.read_text(encoding="utf-8")
    assert "old" in body
    assert "new" in body


def test_default_path_constant_under_home():
    from tunallama_core.workflow.limitations import DEFAULT_LIMITATIONS_PATH
    from pathlib import Path

    assert DEFAULT_LIMITATIONS_PATH.parent.name == ".tunallama"
    assert DEFAULT_LIMITATIONS_PATH.is_relative_to(Path.home())
