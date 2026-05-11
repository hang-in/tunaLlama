"""``tunallama state`` - project state.md 관리.

서브액션:
- ``show``: 내용 출력
- ``path``: 파일 경로만 출력 (다른 도구와 파이프 용)
- ``clean``: ``(auto)`` 태그 entry 삭제 (manual / verified 보존)
"""

from __future__ import annotations

from ..memory.state import load_state, render, save_state


def run_state(*, action: str) -> int:
    state = load_state()  # cwd / git root 기반 자동 감지

    if action == "path":
        print(state.path)
        return 0

    if action == "show":
        if not state.path.exists():
            print(f"(아직 state.md 없음 - 경로 예정: {state.path})")
            return 0
        print(render(state))
        return 0

    if action == "clean":
        before = len(state.entries)
        # auto entry 삭제 - manual / verified 보존.
        state.entries = [e for e in state.entries if e.source != "auto"]
        removed = before - len(state.entries)
        if state.path.exists() or state.entries:
            save_state(state)
        print(f"[OK] auto entry {removed} 개 삭제 - manual/verified {len(state.entries)} 개 보존.")
        print(f"     파일: {state.path}")
        return 0

    print(f"[오류] 알 수 없는 액션: {action}")
    return 1
