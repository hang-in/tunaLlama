"""HyDE (Hypothetical Document Embeddings, arXiv:2212.10496).

original query → LLM "가상 답변" 생성 → 그 답변 텍스트로 검색.
검색 시드의 record 가 "task description" 이고 사용자 query 도 "task" 이면,
LLM 의 hypothetical answer 는 record 와 더 가까운 vocabulary/structure 를
가질 가능성. 그 결과로 검색이 더 잘 매칭.

cloud LLM 1 회 호출 (normalize_query 와 동급 비용). 실패 시 fallback = 원
query.
"""

from __future__ import annotations

from ..llm.base import LLMClient

_HYDE_SYSTEM = (
    "You are a hypothetical document generator for a code memory search "
    "engine.\n"
    "Given a user's coding task or query, write a 1-3 sentence English "
    "description of the task as if it were a stored memory record - "
    "include the technical keywords, key library/function names, and "
    "common terminology a developer would use.\n"
    "Examples:\n"
    "- 'GC 가 안 돌아가는 문제' → 'Debugging memory leak in Python where "
    "garbage collection fails to release objects, often involving "
    "circular references or strong references in caches.'\n"
    "- 'salt 추가한 hash' → 'Password hashing using bcrypt or argon2 "
    "with a per-user random salt to prevent rainbow table attacks.'\n"
    "Respond with only the description, no quotes, no markdown, no "
    "preamble."
)


def generate_hyde(query: str, *, client: LLMClient) -> str:
    """가상 답변 텍스트 생성. 실패 시 원 query 반환."""
    if not query or not query.strip():
        return query
    try:
        resp = client.chat(system=_HYDE_SYSTEM, prompt=query)
    except Exception:
        return query
    text = (resp.text or "").strip()
    if not text:
        return query
    # ```...``` 펜스 제거.
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return text or query
