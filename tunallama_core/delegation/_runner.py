"""모든 delegation 도구가 공유하는 호출/기록 경로.

도구 함수는 prompt 빌드까지만 책임지고 LLM 호출과 메모리 기록은 ``run_delegation``
이 일괄 처리한다 — 도구별로 흩어지지 않게.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from ..llm.base import LLMClient
from ..memory.store import MemoryStore

_logger = logging.getLogger("tunallama.delegation")


def _maybe_extract_to_state(text: str, *, project_root: str | None) -> None:
    """Phase 6-2 - delegation 출력에서 decision/convention/constraint/antipattern
    자동 추출 → project state.md 저장. ``TUNA_AUTO_EXTRACT_STATE=0`` 이면 skip.
    실패는 logger.warning 으로 기록 (사용자한테 안 보이지만 dev / log 에서
    추적 가능 - silent corruption 방지). delegation 자체에는 영향 없음.
    """
    if os.environ.get("TUNA_AUTO_EXTRACT_STATE", "1") == "0":
        return
    try:
        from ..memory.extract import extract_all, store_extracted_entries
        from ..memory.state import load_state, save_state
        extracted = extract_all(text)
        if not extracted:
            return
        state = load_state(project_root)
        store_extracted_entries(state, extracted)
        save_state(state)
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "state.md auto-extract failed (skipped, delegation unaffected): %s",
            exc,
        )


def _maybe_collect_organic_metrics(
    text: str, *, tool_name: str, project_root: str | None,
) -> None:
    """v0.5.7 - 매 delegation 후 organic dogfooding metric 자동 수집.

    standalone_toy_rate / convention_adherence_rate / ast_excess_score /
    syntactically_valid 가 metrics.db 에 source="organic" 으로 적재.
    ``TUNA_ORGANIC_METRICS=0`` 이면 skip. 실패해도 silent.
    """
    try:
        from ..measurement.organic import collect_organic_after_delegation
        collect_organic_after_delegation(
            text, tool_name=tool_name, project_root=project_root,
        )
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "organic metrics collect failed (delegation unaffected): %s", exc,
        )


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
    response_schema: dict | None = None,
) -> DelegationResult:
    full_prompt = (
        f"{recall_prefix}\n\n# Task\n{user_prompt}"
        if recall_prefix
        else user_prompt
    )
    resp = client.chat(
        system=system_prompt, prompt=full_prompt, response_schema=response_schema
    )
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
        _maybe_extract_to_state(resp.text, project_root=project_root)
        _maybe_collect_organic_metrics(
            resp.text, tool_name=tool_name, project_root=project_root,
        )
    return DelegationResult(
        text=resp.text,
        model=resp.model,
        duration_ms=resp.duration_ms,
        tool_name=tool_name,
        tokens_estimated=resp.tokens_estimated,
        call_id=call_id,
    )
