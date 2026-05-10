"""검색 품질 metrics - P@1, P@K, R@K, MRR.

R@5 만 보면 ranking 정보 손실 (top-1 이 정답인지 5위인지 같은 점수).
P@1 (top-1 정확도) + MRR (Mean Reciprocal Rank) 가 실 사용자 패턴 (첫 결과
주로 보는 흐름) 에 더 가깝다.

순수 함수 - 외부 의존 없음. 통합 테스트나 ad-hoc 측정에서 import.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalMetrics:
    p1: float       # top-1 가 relevant 면 1.0 / 아니면 0.0
    p_at_k: float   # |relevant ∩ top-k| / k  (k 까지 잡힌 갯수 기준)
    r_at_k: float   # |relevant ∩ top-k| / |relevant|
    mrr: float      # 1 / rank (첫 relevant 의 1-based rank). 못 찾으면 0.0


def compute_metrics(
    retrieved: list[int], relevant: set[int], *, k: int = 5
) -> RetrievalMetrics:
    """단일 query 에 대한 metrics. ``retrieved`` 는 점수 내림차순 id 리스트."""
    if not retrieved or not relevant:
        return RetrievalMetrics(0.0, 0.0, 0.0, 0.0)

    p1 = 1.0 if retrieved[0] in relevant else 0.0
    top = retrieved[:k]
    hits = len(set(top) & relevant)
    p_at_k = hits / len(top) if top else 0.0
    r_at_k = hits / len(relevant)

    mrr = 0.0
    for i, rid in enumerate(retrieved, start=1):
        if rid in relevant:
            mrr = 1.0 / i
            break
    return RetrievalMetrics(p1=p1, p_at_k=p_at_k, r_at_k=r_at_k, mrr=mrr)


def average_metrics(per_query: list[RetrievalMetrics]) -> RetrievalMetrics:
    """여러 query 의 metrics 평균. 빈 리스트는 0 metrics."""
    n = len(per_query)
    if n == 0:
        return RetrievalMetrics(0.0, 0.0, 0.0, 0.0)
    return RetrievalMetrics(
        p1=sum(m.p1 for m in per_query) / n,
        p_at_k=sum(m.p_at_k for m in per_query) / n,
        r_at_k=sum(m.r_at_k for m in per_query) / n,
        mrr=sum(m.mrr for m in per_query) / n,
    )
