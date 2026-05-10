"""Rule-based 그래프 엣지 — LLM 호출 없이 SQL JOIN 만으로 도출.

3 종 relation:
- ``same_project``: 같은 ``project_root``.
- ``same_day``: 같은 날짜(``timestamp[:10]``).
- ``same_tool``: 같은 ``tool_name``.

정규화: ``source_id < target_id`` — 양방향 같은 엣지 중복 저장 방지 + self-loop 차단.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

from .store import MemoryStore

# (JOIN 조건 SQL, relation 이름). col_expr 들은 모두 hardcoded — SQL 인젝션 X.
_RELATIONS: tuple[tuple[str, str], ...] = (
    (
        "a.project_root = b.project_root AND a.project_root IS NOT NULL",
        "same_project",
    ),
    (
        "substr(a.timestamp, 1, 10) = substr(b.timestamp, 1, 10)",
        "same_day",
    ),
    (
        "a.tool_name = b.tool_name AND a.tool_name IS NOT NULL",
        "same_tool",
    ),
)


@dataclass(frozen=True)
class Edge:
    source_id: int
    target_id: int
    relation: str
    created_at: str


def rebuild_edges(store: MemoryStore) -> int:
    """모든 calls 보고 엣지 재구성. 기존 ``graph_edges`` 비우고 새로 INSERT.

    SQL self-join 으로 O(n²) 를 DB 가 처리 — Python 메모리에 모든 record 안 올림.
    반환은 생성된 엣지 수.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = store.conn
    with store._lock:  # noqa: SLF001 — 같은 lock 으로 직렬화
        conn.execute("DELETE FROM graph_edges")
        total = 0
        for join_cond, relation in _RELATIONS:
            cur = conn.execute(
                f"""
                INSERT OR IGNORE INTO graph_edges (source_id, target_id, relation, created_at)
                SELECT a.id, b.id, ?, ?
                FROM calls a JOIN calls b
                  ON a.id < b.id AND ({join_cond})
                """,
                (relation, now),
            )
            total += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        conn.commit()
    return total


def traverse(
    store: MemoryStore,
    start_id: int,
    *,
    max_hops: int = 3,
    relations: tuple[str, ...] | None = None,
) -> list[Edge]:
    """BFS — ``start_id`` 에서 출발해 ``max_hops`` 까지 도달 가능한 엣지 반환.

    Python 단의 BFS — 재귀 CTE 보다 단순하고 cycle 처리 명확. 노드 수가 큰
    그래프에선 hop 별 fanout 이 클 수 있으나 Phase 2 단계에서는 충분.
    """
    if max_hops <= 0:
        return []
    rel_filter = ""
    rel_params: tuple = ()
    if relations:
        placeholders = ",".join("?" * len(relations))
        rel_filter = f" AND relation IN ({placeholders})"
        rel_params = tuple(relations)

    visited_nodes: set[int] = {start_id}
    visited_edges: set[tuple[int, int, str]] = set()
    result: list[Edge] = []
    frontier = deque([(start_id, 0)])

    while frontier:
        node, depth = frontier.popleft()
        if depth >= max_hops:
            continue
        rows = store.conn.execute(
            f"""
            SELECT source_id, target_id, relation, created_at
            FROM graph_edges
            WHERE (source_id = ? OR target_id = ?){rel_filter}
            """,
            (node, node, *rel_params),
        ).fetchall()
        for row in rows:
            key = (row["source_id"], row["target_id"], row["relation"])
            if key in visited_edges:
                continue
            visited_edges.add(key)
            result.append(
                Edge(
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    relation=row["relation"],
                    created_at=row["created_at"],
                )
            )
            other = (
                row["target_id"]
                if row["source_id"] == node
                else row["source_id"]
            )
            if other not in visited_nodes:
                visited_nodes.add(other)
                frontier.append((other, depth + 1))
    return result
