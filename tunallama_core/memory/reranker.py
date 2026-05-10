"""Cross-encoder reranker - precision/recall 둘 다 향상.

bi-encoder (BGE-M3, vector path) 는 query 와 doc 를 각자 임베딩하므로 query-doc
상호 attention 이 없다. cross-encoder 는 둘을 한번에 attention 으로 보고 점수
를 내므로 precision 이 크게 좋아진다 (대신 모든 페어 모델 호출 → 비싸다).

전형적 사용: 1차 빠른 검색(BM25/vector/hybrid) 으로 candidate_pool=20 받고,
2차 reranker 로 query-doc 페어 점수 재산출 → top limit=5.
"""

from __future__ import annotations

import os
import threading
from typing import Sequence

from .search import RecallSnippet

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

_model = None
_model_lock = threading.Lock()


def _resolve_device() -> str | None:
    """``TUNA_EMBEDDING_DEVICE`` 환경변수 공유 - 같은 device 정책."""
    raw = os.environ.get("TUNA_EMBEDDING_DEVICE", "").strip().lower()
    if raw in ("cpu", "mps", "cuda"):
        return raw
    return None


def _get_reranker():
    """lazy load - 첫 ``rerank()`` 호출 시 ~600MB 모델 다운로드/로드.

    ``TUNA_EMBEDDING_DEVICE`` 환경변수 (vector.py 와 공유) 로 device 제어.
    """
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import CrossEncoder

            kwargs: dict = {}
            device = _resolve_device()
            if device is not None:
                kwargs["device"] = device
            _model = CrossEncoder(RERANKER_MODEL, **kwargs)
    return _model


def rerank(
    query: str,
    snippets: Sequence[RecallSnippet],
    *,
    top_k: int = 5,
) -> list[RecallSnippet]:
    """``snippets`` 를 cross-encoder 로 query-doc 페어 점수 재산출 + 상위 ``top_k``.

    ``RecallSnippet`` 의 ``inputs_summary + output_excerpt`` 를 doc 로 본다.
    반환은 새 ``score`` (cross-encoder 점수) 가 채워진 새 snippet 리스트, 점수 내림차순.
    빈 입력은 빈 리스트.
    """
    if not snippets or top_k <= 0:
        return []
    model = _get_reranker()
    pairs = [
        [query, f"{s.inputs_summary} {s.output_excerpt}".strip()]
        for s in snippets
    ]
    scores = model.predict(pairs)
    ranked = sorted(zip(scores, snippets), key=lambda x: float(x[0]), reverse=True)
    return [
        RecallSnippet(
            full_id=s.full_id,
            timestamp=s.timestamp,
            tool_name=s.tool_name,
            inputs_summary=s.inputs_summary,
            output_excerpt=s.output_excerpt,
            score=float(score),
        )
        for score, s in ranked[:top_k]
    ]
