"""Tiered recall - 검색 결과를 신뢰도 별 3 tier 로 분류.

`auto_recall=always` 모드의 risk 완화. R@5 0.5 환경에서 자동 prepend 시
무관 record 가 절반 → context pollution. tier 분류로 hard tier 는 자동
prepend 에서 제외.

3 tier (FTS5 bm25() 는 음수, more negative = stronger match):
- ``exact``: BM25 점수 ≤ ``threshold_bm25`` (e.g. -1.0). 정확 토큰 일치.
- ``near``: vector cosine ≥ ``threshold_cosine`` (e.g. 0.5). 의미 유사.
- ``hard``: 둘 다 약함.
"""

from __future__ import annotations

from dataclasses import dataclass

from .search import RecallSnippet, recall_hybrid
from .store import MemoryStore


@dataclass(frozen=True)
class TieredRecall:
    exact: tuple[RecallSnippet, ...]
    near: tuple[RecallSnippet, ...]
    hard: tuple[RecallSnippet, ...]

    @property
    def confident(self) -> tuple[RecallSnippet, ...]:
        """auto_recall=always 모드에서 자동 prepend 해도 안전한 tier 만."""
        return self.exact + self.near

    def __iter__(self):
        yield from self.exact
        yield from self.near
        yield from self.hard


def recall_tiered(
    store: MemoryStore,
    query: str,
    *,
    limit: int = 10,
    threshold_bm25: float = -1.0,
    threshold_cosine: float = 0.5,
) -> TieredRecall:
    """hybrid 검색 결과를 3 tier 로 분류.

    BM25 점수 / cosine 점수 따로 받기 위해 BM25 직검색 + vector 직검색
    실행. RRF 점수 (recall_hybrid 의 score) 는 raw 점수가 아니라 분류에
    사용 어려워 raw path 다시 호출.

    FTS5 의 bm25() 는 음수 - more negative = stronger. threshold_bm25 도
    음수 (default -1.0) 로 비교 (``bm_s <= threshold_bm25``).
    """
    if limit <= 0 or not query or not query.strip():
        return TieredRecall((), (), ())

    # BM25 직검색 - 정확 토큰 일치 신호
    from .search import recall as recall_bm25

    bm_result = recall_bm25(store, query, limit=limit * 3)
    bm_scores: dict[int, float] = {
        s.full_id: s.score for s in bm_result.snippets
    }

    # vector 직검색 - 의미 유사 신호 (cosine)
    vec_hits = store.search_vectors(query, limit=limit * 3)
    vec_scores: dict[int, float] = {h.id: h.score for h in vec_hits}

    # hybrid 의 통합 ranking 따라서 후보 limit 정렬
    hyb_result = recall_hybrid(store, query, limit=limit)

    exact: list[RecallSnippet] = []
    near: list[RecallSnippet] = []
    hard: list[RecallSnippet] = []

    for snippet in hyb_result.snippets:
        rid = snippet.full_id
        bm_s = bm_scores.get(rid)  # None 이면 BM25 미스
        vec_s = vec_scores.get(rid, 0.0)
        if bm_s is not None and bm_s <= threshold_bm25:
            exact.append(snippet)
        elif vec_s >= threshold_cosine:
            near.append(snippet)
        else:
            hard.append(snippet)

    return TieredRecall(
        exact=tuple(exact), near=tuple(near), hard=tuple(hard),
    )
