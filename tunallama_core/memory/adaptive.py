"""Adaptive routing - query 특성 따라 검색 path 동적 선택.

외부 검토 (Opus 4.7 + Codex 5.5) 의 σ 감소 후속 권고:
"σR@5 0.22 = 일부 query 에서 실패 → 분기 라우팅이 분산 자체를 줄임"

현재 path 우열 (524 record LOPO):
- 짧고 키워드성 (식별자, 영문 단어) → BM25 가 충분
- 길고 자연어 (한국어 + 의미) → vec/hybrid 가 강함
- 혼합/모호 → HyDE (cloud LLM 1회 비용)

휴리스틱 라우터 (cloud 0): query length / language / code-token 비율 보고
path 선택. cloud LLM 호출 학습 라우터 (RAGRouter-Bench) 보다 단순하지만
σ 감소 효과는 큼.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .search import RecallResult, recall, recall_reranked
from .store import MemoryStore

_HANGUL_RE = re.compile(r"[가-힣]")
_CODE_TOKEN_RE = re.compile(
    r"\b[a-z][a-z0-9_]*[A-Z][a-zA-Z0-9_]*\b"  # camelCase
    r"|\b[a-z]+_[a-z0-9_]+\b"                  # snake_case
    r"|\b[A-Z]+_[A-Z0-9_]+\b"                  # CONSTANT
    r"|\b[a-zA-Z]+\.[a-zA-Z_]+\b"              # module.func
)


@dataclass(frozen=True)
class QueryFeatures:
    """query 분류용 휴리스틱 features."""
    n_chars: int
    n_words: int
    has_korean: bool
    korean_ratio: float
    has_code_tokens: bool
    is_short_keyword: bool   # < 4 단어 + 영문만 + code token 포함

    @property
    def category(self) -> str:
        """라우팅 결정용 카테고리 - 'keyword' | 'natural' | 'mixed'."""
        if self.is_short_keyword:
            return "keyword"
        if self.has_korean and self.korean_ratio > 0.3:
            return "natural"
        return "mixed"


def extract_features(query: str) -> QueryFeatures:
    """query 의 통계 features. 모두 deterministic, cloud 0."""
    if not query or not query.strip():
        return QueryFeatures(0, 0, False, 0.0, False, False)
    n_chars = len(query)
    words = query.split()
    n_words = len(words)
    hangul_count = len(_HANGUL_RE.findall(query))
    has_korean = hangul_count > 0
    korean_ratio = hangul_count / max(n_chars, 1)
    code_tokens = _CODE_TOKEN_RE.findall(query)
    has_code_tokens = bool(code_tokens)
    is_short_keyword = (
        n_words <= 3 and not has_korean and has_code_tokens
    )
    return QueryFeatures(
        n_chars=n_chars,
        n_words=n_words,
        has_korean=has_korean,
        korean_ratio=korean_ratio,
        has_code_tokens=has_code_tokens,
        is_short_keyword=is_short_keyword,
    )


def recall_adaptive(
    store: MemoryStore,
    query: str,
    *,
    cloud_client=None,
    limit: int = 5,
    project_root: str | None = None,
) -> RecallResult:
    """query 특성에 맞는 path 자동 선택 후 검색.

    routing:
    - ``keyword`` (식별자성 짧은 영문): BM25 단독 (cloud 0).
    - ``natural`` (한국어 비중 큰 자연어): cloud_client 있으면 HyDE,
      없으면 reranked hybrid.
    - ``mixed`` (영문 자연어 / 혼합): reranked hybrid (cloud 0) - HyDE 의
      가성비 차이가 작은 영역.

    cloud_client 없으면 모든 ``natural`` 도 reranked hybrid 로 fallback.
    """
    features = extract_features(query)
    cat = features.category

    if cat == "keyword":
        return recall(store, query, limit=limit, project_root=project_root)

    if cat == "natural" and cloud_client is not None:
        from .search import recall_hyde
        return recall_hyde(
            store, query, client=cloud_client,
            base="hybrid", limit=limit, project_root=project_root,
        )

    return recall_reranked(
        store, query, limit=limit,
        candidate_pool=20, base="hybrid",
        project_root=project_root,
    )
