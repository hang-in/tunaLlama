"""mcp_server 도구 wrapper 의 공통 흐름.

각 ``tuna_*`` 도구가 매번 반복하던 패턴 — _state 보장, project_root 결정,
auto_recall 정책 적용, 빈 문자열을 None 으로 정규화 — 을 한 곳에 모은다.
새 도구 추가 시 정책(특히 recall) 누락 위험을 줄인다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from tunallama_core import recall_for_delegation

from . import _state


def project_root() -> str:
    return str(Path.cwd())


def empty_to_none(value: str) -> str | None:
    """MCP tool 인자 기본값 ``""`` 을 backend 가 기대하는 ``None`` 으로 정규화."""
    return value or None


def _build_recall_prefix(
    cfg, store, *, fallback_query: str | None, root: str
) -> str | None:
    if store is None or not fallback_query:
        return None
    rec = recall_for_delegation(
        cfg.routing,
        store,
        explicit_query=None,
        fallback_query=fallback_query,
        project_root=root,
    )
    if rec is None:
        return None
    block = rec.to_prompt_block()
    return block or None


def call_delegation(
    fn: Callable[..., Any],
    *,
    recall_query: str | None = None,
    **kwargs,
) -> str:
    """core delegation 도구 ``fn`` 을 호출하고 결과 텍스트를 돌려준다.

    - _state._ensure() 를 부르고 cfg/client/store 를 자동 주입.
    - ``recall_query`` 가 주어지면 routing 정책에 맞춰 recall_prefix 를 빌드해 fn 에 전달.
    - 호출자는 도구별 인자만 ``kwargs`` 로 넘기면 됨.
    """
    cfg, client, store = _state._ensure()
    root = project_root()
    prefix = _build_recall_prefix(
        cfg, store, fallback_query=recall_query, root=root
    )
    result = fn(
        client=client,
        store=store,
        project_root=root,
        recall_prefix=prefix,
        **kwargs,
    )
    return result.text


def call_dev_review(fn: Callable[..., Any], **kwargs) -> str:
    """``dev_review_loop`` / ``dev_review_from_spec`` 호출 wrapper.

    routing 을 전달해 내부 generate/review/fix 가 모두 동일 recall context 를 받도록.
    결과는 ``DevReviewResult.summary()`` 텍스트.
    """
    cfg, client, store = _state._ensure()
    result = fn(
        client=client,
        store=store,
        project_root=project_root(),
        routing=cfg.routing,
        **kwargs,
    )
    return result.summary()
