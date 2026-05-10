"""Query normalization - 검색 전 query 를 standard form 으로 재작성.

LOPO σR@5 0.18-0.30 의 dominant 변수가 query 표현 차이라는 외부 검토 진단.
LLM 으로 query 를 정규화하면 같은 task 의 다양한 표현이 비슷한 검색 path
밟아 σ 감소 가능성.

비용: cloud LLM 1 회 추가 / 검색. 실패 시 fallback = 원 query.
"""

from __future__ import annotations

import re

from ..llm.base import LLMClient

_NORMALIZE_SYSTEM = (
    "You are a query normalizer for a code memory search engine.\n"
    "Given a user query (Korean or English), output a single short English "
    "phrase (3-7 words) that captures the same task in standard technical "
    "vocabulary. Examples:\n"
    "- '메모리 누수 탐지' → 'memory leak detection'\n"
    "- 'GC 가 안 돌아가는 문제' → 'garbage collection failure'\n"
    "- 'salt 추가한 hash' → 'password hashing with salt'\n"
    "Respond with only the normalized phrase. No explanation, no quotes, "
    "no markdown."
)

_QUOTE_RE = re.compile(r"^[\"'`]+|[\"'`]+$")


def normalize_query(query: str, *, client: LLMClient) -> str:
    """Query 를 standard English form 으로 재작성. 실패 시 원 query 반환."""
    if not query or not query.strip():
        return query
    try:
        resp = client.chat(system=_NORMALIZE_SYSTEM, prompt=query)
    except Exception:
        return query
    text = (resp.text or "").strip()
    # 1줄만 추출 (LLM 이 multi-line 으로 답하면 첫 줄만).
    text = text.split("\n", 1)[0].strip()
    # 양 끝 따옴표 / 백틱 제거.
    text = _QUOTE_RE.sub("", text).strip()
    if not text:
        return query
    return text
