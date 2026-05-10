"""모든 delegation 도구가 공유하는 호출/기록 경로.

도구 함수는 prompt 빌드까지만 책임지고 LLM 호출과 메모리 기록은 ``run_delegation``
이 일괄 처리한다 — 도구별로 흩어지지 않게.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..llm.base import LLMClient
from ..memory.store import MemoryStore


@dataclass(frozen=True)
class DelegationResult:
    text: str
    model: str
    duration_ms: int
    tool_name: str
    tokens_estimated: int | None = None
    call_id: int | None = None  # store 가 주어졌을 때 기록된 ID


def run_delegation(
    *,
    client: LLMClient,
    tool_name: str,
    system_prompt: str,
    user_prompt: str,
    inputs_for_log: dict[str, Any],
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    full_prompt = (
        f"{recall_prefix}\n\n# Task\n{user_prompt}"
        if recall_prefix
        else user_prompt
    )
    resp = client.chat(system=system_prompt, prompt=full_prompt)
    call_id: int | None = None
    if store is not None:
        call_id = store.record_call(
            tool_name=tool_name,
            inputs=inputs_for_log,
            output=resp.text,
            model=resp.model,
            duration_ms=resp.duration_ms,
            tokens_estimated=resp.tokens_estimated,
            project_root=project_root,
            session_id=session_id,
        )
    return DelegationResult(
        text=resp.text,
        model=resp.model,
        duration_ms=resp.duration_ms,
        tool_name=tool_name,
        tokens_estimated=resp.tokens_estimated,
        call_id=call_id,
    )
