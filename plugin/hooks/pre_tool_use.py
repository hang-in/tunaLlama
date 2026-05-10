#!/usr/bin/env python3
"""tunaLlama PreToolUse hook — 큰 파일을 ``Read`` 하려는 호출에 권유 메시지.

block 하지 않는다 (suggest only). 사용자가 의도적으로 Read 를 쓰는 경우도 있어,
강제로 막지 않고 stderr 로 안내한다.

활성화 (off by default):
- `~/.claude/settings.json` 또는 프로젝트 `.claude/settings.json` 의 ``hooks``:
  {
    "hooks": {
      "PreToolUse": [
        {"matcher": "Read", "hooks": [
          {"type": "command",
           "command": "python /절대/경로/plugin/hooks/pre_tool_use.py"}
        ]}
      ]
    }
  }

환경변수:
- ``TUNALLAMA_HOOK_THRESHOLD`` — 권유 트리거 바이트 수. 기본 5000.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_DEFAULT_THRESHOLD_BYTES = 5_000


def _threshold() -> int:
    raw = os.environ.get("TUNALLAMA_HOOK_THRESHOLD")
    if not raw:
        return _DEFAULT_THRESHOLD_BYTES
    try:
        v = int(raw)
        return v if v > 0 else _DEFAULT_THRESHOLD_BYTES
    except ValueError:
        return _DEFAULT_THRESHOLD_BYTES


def evaluate(payload: dict, *, threshold: int) -> str | None:
    """입력 payload 보고 권유 메시지를 반환. 없으면 None."""
    if payload.get("tool_name") != "Read":
        return None
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return None
    p = Path(file_path)
    if not p.is_file():
        return None
    size = p.stat().st_size
    if size < threshold:
        return None
    return (
        f"[tunaLlama] {file_path} 가 {size:,} 바이트입니다 "
        f"(threshold {threshold:,}).\n"
        f"리뷰/설명/분석이 목적이면 `tuna_review_file` / `tuna_explain_file` / "
        f"`tuna_analyze_files` 사용 고려 — 파일 내용이 Claude 컨텍스트에 안 들어옵니다."
    )


def main(stdin_text: str | None = None) -> int:
    raw = stdin_text if stdin_text is not None else sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0
    msg = evaluate(payload, threshold=_threshold())
    if msg:
        print(msg, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
