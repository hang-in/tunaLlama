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

    # Claude Code hook 의 stdout 은 system 메시지로 architect 컨텍스트 추가됨.
    # `additionalContext` JSON 도 일부 클라이언트가 인식 - 두 방식 같이.
    payload = {
        "additionalContext": (
            "[tunaLlama project memory - state.md auto-prepend]\n"
            f"Source: {state.path}\n\n"
            + render(state)
        )
    }
    try:
        # JSON 출력 - Claude Code SessionStart 가 인식하면 컨텍스트 attach.
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        # plain text fallback - JSON 인식 안 되면 raw 출력.
        sys.stdout.write(payload["additionalContext"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
