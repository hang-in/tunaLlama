"""Query expansion — LLM 으로 query 를 동의어/paraphrase 로 확장.

paraphrase 시드의 BM25 R@5 = 0.25 약점을 직접 공략. LLM 한 번 호출에 4개 정도
대안 표현을 받고, 원 query 와 함께 검색해서 RRF 로 합산.

비용 / 효과:
- 검색당 LLM 1 회 (Phase 1.5 의 single-token classifier 와 비슷한 비용).
- LLM 응답 실패 시 빈 expansion 반환 — 호출자가 원 query 만으로 검색하도록.
"""

from __future__ import annotations

import re

from ..llm.base import LLMClient

_SYSTEM = (
    "You generate alternative phrasings of a search query.\n"
    "Output exactly the requested number of phrasings, one per line.\n"
    "Mix Korean and English freely. Use synonyms, paraphrases, and "
    "domain-specific jargon. No numbering, no bullets, no commentary."
)
_USER_TMPL = "Query: {q}\n\nOutput {n} alternative phrasings (one per line):"

_PREFIX_RE = re.compile(r"^\s*(?:\d+[.)]\s+|[-*•]\s+|>\s+)")


def _clean(line: str) -> str:
    return _PREFIX_RE.sub("", line).strip().strip('"').strip("'")


def expand_query(
    client: LLMClient, query: str, *, max_expansions: int = 4
) -> list[str]:
    """원 query + 대안 표현 최대 ``max_expansions`` 개.

    LLM 호출 실패 / 형식 깨짐 시 ``[query]`` 만 반환 — 호출자가 원 query 로 검색.
    중복(원 query 와 같거나 빈 줄) 자동 제거.
    """
    if not query.strip() or max_expansions <= 0:
        return [query]
    try:
        resp = client.chat(
            system=_SYSTEM,
            prompt=_USER_TMPL.format(q=query, n=max_expansions),
        )
    except Exception:  # noqa: BLE001 — 실패 시 expansion 없이 진행
        return [query]

    lines = (resp.text or "").splitlines()
    candidates: list[str] = [query]
    seen: set[str] = {query.lower()}
    for line in lines:
        c = _clean(line)
        if not c or c.lower() in seen:
            continue
        seen.add(c.lower())
        candidates.append(c)
        if len(candidates) > max_expansions:
            break
    return candidates
