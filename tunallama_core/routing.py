"""auto_recall 정책에 맞춰 ``recall()`` 호출.

도구 호출자(plugin layer 또는 다른 frontend)가 이 함수를 거쳐 recall 첨부 여부를
일관되게 결정한다.
"""

from __future__ import annotations

from .config.models import RoutingConfig
from .memory.search import RecallResult, recall
from .memory.store import MemoryStore


def recall_for_delegation(
    routing: RoutingConfig,
    store: MemoryStore,
    *,
    explicit_query: str | None,
    fallback_query: str | None = None,
    project_root: str | None = None,
) -> RecallResult | None:
    """auto_recall 정책별 동작:

    - ``never``: 무조건 None (메모리 비활성).
    - ``on_request``: ``explicit_query`` 가 있을 때만 검색.
    - ``always``: ``explicit_query`` 또는 ``fallback_query`` 둘 중 하나로 검색.
    """
    mode = routing.auto_recall
    if mode == "never":
        return None

    q = explicit_query if mode == "on_request" else (explicit_query or fallback_query)
    if not q or not q.strip():
        return None
    return recall(store, q, limit=routing.recall_limit, project_root=project_root)
