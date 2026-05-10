# Task: Rule-based 그래프 엣지 (Phase 2-3)

call 간 관계를 graph 로 표현. LLM 호출 없이 SQL 만으로 도출 가능한 rule-based edges 만 (semantic edges 는 Phase 3+ 후보). seCall 의 graph_repo 패턴 참고.

## Phase
IMPLEMENT

## Focus
3 종 rule edge 생성 + BFS 인접 조회. LLM 호출 0.

## Requirements

- `tunallama_core/memory/schema.sql` 에 추가:
  ```sql
  CREATE TABLE IF NOT EXISTS graph_edges (
      source_id INTEGER NOT NULL,
      target_id INTEGER NOT NULL,
      relation TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (source_id, target_id, relation)
  );
  CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id);
  CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id);
  ```
- 새 모듈 `tunallama_core/memory/graph.py`:
  - frozen dataclass `Edge(source_id: int, target_id: int, relation: str, created_at: str)`.
  - 함수 `rebuild_edges(store: MemoryStore) -> int` — 모든 calls 보고 edges 재구성. 기존 `graph_edges` 비우고 새로 INSERT. 반환은 생성된 엣지 수.
  - 함수 `traverse(store, start_id, *, max_hops=3, relations=None) -> list[Edge]` — BFS 인접 엣지. `relations` 가 주어지면 해당 relation 만.
- 적용할 3 종 relation (모두 양방향, source < target 정규화):
  - `same_project`: `calls.project_root` 가 같은 두 record.
  - `same_day`: `calls.timestamp[:10]` (YYYY-MM-DD) 가 같은 두 record.
  - `same_tool`: `calls.tool_name` 이 같은 두 record.
- `tunallama_core/__init__.py` 에 `Edge`, `rebuild_edges`, `traverse` re-export.

## Constraints (hard rules)

- **LLM 호출 0** — pure SQL.
- `rebuild_edges` 는 `O(n²)` 가능하지만 SQL self-join 으로 처리. 1만 record 까지 1초 이내 목표.
- 같은 record 끼리(self-loop) 엣지 생성 금지 (`source_id != target_id`).
- 정규화: 양방향 같은 엣지를 중복 저장 안 함 — `source_id < target_id` 로 강제.
- 기존 `calls` schema / FTS5 / vector 동작 무영향.
- 한국어 docstring.

## Acceptance

- pytest 6+ 케이스 (`tests/core/test_memory_graph.py` 신규):
  1. 빈 store → `rebuild_edges` 반환값 0.
  2. 같은 project_root 인 record 2 개 → `same_project` 엣지 1 개.
  3. 같은 날짜 timestamp 두 record → `same_day` 엣지 1 개.
  4. 같은 tool_name → `same_tool` 엣지 1 개.
  5. self-loop 없음 (한 record 만 있어도 0 edges).
  6. `traverse(start_id=1, max_hops=2)` 가 BFS 로 인접 엣지 반환.
- 기존 테스트 통과 (regression 없음).
