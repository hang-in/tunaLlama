"""SessionStart hook - state.md auto-prepend 우회.

Claude Code / Codex CLI 둘 다 MCP resource auto-attach 미작동 (v0.5.1
실측). 이 hook 이 session 시작 시 stdout 으로 state.md 내용을 출력해
architect 컨텍스트에 surface.

stdout 만 출력 - block / abort 안 함. 안전.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    """state.md 내용을 stdout 으로 출력. 없으면 안내만."""
    try:
        from tunallama_core.memory.state import load_state, render
    except Exception:  # noqa: BLE001
        # tunallama_core 못 찾으면 silent skip - hook 이 다른 환경 막지 않게.
        return 0

    try:
        state = load_state()
    except Exception:  # noqa: BLE001
        return 0

    if not state.entries:
        # 빈 state - prepend 가치 X, silent.
        return 0

    # Claude Code SessionStart hook 의 정확한 응답 schema (context-mode 비교
    # 분석 결과): hookSpecificOutput.hookEventName + nested additionalContext.
    # flat {additionalContext: ...} 는 인식 안 됨 (v0.5.2 / v0.5.3 / v0.5.4 실측).
    additional_context = (
        "[tunaLlama project memory - state.md auto-prepend]\n"
        f"Source: {state.path}\n\n"
        + render(state)
    )
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": additional_context,
        }
    }
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        sys.stdout.write(additional_context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
