"""FTS5 BM25 리콜.

응답은 항상 요약 + 발췌 — 호출자가 ``full_id`` 로 ``MemoryStore.get`` 을 따로
부르도록 한다. 그래야 recall 결과가 컨텍스트를 폭발시키지 않는다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..errors import RecallError
from .store import MemoryStore
from .tokenize import tokenize_for_index

_INPUTS_SUMMARY_LEN = 100
_OUTPUT_EXCERPT_LEN = 200


@dataclass(frozen=True)
class RecallSnippet:
    full_id: int
    timestamp: str
    tool_name: str
    inputs_summary: str
    output_excerpt: str
    score: float


@dataclass(frozen=True)
class RecallResult:
    query: str
    total_matches: int
    snippets: tuple[RecallSnippet, ...]

    def to_prompt_block(self) -> str:
        """LLM prompt 위에 prepend 하기 좋은 짧은 markdown block.

        recall 이 비어있으면 빈 문자열을 돌려 호출자가 분기 없이 ``""+prompt`` 가능.
        """
        if self.total_matches == 0 or not self.snippets:
            return ""
        lines = [
            "# 과거 관련 작업 (참고용, 반드시 따를 필요는 없음):",
        ]
        for s in self.snippets:
            lines.append(
                f"- [{s.full_id}] {s.tool_name} · {s.timestamp}\n"
                f"  in:  {s.inputs_summary}\n"
                f"  out: {s.output_excerpt}"
            )
        return "\n".join(lines)


def recall(
    store: MemoryStore,
    query: str,
    *,
    limit: int = 5,
    project_root: str | None = None,
) -> RecallResult:
    if not query.strip():
        raise RecallError("recall query 가 비어있습니다.")
    if limit <= 0:
        raise RecallError(f"limit 는 양수여야 합니다: {limit}")

    fts_q = _build_fts_query(query, store.tokenizer)
    where = "calls_fts MATCH ?"
    params: list = [fts_q]
    if project_root:
        where += " AND c.project_root = ?"
        params.append(project_root)

    select_sql = f"""
        SELECT c.id, c.timestamp, c.tool_name, c.inputs_json, c.output,
               bm25(calls_fts) AS score
        FROM calls_fts
        JOIN calls c ON c.id = calls_fts.rowid
        WHERE {where}
        ORDER BY score
        LIMIT ?
    """
    count_sql = f"""
        SELECT COUNT(*)
        FROM calls_fts
        JOIN calls c ON c.id = calls_fts.rowid
        WHERE {where}
    """

    try:
        rows = store.conn.execute(select_sql, (*params, limit)).fetchall()
        total = store.conn.execute(count_sql, params).fetchone()[0]
    except sqlite3.OperationalError as e:
        raise RecallError(f"FTS5 쿼리 실패: {e}") from e

    snippets = tuple(_to_snippet(r) for r in rows)
    return RecallResult(query=query, total_matches=total, snippets=snippets)


def _build_fts_query(raw: str, tokenizer: str) -> str:
    """form: "tok1" OR "tok2" OR ... — FTS5 syntax 안전화 + 한국어 형태소 포함.

    빈 query 는 ``recall()`` 이 이미 RecallError 로 막아 두므로 토큰이 항상 1개 이상이다.
    """
    expanded = tokenize_for_index(raw, tokenizer)
    tokens = [t for t in expanded.split() if t.strip()]
    return " OR ".join(_quote(t) for t in tokens)


def _quote(token: str) -> str:
    return '"' + token.replace('"', '""') + '"'


def _to_snippet(row: sqlite3.Row) -> RecallSnippet:
    return RecallSnippet(
        full_id=row["id"],
        timestamp=row["timestamp"],
        tool_name=row["tool_name"],
        inputs_summary=_truncate(row["inputs_json"], _INPUTS_SUMMARY_LEN),
        output_excerpt=_truncate(row["output"], _OUTPUT_EXCERPT_LEN),
        score=row["score"],
    )


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def recall_reranked(
    store: MemoryStore,
    query: str,
    *,
    limit: int = 5,
    project_root: str | None = None,
    candidate_pool: int = 20,
    base: str = "hybrid",
) -> RecallResult:
    """1차 검색(BM25/hybrid) 후 cross-encoder 로 재정렬.

    ``base``:
    - ``"hybrid"`` (기본): `recall_hybrid` 로 candidate_pool 후보 → reranker.
    - ``"bm25"``: `recall` 로 후보 → reranker.

    `BAAI/bge-reranker-v2-m3` 가 query-doc 페어 점수 재산출 → top ``limit``.
    모델 미설치/실패 시 1차 결과의 top ``limit`` 그대로 반환 (graceful degrade).
    """
    if limit <= 0:
        raise RecallError(f"limit 는 양수여야 합니다: {limit}")
    if base not in ("bm25", "hybrid"):
        raise RecallError(f"base 는 'bm25' 또는 'hybrid' 여야: {base!r}")

    if base == "bm25":
        initial = recall(store, query, limit=candidate_pool, project_root=project_root)
    else:
        initial = recall_hybrid(
            store, query, limit=candidate_pool, project_root=project_root
        )

    if not initial.snippets:
        return initial

    try:
        from .reranker import rerank
        reranked = rerank(query, initial.snippets, top_k=limit)
    except Exception:  # noqa: BLE001 - 모델 로드/호출 실패 시 1차 결과 사용
        reranked = list(initial.snippets[:limit])

    return RecallResult(
        query=query, total_matches=initial.total_matches, snippets=tuple(reranked)
    )


def recall_expanded(
    store: MemoryStore,
    query: str,
    *,
    client,  # LLMClient — 순환 import 회피 위해 untyped
    limit: int = 5,
    project_root: str | None = None,
    max_expansions: int = 4,
    mode: str = "hybrid",
    k: int = 60,
) -> RecallResult:
    """LLM query expansion + 각 확장 query 로 검색 → RRF 합산.

    ``mode``:
    - ``"bm25"``: BM25 (`recall`) 만 — paraphrase 약점 직접 공략.
    - ``"hybrid"`` (기본): `recall_hybrid` — BM25 + 벡터 + expansion.

    LLM 호출 1 회 (expansion 생성). 검색은 expansion 개수만큼 순차.
    """
    if limit <= 0:
        raise RecallError(f"limit 는 양수여야 합니다: {limit}")
    if mode not in ("bm25", "hybrid"):
        raise RecallError(f"mode 는 'bm25' 또는 'hybrid' 여야: {mode!r}")

    from .query_expansion import expand_query

    queries = expand_query(client, query, max_expansions=max_expansions)
    expanded_limit = limit * 2

    scores: dict[int, float] = {}
    snippet_map: dict[int, RecallSnippet] = {}
    for q in queries:
        if mode == "bm25":
            res = recall(store, q, limit=expanded_limit, project_root=project_root)
        else:  # hybrid
            res = recall_hybrid(
                store, q, limit=expanded_limit, project_root=project_root
            )
        for rank, s in enumerate(res.snippets, start=1):
            scores[s.full_id] = scores.get(s.full_id, 0.0) + 1.0 / (k + rank)
            if s.full_id not in snippet_map:
                snippet_map[s.full_id] = s

    ranked_ids = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
    top = tuple(snippet_map[i] for i in ranked_ids[:limit])
    return RecallResult(query=query, total_matches=len(scores), snippets=top)


def recall_hybrid(
    store: MemoryStore,
    query: str,
    *,
    limit: int = 5,
    project_root: str | None = None,
    k: int = 60,
) -> RecallResult:
    """BM25(:func:`recall`) + 벡터(:meth:`MemoryStore.search_vectors`) RRF 병합.

    각 결과 list 의 1-based rank 로 ``score = 1/(k+rank)`` 를 부여하고,
    같은 record id 가 양쪽에 잡히면 score 를 합산. 합산 score 내림차순으로
    상위 ``limit`` 개를 ``RecallResult.snippets`` 로 반환.

    벡터 결과가 비어있어도(임베딩 모델 미가용 등) BM25 결과만으로 정상 동작.
    """
    if limit <= 0:
        raise RecallError(f"limit 는 양수여야 합니다: {limit}")

    expanded = limit * 2
    bm25 = recall(store, query, limit=expanded, project_root=project_root)
    vec_hits = store.search_vectors(
        query, limit=expanded, project_root=project_root
    )

    # rank 합산 점수 — id → 누적 점수
    scores: dict[int, float] = {}
    # snippet 본문은 BM25 의 RecallSnippet 우선, 없으면 VectorHit 변환.
    snippet_map: dict[int, RecallSnippet] = {}

    for rank, s in enumerate(bm25.snippets, start=1):
        scores[s.full_id] = scores.get(s.full_id, 0.0) + 1.0 / (k + rank)
        snippet_map[s.full_id] = s

    for rank, h in enumerate(vec_hits, start=1):
        scores[h.id] = scores.get(h.id, 0.0) + 1.0 / (k + rank)
        if h.id not in snippet_map:
            snippet_map[h.id] = RecallSnippet(
                full_id=h.id,
                timestamp=h.timestamp,
                tool_name=h.tool_name,
                inputs_summary=h.inputs_summary,
                output_excerpt=h.output_excerpt,
                score=h.score,
            )

    ranked_ids = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
    top = tuple(snippet_map[i] for i in ranked_ids[:limit])
    return RecallResult(query=query, total_matches=len(scores), snippets=top)


def recall_normalized(
    store: MemoryStore,
    query: str,
    *,
    client,
    base: str = "hybrid",
    limit: int = 5,
    project_root: str | None = None,
) -> RecallResult:
    """Phase 5-2 path A - LLM 으로 query 를 standard form 으로 정규화 후 검색.

    Phase 5-2 측정 (524 record LOPO) 에서 hybrid baseline 대비 P@1 +0.38,
    σR@5 -0.06 의 강한 개선. cloud LLM 1 회 호출 비용 - expanded 의 2 회
    호출보다 가성비 좋음.

    base 는 "hybrid" (default) / "bm25" / "rerank". 정규화된 query 로 해당
    path 호출. LLM 실패 시 ``normalize_query`` 가 원 query fallback.
    """
    from .normalization import normalize_query

    if base not in ("hybrid", "bm25", "rerank"):
        raise RecallError(f"base 는 'hybrid'|'bm25'|'rerank' 여야: {base!r}")

    norm_q = normalize_query(query, client=client)

    if base == "hybrid":
        return recall_hybrid(store, norm_q, limit=limit, project_root=project_root)
    if base == "bm25":
        return recall(store, norm_q, limit=limit, project_root=project_root)
    return recall_reranked(
        store, norm_q, limit=limit,
        candidate_pool=limit * 4, base="hybrid",
        project_root=project_root,
    )


def recall_hyde(
    store: MemoryStore,
    query: str,
    *,
    client,
    base: str = "hybrid",
    limit: int = 5,
    project_root: str | None = None,
) -> RecallResult:
    """HyDE - LLM 가상 답변 생성 후 그 텍스트로 검색.

    arXiv:2212.10496. record 가 "task description" 형태 (우리 시드)면,
    LLM 의 hypothetical answer 가 record 와 더 가까운 vocabulary/structure
    를 가져 검색이 더 잘 매칭. cloud LLM 1 회.
    """
    from .hyde import generate_hyde

    if base not in ("hybrid", "bm25", "rerank"):
        raise RecallError(f"base 는 'hybrid'|'bm25'|'rerank' 여야: {base!r}")

    hyde_doc = generate_hyde(query, client=client)

    if base == "hybrid":
        return recall_hybrid(store, hyde_doc, limit=limit, project_root=project_root)
    if base == "bm25":
        return recall(store, hyde_doc, limit=limit, project_root=project_root)
    return recall_reranked(
        store, hyde_doc, limit=limit,
        candidate_pool=limit * 4, base="hybrid",
        project_root=project_root,
    )


def recall_mmr(
    store: MemoryStore,
    query: str,
    *,
    limit: int = 5,
    candidate_pool: int = 20,
    lambda_: float = 0.5,
    project_root: str | None = None,
) -> RecallResult:
    """MMR (Maximal Marginal Relevance) - 관련성 + 다양성 균형.

    1. ``recall_hybrid`` 로 후보 ``candidate_pool`` 추출.
    2. MMR 로 ``limit`` 개 선택 (lambda_=0.5 default).
    3. cloud 호출 0. 임베딩 비활성 환경에선 hybrid 결과 그대로 (MMR fallback).
    """
    from .mmr import mmr_select

    if limit <= 0:
        raise RecallError(f"limit 는 양수: {limit}")

    base = recall_hybrid(
        store, query, limit=candidate_pool, project_root=project_root,
    )
    if not base.snippets:
        return base
    if not 0.0 <= lambda_ <= 1.0:
        raise RecallError(f"lambda_ 는 [0, 1]: {lambda_}")

    q_emb = store.embed_query(query)
    if q_emb is None:
        # 임베딩 비활성 - MMR 적용 불가, hybrid 결과 limit 까지.
        return RecallResult(
            query=query,
            total_matches=base.total_matches,
            snippets=tuple(base.snippets[:limit]),
        )

    selected = mmr_select(
        list(base.snippets), store=store,
        query_embedding=q_emb, k=limit, lambda_=lambda_,
    )
    return RecallResult(
        query=query, total_matches=base.total_matches,
        snippets=tuple(selected),
    )
