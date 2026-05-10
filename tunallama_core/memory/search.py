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
