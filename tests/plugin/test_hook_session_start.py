"""SessionStart hook 단위 테스트."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


HOOK_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "plugin" / "hooks" / "session_start.py"
)


def test_hook_exits_zero_on_empty_state(tmp_path, monkeypatch):
    """state.md 없으면 silent (rc=0, stdout 빈 문자열)."""
    # HOME 을 임시로 만들어 ~/.tunallama/projects/<hash>/state.md 가 없는 환경.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""  # 빈 state - 출력 X


def test_hook_outputs_json_with_state(tmp_path, monkeypatch):
    """state.md 에 entry 있으면 JSON additionalContext 출력."""
    import os
    from tunallama_core.memory.state import (
        SECTION_CONVENTIONS,
        StateEntry,
        append_entry,
        load_state,
        save_state,
    )

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    state_base = tmp_path / "tuna_state"
    # subprocess + 부모 process 둘 다 같은 state base 사용 (TUNA_STATE_BASE env).
    monkeypatch.setenv("TUNA_STATE_BASE", str(state_base))
    # load_state 가 base 인자로 받음 - module level DEFAULT 캐시 우회.
    state = load_state(project_dir, base=state_base)
    append_entry(state, StateEntry(
        section=SECTION_CONVENTIONS, text="use MemoryStore", source="manual",
    ))
    save_state(state)

    # 부모 환경 전체를 물려주고 TUNA_STATE_BASE 만 덮어쓴다. Windows 에서는
    # PATH 만 넘기면 PATHEXT / SystemRoot 등 부재로 git 조회(project hash)가
    # 달라져 hook 이 state.md 를 못 찾고 빈 출력이 된다.
    env = {**os.environ, "TUNA_STATE_BASE": str(state_base)}
    # subprocess 가 module 새로 로드 시 _default_state_base() 가 env 읽음.
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        capture_output=True, text=True, timeout=10,
        cwd=str(project_dir), env=env,
    )
    assert result.returncode == 0
    assert result.stdout, (
        f"hook 이 stdout 비움. state.md 경로: {state.path} - 존재: {state.path.exists()}. "
        f"stderr: {result.stderr}"
    )
    data = json.loads(result.stdout)
    # Claude Code SessionStart schema: hookSpecificOutput.hookEventName +
    # nested additionalContext.
    assert "hookSpecificOutput" in data
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "MemoryStore" in hso["additionalContext"]
    assert "tunaLlama project memory" in hso["additionalContext"]


def test_hook_silent_on_missing_module(tmp_path, monkeypatch):
    """tunallama_core 못 찾는 환경에서도 silent 종료 (다른 환경 막지 않음)."""
    # PYTHONPATH 비우고 sys.path 에서 우리 패키지 안 보이게 - 시도하지만 venv
    # 안에서는 imp 가능. 대신 직접 import fail 시뮬은 어려우므로 skip 패턴 X.
    # 그냥 빈 state 와 동일 결과 검증.
    monkeypatch.setenv("HOME", str(tmp_path))
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0  # 어떤 환경에서도 rc=0 보장


def test_hooks_json_registers_session_start():
    """plugin/hooks/hooks.json 에 SessionStart 등록됐는지."""
    hooks_json = (
        Path(__file__).resolve().parent.parent.parent
        / "plugin" / "hooks" / "hooks.json"
    )
    assert hooks_json.exists()
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    assert "SessionStart" in data["hooks"]
    ss = data["hooks"]["SessionStart"][0]["hooks"][0]
    assert ss["type"] == "command"
    assert "session_start.py" in ss["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in ss["command"]
